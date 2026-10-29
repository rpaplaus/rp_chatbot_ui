import uuid
from typing import List
from pydantic import BaseModel, Field


class ModelUsageBreakdown(BaseModel):
    provider: str = Field(..., description="LLM provider key (openai, anthropic, gemini, xai, qwen)")
    model_name: str = Field(..., description="Concrete model identifier")
    request_count: int = Field(0, description="Number of requests executed with this model")
    prompt_tokens: int = Field(0, description="Accumulated input/prompt tokens")
    completion_tokens: int = Field(0, description="Accumulated output/completion tokens")
    total_tokens: int = Field(0, description="Total tokens (prompt + completion)")
    total_cost_usd: float = Field(0.0, description="Total cost in USD for this model")
    percentage_of_cost: float = Field(0.0, description="Share (0-100%) of total cost")


class UserUsageSummaryResponse(BaseModel):
    user_id: uuid.UUID
    username: str
    total_requests: int = 0
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    current_month_cost_usd: float = 0.0
    current_month_tokens: int = 0
    by_model: List[ModelUsageBreakdown] = []


class AdminUserRankingItem(BaseModel):
    user_id: uuid.UUID
    username: str
    email: str
    role: str
    is_active: bool
    request_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    current_month_cost_usd: float = 0.0


class AdminUsageSummaryResponse(BaseModel):
    total_platform_cost_usd: float = 0.0
    current_month_platform_cost_usd: float = 0.0
    total_platform_tokens: int = 0
    total_platform_requests: int = 0
    active_users_count: int = 0
    by_model: List[ModelUsageBreakdown] = []
    user_ranking: List[AdminUserRankingItem] = []

