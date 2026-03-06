"""
Authentication endpoints.

POST /api/auth/login   — submit credentials, receive JWT
GET  /api/auth/me      — return the token's user profile
"""
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr

from ..auth import authenticate_user, create_access_token, get_current_user

router = APIRouter()


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


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Authenticate and receive a JWT token",
)
def login(body: LoginRequest):
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
