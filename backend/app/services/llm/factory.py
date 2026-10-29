from typing import Dict, Tuple, Optional, List
import logging
from app.services.llm.base import BaseLLMProvider, ModelNotFoundException
from app.services.llm.openai_provider import OpenAIProvider
from app.services.llm.anthropic_provider import AnthropicProvider
from app.services.llm.gemini_provider import GeminiProvider
from app.services.llm.xai_provider import XAIProvider
from app.services.llm.qwen_provider import QwenProvider

logger = logging.getLogger(__name__)

class LLMFactory:
    """
    Factory for resolving, instantiating, and caching LLM Provider instances.
    """
    _instances: Dict[str, BaseLLMProvider] = {}

    # Map model aliases to (provider_name, target_model_id)
    MODEL_MAP: Dict[str, Tuple[str, str]] = {
        # OpenAI
        "GPT-5 (OpenAI)": ("openai", "gpt-5-2025-08-07"),
        "gpt-5-2025-08-07": ("openai", "gpt-5-2025-08-07"),
        "gpt-5": ("openai", "gpt-5-2025-08-07"),

        # Anthropic
        "Claude Sonnet 4.6": ("anthropic", "claude-sonnet-4-6"),
        "claude-sonnet-4-6": ("anthropic", "claude-sonnet-4-6"),
        "claude": ("anthropic", "claude-sonnet-4-6"),

        # Google Gemini
        "Gemini-3": ("gemini", "gemini-3.1-pro-preview"),
        "gemini-3.1-pro-preview": ("gemini", "gemini-3.1-pro-preview"),
        "gemini": ("gemini", "gemini-3.1-pro-preview"),

        # xAI Grok
        "grok-4-1-fast-reasoning": ("xai", "grok-4-1-fast-reasoning"),
        "grok-4": ("xai", "grok-4-1-fast-reasoning"),
        "grok": ("xai", "grok-4-1-fast-reasoning"),

        # Qwen
        "Qwen3-Coder": ("qwen", "qwen3.5-plus"),
        "qwen3.5-plus": ("qwen", "qwen3.5-plus"),
        "qwen": ("qwen", "qwen3.5-plus"),
    }

    @classmethod
    def get_provider(cls, provider_name: str) -> BaseLLMProvider:
        """Returns or creates a cached provider instance."""
        p_name = provider_name.lower().strip()
        if p_name not in cls._instances:
            if p_name == "openai":
                cls._instances[p_name] = OpenAIProvider()
            elif p_name == "anthropic":
                cls._instances[p_name] = AnthropicProvider()
            elif p_name == "gemini":
                cls._instances[p_name] = GeminiProvider()
            elif p_name == "xai":
                cls._instances[p_name] = XAIProvider()
            elif p_name == "qwen":
                cls._instances[p_name] = QwenProvider()
            else:
                raise ModelNotFoundException(f"Provedor desconhecido: '{provider_name}'")
        return cls._instances[p_name]

    @classmethod
    def resolve(cls, model_identifier: str) -> Tuple[BaseLLMProvider, str]:
        """
        Resolves a model name or alias to its provider instance and actual model ID.
        :param model_identifier: e.g. 'GPT-5 (OpenAI)' or 'claude-sonnet-4-6'
        :return: (provider_instance, target_model_id)
        """
        mapping = cls.MODEL_MAP.get(model_identifier.strip())
        if not mapping:
            # Fallback check case-insensitive
            for key, val in cls.MODEL_MAP.items():
                if key.lower() == model_identifier.lower().strip():
                    mapping = val
                    break

        if not mapping:
            raise ModelNotFoundException(
                f"Modelo '{model_identifier}' não reconhecido pelo sistema."
            )

        provider_name, target_model_id = mapping
        provider = cls.get_provider(provider_name)
        return provider, target_model_id

