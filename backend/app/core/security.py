from fastapi import Depends, HTTPException, status, Request
import jwt
from jwt import PyJWTError
from typing import Optional, Dict, Any
from uuid import UUID
from .config import settings


async def verify_supabase_jwt(request: Request) -> Dict[str, Any]:
    """Verify Supabase JWT token from Authorization header"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    auth_header = request.headers.get("Authorization", "")
    parts = auth_header.split()
    if len(parts) != 2 or parts[0].lower() != "bearer":
        raise credentials_exception

    if not settings.SUPABASE_JWT_SECRET:
        raise HTTPException(status_code=503, detail="Authentication verification is not configured")
    token = parts[1]
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
            options={"require": ["sub", "aud", "exp"]},
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        UUID(user_id)
        return payload
    except (PyJWTError, ValueError, TypeError):
        raise credentials_exception


async def get_current_user(user_payload: Dict[str, Any] = Depends(verify_supabase_jwt)) -> Dict[str, Any]:
    """Extract current user information from verified JWT"""
    user_id = user_payload.get("sub")
    # A still-valid JWT must not keep granting access after an account is disabled.
    from app.db.database import SessionLocal
    from sqlalchemy import text
    db = SessionLocal()
    try:
        account_status = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id"), {"id": user_id}).scalar_one_or_none()
        if account_status != "ACTIVE":
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
    finally:
        db.close()
    return {"user_id": user_id, "email": user_payload.get("email"), "role": user_payload.get("role", "authenticated")}


def require_role(allowed_roles: list[str]):
    """Dependency factory to require specific user roles"""
    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        from app.db.database import SessionLocal
        from sqlalchemy import text
        db = SessionLocal()
        try:
            found = db.execute(text("""
                SELECT 1 FROM app_private.user_role_assignments
                WHERE user_id = :id AND revoked_at IS NULL AND role_code = ANY(:roles) LIMIT 1
            """), {"id": user["user_id"], "roles": allowed_roles}).first()
            if not found:
                raise HTTPException(status_code=403, detail="Required role is not assigned")
            return user
        finally:
            db.close()
    return role_checker
