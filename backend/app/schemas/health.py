from typing import List, Dict, Any
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    version: str = Field(..., example="1.0.0")
    environment: str = Field(..., example="production")
    database: str = Field(..., example="connected")
    redis: str = Field(..., example="connected")
    active_providers: List[str] = Field(..., example=["openrouter"])
    available_models: List[Dict[str, Any]] = Field(..., example=[{"id": "openai/gpt-5", "name": "OpenAI: GPT-5", "provider": "openai"}])

