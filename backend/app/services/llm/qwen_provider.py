from typing import AsyncGenerator, List, Dict, Optional, Any
import logging
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, ProviderNotConfiguredException, StreamItem

logger = logging.getLogger(__name__)


class QwenProvider(BaseLLMProvider):
    """
    Integration for Qwen3-Coder / Alibaba DashScope LLMs.
    Specialized strictly for Software Engineering & Code Generation:
    Web Search tool injection is programmatically disabled to save tokens and prevent hallucinations.
    """

    provider_name = "qwen"
    default_model = "qwen3.5-plus"
    supports_web_search = False
    specialization = "code_specialist"

    def __init__(self):
        self.api_key = settings.QWEN_API_KEY
        self.base_url = settings.QWEN_BASE_URL
        self.client: Optional[AsyncOpenAI] = None
        if self.api_key and self.api_key.strip():
            self.client = AsyncOpenAI(
                api_key=self.api_key.strip(),
                base_url=self.base_url
            )

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None,
        tools_mode: str = "disabled",
        tool_interaction: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamItem, None]:
        if not self.client:
            raise ProviderNotConfiguredException(
                "Chave QWEN_API_KEY não configurada no ambiente."
            )

        target_model = model or self.default_model
        # Programmatically enforce tools_mode="disabled" for code specialist models
        async for item in self._stream_openai_compatible(
            client=self.client,
            target_model=target_model,
            messages=messages,
            system_prompt=system_prompt,
            web_search_context=web_search_context,
            tools_mode="disabled",
            tool_interaction=None,
            provider_label="Qwen"
        ):
            yield item
