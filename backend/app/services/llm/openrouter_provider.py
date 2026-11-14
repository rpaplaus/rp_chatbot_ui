import asyncio
import logging
import time
from decimal import Decimal
from typing import AsyncGenerator, List, Dict, Optional, Any, Tuple

import httpx
from openai import AsyncOpenAI

from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, ProviderNotConfiguredException, StreamItem

logger = logging.getLogger(__name__)

# Display badge mapping by OpenRouter provider prefix (author slug before '/')
PROVIDER_BADGE_MAP: Dict[str, str] = {
    "openai": "OpenAI",
    "anthropic": "Anthropic",
    "google": "Google",
    "x-ai": "xAI",
    "qwen": "Qwen",
    "deepseek": "DeepSeek",
    "meta-llama": "Meta Llama",
    "meta": "Meta",
    "mistralai": "Mistral",
    "cohere": "Cohere",
    "nvidia": "NVIDIA",
    "microsoft": "Microsoft",
    "perplexity": "Perplexity",
    "amazon": "Amazon",
    "minimax": "MiniMax",
    "moonshotai": "Moonshot",
    "z-ai": "Z.AI",
    "baidu": "Baidu",
    "Xiaomi": "Xiaomi",
    "xiaomi": "Xiaomi",
    "stepfun": "StepFun",
    "tencent": "Tencent",
    "bytedance-seed": "ByteDance",
    "liquid": "Liquid",
    "ai21": "AI21",
    "inflection": "Inflection",
}

# Featured / Recommended OpenRouter models shown first when present in the catalog
FEATURED_MODEL_IDS: List[str] = [
    "openai/gpt-5",
    "anthropic/claude-sonnet-4.6",
    "google/gemini-3.1-pro-preview",
    "x-ai/grok-4.6",
    "qwen/qwen3-coder",
    "deepseek/deepseek-r1-0528",
    "openai/gpt-4o",
    "anthropic/claude-sonnet-4.5",
    "google/gemini-2.5-pro",
    "google/gemini-2.5-flash",
]


def extract_provider_slug(model_id: str) -> str:
    """Extracts the provider prefix from an OpenRouter model ID (e.g. 'anthropic/claude-...' -> 'anthropic')."""
    if "/" in model_id:
        return model_id.split("/", 1)[0].strip().lower()
    return "openrouter"


def get_provider_badge(provider_slug: str) -> str:
    """Returns a clean human-readable badge name for a provider slug."""
    slug = (provider_slug or "").strip().lower()
    if slug in PROVIDER_BADGE_MAP:
        return PROVIDER_BADGE_MAP[slug]
    return slug.replace("-", " ").title() if slug else "OpenRouter"


