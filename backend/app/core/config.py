import hashlib
import os
from typing import List, Optional, Dict, Any
from urllib.parse import urlsplit
from pydantic import Field, ValidationInfo, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# SHA-256 of credentials that were committed to the public repository and must never be reused.
_LEAKED_SECRET_SHA256 = frozenset({
    "3d8ebf0c17dd58117a1b3bd79ba5736f6e8d4334a075703a655fde3d07971135",
    "10a4be6318d47a86ec62c05e0970315798b70fe94ad1edfc552d8dcd305774fd",
    "31c21db75414872d6ef758597e3b4413ab3371394ecf66764cb7ece248c87aad",
    "80b1abb54ee0548bbd39a9a05b94abf6348aeba9b5fc4890dd4afde5bb788e08",
    "c8a94fe5db2294678d48c76689e872962922cc0fc92117b06496277b7ffc4d3f",
})

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
    # Secrets have no defaults: they MUST be provided via .env / environment variables.
    POSTGRES_USER: str = "rp_admin"
    POSTGRES_PASSWORD: Optional[str] = None
    POSTGRES_DB: str = "rp_chatbot"
    POSTGRES_PORT: int = 5438
    DATABASE_URL: str

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
    REDIS_PASSWORD: Optional[str] = None
    REDIS_PORT: int = 6388
    REDIS_URL: str
    SEMANTIC_CACHE_ENABLED: bool = True
    SEMANTIC_CACHE_THRESHOLD: float = 0.95
    SEMANTIC_CACHE_DIMENSIONS: int = 512
    SEMANTIC_CACHE_EMBEDDING_MODEL: str = "openai/text-embedding-3-small"

    # --- Security, JWT & Whitelist Admin Seed ---
    SECRET_KEY: str = Field(..., min_length=32)
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    SERVICE_TOKEN_EXPIRE_DAYS: int = 90
    CYBERNEXUS_API_KEY: str = Field(..., min_length=32)
    COOKIE_SECURE: bool = False

    APP_USER: str = "rpaplaus"
    APP_PASSWORD: str = Field(..., min_length=12)
    APP_EMAIL: str = "admin@rpaplaus.com"

    @field_validator("DATABASE_URL", "REDIS_URL", "SECRET_KEY", "CYBERNEXUS_API_KEY", "APP_PASSWORD")
    @classmethod
    def reject_blank_or_leaked_secrets(cls, v: str, info: ValidationInfo) -> str:
        if not v or not v.strip():
            raise ValueError(f"{info.field_name} must be set in .env")
        secret = urlsplit(v).password if info.field_name.endswith("_URL") else v
        if secret and hashlib.sha256(secret.encode()).hexdigest() in _LEAKED_SECRET_SHA256:
            raise ValueError(f"{info.field_name} uses a publicly leaked value; rotate it in .env")
        return v

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
    SERPER_API_KEY: Optional[str] = None

    # --- Generation & Multimodal ---
    UPLOAD_DIR: str = "/app/uploads"
    LLM_MAX_OUTPUT_TOKENS: int = 16384
    # Used to transcribe audio attachments when the selected chat model has no audio input.
    AUDIO_TRANSCRIPTION_MODEL: str = "google/gemini-2.5-flash"
    MAX_AUDIO_ATTACHMENT_BYTES: int = 20 * 1024 * 1024

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
            "serper": bool(self.SERPER_API_KEY and self.SERPER_API_KEY.strip()),
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
