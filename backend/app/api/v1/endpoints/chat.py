import json
import uuid
import logging
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.api.deps import get_db, get_current_active_user
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.session import ChatSession
from app.models.message import ChatMessage
from app.schemas.chat import ChatCompletionRequest
from app.services.chat_orchestrator import ChatOrchestrator
from app.services.cost_engine import CostEngine, record_token_usage_background
from app.services.semantic_cache import store_semantic_cache_background
from app.services.llm.factory import LLMFactory

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["Chat"])

@router.post("/completions/stream", summary="Stream chat response via Server-Sent Events (SSE)")
async def chat_completion_stream(
    request: ChatCompletionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Initiates real-time Server-Sent Events streaming response for an authenticated user:
    1. Validates session existence and tenant ownership (user_id).
    2. Persists the user's message immediately into PostgreSQL.
    3. Loads session history.
    4. Streams AI chunks and web search events in real-time.
    5. Persists the complete assistant response into PostgreSQL upon stream completion.
    6. Dispatches asynchronous token usage & USD cost persistence via BackgroundTasks.
    """
    # 1. Verify session exists and belongs to current_user
    session_id = request.session_id
    sess_stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    )
    res = await db.execute(sess_stmt)
    session = res.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada."
        )

    # 2. Persist user message immediately
    user_metadata: Dict[str, Any] = {}
    if request.message.attachments:
        user_metadata["attachments"] = [
            a.model_dump() for a in request.message.attachments
        ]

    user_msg = ChatMessage(
        session_id=session_id,
        role="user",
        content=request.message.content,
        metadata_json=user_metadata
    )
    db.add(user_msg)
    await db.commit()
    await db.refresh(user_msg)

    # 3. Load full conversation history for context
    hist_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    hist_res = await db.execute(hist_stmt)
    history_messages = hist_res.scalars().all()
    history_dicts = [{"role": m.role, "content": m.content} for m in history_messages]

    # Resolve settings
    target_model_name = request.model_name or session.model_name
    profile_id = request.profile_id or "software_engineer"
    system_prompt = request.system_prompt if request.system_prompt is not None else session.system_prompt
    web_search_mode = request.web_search_mode or session.web_search_mode
    file_contexts = [a.model_dump() for a in request.message.attachments] if request.message.attachments else None
    client_timezone = request.client_timezone
    client_local_time = request.client_local_time
    user_prompt_snippet = request.message.content.strip()
    user_id_val = current_user.id

    # 4. Define Asynchronous SSE Generator
    async def sse_event_generator():
        orchestrator = ChatOrchestrator()
        accumulated_text = ""
        sources_metadata: List[Dict[str, Any]] = []
        resolved_model_id = ""
        resolved_provider = ""
        captured_usage: Optional[Dict[str, Any]] = None
        was_cached: bool = False
        cache_store_candidate: Optional[Dict[str, Any]] = None

        try:
            async for event in orchestrator.stream_chat(
                messages=history_dicts,
                model_name=target_model_name,
                system_prompt=system_prompt,
                web_search_mode=web_search_mode,
                file_contexts=file_contexts,
                client_timezone=client_timezone,
                client_local_time=client_local_time,
                profile_id=profile_id,
                user_id=user_id_val
            ):
                event_type = event["event"]
                event_data = event["data"]

                if event_type == "chunk":
                    accumulated_text += event_data.get("text", "")
                elif event_type == "sources":
                    sources_metadata = event_data.get("sources", [])
                elif event_type == "done":
                    resolved_model_id = event_data.get("model", target_model_name)
                    resolved_provider = event_data.get("provider", "")
                    captured_usage = event_data.get("usage")
                    was_cached = bool(event_data.get("cached", False))
                    cache_store_candidate = event_data.pop("cache_store_candidate", None)

                # Format SSE packet
                payload = json.dumps(event_data, ensure_ascii=False)
                yield f"event: {event_type}\ndata: {payload}\n\n"

            # 5. Persist the Assistant's response to PostgreSQL in a dedicated session
            if accumulated_text:
                async with AsyncSessionLocal() as post_db:
                    assistant_msg = ChatMessage(
                        session_id=session_id,
                        role="assistant",
                        content=accumulated_text,
                        metadata_json={
                            "model": resolved_model_id or target_model_name,
                            "sources": sources_metadata
                        }
                    )
                    post_db.add(assistant_msg)

                    # Update session updated_at and rename if default title
                    cur_sess_res = await post_db.execute(
                        select(ChatSession).where(ChatSession.id == session_id)
                    )
                    cur_sess = cur_sess_res.scalar_one_or_none()
                    if cur_sess:
                        cur_sess.updated_at = func.now()
                        if cur_sess.title in ["New Chat", "Novo Chat"]:
                            cur_sess.title = user_prompt_snippet[:40] or "Nova Conversa"

                    await post_db.commit()
                    await post_db.refresh(assistant_msg)

                    # Final persistence confirmation event
                    persisted_payload = json.dumps({
                        "message_id": str(assistant_msg.id),
                        "model": resolved_model_id or target_model_name,
                        "session_id": str(session_id),
                        "created_at": assistant_msg.created_at.isoformat()
                    }, ensure_ascii=False)
                    yield f"event: persisted\ndata: {persisted_payload}\n\n"

        except Exception as e:
            logger.error(f"Error streaming SSE completions: {e}", exc_info=True)
            err_data = json.dumps({"message": f"Erro no streaming: {str(e)}"}, ensure_ascii=False)
            yield f"event: error\ndata: {err_data}\n\n"
        finally:
            # 6. Schedule non-blocking Telemetry & Cost + Semantic Cache persistence via BackgroundTasks
            if not was_cached:
                p_tokens = 0
                c_tokens = 0
                if captured_usage:
                    p_tokens = int(captured_usage.get("prompt_tokens", 0) or 0)
                    c_tokens = int(captured_usage.get("completion_tokens", 0) or 0)
                    resolved_provider = resolved_provider or captured_usage.get("provider", "")
                    resolved_model_id = resolved_model_id or captured_usage.get("model", target_model_name)
                elif accumulated_text:
                    # Fallback if client aborted stream before the final 'done' event
                    p_tokens = CostEngine.estimate_messages_tokens(history_dicts, system_prompt)
                    c_tokens = CostEngine.estimate_tokens_from_text(accumulated_text)

                if not resolved_provider or not resolved_model_id:
                    try:
                        prov_inst, mod_id = LLMFactory.resolve(target_model_name)
                        resolved_provider = resolved_provider or prov_inst.provider_name
                        resolved_model_id = resolved_model_id or mod_id
                    except Exception:
                        resolved_provider = resolved_provider or "openai"
                        resolved_model_id = resolved_model_id or target_model_name

                if p_tokens > 0 or c_tokens > 0:
                    background_tasks.add_task(
                        record_token_usage_background,
                        user_id=user_id_val,
                        session_id=session_id,
                        provider=resolved_provider,
                        model_name=resolved_model_id,
                        prompt_tokens=p_tokens,
                        completion_tokens=c_tokens
                    )

                if cache_store_candidate and accumulated_text:
                    background_tasks.add_task(
                        store_semantic_cache_background,
                        prompt_text=cache_store_candidate["prompt_text"],
                        effective_profile=cache_store_candidate["effective_profile"],
                        scope_key=cache_store_candidate["scope_key"],
                        prompt_hash=cache_store_candidate["prompt_hash"],
                        query_embedding=cache_store_candidate.get("query_embedding"),
                        response_text=accumulated_text,
                        model_name=resolved_model_id,
                        provider=resolved_provider,
                        sources=sources_metadata
                    )

    # Return StreamingResponse with SSE headers and attached BackgroundTasks
    return StreamingResponse(
        sse_event_generator(),
        media_type="text/event-stream",
        background=background_tasks,
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
