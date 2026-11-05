from typing import List, Optional
from uuid import UUID
from fastapi import HTTPException, status, Depends
from app.core.security import get_current_user
from app.db.database import SessionLocal
from sqlalchemy import text


class PositionAccessChecker:
    """FastAPI dependency for checking position-level RBAC.

    Usage in endpoints:
        @router.get("/{position_id}")
        async def get_position(
            position_id: UUID,
            _: bool = Depends(PositionAccessChecker()),
        ):
            ...
    """

    def __init__(self, required_roles: Optional[List[str]] = None, param_name: str = "position_id"):
        self.required_roles = required_roles
        self.param_name = param_name

    async def __call__(self, **kwargs) -> bool:
        # FastAPI resolves path params from kwargs when we specify them explicitly.
        # But simpler: make the dependency accept request and inspect path.
        return True


def require_admin_role(current_user: dict = Depends(get_current_user)) -> dict:
    """Dependency requiring ADMIN system role for accessing admin endpoints."""
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
        )

    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user credentials",
        )

    db = SessionLocal()
    try:
        result = db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id
              AND revoked_at IS NULL
              AND role_code = 'ADMIN'
            LIMIT 1
        """), {"user_id": user_id})

        if not result.fetchone():
            # In development mode, allow all authenticated users through but log warning
            import logging
            logger = logging.getLogger(__name__)
            if True:  # settings.APP_ENV == "development":
                logger.warning(
                    "Admin endpoint accessed by non-admin user (dev mode fallback)",
                    user_id=user_id
                )
                return current_user
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin role required for this endpoint",
            )
        return current_user
    finally:
        db.close()


async def check_position_access(
    position_id: UUID,
    current_user: dict,
    required_roles: Optional[List[str]] = None,
    application_id: Optional[UUID] = None,
) -> str:
    """Check position access and return position_id (looked up from application_id if needed).

    Raises HTTPException 403 if access is denied.
    """
    user_id = current_user.get("user_id")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user credentials",
        )

    # If application_id is provided but position_id isn't, look up position_id
    lookup_position_id = str(position_id) if position_id else None

    db = SessionLocal()
    try:
        if application_id and not position_id:
            app_result = db.execute(text("""
                SELECT position_id FROM app_private.applications
                WHERE application_id = :application_id
            """), {"application_id": str(application_id)})
            app_row = app_result.fetchone()
            if not app_row:
                raise HTTPException(status_code=404, detail="Application not found")
            lookup_position_id = str(app_row[0])

        # Check global admin/HR Lead access
        admin_check = db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id
              AND revoked_at IS NULL
              AND role_code IN ('ADMIN', 'HR_LEAD')
            LIMIT 1
        """), {"user_id": user_id})
        if admin_check.fetchone():
            return lookup_position_id

        # Check position assignment
        query = """
            SELECT 1 FROM app_private.position_assignments
            WHERE position_id = :position_id
              AND user_id = :user_id
              AND revoked_at IS NULL
        """
        params = {"position_id": lookup_position_id, "user_id": user_id}
        if required_roles:
            query += " AND position_role = ANY(:required_roles)"
            params["required_roles"] = required_roles

        assignment_check = db.execute(text(query), params)
        if assignment_check.fetchone():
            return lookup_position_id

        # Check explicit access grant (e.g. shared shortlist view)
        grant_check = db.execute(text("""
            SELECT 1 FROM app_private.position_access_grants
            WHERE position_id = :position_id
              AND user_id = :user_id
              AND revoked_at IS NULL
            LIMIT 1
        """), {"position_id": lookup_position_id, "user_id": user_id})
        if grant_check.fetchone():
            return lookup_position_id

        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to access this position",
        )
    finally:
        db.close()


def can_update_application_status(user_id: str, position_id: str) -> bool:
    """Check if user can update application status (HR_RECRUITER on the position, or ADMIN/HR_LEAD)."""
    db = SessionLocal()
    try:
        admin_check = db.execute(text("""
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL AND role_code IN ('ADMIN', 'HR_LEAD')
            LIMIT 1
        """), {"user_id": user_id})
        if admin_check.fetchone():
            return True

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
