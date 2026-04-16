"""Authentication: JWT tokens + role-based access control."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Request
from jose import JWTError, jwt  # type: ignore[import-untyped]

from fpl.config import get_settings

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 30


def create_token(user_id: int, username: str, role: str) -> str:
    """Create a JWT token for a user."""
    settings = get_settings()
    payload = {
        "sub": str(user_id),
        "username": username,
        "role": role,
        "exp": datetime.now(UTC) + timedelta(days=_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT token."""
    settings = get_settings()
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[_ALGORITHM]
        )
        return payload  # type: ignore[no-any-return]
    except JWTError as exc:
        raise HTTPException(
            status_code=401, detail="Invalid or expired token"
        ) from exc


def get_current_user(request: Request) -> dict[str, Any]:
    """FastAPI dependency: extract current user from Authorization header."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(
            status_code=401, detail="Missing authentication token"
        )
    token = auth[7:]
    payload = decode_token(token)
    return {
        "user_id": int(payload["sub"]),
        "username": payload["username"],
        "role": payload["role"],
    }


def require_admin(
    user: dict[str, Any] = Depends(get_current_user),
) -> dict[str, Any]:
    """FastAPI dependency: require admin role."""
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