class OpenRouterCatalog:
    """
    Asynchronous OpenRouter Model Catalog manager with TTL caching.
    Fetches all available models from https://openrouter.ai/api/v1/models,
    including real-time per-token pricing, context window size, and tool calling capabilities.
    """

    CACHE_TTL_SECONDS: float = 1800.0  # 30 minutes
    _models: List[Dict[str, Any]] = []
    _models_by_id: Dict[str, Dict[str, Any]] = {}
    _pricing_per_1m: Dict[str, Tuple[Decimal, Decimal]] = {}
    _last_fetched: float = 0.0
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def _parse_rate_per_1m(cls, raw_token_price: Any) -> Decimal:
        """Converts OpenRouter's per-token USD price string into USD per 1,000,000 tokens."""
        try:
            if raw_token_price is None:
                return Decimal("0")
            val = Decimal(str(raw_token_price))
            if val < 0:
                return Decimal("0")
            return val * Decimal("1000000")
        except Exception:
            return Decimal("0")

    @classmethod
    def _normalize_model_entry(cls, raw: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        model_id = str(raw.get("id") or "").strip()
        if not model_id:
            return None

        name = str(raw.get("name") or model_id).strip()
        description = str(raw.get("description") or "").strip()
        context_length = int(raw.get("context_length") or 0)
        pricing = raw.get("pricing") or {}

        prompt_per_1m = cls._parse_rate_per_1m(pricing.get("prompt", "0"))
        completion_per_1m = cls._parse_rate_per_1m(pricing.get("completion", "0"))

        supported_params = raw.get("supported_parameters") or []
        if not isinstance(supported_params, list):
            supported_params = []
        supports_tools = "tools" in supported_params

        architecture = raw.get("architecture") or {}
        input_modalities = architecture.get("input_modalities") or ["text"]
        top_provider = raw.get("top_provider") or {}
        max_completion_tokens = top_provider.get("max_completion_tokens")

        provider_slug = extract_provider_slug(model_id)
        badge = get_provider_badge(provider_slug)
        is_free = model_id.endswith(":free") or (prompt_per_1m == Decimal("0") and completion_per_1m == Decimal("0"))

        # Build concise fallback description if empty
        if not description:
            ctx_label = f"{context_length // 1000}k ctx" if context_length >= 1000 else ""
            price_label = "Gratuito" if is_free else f"${prompt_per_1m:.2f}/${completion_per_1m:.2f} por 1M"
            description = " • ".join(filter(None, [badge, ctx_label, price_label]))
        else:
            # First sentence or first 160 chars for clean UI rendering
            first_line = description.split("\n")[0].strip()
            description = first_line[:160] + ("..." if len(first_line) > 160 else "")

        return {
            "id": model_id,
            "name": name,
            "provider": provider_slug,
            "badge": badge,
            "description": description,
            "context_length": context_length,
            "prompt_price_per_1m": float(round(prompt_per_1m, 4)),
            "completion_price_per_1m": float(round(completion_per_1m, 4)),
            "supports_tools": supports_tools,
            "supports_vision": "image" in input_modalities,
            "supports_audio": "audio" in input_modalities,
            "input_modalities": input_modalities,
            "supported_parameters": supported_params,
            "max_completion_tokens": int(max_completion_tokens) if max_completion_tokens else None,
            "is_free": is_free,
            "featured": model_id in FEATURED_MODEL_IDS,
        }

    @classmethod
    async def get_models(cls, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """Returns the cached list of all OpenRouter models, refreshing from the API if expired."""
        now = time.monotonic()
        if not force_refresh and cls._models and (now - cls._last_fetched) < cls.CACHE_TTL_SECONDS:
            return cls._models

        async with cls._lock:
            now = time.monotonic()
            if not force_refresh and cls._models and (now - cls._last_fetched) < cls.CACHE_TTL_SECONDS:
                return cls._models

            await cls._fetch_from_openrouter()
            return cls._models

    @classmethod
    async def _fetch_from_openrouter(cls) -> None:
        headers: Dict[str, str] = {
            "Accept": "application/json",
            "HTTP-Referer": settings.OPENROUTER_APP_URL,
            "X-Title": settings.OPENROUTER_APP_NAME,
        }
        if settings.OPENROUTER_API_KEY and settings.OPENROUTER_API_KEY.strip():
            headers["Authorization"] = f"Bearer {settings.OPENROUTER_API_KEY.strip()}"

        url = f"{settings.OPENROUTER_BASE_URL.rstrip('/')}/models"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                payload = response.json()

            raw_list = payload.get("data") or []
            parsed_models: List[Dict[str, Any]] = []
            by_id: Dict[str, Dict[str, Any]] = {}
            pricing_map: Dict[str, Tuple[Decimal, Decimal]] = {}

            for raw_item in raw_list:
                if not isinstance(raw_item, dict):
                    continue
                entry = cls._normalize_model_entry(raw_item)
                if not entry:
                    continue

                m_id = entry["id"]
                parsed_models.append(entry)
                by_id[m_id.lower()] = entry

                raw_pricing = raw_item.get("pricing") or {}
                p_rate = cls._parse_rate_per_1m(raw_pricing.get("prompt", "0"))
                c_rate = cls._parse_rate_per_1m(raw_pricing.get("completion", "0"))
                pricing_map[m_id.lower()] = (p_rate, c_rate)

            # Sort: featured models first (in FEATURED_MODEL_IDS order), then alphabetically by name
            featured_rank = {mid: idx for idx, mid in enumerate(FEATURED_MODEL_IDS)}
            parsed_models.sort(
                key=lambda m: (
                    0 if m["id"] in featured_rank else 1,
                    featured_rank.get(m["id"], 9999),
                    m["name"].lower()
                )
            )

            if parsed_models:
                cls._models = parsed_models
                cls._models_by_id = by_id
                cls._pricing_per_1m = pricing_map
                cls._last_fetched = time.monotonic()
                logger.info(f"[OpenRouter Catalog] Loaded {len(parsed_models)} models from OpenRouter API.")
        except Exception as e:
            logger.error(f"[OpenRouter Catalog] Failed to fetch models from OpenRouter: {e}", exc_info=True)
            if not cls._models:
                cls._models = cls._get_fallback_models()
                cls._models_by_id = {m["id"].lower(): m for m in cls._models}

    @classmethod
    def get_cached_model_info(cls, model_id: str) -> Optional[Dict[str, Any]]:
        """Synchronously inspects cached model metadata if already loaded."""
        if not model_id:
            return None
        return cls._models_by_id.get(model_id.strip().lower())

    @classmethod
    def get_cached_pricing_per_1m(cls, model_id: str) -> Optional[Tuple[Decimal, Decimal]]:
        """Synchronously returns (input_usd_per_1m, output_usd_per_1m) from the OpenRouter catalog cache."""
        if not model_id:
            return None
        norm = model_id.strip().lower()
        if norm in cls._pricing_per_1m:
            return cls._pricing_per_1m[norm]
        return None

    @classmethod
    def model_supports_tools(cls, model_id: str) -> bool:
        """Returns whether a given OpenRouter model supports native tool calling."""
        info = cls.get_cached_model_info(model_id)
        if info is not None:
            return bool(info.get("supports_tools", True))
        return True

    @classmethod
    def model_supports_modality(cls, model_id: str, modality: str) -> bool:
        """Returns whether the model accepts the given input modality ('image', 'audio', 'file', ...)."""
        info = cls.get_cached_model_info(model_id)
        if info is None:
            return False
        return modality in (info.get("input_modalities") or [])

    @classmethod
    def model_supports_parameter(cls, model_id: str, parameter: str) -> bool:
        """
        Returns whether the model advertises a request parameter (e.g. 'temperature', 'reasoning').
        Unknown models are assumed NOT to support it, so optional params are simply omitted.
        """
        info = cls.get_cached_model_info(model_id)
        if info is None:
            return False
        return parameter in (info.get("supported_parameters") or [])

    @classmethod
    def get_max_completion_tokens(cls, model_id: str) -> Optional[int]:
        info = cls.get_cached_model_info(model_id)
        return info.get("max_completion_tokens") if info else None

    @classmethod
    def _get_fallback_models(cls) -> List[Dict[str, Any]]:
        """Fallback list used only if OpenRouter /models endpoint is temporarily unreachable."""
        models: List[Dict[str, Any]] = [
            {
                "id": "openai/gpt-5",
                "name": "OpenAI: GPT-5",
                "provider": "openai",
                "badge": "OpenAI",
                "description": "Raciocínio avançado e arquitetura de software via OpenRouter",
                "context_length": 400000,
                "prompt_price_per_1m": 1.25,
                "completion_price_per_1m": 10.0,
                "supports_tools": True,
                "is_free": False,
                "featured": True,
            },
            {
                "id": "anthropic/claude-sonnet-4.6",
                "name": "Anthropic: Claude Sonnet 4.6",
                "provider": "anthropic",
                "badge": "Anthropic",
                "description": "Excelência em engenharia de código e análise longa via OpenRouter",
                "context_length": 200000,
                "prompt_price_per_1m": 3.0,
                "completion_price_per_1m": 15.0,
                "supports_tools": True,
                "is_free": False,
                "featured": True,
            },
            {
                "id": "google/gemini-3.1-pro-preview",
                "name": "Google: Gemini 3.1 Pro Preview",
                "provider": "google",
                "badge": "Google",
                "description": "Multimodal de alta velocidade e janela de contexto ampla via OpenRouter",
                "context_length": 1048576,
                "prompt_price_per_1m": 1.25,
                "completion_price_per_1m": 5.0,
                "supports_tools": True,
                "is_free": False,
                "featured": True,
            },
            {
                "id": "x-ai/grok-4.6",
                "name": "xAI: Grok 4.6",
                "provider": "x-ai",
                "badge": "xAI",
                "description": "Raciocínio rápido em tempo real via OpenRouter",
                "context_length": 256000,
                "prompt_price_per_1m": 2.0,
                "completion_price_per_1m": 10.0,
                "supports_tools": True,
                "is_free": False,
                "featured": True,
            },
            {
                "id": "qwen/qwen3-coder",
                "name": "Qwen: Qwen3 Coder",
                "provider": "qwen",
                "badge": "Qwen",
                "description": "Especialista em geração e refatoração de código via OpenRouter",
                "context_length": 262144,
                "prompt_price_per_1m": 0.8,
                "completion_price_per_1m": 2.4,
                "supports_tools": True,
                "is_free": False,
                "featured": True,
            },
        ]
        for m in models:
            vision = m["provider"] != "qwen"
            m.setdefault("input_modalities", ["text", "image"] if vision else ["text"])
            m.setdefault("supports_vision", vision)
            m.setdefault("supports_audio", False)
            m.setdefault("supported_parameters", ["tools", "tool_choice", "max_tokens"])
            m.setdefault("max_completion_tokens", None)
        return models


class OpenRouterProvider(BaseLLMProvider):
    """
    Unified LLM Provider powered by OpenRouter (https://openrouter.ai/api/v1).
    Replaces all individual provider SDKs with a single OpenAI-compatible gateway
    supporting all 400+ models on OpenRouter, streaming, native Function Calling,
    and real-time token usage telemetry.
    """

    provider_name = "openrouter"
    default_model = settings.DEFAULT_OPENROUTER_MODEL
    supports_web_search = True
    specialization = "generalist"

    def __init__(self):
        self.api_key = settings.OPENROUTER_API_KEY
        self.base_url = settings.OPENROUTER_BASE_URL
        self.client: Optional[AsyncOpenAI] = None
        if self.api_key and self.api_key.strip():
            self.client = AsyncOpenAI(
                api_key=self.api_key.strip(),
                base_url=self.base_url,
                default_headers={
                    "HTTP-Referer": settings.OPENROUTER_APP_URL,
                    "X-Title": settings.OPENROUTER_APP_NAME,
                },
            )

    async def transcribe_audio(self, audio_b64: str, audio_format: str) -> Optional[str]:
        """Transcribes an audio clip with an audio-capable model (settings.AUDIO_TRANSCRIPTION_MODEL)."""
        if not self.client:
            return None
        try:
            response = await self.client.chat.completions.create(
                model=settings.AUDIO_TRANSCRIPTION_MODEL,
                temperature=0,
                messages=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Transcreva fielmente este áudio, no idioma original. "
                                "Responda apenas com a transcrição, sem comentários."
                            ),
                        },
                        {"type": "input_audio", "input_audio": {"data": audio_b64, "format": audio_format}},
                    ],
                }],
            )
            return (response.choices[0].message.content or "").strip() or None
        except Exception as e:
            logger.warning(f"[OpenRouter] Audio transcription failed ({settings.AUDIO_TRANSCRIPTION_MODEL}): {e}")
            return None

    @staticmethod
    def resolve_generation_params(
        target_model: str,
        requested: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Translates profile-level generation preferences into OpenRouter request parameters,
        keeping only those the target model advertises in `supported_parameters`
        (e.g. openai/gpt-5 rejects `temperature`; qwen3-coder has no `reasoning`).
        """
        if not requested:
            return {}

        resolved: Dict[str, Any] = {}
        supports = lambda p: OpenRouterCatalog.model_supports_parameter(target_model, p)

        temperature = requested.get("temperature")
        if temperature is not None and supports("temperature"):
            resolved["temperature"] = float(temperature)

        max_tokens = requested.get("max_tokens")
        if max_tokens and supports("max_tokens"):
            model_cap = OpenRouterCatalog.get_max_completion_tokens(target_model)
            resolved["max_tokens"] = min(int(max_tokens), model_cap) if model_cap else int(max_tokens)

        effort = requested.get("reasoning_effort")
        if effort and supports("reasoning"):
            # OpenRouter unified reasoning parameter; the reasoning text itself is not streamed to the UI.
            resolved["extra_body"] = {"reasoning": {"effort": effort, "exclude": True}}

        return resolved

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None,
        tools_mode: str = "disabled",
        tool_interaction: Optional[Dict[str, Any]] = None,
        generation_params: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamItem, None]:
        if not self.client:
            raise ProviderNotConfiguredException(
                "Chave OPENROUTER_API_KEY não configurada no ambiente (.env)."
            )

        target_model = (model or self.default_model).strip()

        # Ensure catalog is warm so tool support and pricing are known
        if not OpenRouterCatalog._models:
            await OpenRouterCatalog.get_models()

        # Automatically disable tool calling if the chosen OpenRouter model does not support tools
        effective_tools_mode = tools_mode
        if tools_mode in ("auto", "always") and not OpenRouterCatalog.model_supports_tools(target_model):
            logger.info(
                f"[OpenRouter] Model '{target_model}' does not advertise 'tools' in supported_parameters; "
                "disabling native tool calling for this request."
            )
            effective_tools_mode = "disabled"

        provider_slug = extract_provider_slug(target_model)

        async for item in self._stream_openai_compatible(
            client=self.client,
            target_model=target_model,
            messages=messages,
            system_prompt=system_prompt,
            web_search_context=web_search_context,
            tools_mode=effective_tools_mode,
            tool_interaction=tool_interaction,
            provider_label="OpenRouter",
            generation_params=self.resolve_generation_params(target_model, generation_params)
        ):
            # Tag UsageMetadata with the upstream provider family (e.g. 'openai', 'anthropic', 'google', etc.)
            if hasattr(item, "provider") and hasattr(item, "prompt_tokens"):
                item.provider = provider_slug
            yield item
