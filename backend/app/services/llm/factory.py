from typing import Dict, Tuple
import logging
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, ModelNotFoundException
from app.services.llm.openrouter_provider import OpenRouterProvider, OpenRouterCatalog

logger = logging.getLogger(__name__)


class LLMFactory:
    """
    Factory for resolving, instantiating, and caching the unified OpenRouter LLM Provider.
    Supports any OpenRouter model ID (e.g. 'openai/gpt-5', 'anthropic/claude-sonnet-4.6',
    'deepseek/deepseek-r1-0528') as well as legacy aliases stored in existing database sessions.
    """
    _instances: Dict[str, BaseLLMProvider] = {}

    # Backwards-compatible map from legacy 5-model aliases to canonical OpenRouter model IDs
    LEGACY_MODEL_ALIASES: Dict[str, str] = {
        # OpenAI
        "gpt-5 (openai)": "openai/gpt-5",
        "gpt-5-2025-08-07": "openai/gpt-5",
        "gpt-5": "openai/gpt-5",
        "openai": "openai/gpt-5",

        # Anthropic
        "claude sonnet 4.6": "anthropic/claude-sonnet-4.6",
        "claude-sonnet-4-6": "anthropic/claude-sonnet-4.6",
        "claude": "anthropic/claude-sonnet-4.6",
        "anthropic": "anthropic/claude-sonnet-4.6",

        # Google Gemini
        "gemini-3": "google/gemini-3.1-pro-preview",
        "gemini-3.1-pro-preview": "google/gemini-3.1-pro-preview",
        "gemini": "google/gemini-3.1-pro-preview",
        "google": "google/gemini-3.1-pro-preview",

        # xAI Grok
        "grok-4-1-fast-reasoning": "x-ai/grok-4.6",
        "grok-4": "x-ai/grok-4.6",
        "grok": "x-ai/grok-4.6",
        "xai": "x-ai/grok-4.6",

        # Alibaba Qwen
        "qwen3-coder": "qwen/qwen3-coder",
        "qwen3.5-plus": "qwen/qwen3-coder",
        "qwen": "qwen/qwen3-coder",
    }

    @classmethod
    def get_provider(cls, provider_name: str = "openrouter") -> BaseLLMProvider:
        """Returns or creates the cached OpenRouterProvider instance."""
        key = "openrouter"
        if key not in cls._instances:
            cls._instances[key] = OpenRouterProvider()
        return cls._instances[key]

    @classmethod
    def resolve(cls, model_identifier: str) -> Tuple[BaseLLMProvider, str]:
        """
        Resolves any OpenRouter model ID or legacy alias to the OpenRouterProvider instance
        and the canonical OpenRouter model slug (e.g. 'author/model-slug').
        """
        cleaned = (model_identifier or "").strip()
        if not cleaned:
            cleaned = settings.DEFAULT_OPENROUTER_MODEL

        lower_key = cleaned.lower()

        # 1. Check legacy aliases first (for seamless compatibility with existing DB sessions)
        if lower_key in cls.LEGACY_MODEL_ALIASES:
            target_model_id = cls.LEGACY_MODEL_ALIASES[lower_key]
            provider = cls.get_provider("openrouter")
            return provider, target_model_id

        # 2. Any OpenRouter model ID (contains '/' or is in OpenRouterCatalog)
        if "/" in cleaned or OpenRouterCatalog.get_cached_model_info(cleaned) is not None:
            provider = cls.get_provider("openrouter")
            return provider, cleaned

        raise ModelNotFoundException(
            f"Modelo '{model_identifier}' não reconhecido. Selecione um modelo válido do OpenRouter (ex: 'openai/gpt-5')."
        )

