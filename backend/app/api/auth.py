from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.db.supabase import get_supabase_client
from app.core.security import get_current_user

router = APIRouter()


class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: dict


@router.post("/login", response_model=LoginResponse)
async def login(credentials: LoginRequest):
    """Login with email/password (Phase 1 internal auth via Supabase)"""
    supabase = get_supabase_client()
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password
        })
        return LoginResponse(
            access_token=response.session.access_token,
            expires_in=response.session.expires_in,
            user={
                "id": response.user.id,
                "email": response.user.email,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information and roles"""
    # TODO: Fetch user roles and position assignments from database
    return current_user
