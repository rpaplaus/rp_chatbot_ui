import uuid
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Tuple, Optional
import bcrypt
import jwt
import redis.asyncio as aioredis
from app.core.config import settings

REFRESH_COOKIE_NAME = "rp_refresh_token"

def hash_password(password: str) -> str:
    """Hashes a plaintext password using Bcrypt with a random salt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt(rounds=12)
    hashed = bcrypt.hashpw(pwd_bytes, salt)
    return hashed.decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plaintext password against a stored Bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8")
        )
    except Exception:
        return False

def create_access_token(user_id: uuid.UUID, username: str, role: str) -> Tuple[str, int]:
    """
    Creates a short-lived JWT access token.
    Returns (encoded_jwt, expires_in_seconds).
    """
    expires_delta = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4())
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())

def create_service_account_token(
    user_id: uuid.UUID,
    username: str,
    role: str,
    client_name: str = "cybernexus",
    expire_days: Optional[int] = None
) -> Tuple[str, int]:
    """
    Creates a long-lived JWT Service Account Token for Headless M2M integrations (e.g., CyberNexus).
    Returns (encoded_jwt, expires_in_seconds).
    """
    days = expire_days if expire_days is not None else settings.SERVICE_TOKEN_EXPIRE_DAYS
    expires_delta = timedelta(days=days)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "type": "service_account",
        "client": client_name,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "jti": str(uuid.uuid4())
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, int(expires_delta.total_seconds())

def create_refresh_token(user_id: uuid.UUID) -> Tuple[str, str, int]:
    """
    Creates a long-lived JWT refresh token with a unique JTI for Redis rotation.
    Returns (encoded_jwt, jti, ttl_seconds).
    """
    expires_delta = timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    jti = str(uuid.uuid4())
    ttl_seconds = int(expires_delta.total_seconds())

    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp())
    }
    token = jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, jti, ttl_seconds

def decode_jwt_token(token: str) -> Dict[str, Any]:
    """Decodes and validates a JWT token signature and expiration."""
    return jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM]
    )

def _redis_jti_key(user_id: str, jti: str) -> str:
    return f"auth:refresh:{user_id}:{jti}"

async def store_refresh_jti(
    redis_client: aioredis.Redis,
    user_id: str,
    jti: str,
    ttl_seconds: int
) -> None:
    """Stores a valid refresh token JTI in Redis with expiration."""
    key = _redis_jti_key(user_id, jti)
    await redis_client.setex(key, ttl_seconds, "valid")

async def verify_and_consume_refresh_jti(
    redis_client: aioredis.Redis,
    user_id: str,
    jti: str
) -> bool:
    """
    Atomically checks if the refresh JTI exists in Redis and deletes it
    to enforce one-time use (Strict Refresh Token Rotation).
    """
    key = _redis_jti_key(user_id, jti)
    deleted_count = await redis_client.delete(key)
    return deleted_count == 1

async def revoke_refresh_jti(
    redis_client: aioredis.Redis,
    user_id: str,
    jti: str
) -> None:
    """Explicitly revokes a refresh token JTI on logout."""
    key = _redis_jti_key(user_id, jti)
    await redis_client.delete(key)

