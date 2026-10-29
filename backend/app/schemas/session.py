import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field
from app.schemas.message import MessageResponse

class SessionBase(BaseModel):
    title: str = Field(default="New Chat", max_length=255)
    system_prompt: Optional[str] = None
    model_name: str = Field(default="GPT-5 (OpenAI)", max_length=100)
    web_search_mode: str = Field(default="auto", pattern="^(auto|always|disabled)$")

class SessionCreate(SessionBase):
    pass

class SessionUpdate(BaseModel):
    title: Optional[str] = Field(None, max_length=255)
    system_prompt: Optional[str] = None
    model_name: Optional[str] = Field(None, max_length=100)
    web_search_mode: Optional[str] = Field(None, pattern="^(auto|always|disabled)$")

class SessionResponse(SessionBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class SessionDetailResponse(SessionResponse):
    messages: List[MessageResponse] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)
