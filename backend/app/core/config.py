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
        "http://127.0.0.1:5185",
        "http://127.0.0.1:8085",
        "http://127.0.0.1:8002",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5190",
        "http://127.0.0.1:8000",
        "http://127.0.0.1:8080"
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
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = "text-embedding-3-small"

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

    # --- LLM Providers API Keys ---
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
        """Returns the readiness status of each LLM provider."""
        return {
            "openai": bool(self.OPENAI_API_KEY and self.OPENAI_API_KEY.strip()),
            "anthropic": bool(self.ANTHROPIC_API_KEY and self.ANTHROPIC_API_KEY.strip()),
            "gemini": bool(self.effective_gemini_key and self.effective_gemini_key.strip()),
            "xai": bool(self.effective_xai_key and self.effective_xai_key.strip()),
            "qwen": bool(self.QWEN_API_KEY and self.QWEN_API_KEY.strip()),
            "tavily": bool(self.TAVILY_API_KEY and self.TAVILY_API_KEY.strip()),
        }

    def get_active_providers(self) -> List[str]:
        """Returns a list of provider names that have valid API keys configured."""
        status = self.get_provider_status()
        return [provider for provider, is_active in status.items() if is_active]

    def get_available_models(self) -> List[Dict[str, str]]:
        """Returns list of models that can currently be executed based on active keys."""
        status = self.get_provider_status()
        catalog = [
            {"id": "gpt-5-2025-08-07", "name": "GPT-5 (OpenAI)", "provider": "openai"},
            {"id": "claude-sonnet-4-6", "name": "Claude Sonnet 4.6", "provider": "anthropic"},
            {"id": "gemini-3.1-pro-preview", "name": "Gemini-3", "provider": "gemini"},
            {"id": "grok-4-1-fast-reasoning", "name": "grok-4-1-fast-reasoning", "provider": "xai"},
            {"id": "qwen3.5-plus", "name": "Qwen3-Coder", "provider": "qwen"},
        ]
        return [m for m in catalog if status.get(m["provider"], False)]

settings = Settings()
