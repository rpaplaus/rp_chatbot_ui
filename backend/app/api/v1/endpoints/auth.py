import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
import redis.asyncio as aioredis
import jwt

from app.api.deps import get_db, get_redis, get_current_active_user, get_current_admin_user
from app.core.config import settings
from app.core.security import (
    REFRESH_COOKIE_NAME,
    verify_password,
    create_access_token,
    create_service_account_token,
    create_refresh_token,
    decode_jwt_token,
    store_refresh_jti,
    verify_and_consume_refresh_jti,
    revoke_refresh_jti
)
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    TokenResponse,
    UserResponse,
    ServiceTokenRequest,
    ServiceTokenResponse
)

router = APIRouter(prefix="/auth", tags=["Authentication"])

def _is_secure_context(request: Request) -> bool:
    """Determines whether the Secure flag should be enforced on cookies."""
    if settings.COOKIE_SECURE:
        return True
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    return request.url.scheme == "https" or forwarded_proto.lower() == "https"

def _set_refresh_cookie(
    response: Response,
    request: Request,
    refresh_token: str,
    max_age: int
) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=_is_secure_context(request),
        samesite="lax",
        max_age=max_age,
        path="/api/v1/auth"
    )

@router.post("/login", response_model=TokenResponse, summary="Authenticate user and issue JWT + HttpOnly Refresh Cookie")
async def login(
    data: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """
    Authenticates user credentials against the closed Whitelist database.
    Issues a short-lived access_token in JSON and a rotated refresh_token in an HttpOnly cookie.
    """
    identifier = data.username.strip().lower()
    stmt = select(User).where(
        or_(
            func.lower(User.username) == identifier,
            func.lower(User.email) == identifier
        )
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos."
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Esta conta está desativada. Contate o administrador."
        )

    access_token, expires_in = create_access_token(user.id, user.username, user.role)
    refresh_token, jti, refresh_ttl = create_refresh_token(user.id)

    await store_refresh_jti(redis_client, str(user.id), jti, refresh_ttl)
    _set_refresh_cookie(response, request, refresh_token, refresh_ttl)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user)
    )

@router.post("/refresh", response_model=TokenResponse, summary="Rotate Refresh Token from HttpOnly Cookie and issue new Access Token")
async def refresh_token_endpoint(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """
    Reads the HttpOnly refresh token cookie, validates and consumes its JTI in Redis
    (Strict Rotation), and returns a fresh access_token + rotated refresh_token cookie.
    """
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw_refresh:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token ausente."
        )

    try:
        payload = decode_jwt_token(raw_refresh)
        if payload.get("type") != "refresh":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Tipo de token inválido para refresh."
            )
        user_id_str = payload.get("sub")
        jti = payload.get("jti")
        if not user_id_str or not jti:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token malformado."
            )
        user_id = uuid.UUID(user_id_str)
    except jwt.ExpiredSignatureError:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sessão expirada. Faça login novamente."
        )
    except (jwt.PyJWTError, ValueError):
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token inválido."
        )

    # Verify JTI in Redis and consume it atomically (one-time rotation)
    is_valid_jti = await verify_and_consume_refresh_jti(redis_client, str(user_id), jti)
    if not is_valid_jti:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token já utilizado ou revogado."
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not user.is_active:
        response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário inativo ou inexistente."
        )

    new_access_token, expires_in = create_access_token(user.id, user.username, user.role)
    new_refresh_token, new_jti, refresh_ttl = create_refresh_token(user.id)

    await store_refresh_jti(redis_client, str(user.id), new_jti, refresh_ttl)
    _set_refresh_cookie(response, request, new_refresh_token, refresh_ttl)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        expires_in=expires_in,
        user=UserResponse.model_validate(user)
    )

@router.post("/logout", summary="Revoke Refresh Token in Redis and clear HttpOnly Cookie")
async def logout(
    request: Request,
    response: Response,
    redis_client: aioredis.Redis = Depends(get_redis)
):
    """Revokes the active refresh token JTI in Redis and clears the HttpOnly cookie."""
    raw_refresh = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw_refresh:
        try:
            payload = decode_jwt_token(raw_refresh)
            user_id_str = payload.get("sub")
            jti = payload.get("jti")
            if user_id_str and jti:
                await revoke_refresh_jti(redis_client, user_id_str, jti)
        except Exception:
            pass

    response.delete_cookie(REFRESH_COOKIE_NAME, path="/api/v1/auth")
    return {"message": "Logout realizado com sucesso."}

@router.get("/me", response_model=UserResponse, summary="Get current authenticated user profile")
async def get_me(current_user: User = Depends(get_current_active_user)):
    """Returns the currently authenticated user's profile."""
    return UserResponse.model_validate(current_user)

@router.post(
    "/service-token",
    response_model=ServiceTokenResponse,
    summary="Issue a long-lived Service Account JWT for Headless integrations (e.g. CyberNexus)"
)
async def issue_service_token(
    data: ServiceTokenRequest,
    current_admin: User = Depends(get_current_admin_user)
):
    """
    Issues a long-lived Service Account Token (JWT with type='service_account') bound to the
    administrator tenant for secure Headless M2M consumption by CyberNexus.
    """
    token, expires_in = create_service_account_token(
        user_id=current_admin.id,
        username=current_admin.username,
        role=current_admin.role,
        client_name=data.client_name,
        expire_days=data.expire_days
    )
    return ServiceTokenResponse(
        access_token=token,
        token_type="bearer",
        client_name=data.client_name,
        expires_in=expires_in
    )

