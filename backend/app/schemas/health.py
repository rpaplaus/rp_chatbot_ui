from typing import List, Dict
from pydantic import BaseModel, Field

class HealthResponse(BaseModel):
    status: str = Field(..., example="healthy")
    version: str = Field(..., example="1.0.0")
    environment: str = Field(..., example="production")
    database: str = Field(..., example="connected")
    redis: str = Field(..., example="connected")
    active_providers: List[str] = Field(..., example=["openai", "anthropic", "gemini", "xai", "qwen"])
    available_models: List[Dict[str, str]] = Field(..., example=[{"id": "gpt-5-2025-08-07", "name": "GPT-5 (OpenAI)"}])

