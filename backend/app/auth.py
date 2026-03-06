"""
JWT authentication utilities for MedIntel.

Uses:
  - python-jose  for JWT encoding / decoding
  - bcrypt (>=4)  for password hashing  (no passlib — incompatible with bcrypt 4+)

Flow:
  1. POST /api/auth/login  →  verify credentials  →  return JWT
  2. Protected routes       →  validate Bearer token via get_current_user dependency
"""
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt

from .config import settings

bearer_scheme = HTTPBearer(auto_error=False)


# ── Password helpers ──────────────────────────────────────────────────────────

def _hash(password: str) -> bytes:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt())


def _verify(password: str, hashed: bytes) -> bool:
    return bcrypt.checkpw(password.encode(), hashed)


# ── Demo user store ───────────────────────────────────────────────────────────
# Hashed once at startup.  In production: query a users table in the DB.
_USERS: dict[str, dict] = {
    "demo@medintel.io": {
        "email":  "demo@medintel.io",
        "name":   "Dr. Olivia Carter",
        "role":   "Analyst",
        "hashed": _hash("demo1234"),
    },
    "admin@medintel.io": {
        "email":  "admin@medintel.io",
        "name":   "Admin User",
        "role":   "Admin",
        "hashed": _hash("admin1234"),
    },
}


# ── Core helpers ──────────────────────────────────────────────────────────────

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """Return the user dict if credentials are valid, otherwise None."""
    user = _USERS.get(email.lower().strip())
    if not user or not _verify(password, user["hashed"]):
        return None
    return user


def create_access_token(email: str, name: str, role: str) -> str:
    """Sign and return a JWT that expires after settings.jwt_expire_hours."""
    payload = {
        "sub":  email,
        "name": name,
        "role": role,
        "exp":  datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expire_hours),
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)


# ── FastAPI dependency ────────────────────────────────────────────────────────

def get_current_user(
    creds: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> dict:
    """
    Validate the Bearer token on every protected request.
    Raises HTTP 401 if the token is missing, expired, or tampered.
    """
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated — please log in.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(
            creds.credentials,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
        )
        return {
            "email": payload["sub"],
            "name":  payload["name"],
            "role":  payload["role"],
        }
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired — please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
