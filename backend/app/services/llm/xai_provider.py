from typing import AsyncGenerator, List, Dict, Optional, Any
import logging
from openai import AsyncOpenAI
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider, ProviderNotConfiguredException, StreamItem

logger = logging.getLogger(__name__)


class XAIProvider(BaseLLMProvider):
    """Integration for xAI LLMs (e.g. Grok-4) with native Function Calling."""

    provider_name = "xai"
    default_model = "grok-4-1-fast-reasoning"

    def __init__(self):
        self.api_key = settings.effective_xai_key
        self.client: Optional[AsyncOpenAI] = None
        if self.api_key and self.api_key.strip():
            self.client = AsyncOpenAI(
                api_key=self.api_key.strip(),
                base_url="https://api.x.ai/v1"
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
                "Chave XAI_API_KEY ou GROK_API_KEY não configurada no ambiente."
            )

        target_model = model or self.default_model
        async for item in self._stream_openai_compatible(
            client=self.client,
            target_model=target_model,
            messages=messages,
            system_prompt=system_prompt,
            web_search_context=web_search_context,
            tools_mode=tools_mode,
            tool_interaction=tool_interaction,
            provider_label="xAI"
        ):
            yield item
