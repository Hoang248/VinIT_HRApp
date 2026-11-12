"""F2.03 — operational analytics API (pilot report)."""
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.analytics import AnalyticsError, has_any_hr_scope, operational_report, resolve_range

router = APIRouter()


@router.get("/operations")
async def operations_report(date_from: Optional[str] = None, date_to: Optional[str] = None,
                            position_id: Optional[UUID] = None, department_id: Optional[UUID] = None,
                            current_user: dict = Depends(get_current_user)):
    """HR Lead/Admin see every position; HR recruiters only positions they handle.
    Hiring Managers have no access. Nothing is reported per recruiter."""
    try:
        start, end = resolve_range(date_from, date_to)
    except AnalyticsError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    db = SessionLocal()
    try:
        if not has_any_hr_scope(db, current_user["user_id"]):
            raise HTTPException(status_code=403, detail="Chỉ HR, HR Lead hoặc Admin được xem báo cáo vận hành")
        return operational_report(db, user_id=current_user["user_id"], start=start, end=end,
                                  position_id=str(position_id) if position_id else None,
                                  department_id=str(department_id) if department_id else None)
    finally:
        db.close()
