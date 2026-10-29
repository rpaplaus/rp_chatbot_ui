from typing import AsyncGenerator, List, Dict, Optional, Any
import logging
from anthropic import AsyncAnthropic
from app.core.config import settings
from app.services.llm.base import (
    BaseLLMProvider,
    ProviderNotConfiguredException,
    StreamItem,
    UsageMetadata
)
from app.services.llm.tools import (
    ToolCallRequest,
    SEARCH_WEB_TOOL_NAME,
    get_anthropic_tools_and_choice,
    parse_tool_query,
    ensure_tool_call_id
)
from app.services.cost_engine import CostEngine

logger = logging.getLogger(__name__)


class AnthropicProvider(BaseLLMProvider):
    """Integration for Anthropic LLMs (e.g. Claude Sonnet 4.6) with native Tool Use and Token Telemetry."""

    provider_name = "anthropic"
    default_model = "claude-sonnet-4-6"

    def __init__(self):
        self.api_key = settings.ANTHROPIC_API_KEY
        self.client: Optional[AsyncAnthropic] = None
        if self.api_key and self.api_key.strip():
            self.client = AsyncAnthropic(api_key=self.api_key.strip())

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
                "Chave ANTHROPIC_API_KEY não configurada no ambiente."
            )

        target_model = model or self.default_model
        prepared_msgs = self._prepare_messages(messages, system_prompt, web_search_context)

        # Anthropic requires system prompt outside of the messages array
        system_msg = next((m["content"] for m in prepared_msgs if m["role"] == "system"), None)
        anthropic_msgs: List[Dict[str, Any]] = [
            {"role": m["role"], "content": m["content"]}
            for m in prepared_msgs if m["role"] in ["user", "assistant"]
        ]
        if anthropic_msgs and anthropic_msgs[0]["role"] != "user":
            anthropic_msgs = anthropic_msgs[1:]

        # If resuming in Turn 2 after executing a tool_use
        if tool_interaction:
            call_req: ToolCallRequest = tool_interaction["call"]
            tool_output: str = tool_interaction["output"]
            anthropic_msgs.append({
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": call_req.id,
                        "name": call_req.name,
                        "input": {"query": call_req.query}
                    }
                ]
            })
            anthropic_msgs.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": call_req.id,
                        "content": tool_output
                    }
                ]
            })

        kwargs: Dict[str, Any] = {
            "model": target_model,
            "max_tokens": 4096,
            "messages": anthropic_msgs,
            "stream": True
        }
        if system_msg:
            kwargs["system"] = system_msg

        if not tool_interaction and tools_mode in ("auto", "always"):
            tools_list, tool_choice = get_anthropic_tools_and_choice(tools_mode)
            if tools_list:
                kwargs["tools"] = tools_list
                kwargs["tool_choice"] = tool_choice

        usage_prompt_tokens: int = 0
        usage_completion_tokens: int = 0
        streamed_output_text: str = ""

        try:
            response = await self.client.messages.create(**kwargs)

            tool_use_id: Optional[str] = None
            tool_use_name: Optional[str] = None
            partial_json_chunks: List[str] = []

            async for chunk in response:
                if chunk.type == "message_start":
                    msg_obj = getattr(chunk, "message", None)
                    msg_usage = getattr(msg_obj, "usage", None) if msg_obj else None
                    if msg_usage:
                        usage_prompt_tokens = getattr(msg_usage, "input_tokens", 0) or 0
                elif chunk.type == "content_block_start":
                    block = getattr(chunk, "content_block", None)
                    if block and getattr(block, "type", None) == "tool_use":
                        tool_use_id = getattr(block, "id", None)
                        tool_use_name = getattr(block, "name", SEARCH_WEB_TOOL_NAME)
                elif chunk.type == "content_block_delta":
                    delta = getattr(chunk, "delta", None)
                    if delta:
                        delta_type = getattr(delta, "type", None)
                        if delta_type == "text_delta" and getattr(delta, "text", None):
                            streamed_output_text += delta.text
                            yield delta.text
                        elif delta_type == "input_json_delta" and getattr(delta, "partial_json", None):
                            partial_json_chunks.append(delta.partial_json)
                elif chunk.type == "message_delta":
                    delta_usage = getattr(chunk, "usage", None)
                    if delta_usage:
                        out_tok = getattr(delta_usage, "output_tokens", 0) or 0
                        if out_tok > 0:
                            usage_completion_tokens = out_tok

            if tool_use_name or partial_json_chunks:
                final_id = ensure_tool_call_id(tool_use_id)
                final_name = tool_use_name or SEARCH_WEB_TOOL_NAME
                raw_json_str = "".join(partial_json_chunks)
                streamed_output_text += raw_json_str
                last_user = next(
                    (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                    ""
                )
                parsed_query = parse_tool_query(raw_json_str, fallback_query=last_user[:200])

                yield ToolCallRequest(
                    id=final_id,
                    name=final_name,
                    query=parsed_query
                )

            if usage_prompt_tokens == 0 and usage_completion_tokens == 0 and streamed_output_text:
                usage_prompt_tokens = CostEngine.estimate_messages_tokens(anthropic_msgs, system_msg)
                usage_completion_tokens = CostEngine.estimate_tokens_from_text(streamed_output_text)

            if usage_prompt_tokens > 0 or usage_completion_tokens > 0:
                yield UsageMetadata(
                    prompt_tokens=usage_prompt_tokens,
                    completion_tokens=usage_completion_tokens,
                    total_tokens=usage_prompt_tokens + usage_completion_tokens,
                    model=target_model,
                    provider=self.provider_name
                )

        except Exception as e:
            logger.error(f"Anthropic API Streaming error: {e}", exc_info=True)
            yield f"\n[Anthropic Error: {str(e)}]"
