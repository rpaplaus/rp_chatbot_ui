import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.database import check_db_health, async_engine
from app.core.redis import check_redis_health, redis_pool
from app.api.v1.router import api_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("rp_chatbot.backend")

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle events management for startup and shutdown."""
    logger.info("=" * 60)
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    
    # 1. Inspect Database & Redis
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()
    logger.info(f"PostgreSQL connection: {'ONLINE' if db_ok else 'OFFLINE/WAITING'}")
    logger.info(f"Redis connection: {'ONLINE' if redis_ok else 'OFFLINE/WAITING'}")

    # 2. Inspect LLM Provider Readiness
    provider_status = settings.get_provider_status()
    for provider, is_ready in provider_status.items():
        status_icon = "READY" if is_ready else "DISABLED (Missing Key)"
        logger.info(f"LLM Provider [{provider.upper()}]: {status_icon}")

    active_models = settings.get_available_models()
    logger.info(f"Active Model Endpoints: {len(active_models)} available")
    logger.info("=" * 60)

    yield

    # Shutdown logic
    logger.info("Shutting down backend services...")
    await async_engine.dispose()
    await redis_pool.disconnect()
    logger.info("Backend connections gracefully closed.")

# Initialize FastAPI App
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="RP_ChatBot Backend Microservice - High Performance AI Gateway with SSE streaming.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "X-API-Key", "Content-Type", "Accept", "Cache-Control", "X-Requested-With"],
    expose_headers=["Content-Type", "Cache-Control", "X-Accel-Buffering"],
)

# Register API v1 routes
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs": "/docs",
        "health": "/api/v1/health"
    }

