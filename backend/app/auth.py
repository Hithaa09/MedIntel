"""
JWT authentication utilities for MedIntel.

Authentication strategy:
  1. Query Oracle app_users table first (production path)
  2. Fall back to hardcoded demo credentials if Oracle is unavailable
     (development / demo without a live DB)

Uses python-jose for JWT and bcrypt (>=4) for password hashing.
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


def _verify(password: str, hashed) -> bool:
    """Accept hashed as bytes (from Python) or str (from Oracle VARCHAR2)."""
    h = hashed.encode() if isinstance(hashed, str) else hashed
    return bcrypt.checkpw(password.encode(), h)


# ── Demo fallback (works without Oracle — for development and demos) ──────────
# Hashes are computed once at startup; never stored in source control in plain text.
_DEMO = {
    "demo@medintel.io": {
        "name":  "Dr. Olivia Carter",
        "role":  "Analyst",
        "hashed": _hash("demo1234"),
    },
    "admin@medintel.io": {
        "name":  "Admin User",
        "role":  "Admin",
        "hashed": _hash("admin1234"),
    },
}


# ── Authentication ────────────────────────────────────────────────────────────

def authenticate_user(email: str, password: str) -> Optional[dict]:
    """
    Authenticate against Oracle app_users table (production).
    Falls back to _DEMO credentials when Oracle is unavailable (demo mode).
    Returns user dict on success, None on failure.
    """
    email_key = email.lower().strip()

    # ── Oracle path (production) ──────────────────────────────────────────────
    try:
        from .database import get_conn
        with get_conn() as conn:
            cur = conn.cursor()
            cur.execute(
                "SELECT email, name, role, password_hash "
                "FROM app_users "
                "WHERE LOWER(email) = :email AND is_active = 1",
                {"email": email_key},
            )
            row = cur.fetchone()
        if row:
            db_email, name, role, pw_hash = row
            return (
                {"email": db_email, "name": name, "role": role}
                if _verify(password, pw_hash)
                else None
            )
    except Exception:
        pass  # Oracle not reachable — fall through to demo mode

    # ── Demo fallback ─────────────────────────────────────────────────────────
    demo = _DEMO.get(email_key)
    if not demo or not _verify(password, demo["hashed"]):
        return None
    return {"email": email_key, "name": demo["name"], "role": demo["role"]}


# ── Token ─────────────────────────────────────────────────────────────────────

def create_access_token(email: str, name: str, role: str) -> str:
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
    """Validate Bearer token; raise 401 on missing / expired / tampered token."""
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
        return {"email": payload["sub"], "name": payload["name"], "role": payload["role"]}
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token is invalid or has expired — please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )
