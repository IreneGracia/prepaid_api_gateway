import logging
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.security.config import (
    ADMIN_PASSWORD,
    ADMIN_USERNAME,
    JWT_ALGORITHM,
    JWT_EXPIRE_MINUTES,
    JWT_SECRET,
    SEC_AUTH_ENABLED,
)

'''
JWT authentication for the admin portal.

Provides:
- POST /api/auth/login — returns a JWT token
- GET /api/auth/me — returns the current user from the token
- require_admin_auth() — FastAPI dependency for protected routes

When SEC_AUTH_ENABLED is false, require_admin_auth is a no-op
so the admin portal works without login during development.
'''

logger = logging.getLogger("security.auth")

auth_router = APIRouter()


class LoginRequest(BaseModel):
    username: str
    password: str


def _create_token(subject: str) -> str:
    '''Create a signed JWT token.'''
    payload = {
        "sub": subject,
        "exp": datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRE_MINUTES),
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def _verify_token(token: str) -> dict:
    '''Verify and decode a JWT token.'''
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail={"error": "Token expired"})
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail={"error": "Invalid token"})


def _extract_token(request: Request) -> str | None:
    '''Extract JWT from Authorization header or session_token cookie.'''
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        return auth_header[7:]

    return request.cookies.get("session_token")


@auth_router.post("/login")
async def login(payload: LoginRequest):
    '''Authenticate and return a JWT token.'''
    if payload.username != ADMIN_USERNAME or payload.password != ADMIN_PASSWORD:
        logger.warning("Failed admin login attempt: %s", payload.username)
        raise HTTPException(status_code=401, detail={"error": "Invalid credentials"})

    token = _create_token(payload.username)
    return {"token": token, "expiresInMinutes": JWT_EXPIRE_MINUTES}


@auth_router.get("/me")
async def me(request: Request):
    '''Return the current authenticated user.'''
    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail={"error": "Not authenticated"})

    claims = _verify_token(token)
    return {"username": claims["sub"]}


async def require_admin_auth(request: Request):
    '''
    FastAPI dependency that enforces admin authentication.

    When SEC_AUTH_ENABLED is false, this is a no-op (allows
    unauthenticated access to admin routes during development).
    '''
    if not SEC_AUTH_ENABLED:
        return

    token = _extract_token(request)
    if not token:
        raise HTTPException(status_code=401, detail={"error": "Authentication required"})

    _verify_token(token)
