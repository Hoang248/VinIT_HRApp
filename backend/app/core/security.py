from fastapi import Depends, HTTPException, status, Request
from jose import jwt, JWTError
from typing import Optional, Dict, Any
from .config import settings


async def verify_supabase_jwt(request: Request) -> Dict[str, Any]:
    """Verify Supabase JWT token from Authorization header"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        raise credentials_exception

    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(
            token,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated",
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        return payload
    except JWTError:
        raise credentials_exception


async def get_current_user(user_payload: Dict[str, Any] = Depends(verify_supabase_jwt)) -> Dict[str, Any]:
    """Extract current user information from verified JWT"""
    return {
        "user_id": user_payload.get("sub"),
        "email": user_payload.get("email"),
        "role": user_payload.get("role", "authenticated"),
    }


def require_role(allowed_roles: list[str]):
    """Dependency factory to require specific user roles"""
    async def role_checker(user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        # In Phase 1, role assignment will be checked against app_private.user_role_assignments
        # For now, pass through and let API layer handle position-level permissions
        return user
    return role_checker
