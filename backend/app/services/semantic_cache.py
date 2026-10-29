import asyncio
import hashlib
import json
import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from sqlalchemy import select, func, delete

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.core.redis import get_redis_client
from app.models.semantic_cache import SemanticCache

logger = logging.getLogger(__name__)


@dataclass
class SemanticCacheLookupResult:
    """Result returned by the Two-Tier Semantic Cache lookup."""
    is_hit: bool
    tier: Optional[str] = None  # "L1_REDIS" | "L2_PGVECTOR"
    similarity: float = 0.0
    response_text: str = ""
    model_name: str = ""
    provider: str = ""
    sources: List[Dict[str, Any]] = field(default_factory=list)
    query_embedding: Optional[List[float]] = None
    prompt_hash: str = ""
    effective_profile: str = "software_engineer"
    scope_key: str = "global"


class SemanticCacheService:
    """
    Two-Tier Semantic Cache Engine:
    - L1: Redis exact canonical hash match (< 2ms, 0 embedding API calls).
    - L2: PostgreSQL 16 + pgvector (512-d Matryoshka embeddings via text-embedding-3-small, HNSW cosine >= 0.95).
    Includes profile/tenant isolation and 3-tier dynamic temporal TTL.
    """

    # Tier 1 Temporal Volatility: Strict real-time markers -> Bypass cache (TTL = 0)
    EPHEMERAL_REALTIME_PATTERNS = (
        r"\b(agora|hoje|neste momento|ao vivo|cotação atual|cotacao atual|preço hoje|preco hoje|placar de hoje)\b",
    )

    # Tier 2 Temporal Volatility: Periodic / recent events -> Short TTL (6 hours)
    RECENT_EVENTS_PATTERNS = (
        r"\b(último|última|ultimo|ultima|recente|recentes|atual|atuais|esta semana|este mês|este mes|"
        r"este ano|notícias|noticias|campeonato|classificação|classificacao|tabela)\b",
    )

    TTL_SHORT_SECONDS = 21600       # 6 hours for recent events or web-searched answers
    TTL_STANDARD_SECONDS = 604800   # 7 days for stable/conceptual knowledge

    _openai_client: Optional[AsyncOpenAI] = None

    @classmethod
    def _get_embedding_client(cls) -> Optional[AsyncOpenAI]:
        if cls._openai_client is None:
            if settings.OPENAI_API_KEY and settings.OPENAI_API_KEY.strip():
                cls._openai_client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.strip())
        return cls._openai_client

    @staticmethod
    def normalize_prompt(text: str) -> str:
        """
        Normalizes prompt text for canonical L1 hashing:
        lowercase, strip accents, strip punctuation, and collapse whitespace.
        """
        if not text:
            return ""
        lowered = text.strip().lower()
        decomposed = unicodedata.normalize("NFD", lowered)
        no_accents = "".join(ch for ch in decomposed if unicodedata.category(ch) != "Mn")
        alnum_only = re.sub(r"[^a-z0-9\s]", " ", no_accents)
        return re.sub(r"\s+", " ", alnum_only).strip()

    @staticmethod
    def resolve_effective_profile(profile_id: Optional[str], supports_web_search: bool) -> str:
        """
        Resolves the cache partition profile_id, respecting the Tool Disabling guardrail
        for code specialist models (e.g., Qwen3-Coder).
        """
        if not supports_web_search:
            return "code_specialist"
        norm = (profile_id or "software_engineer").strip().lower()
        if norm in ("general_assistant", "cybernexus_soc"):
            return norm
        return "software_engineer"

    @staticmethod
    def resolve_scope_key(user_id: Optional[Any], user_system_prompt: Optional[str]) -> str:
        """
        Computes the isolation scope key:
        - 'global' when no custom session system_prompt is active.
        - 'user:<user_id>:sp:<hash>' when the user configured a custom system_prompt on the session.
        """
        if user_system_prompt and user_system_prompt.strip():
            sp_hash = hashlib.sha256(user_system_prompt.strip().encode("utf-8")).hexdigest()[:16]
            uid_str = str(user_id) if user_id else "anon"
            return f"user:{uid_str}:sp:{sp_hash}"
        return "global"

    @classmethod
    def compute_prompt_hash(cls, prompt_text: str, effective_profile: str, scope_key: str) -> str:
        norm = cls.normalize_prompt(prompt_text)
        raw = f"{scope_key}:{effective_profile}:{norm}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def compute_ttl_seconds(cls, prompt_text: str, used_web_search: bool = False) -> int:
        """
        Evaluates the 3-tier temporal volatility matrix and returns the TTL in seconds
        (0 means bypass caching).
        """
        lowered = (prompt_text or "").lower().strip()
        for pattern in cls.EPHEMERAL_REALTIME_PATTERNS:
            if re.search(pattern, lowered):
                return 0

        if used_web_search:
            return cls.TTL_SHORT_SECONDS

        for pattern in cls.RECENT_EVENTS_PATTERNS:
            if re.search(pattern, lowered):
                return cls.TTL_SHORT_SECONDS

        return cls.TTL_STANDARD_SECONDS

    @classmethod
    async def generate_embedding(cls, text: str) -> Optional[List[float]]:
        """
        Generates a 512-dimensional Matryoshka embedding vector using OpenAI text-embedding-3-small.
        """
        client = cls._get_embedding_client()
        if not client or not text.strip():
            return None

        try:
            response = await asyncio.wait_for(
                client.embeddings.create(
                    model=settings.SEMANTIC_CACHE_EMBEDDING_MODEL,
                    input=text.strip(),
                    dimensions=settings.SEMANTIC_CACHE_DIMENSIONS
                ),
                timeout=3.5
            )
            if response.data and len(response.data) > 0:
                return list(response.data[0].embedding)
        except Exception as e:
            logger.warning(f"[Semantic Cache] Embedding generation failed or timed out: {e}")
        return None

    @classmethod
    async def lookup(
        cls,
        prompt_text: str,
        profile_id: Optional[str],
        supports_web_search: bool = True,
        user_id: Optional[Any] = None,
        user_system_prompt: Optional[str] = None
    ) -> SemanticCacheLookupResult:
        """
        Executes Two-Tier lookup:
        1. L1 Redis exact canonical hash check.
        2. L2 PostgreSQL pgvector cosine similarity search (>= 0.95).
        """
        effective_profile = cls.resolve_effective_profile(profile_id, supports_web_search)
        scope_key = cls.resolve_scope_key(user_id, user_system_prompt)
        prompt_hash = cls.compute_prompt_hash(prompt_text, effective_profile, scope_key)

        if not settings.SEMANTIC_CACHE_ENABLED:
            return SemanticCacheLookupResult(
                is_hit=False,
                prompt_hash=prompt_hash,
                effective_profile=effective_profile,
                scope_key=scope_key
            )

        # Check temporal bypass rule before lookup
        ttl_policy = cls.compute_ttl_seconds(prompt_text, used_web_search=False)
        if ttl_policy <= 0:
            logger.info("[Semantic Cache BYPASS] Prompt contains strict real-time temporal markers.")
            return SemanticCacheLookupResult(
                is_hit=False,
                prompt_hash=prompt_hash,
                effective_profile=effective_profile,
                scope_key=scope_key
            )

        redis_key = f"semcache:l1:{prompt_hash}"

        # --- Tier 1: Redis L1 Exact Canonical Match ---
        try:
            redis_client = await get_redis_client()
            try:
                cached_raw = await redis_client.get(redis_key)
                if cached_raw:
                    payload = json.loads(cached_raw)
                    logger.info(
                        f"[Semantic Cache HIT | L1_REDIS] hash={prompt_hash[:12]} | "
                        f"profile={effective_profile} | scope={scope_key}"
                    )
                    return SemanticCacheLookupResult(
                        is_hit=True,
                        tier="L1_REDIS",
                        similarity=1.0,
                        response_text=payload.get("response_text", ""),
                        model_name=payload.get("model_name", ""),
                        provider=payload.get("provider", ""),
                        sources=payload.get("sources", []),
                        prompt_hash=prompt_hash,
                        effective_profile=effective_profile,
                        scope_key=scope_key
                    )
            finally:
                await redis_client.aclose()
        except Exception as redis_err:
            logger.warning(f"[Semantic Cache] L1 Redis lookup error: {redis_err}")

        # --- Tier 2: PostgreSQL pgvector L2 Semantic Similarity Search ---
        query_embedding = await cls.generate_embedding(prompt_text)
        if not query_embedding:
            return SemanticCacheLookupResult(
                is_hit=False,
                prompt_hash=prompt_hash,
                effective_profile=effective_profile,
                scope_key=scope_key
            )

        try:
            threshold = settings.SEMANTIC_CACHE_THRESHOLD
            distance_expr = SemanticCache.embedding.cosine_distance(query_embedding)
            similarity_expr = (1.0 - distance_expr).label("similarity")

            async with AsyncSessionLocal() as db:
                stmt = (
                    select(SemanticCache, similarity_expr)
                    .where(
                        SemanticCache.profile_id == effective_profile,
                        SemanticCache.scope_key == scope_key,
                        SemanticCache.expires_at > func.now(),
                        (1.0 - distance_expr) >= threshold
                    )
                    .order_by(distance_expr.asc())
                    .limit(1)
                )
                result = await db.execute(stmt)
                row = result.first()

                if row:
                    entry: SemanticCache = row[0]
                    sim_score: float = float(row[1])

                    entry.hit_count = (entry.hit_count or 0) + 1
                    resp_text = entry.response_text
                    mod_name = entry.model_name
                    prov_name = entry.provider
                    srcs = entry.sources_json or []
                    exp_at = entry.expires_at
                    await db.commit()

                    # Warm up L1 Redis for this exact phrasing
                    try:
                        now_utc = datetime.now(timezone.utc)
                        rem_ttl = int((exp_at - now_utc).total_seconds()) if exp_at else 3600
                        if rem_ttl > 10:
                            redis_client = await get_redis_client()
                            try:
                                l1_data = json.dumps({
                                    "response_text": resp_text,
                                    "model_name": mod_name,
                                    "provider": prov_name,
                                    "sources": srcs
                                }, ensure_ascii=False)
                                await redis_client.setex(redis_key, rem_ttl, l1_data)
                            finally:
                                await redis_client.aclose()
                    except Exception:
                        pass

                    logger.info(
                        f"[Semantic Cache HIT | L2_PGVECTOR] similarity={sim_score:.4f} | "
                        f"profile={effective_profile} | scope={scope_key} | hits={entry.hit_count}"
                    )
                    return SemanticCacheLookupResult(
                        is_hit=True,
                        tier="L2_PGVECTOR",
                        similarity=sim_score,
                        response_text=resp_text,
                        model_name=mod_name,
                        provider=prov_name,
                        sources=srcs,
                        query_embedding=query_embedding,
                        prompt_hash=prompt_hash,
                        effective_profile=effective_profile,
                        scope_key=scope_key
                    )

        except Exception as db_err:
            logger.error(f"[Semantic Cache] L2 pgvector lookup error: {db_err}", exc_info=True)

        logger.info(
            f"[Semantic Cache MISS] profile={effective_profile} | scope={scope_key} | "
            f"hash={prompt_hash[:12]}"
        )
        return SemanticCacheLookupResult(
            is_hit=False,
            query_embedding=query_embedding,
            prompt_hash=prompt_hash,
            effective_profile=effective_profile,
            scope_key=scope_key
        )


