from typing import List, Optional
from uuid import UUID
from functools import wraps
from fastapi import HTTPException, status, Depends
from app.core.security import get_current_user
from app.db.database import SessionLocal
from sqlalchemy import text


async def require_position_access(
    position_id: UUID,
    required_roles: Optional[List[str]] = None,
    current_user: dict = None
) -> bool:
    """Check if current user has access to a position.

    Args:
        position_id: UUID of the position to check
        required_roles: Optional list of required position roles (HR_RECRUITER, HIRING_MANAGER, HR_LEAD)
        current_user: Authenticated user payload

    Returns:
        True if access is allowed

    Raises:
        HTTPException 403 if access denied
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required"
        )

    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user credentials"
        )

    db = SessionLocal()
    try:
        # Check if user is system Admin or HR Lead (global access)
        admin_check = db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id
              AND revoked_at IS NULL
              AND role_code IN ('ADMIN', 'HR_LEAD')
            LIMIT 1
        """), {"user_id": user_id})

        if admin_check.fetchone():
            return True

        # Check position assignment
        query = """
            SELECT 1 FROM app_private.position_assignments
            WHERE position_id = :position_id
              AND user_id = :user_id
              AND revoked_at IS NULL
        """
        params = {"position_id": str(position_id), "user_id": user_id}

        if required_roles:
            query += " AND position_role = ANY(:required_roles)"
            params["required_roles"] = required_roles

        position_check = db.execute(text(query), params)
        if position_check.fetchone():
            return True

        # Check if user has explicit access grant
        grant_check = db.execute(text("""
            SELECT 1 FROM app_private.position_access_grants
            WHERE position_id = :position_id
              AND user_id = :user_id
              AND revoked_at IS NULL
              AND permission_code = 'VIEW_POSITION'
            LIMIT 1
        """), {"position_id": str(position_id), "user_id": user_id})

        if grant_check.fetchone():
            return True

        # Access denied
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this position"
        )
    finally:
        db.close()


def can_update_application_status(user_id: str, position_id: str) -> bool:
    """Check if user can update application status (must be HR_RECRUITER on the position)"""
    db = SessionLocal()
    try:
        # Admin always can
        admin_check = db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL AND role_code IN ('ADMIN', 'HR_LEAD')
            LIMIT 1
        """), {"user_id": user_id})
        if admin_check.fetchone():
            return True

        # Must be HR_RECRUITER assigned to position
        hr_check = db.execute(text("""
            SELECT 1 FROM app_private.position_assignments
            WHERE position_id = :position_id
              AND user_id = :user_id
              AND position_role = 'HR_RECRUITER'
              AND revoked_at IS NULL
            LIMIT 1
        """), {"position_id": position_id, "user_id": user_id})

        return hr_check.fetchone() is not None
    finally:
        db.close()
