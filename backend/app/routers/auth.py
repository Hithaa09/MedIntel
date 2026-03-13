"""
Authentication endpoints.

POST /api/auth/login   — submit credentials, receive JWT
GET  /api/auth/me      — return the token's user profile
"""
import time
from collections import defaultdict
from threading import Lock

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from ..auth import authenticate_user, create_access_token, get_current_user

router = APIRouter()

# ── Brute-force rate limiter ──────────────────────────────────────────────────
# Sliding window: max 5 attempts per email per 5 minutes.
_attempts: dict[str, list[float]] = defaultdict(list)
_rl_lock  = Lock()
_MAX_ATTEMPTS = 5
_WINDOW_SEC   = 300  # 5 minutes


def _check_rate_limit(email: str) -> None:
    """Raise 429 if this email has exceeded the login attempt threshold."""
    now = time.monotonic()
    with _rl_lock:
        window_start = now - _WINDOW_SEC
        recent = [t for t in _attempts[email] if t > window_start]
        recent.append(now)
        _attempts[email] = recent          # evict old entries

    if len(recent) > _MAX_ATTEMPTS:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Too many login attempts. Try again in {_WINDOW_SEC // 60} minutes.",
            headers={"Retry-After": str(_WINDOW_SEC)},
        )


# ── Schemas ───────────────────────────────────────────────────────────────────

class LoginRequest(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    email: str
    name:  str
    role:  str


class TokenResponse(BaseModel):
    access_token: str
    token_type:   str = "bearer"
    user:         UserOut


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT token",
)
def login(body: LoginRequest, request: Request):
    _check_rate_limit(body.email.lower().strip())

    user = authenticate_user(body.email, body.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password.",
        )
    token = create_access_token(user["email"], user["name"], user["role"])
    return TokenResponse(
        access_token=token,
        user=UserOut(email=user["email"], name=user["name"], role=user["role"]),
    )


@router.get(
    "/me",
    response_model=UserOut,
    summary="Return the currently authenticated user",
)
def me(user: dict = Depends(get_current_user)):
    return UserOut(**user)
