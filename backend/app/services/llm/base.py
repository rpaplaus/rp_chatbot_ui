from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import AsyncGenerator, List, Dict, Optional, Any, Union
import json
import logging
from app.services.llm.tools import (
    ToolCallRequest,
    SEARCH_WEB_TOOL_NAME,
    get_openai_tools_and_choice,
    parse_tool_query,
    ensure_tool_call_id
)
from app.services.cost_engine import CostEngine

logger = logging.getLogger(__name__)


@dataclass
class UsageMetadata:
    """Structured token consumption statistics captured from the final stream chunk."""
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    model: str
    provider: str = ""


StreamItem = Union[str, ToolCallRequest, UsageMetadata]


class LLMProviderException(Exception):
    """Base exception for LLM provider errors."""
    pass


class ProviderNotConfiguredException(LLMProviderException):
    """Raised when an API key or endpoint configuration is missing."""
    pass


class ModelNotFoundException(LLMProviderException):
    """Raised when an unknown model name or identifier is requested."""
    pass


class BaseLLMProvider(ABC):
    """
    Abstract Strategy Interface for all Large Language Model providers.
    Supports both direct token streaming and Agentic Tool Calling (Function Calling),
    as well as provider-specific capability routing and native token telemetry interception.
    """
    provider_name: str
    default_model: str
    supports_web_search: bool = True
    specialization: str = "generalist"  # "generalist" | "code_specialist"

    @abstractmethod
    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None,
        tools_mode: str = "disabled",
        tool_interaction: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamItem, None]:
        """
        Asynchronously streams text tokens (`str`), a `ToolCallRequest`, or `UsageMetadata`.
        """
        pass

    def _prepare_messages(
        self,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Normalizes and injects system prompt and optional web search context into the message history.
        """
        prepared: List[Dict[str, Any]] = [dict(m) for m in messages]

        combined_system = ""
        if system_prompt and system_prompt.strip():
            combined_system += system_prompt.strip()

        if web_search_context and web_search_context.strip():
            if combined_system:
                combined_system += f"\n\n{web_search_context.strip()}"
            else:
                combined_system = f"Você é um assistente prestativo e inteligente.\n\n{web_search_context.strip()}"

        if combined_system:
            has_system = False
            for m in prepared:
                if m.get("role") == "system":
                    m["content"] = f"{combined_system}\n\n{m['content']}"
                    has_system = True
                    break
            if not has_system:
                prepared.insert(0, {"role": "system", "content": combined_system})

        return prepared

    async def _stream_openai_compatible(
        self,
        client: Any,
        target_model: str,
        messages: List[Dict[str, str]],
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None,
        tools_mode: str = "disabled",
        tool_interaction: Optional[Dict[str, Any]] = None,
        provider_label: str = "OpenAI"
    ) -> AsyncGenerator[StreamItem, None]:
        """
        Shared streaming engine for OpenAI-compatible SDKs (OpenAI, xAI Grok, Qwen DashScope).
        Handles:
        - Turn 1 with native Function Calling (`tools` & `tool_choice`), accumulating streamed tool_calls deltas.
        - Turn 2 with injected `assistant` (tool_calls) + `tool` (tool_response) messages.
        - Native token telemetry interception via `stream_options={"include_usage": True}` on the final chunk.
        """
        prepared_msgs = self._prepare_messages(messages, system_prompt, web_search_context)

        # If this is Turn 2 (resuming after executing a tool call), append assistant tool_calls + tool response
        if tool_interaction:
            call_req: ToolCallRequest = tool_interaction["call"]
            tool_output: str = tool_interaction["output"]
            assistant_tool_msg = call_req.raw_assistant_data or {
                "role": "assistant",
                "content": None,
                "tool_calls": [
                    {
                        "id": call_req.id,
                        "type": "function",
                        "function": {
                            "name": call_req.name,
                            "arguments": json.dumps({"query": call_req.query}, ensure_ascii=False)
                        }
                    }
                ]
            }
            prepared_msgs.append(assistant_tool_msg)
            prepared_msgs.append({
                "role": "tool",
                "tool_call_id": call_req.id,
                "content": tool_output
            })

        create_kwargs: Dict[str, Any] = {
            "model": target_model,
            "messages": prepared_msgs,
            "stream": True,
            "stream_options": {"include_usage": True}
        }

        if not tool_interaction and tools_mode in ("auto", "always"):
            tools_list, tool_choice = get_openai_tools_and_choice(tools_mode)
            if tools_list:
                create_kwargs["tools"] = tools_list
                create_kwargs["tool_choice"] = tool_choice

        usage_prompt_tokens: int = 0
        usage_completion_tokens: int = 0
        streamed_output_text: str = ""

        try:
            try:
                response = await client.chat.completions.create(**create_kwargs)
            except Exception as initial_err:
                # Fallback if an OpenAI-compatible endpoint rejects stream_options
                if "stream_options" in str(initial_err):
                    create_kwargs.pop("stream_options", None)
                    response = await client.chat.completions.create(**create_kwargs)
                else:
                    raise

            tool_call_id: Optional[str] = None
            tool_call_name: Optional[str] = None
            tool_call_args_chunks: List[str] = []

            async for chunk in response:
                # 0. Intercept native usage statistics in the final chunk (where choices may be empty [])
                chunk_usage = getattr(chunk, "usage", None)
                if chunk_usage:
                    p_tok = getattr(chunk_usage, "prompt_tokens", 0) or 0
                    c_tok = getattr(chunk_usage, "completion_tokens", 0) or 0
                    if p_tok > 0:
                        usage_prompt_tokens = p_tok
                    if c_tok > 0:
                        usage_completion_tokens = c_tok

                if not chunk.choices:
                    continue

                delta = chunk.choices[0].delta

                # 1. Check if LLM is streaming a tool_call
                if getattr(delta, "tool_calls", None):
                    for tc_delta in delta.tool_calls:
                        if getattr(tc_delta, "id", None):
                            tool_call_id = tc_delta.id
                        fn = getattr(tc_delta, "function", None)
                        if fn:
                            if getattr(fn, "name", None):
                                tool_call_name = fn.name
                            if getattr(fn, "arguments", None):
                                tool_call_args_chunks.append(fn.arguments)

                # 2. Check if LLM is streaming normal text content
                if getattr(delta, "content", None):
                    streamed_output_text += delta.content
                    yield delta.content

            # If a tool call was accumulated during Turn 1, emit ToolCallRequest
            if tool_call_name or tool_call_args_chunks:
                final_id = ensure_tool_call_id(tool_call_id)
                final_name = tool_call_name or SEARCH_WEB_TOOL_NAME
                raw_args_str = "".join(tool_call_args_chunks)
                streamed_output_text += raw_args_str

                # Fallback query uses the last user message if arguments were empty
                last_user = next(
                    (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                    ""
                )
                parsed_query = parse_tool_query(raw_args_str, fallback_query=last_user[:200])

                raw_assistant_msg = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [
                        {
                            "id": final_id,
                            "type": "function",
                            "function": {
                                "name": final_name,
                                "arguments": json.dumps({"query": parsed_query}, ensure_ascii=False)
                            }
                        }
                    ]
                }

                yield ToolCallRequest(
                    id=final_id,
                    name=final_name,
                    query=parsed_query,
                    raw_assistant_data=raw_assistant_msg
                )

            # Emit UsageMetadata (native or deterministic fallback if omitted by endpoint)
            if usage_prompt_tokens == 0 and usage_completion_tokens == 0 and streamed_output_text:
                usage_prompt_tokens = CostEngine.estimate_messages_tokens(prepared_msgs)
                usage_completion_tokens = CostEngine.estimate_tokens_from_text(streamed_output_text)

            if usage_prompt_tokens > 0 or usage_completion_tokens > 0:
                yield UsageMetadata(
                    prompt_tokens=usage_prompt_tokens,
                    completion_tokens=usage_completion_tokens,
                    total_tokens=usage_prompt_tokens + usage_completion_tokens,
                    model=target_model,
                    provider=getattr(self, "provider_name", provider_label.lower())
                )

        except Exception as e:
            logger.error(f"{provider_label} API Streaming error: {e}", exc_info=True)
            yield f"\n[{provider_label} Error: {str(e)}]"
