import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, model_validator

class AttachmentPayload(BaseModel):
    """Payload for file attachments included in a chat message."""
    file_id: Optional[str] = None
    filename: str = Field(..., example="relatorio.pdf")
    type: str = Field(default="text", example="text")
    content: str = Field(..., example="Conteúdo extraído do arquivo...")

class UserMessageInput(BaseModel):
    """Input structure for the user's message."""
    content: str = Field(..., min_length=1, example="Explique como funciona o Caddy.")
    attachments: Optional[List[AttachmentPayload]] = Field(default=None)

class ChatCompletionRequest(BaseModel):
    """Request payload for starting a Server-Sent Events chat completion."""
    session_id: uuid.UUID = Field(..., example="8e3be249-e76c-49cc-8e65-ba5a029f3437")
    message: Optional[UserMessageInput] = None
    messages: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Array completo de histórico de mensagens [{'role': 'user'|'assistant', 'content': '...'}] fornecido pelo payload."
    )
    model_name: Optional[str] = Field(default=None, example="GPT-5 (OpenAI)")
    profile_id: Optional[str] = Field(
        default="software_engineer",
        pattern="^(software_engineer|general_assistant|cybernexus_soc)$",
        example="cybernexus_soc",
        description=(
            "Perfil contextual de comportamento da IA "
            "('software_engineer', 'general_assistant' ou 'cybernexus_soc')."
        )
    )
    system_prompt: Optional[str] = Field(default=None)
    web_search_mode: Optional[str] = Field(default="auto", pattern="^(auto|always|disabled)$")
    client_timezone: Optional[str] = Field(default=None, max_length=100, example="America/Sao_Paulo")
    client_local_time: Optional[str] = Field(default=None, max_length=64, example="2026-10-28 15:47")

    @model_validator(mode="after")
    def validate_message_or_messages(self) -> "ChatCompletionRequest":
        if not self.message and not self.messages:
            raise ValueError("Pelo menos um dos campos 'message' ou 'messages' deve ser fornecido.")
        return self

class SSEDoneData(BaseModel):
    """Event data sent when completion stream terminates successfully."""
    message_id: uuid.UUID
    model: str
    provider: str
    full_response: str
    sources: List[Dict[str, Any]] = Field(default_factory=list)
