import uuid
from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from sqlalchemy.orm import selectinload

from app.api.deps import get_db, get_current_active_user
from app.models.user import User
from app.models.session import ChatSession
from app.models.message import ChatMessage
from app.schemas.session import SessionCreate, SessionUpdate, SessionResponse, SessionDetailResponse

router = APIRouter(prefix="/sessions", tags=["Sessions"])

@router.get("", response_model=List[SessionResponse], summary="List all chat sessions owned by the current user")
async def list_sessions(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Lists all chat sessions belonging exclusively to the authenticated user."""
    stmt = (
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    result = await db.execute(stmt)
    sessions = result.scalars().all()
    return sessions

@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, summary="Create a new chat session")
async def create_session(
    data: SessionCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Creates a new empty chat conversation session bound to the authenticated user."""
    session = ChatSession(
        user_id=current_user.id,
        title=data.title,
        system_prompt=data.system_prompt,
        model_name=data.model_name,
        web_search_mode=data.web_search_mode
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)
    return session

@router.get("/{session_id}", response_model=SessionDetailResponse, summary="Get session details and message history")
async def get_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Retrieves a single session and its chronological message history (enforcing tenant isolation)."""
    stmt = (
        select(ChatSession)
        .options(selectinload(ChatSession.messages))
        .where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id
        )
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada."
        )
    return session

@router.patch("/{session_id}", response_model=SessionResponse, summary="Update session metadata")
async def update_session(
    session_id: uuid.UUID,
    data: SessionUpdate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Updates session attributes owned by the current user."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada."
        )

    if data.title is not None:
        session.title = data.title
    if data.system_prompt is not None:
        session.system_prompt = data.system_prompt
    if data.model_name is not None:
        session.model_name = data.model_name
    if data.web_search_mode is not None:
        session.web_search_mode = data.web_search_mode

    await db.commit()
    await db.refresh(session)
    return session

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete session and history")
async def delete_session(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Permanently deletes a chat session owned by the current user and all cascading messages."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada."
        )

    await db.delete(session)
    await db.commit()
    return None

@router.delete("/{session_id}/messages", summary="Clear all messages from session")
async def clear_session_messages(
    session_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Deletes all messages inside a session owned by the current user."""
    stmt = select(ChatSession).where(
        ChatSession.id == session_id,
        ChatSession.user_id == current_user.id
    )
    result = await db.execute(stmt)
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sessão com ID '{session_id}' não encontrada."
        )

    del_stmt = delete(ChatMessage).where(ChatMessage.session_id == session_id)
    await db.execute(del_stmt)
    await db.commit()
    return {"message": f"Histórico da sessão '{session_id}' limpo com sucesso."}
