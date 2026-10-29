import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

class LoginRequest(BaseModel):
    """Login credentials (accepts username or email in the identifier field)."""
    username: str = Field(..., min_length=1, example="rpaplaus")
    password: str = Field(..., min_length=1, example="********")

class UserResponse(BaseModel):
    """Public profile representation of an authenticated user."""
    id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TokenResponse(BaseModel):
    """Response payload containing short-lived access token and user profile."""
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse

class ServiceTokenRequest(BaseModel):
    """Request payload for issuing a long-lived Headless Service Account JWT."""
    client_name: str = Field(default="cybernexus", min_length=2, max_length=64, example="cybernexus")
    expire_days: Optional[int] = Field(default=90, ge=1, le=365, example=90)

class ServiceTokenResponse(BaseModel):
    """Response payload containing a long-lived M2M Service Account JWT."""
    access_token: str
    token_type: str = "bearer"
    client_name: str
    expires_in: int

