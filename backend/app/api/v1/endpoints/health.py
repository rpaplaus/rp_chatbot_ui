from fastapi import APIRouter, status, Query
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse
from app.services.llm.openrouter_provider import OpenRouterCatalog

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", response_model=HealthResponse, summary="System Health & Readiness Check")
async def health_check():
    """
    Performs full readiness inspection:
    - PostgreSQL connectivity
    - Redis connectivity
    - Configured OpenRouter gateway & available models catalog
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    active_providers = settings.get_active_providers()
    available_models = await OpenRouterCatalog.get_models()

    overall_healthy = db_ok and redis_ok
    status_str = "healthy" if overall_healthy else "degraded"

    data = {
        "status": status_str,
        "version": settings.VERSION,
        "environment": settings.ENVIRONMENT,
        "database": "connected" if db_ok else "disconnected",
        "redis": "connected" if redis_ok else "disconnected",
        "active_providers": active_providers,
        "available_models": available_models
    }

    http_code = status.HTTP_200_OK if overall_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_code, content=data)


@router.get("/models", summary="List all available OpenRouter models")
async def list_openrouter_models(refresh: bool = Query(default=False, description="Force refresh from OpenRouter API")):
    """Returns the complete catalog of OpenRouter models with pricing, context window, and tool support metadata."""
    models = await OpenRouterCatalog.get_models(force_refresh=refresh)
    return {
        "total": len(models),
        "default_model": settings.DEFAULT_OPENROUTER_MODEL,
        "models": models
    }

