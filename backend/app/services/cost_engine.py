import uuid
import logging
from decimal import Decimal, ROUND_HALF_UP
from typing import Dict, Tuple, Optional, List, Any

from app.core.database import AsyncSessionLocal
from app.models.token_usage import TokenUsage

logger = logging.getLogger(__name__)

# Pricing table in USD per 1,000,000 (1M) tokens: (input_usd_per_1m, output_usd_per_1m)
MODEL_PRICING_PER_1M: Dict[str, Tuple[Decimal, Decimal]] = {
    # OpenAI (GPT-5)
    "gpt-5-2025-08-07": (Decimal("2.50"), Decimal("10.00")),
    "gpt-5": (Decimal("2.50"), Decimal("10.00")),
    "gpt-5 (openai)": (Decimal("2.50"), Decimal("10.00")),

    # Anthropic (Claude Sonnet 4.6)
    "claude-sonnet-4-6": (Decimal("3.00"), Decimal("15.00")),
    "claude sonnet 4.6": (Decimal("3.00"), Decimal("15.00")),
    "claude": (Decimal("3.00"), Decimal("15.00")),

    # Google Gemini (Gemini 3.1 Pro)
    "gemini-3.1-pro-preview": (Decimal("1.25"), Decimal("5.00")),
    "gemini-3": (Decimal("1.25"), Decimal("5.00")),
    "gemini": (Decimal("1.25"), Decimal("5.00")),

    # xAI (Grok-4)
    "grok-4-1-fast-reasoning": (Decimal("2.00"), Decimal("10.00")),
    "grok-4": (Decimal("2.00"), Decimal("10.00")),
    "grok": (Decimal("2.00"), Decimal("10.00")),

    # Alibaba Qwen (Qwen3-Coder / Qwen3.5-Plus)
    "qwen3.5-plus": (Decimal("0.80"), Decimal("2.40")),
    "qwen3-coder": (Decimal("0.80"), Decimal("2.40")),
    "qwen": (Decimal("0.80"), Decimal("2.40")),
}

PROVIDER_FALLBACK_PRICING_PER_1M: Dict[str, Tuple[Decimal, Decimal]] = {
    "openai": (Decimal("2.50"), Decimal("10.00")),
    "anthropic": (Decimal("3.00"), Decimal("15.00")),
    "gemini": (Decimal("1.25"), Decimal("5.00")),
    "xai": (Decimal("2.00"), Decimal("10.00")),
    "qwen": (Decimal("0.80"), Decimal("2.40")),
}

ONE_MILLION = Decimal("1000000")
COST_QUANTIZE = Decimal("0.00000001")


class CostEngine:
    """
    Central FinOps pricing engine for calculating token usage costs in USD
    across all 5 integrated LLM providers.
    """

    @classmethod
    def get_rates_per_1m(cls, model_name: str, provider: str = "") -> Tuple[Decimal, Decimal]:
        """Returns (input_rate_per_1m, output_rate_per_1m) in USD for a model or provider."""
        norm_model = (model_name or "").strip().lower()
        if norm_model in MODEL_PRICING_PER_1M:
            return MODEL_PRICING_PER_1M[norm_model]

        for key, rates in MODEL_PRICING_PER_1M.items():
            if key in norm_model or norm_model in key:
                return rates

        norm_provider = (provider or "").strip().lower()
        if norm_provider in PROVIDER_FALLBACK_PRICING_PER_1M:
            return PROVIDER_FALLBACK_PRICING_PER_1M[norm_provider]

        # Default fallback rate if unmapped
        return (Decimal("2.00"), Decimal("8.00"))

    @classmethod
    def calculate_cost_usd(
        cls,
        model_name: str,
        provider: str,
        prompt_tokens: int,
        completion_tokens: int
    ) -> Decimal:
        """
        Calculates exact USD cost with 8 decimal places precision.
        Formula: (prompt_tokens / 1M * input_rate) + (completion_tokens / 1M * output_rate)
        """
        p_tokens = max(0, int(prompt_tokens or 0))
        c_tokens = max(0, int(completion_tokens or 0))

        input_rate, output_rate = cls.get_rates_per_1m(model_name, provider)

        input_cost = (Decimal(p_tokens) / ONE_MILLION) * input_rate
        output_cost = (Decimal(c_tokens) / ONE_MILLION) * output_rate

        total = (input_cost + output_cost).quantize(COST_QUANTIZE, rounding=ROUND_HALF_UP)
        return total

    @staticmethod
    def estimate_tokens_from_text(text: str) -> int:
        """
        Deterministic fallback estimator (~4 characters per token) used only when a provider
        stream is interrupted or omits native token usage metadata.
        """
        if not text:
            return 0
        return max(1, (len(text) + 3) // 4)

    @classmethod
    def estimate_messages_tokens(cls, messages: List[Dict[str, Any]], system_prompt: Optional[str] = None) -> int:
        """Estimates prompt tokens from a list of messages and optional system prompt."""
        total_chars = len(system_prompt or "")
        for m in messages:
            content = m.get("content")
            if isinstance(content, str):
                total_chars += len(content)
            elif isinstance(content, list):
                total_chars += len(str(content))
        return max(1, (total_chars + 3) // 4)


async def record_token_usage_background(
    user_id: uuid.UUID,
    session_id: Optional[uuid.UUID],
    provider: str,
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int
) -> None:
    """
    Asynchronous BackgroundTask handler that computes the USD cost and persists
    a TokenUsage record in PostgreSQL using an isolated database session.
    """
    try:
        p_tokens = max(0, int(prompt_tokens or 0))
        c_tokens = max(0, int(completion_tokens or 0))
        total_tokens = p_tokens + c_tokens

        if total_tokens <= 0:
            return

        total_cost = CostEngine.calculate_cost_usd(
            model_name=model_name,
            provider=provider,
            prompt_tokens=p_tokens,
            completion_tokens=c_tokens
        )

        async with AsyncSessionLocal() as db:
            usage_record = TokenUsage(
                user_id=user_id,
                session_id=session_id,
                provider=(provider or "unknown").lower().strip(),
                model_name=model_name,
                prompt_tokens=p_tokens,
                completion_tokens=c_tokens,
                total_tokens=total_tokens,
                total_cost=total_cost
            )
            db.add(usage_record)
            await db.commit()

        logger.info(
            f"[Telemetry FinOps] Recorded usage for user={user_id} | provider={provider} | "
            f"model={model_name} | prompt={p_tokens} | completion={c_tokens} | cost=${total_cost:.8f} USD"
        )
    except Exception as e:
        logger.error(f"[Telemetry FinOps] Failed to record token usage in background: {e}", exc_info=True)

