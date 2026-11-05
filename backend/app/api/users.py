from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text

from app.core.permissions import check_position_access
from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()


@router.get("")
async def list_users(search: Optional[str] = Query(None), position_id: Optional[UUID] = Query(None),
                     current_user: dict = Depends(get_current_user)):
    """Search active basic profiles, optionally restricted to a visible position."""
    if position_id:
        await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        if not position_id:
            may_search_directory = db.execute(text("""
                SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments
                               WHERE user_id = :user_id AND revoked_at IS NULL
                                 AND role_code IN ('ADMIN', 'HR_LEAD', 'HR_RECRUITER'))
                    OR EXISTS (SELECT 1 FROM app_private.position_assignments
                               WHERE user_id = :user_id AND revoked_at IS NULL
                                 AND position_role IN ('HR_RECRUITER', 'HR_LEAD'))
            """), {"user_id": current_user["user_id"]}).scalar_one()
            if not may_search_directory:
                raise HTTPException(status_code=403, detail="Chỉ HR được tìm kiếm danh bạ người dùng")
        rows = db.execute(text("""
            SELECT p.user_id, p.display_name, p.preferred_locale,
                COALESCE(array_agg(pa.position_role) FILTER (WHERE pa.position_role IS NOT NULL), ARRAY[]::text[]) AS position_roles
            FROM app_private.user_profiles p
            LEFT JOIN app_private.position_assignments pa
              ON pa.user_id = p.user_id AND pa.revoked_at IS NULL
              AND pa.position_id = CAST(:position_id AS uuid)
            WHERE p.account_status = 'ACTIVE'
              AND (CAST(:position_id AS uuid) IS NULL OR pa.user_id IS NOT NULL)
              AND (CAST(:search AS text) IS NULL OR p.display_name ILIKE :pattern)
            GROUP BY p.user_id, p.display_name, p.preferred_locale
            ORDER BY p.display_name LIMIT 50
        """), {"position_id": str(position_id) if position_id else None,
                "search": search, "pattern": f"%{search}%" if search else None}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()
