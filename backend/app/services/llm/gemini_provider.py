import logging
from typing import AsyncGenerator, List, Dict, Optional, Any
from google import genai
from google.genai import types

from app.services.llm.base import BaseLLMProvider, StreamItem, UsageMetadata
from app.services.llm.tools import (
    ToolCallRequest,
    SEARCH_WEB_TOOL_NAME,
    get_gemini_tools_and_config,
    parse_tool_query,
    ensure_tool_call_id
)
from app.services.cost_engine import CostEngine
from app.core.config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(BaseLLMProvider):
    """Integration for Google Gemini LLMs (google-genai SDK) with native Function Calling and Token Telemetry."""

    provider_name = "gemini"
    default_model = "gemini-3.1-pro-preview"

    def __init__(self):
        if not settings.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY não configurada no arquivo .env.")

        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)

    async def generate_stream(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        system_prompt: Optional[str] = None,
        web_search_context: Optional[str] = None,
        tools_mode: str = "disabled",
        tool_interaction: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamItem, None]:
        target_model = model or self.default_model

        gemini_messages: List[types.Content] = []
        for msg in messages:
            if msg["role"] == "system":
                continue

            role = "model" if msg["role"] == "assistant" else "user"
            gemini_messages.append(
                types.Content(
                    role=role,
                    parts=[types.Part.from_text(text=msg["content"])]
                )
            )

        # If resuming in Turn 2 after executing a function_call
        if tool_interaction:
            call_req: ToolCallRequest = tool_interaction["call"]
            tool_output: str = tool_interaction["output"]

            if call_req.raw_assistant_data and isinstance(call_req.raw_assistant_data, types.Content):
                gemini_messages.append(call_req.raw_assistant_data)
            else:
                gemini_messages.append(
                    types.Content(
                        role="model",
                        parts=[
                            types.Part.from_function_call(
                                name=call_req.name,
                                args={"query": call_req.query}
                            )
                        ]
                    )
                )

            gemini_messages.append(
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_function_response(
                            name=call_req.name,
                            response={"result": tool_output}
                        )
                    ]
                )
            )

        final_system_prompt = system_prompt or ""
        if web_search_context:
            final_system_prompt += f"\n\n--- Contexto de Pesquisa na Web ---\n{web_search_context}"

        config_args: Dict[str, Any] = {}
        if final_system_prompt.strip():
            config_args["system_instruction"] = final_system_prompt.strip()

        if not tool_interaction and tools_mode in ("auto", "always"):
            tools_list, tool_config = get_gemini_tools_and_config(tools_mode)
            if tools_list:
                config_args["tools"] = tools_list
            if tool_config:
                config_args["tool_config"] = tool_config

        config = types.GenerateContentConfig(**config_args)

        usage_prompt_tokens: int = 0
        usage_completion_tokens: int = 0
        streamed_output_text: str = ""

        try:
            response_stream = await self.client.aio.models.generate_content_stream(
                model=target_model,
                contents=gemini_messages,
                config=config
            )

            detected_tool_call: Optional[ToolCallRequest] = None

            async for chunk in response_stream:
                # 0. Extract native usage_metadata from Gemini stream chunk
                um = getattr(chunk, "usage_metadata", None)
                if um:
                    p_tok = getattr(um, "prompt_token_count", 0) or 0
                    c_tok = (getattr(um, "candidates_token_count", 0) or 0) + (
                        getattr(um, "thoughts_token_count", 0) or 0
                    )
                    if p_tok > 0:
                        usage_prompt_tokens = p_tok
                    if c_tok > 0:
                        usage_completion_tokens = c_tok

                # 1. Check for function_calls in chunk
                fn_calls = getattr(chunk, "function_calls", None)
                if fn_calls:
                    fc = fn_calls[0]
                    fc_name = getattr(fc, "name", None) or SEARCH_WEB_TOOL_NAME
                    fc_id = ensure_tool_call_id(getattr(fc, "id", None))
                    fc_args = getattr(fc, "args", None) or {}
                    last_user = next(
                        (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                        ""
                    )
                    parsed_q = parse_tool_query(fc_args, fallback_query=last_user[:200])
                    streamed_output_text += parsed_q

                    raw_content = None
                    if getattr(chunk, "candidates", None) and chunk.candidates[0].content:
                        raw_content = chunk.candidates[0].content

                    detected_tool_call = ToolCallRequest(
                        id=fc_id,
                        name=fc_name,
                        query=parsed_q,
                        raw_assistant_data=raw_content
                    )
                    continue

                # 2. Otherwise yield text chunk if present
                try:
                    if chunk.text:
                        streamed_output_text += chunk.text
                        yield chunk.text
                except Exception:
                    pass

            if detected_tool_call:
                yield detected_tool_call

            if usage_prompt_tokens == 0 and usage_completion_tokens == 0 and streamed_output_text:
                usage_prompt_tokens = CostEngine.estimate_messages_tokens(messages, final_system_prompt)
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
            error_msg = f"Erro na API do Google Gemini: {str(e)}"
            logger.error(error_msg, exc_info=True)
            yield f"\n[Erro de Integração - {error_msg}]"
