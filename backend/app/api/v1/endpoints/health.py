from fastapi import APIRouter, status
from fastapi.responses import JSONResponse
from app.core.config import settings
from app.core.database import check_db_health
from app.core.redis import check_redis_health
from app.schemas.health import HealthResponse

router = APIRouter(prefix="/health", tags=["Health"])

@router.get("", response_model=HealthResponse, summary="System Health & Readiness Check")
async def health_check():
    """
    Performs full readiness inspection:
    - PostgreSQL connectivity
    - Redis connectivity
    - Configured and functional LLM providers
    """
    db_ok = await check_db_health()
    redis_ok = await check_redis_health()

    active_providers = settings.get_active_providers()
    available_models = settings.get_available_models()

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

