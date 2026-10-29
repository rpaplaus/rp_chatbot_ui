import hmac
import uuid
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import jwt

from app.core.config import settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.core.security import decode_jwt_token
from app.models.user import User

bearer_scheme = HTTPBearer(auto_error=False)
api_key_scheme = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    api_key: Optional[str] = Depends(api_key_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """
    Validates Dual-Auth credentials and resolves the User entity from PostgreSQL:
    1. Static Headless API Key ('X-API-Key' header) verified via constant-time HMAC comparison.
    2. Bearer JWT token ('access' session token or long-lived 'service_account' token).
    """
    # 1. Headless Service Account API Key Authentication (CyberNexus M2M)
    if api_key and settings.CYBERNEXUS_API_KEY:
        if hmac.compare_digest(api_key.strip(), settings.CYBERNEXUS_API_KEY.strip()):
            stmt = select(User).where(
                func.lower(User.username) == settings.APP_USER.strip().lower()
            )
            result = await db.execute(stmt)
            service_user = result.scalar_one_or_none()
            if not service_user:
                fallback_stmt = select(User).where(User.is_active.is_(True)).limit(1)
                fallback_res = await db.execute(fallback_stmt)
                service_user = fallback_res.scalar_one_or_none()
            if service_user:
                return service_user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Chave de API (X-API-Key) inválida.",
            headers={"WWW-Authenticate": "ApiKey"}
        )

    # 2. Bearer JWT Authentication (User Access Token or Service Account Token)
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciais de autenticação não fornecidas.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    token = credentials.credentials
    try:
        payload = decode_jwt_token(token)
        if payload.get("type") not in ("access", "service_account"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token inválido para acesso à API.",
                headers={"WWW-Authenticate": "Bearer"}
            )
        user_id_str = payload.get("sub")
        if not user_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token malformado (sub ausente).",
                headers={"WWW-Authenticate": "Bearer"}
            )
        user_id = uuid.UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso expirado.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    except (jwt.PyJWTError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token de acesso inválido.",
            headers={"WWW-Authenticate": "Bearer"}
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário não encontrado.",
            headers={"WWW-Authenticate": "Bearer"}
        )
    return user

async def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensures the authenticated user is active in the Whitelist."""
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Conta de usuário desativada pelo administrador."
        )
    return current_user

async def get_current_admin_user(
    current_user: User = Depends(get_current_active_user)
) -> User:
    """Ensures the authenticated user has administrator privileges (role='admin')."""
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acesso restrito a administradores da plataforma."
        )
    return current_user

__all__ = [
    "get_db",
    "get_redis",
    "get_current_user",
    "get_current_active_user",
    "get_current_admin_user"
]
