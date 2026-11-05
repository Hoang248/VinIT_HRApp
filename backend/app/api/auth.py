from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional
from app.db.database import SessionLocal
from sqlalchemy import text
from app.core.security import get_current_user
from app.core.config import settings
from supabase import create_client

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
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        raise HTTPException(status_code=503, detail="Authentication service is not configured")
    # Never sign in on the cached service-role client: its session would be
    # replaced globally and subsequent requests could run as another user.
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
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
    except Exception as exc:
        if getattr(exc, "status", None) in (400, 401, 403):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Email hoặc mật khẩu không đúng")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="Dịch vụ đăng nhập tạm thời không khả dụng. Vui lòng thử lại sau.")


@router.get("/me")
async def get_current_user_info(current_user: dict = Depends(get_current_user)):
    """Get current authenticated user information, profile, system roles, and position assignments."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT user_id, display_name, preferred_locale, account_status FROM app_private.user_profiles WHERE user_id = :id
        """), {"id": user_id}).mappings().first()
        if not row or row["account_status"] != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        profile = dict(row)
        roles = db.execute(text("SELECT role_code FROM app_private.user_role_assignments WHERE user_id = :id AND revoked_at IS NULL"), {"id": user_id}).scalars().all()
        assignments = db.execute(text("""
            SELECT position_id, position_role FROM app_private.position_assignments WHERE user_id = :id AND revoked_at IS NULL
        """), {"id": user_id}).mappings().all()
        return {"user_id": user_id, "email": current_user.get("email"), "profile": profile,
                "display_name": profile["display_name"], "system_roles": list(roles),
                "position_assignments": [dict(item) for item in assignments]}
    finally:
        db.close()
