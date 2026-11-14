import os
from typing import List, Optional, Dict, Any
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Application configuration and environment variable validation."""
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False
    )

    # --- Project Metadata ---
    PROJECT_NAME: str = "RP_ChatBot API"
    VERSION: str = "1.0.0"
    ENVIRONMENT: str = "production"
    PORT: int = 8000
    DOMAIN: str = "chat.rpaplaus.com"

    # --- CORS Origins ---
    CORS_ORIGINS: List[str] = [
        "https://chat.rpaplaus.com",
        "https://cybernexus.rpaplaus.com",
        "http://localhost:5185",
        "http://localhost:8085",
        "http://localhost:8002",
        "http://localhost:3000",
        "http://localhost:5173",
        "http://localhost:5190",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost:5180",
        "http://127.0.0.1:5185",
        "http://127.0.0.1:8085",
        "http://127.0.0.1:8002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5190",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080",
        "http://127.0.0.1:5180",
    ]

    # --- Database (PostgreSQL) ---
    POSTGRES_USER: str = "rp_admin"
    POSTGRES_PASSWORD: str = "rp_secure_postgres_pass"
    POSTGRES_DB: str = "rp_chatbot"
    POSTGRES_PORT: int = 5438
    DATABASE_URL: str = "postgresql+asyncpg://rp_admin:rp_secure_postgres_pass@database:5432/rp_chatbot"

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_asyncpg_scheme(cls, v: str) -> str:
        if isinstance(v, str):
            if v.startswith("postgresql://"):
                return v.replace("postgresql://", "postgresql+asyncpg://", 1)
            if v.startswith("postgres://"):
                return v.replace("postgres://", "postgresql+asyncpg://", 1)
        return v

    # --- Cache (Redis & Semantic Cache L1/L2) ---
    REDIS_PASSWORD: str = "rp_secure_redis_pass"
    REDIS_PORT: int = 6388
    REDIS_URL: str = "redis://:rp_secure_redis_pass@redis:6379/0"
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_DIMENSIONS: int = 512
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"

    # --- Security, JWT & Whitelist Admin Seed ---
    SECRET_KEY: str = "rp_chatbot_super_secret_session_key_2026_x99!"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SERVICE_TOKEN_EXPIRE_DAYS: int = 90
    CYBERNEXUS_API_KEY: str = "cn_live_rpchatbot_soc_key_2026_x99!"
    COOKIE_SECURE: bool = False

    APP_USER: str = "rpaplaus"
    APP_PASSWORD: str = "Dumai!605Bacon"
    APP_EMAIL: str = "admin@rpaplaus.com"

    # --- OpenRouter Unified LLM Gateway ---
    OPENROUTER_API_KEY: Optional[str] = None
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_APP_URL: str = "https://chat.rpaplaus.com"
    OPENROUTER_APP_NAME: str = "RP_ChatBot"
    DEFAULT_OPENROUTER_MODEL: str = "openai/gpt-5"

    # --- Legacy LLM Keys (Optional fallback) ---
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    XAI_API_KEY: Optional[str] = None
    GROK_API_KEY: Optional[str] = None
    QWEN_API_KEY: Optional[str] = None
    QWEN_BASE_URL: str = "https://dashscope-us.aliyuncs.com/compatible-mode/v1"
    
    # --- Search Providers ---
    TAVILY_API_KEY: Optional[str] = None

    # --- Effective Keys with Fallbacks ---
    @property
    def effective_gemini_key(self) -> Optional[str]:
        return self.GEMINI_API_KEY or self.GOOGLE_API_KEY

    @property
    def effective_xai_key(self) -> Optional[str]:
        return self.XAI_API_KEY or self.GROK_API_KEY

    def get_provider_status(self) -> Dict[str, bool]:
        """Returns the readiness status of OpenRouter and auxiliary providers."""
        return {
            "openrouter": bool(self.OPENROUTER_API_KEY and self.OPENROUTER_API_KEY.strip()),
            "tavily": bool(self.TAVILY_API_KEY and self.TAVILY_API_KEY.strip()),
        }

    def get_active_providers(self) -> List[str]:
        """Returns a list of provider names that have valid API keys configured."""
        status = self.get_provider_status()
        return [provider for provider, is_active in status.items() if is_active]

    def get_available_models(self) -> List[Dict[str, Any]]:
        """Returns initial default OpenRouter models before dynamic catalog hydration."""
        if not (self.OPENROUTER_API_KEY and self.OPENROUTER_API_KEY.strip()):
            return []
        return [
            {"id": self.DEFAULT_OPENROUTER_MODEL, "name": "OpenAI: GPT-5", "provider": "openai"},
        ]

settings = Settings()