async def store_semantic_cache_background(
    prompt_text: str,
    effective_profile: str,
    scope_key: str,
    prompt_hash: str,
    query_embedding: Optional[List[float]],
    response_text: str,
    model_name: str,
    provider: str,
    sources: Optional[List[Dict[str, Any]]] = None
) -> None:
    """
    Asynchronous BackgroundTask handler that persists a new (Question Vector, Final Response)
    pair into L1 Redis and L2 PostgreSQL pgvector after a Cache Miss stream finishes.
    """
    try:
        if not settings.SEMANTIC_CACHE_ENABLED:
            return

        cleaned_response = (response_text or "").strip()
        if len(cleaned_response) < 15:
            return

        used_web_search = bool(sources and len(sources) > 0)
        ttl_seconds = SemanticCacheService.compute_ttl_seconds(
            prompt_text=prompt_text,
            used_web_search=used_web_search
        )
        if ttl_seconds <= 0:
            logger.info("[Semantic Cache] Skipping store due to ephemeral temporal marker (TTL=0).")
            return

        embedding_vec = query_embedding
        if not embedding_vec:
            embedding_vec = await SemanticCacheService.generate_embedding(prompt_text)
        if not embedding_vec:
            return

        now_utc = datetime.now(timezone.utc)
        expires_at = now_utc + timedelta(seconds=ttl_seconds)

        # 1. Persist in L2 PostgreSQL (pgvector) and opportunistically prune expired rows
        async with AsyncSessionLocal() as db:
            await db.execute(
                delete(SemanticCache).where(SemanticCache.expires_at <= func.now())
            )
            new_entry = SemanticCache(
                prompt_hash=prompt_hash,
                prompt_text=prompt_text.strip(),
                profile_id=effective_profile,
                scope_key=scope_key,
                embedding=embedding_vec,
                response_text=cleaned_response,
                model_name=model_name,
                provider=provider,
                sources_json=sources or [],
                hit_count=0,
                expires_at=expires_at
            )
            db.add(new_entry)
            await db.commit()

        # 2. Persist in L1 Redis for sub-2ms exact matches
        try:
            redis_client = await get_redis_client()
            try:
                redis_key = f"semcache:l1:{prompt_hash}"
                l1_payload = json.dumps({
                    "response_text": cleaned_response,
                    "model_name": model_name,
                    "provider": provider,
                    "sources": sources or []
                }, ensure_ascii=False)
                await redis_client.setex(redis_key, ttl_seconds, l1_payload)
            finally:
                await redis_client.aclose()
        except Exception as redis_err:
            logger.warning(f"[Semantic Cache] Failed to warm L1 Redis cache: {redis_err}")

        logger.info(
            f"[Semantic Cache STORED] profile={effective_profile} | scope={scope_key} | "
            f"ttl={ttl_seconds}s | hash={prompt_hash[:12]}"
        )
    except Exception as e:
        logger.error(f"[Semantic Cache] Failed to store cache entry in background: {e}", exc_info=True)

