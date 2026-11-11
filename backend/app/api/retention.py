"""Retention/deletion workflow API.

These endpoints expose the manual, per-application retention queue.  They do
not implement bulk auto-deletion: a case must be generated after its due date,
confirmed by an authorised user, and then executed explicitly.
"""
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.retention import (
    RetentionError,
    can_confirm_retention,
    can_view_retention,
    cancel_retention_case,
    confirm_retention_case,
    execute_retention_case,
    generate_retention_cases,
    get_case,
    public_case,
)

router = APIRouter()


class RetentionActionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Deprecated compatibility field. It is accepted so older clients do not
    # break, but it is intentionally ignored and never stored: free-text
    # reasons can accidentally contain candidate identifiers.
    reason: str | None = Field(
        default=None,
        max_length=500,
        deprecated=True,
        description=(
            "Deprecated compatibility field; accepted but intentionally "
            "ignored and never stored. Do not include candidate identifiers."
        ),
    )


def _raise(error: RetentionError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from None


def _get_case_or_404(db, case_id: UUID) -> dict:
    try:
        return get_case(db, str(case_id))
    except RetentionError as exc:
        _raise(exc)


def _require_view(db, current_user: dict, position_id: str | None) -> None:
    if not position_id or not can_view_retention(db, current_user["user_id"], position_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem retention của vị trí này")


def _require_confirm(db, current_user: dict, position_id: str | None) -> None:
    if not position_id or not can_confirm_retention(db, current_user["user_id"], position_id):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xác nhận xóa dữ liệu của vị trí này")


@router.get("/queue")
async def retention_queue(status: str | None = None, current_user: dict = Depends(get_current_user)):
    """S-19: retention cases across every position the caller may view.

    Global ADMIN/HR_LEAD see all positions; HR assigned to a position sees
    that position. Each row says whether the caller may confirm/execute it.
    Closed positions are listed so HR can scan them for newly due cases.
    """
    if status is not None and status not in ("PENDING", "SCHEDULED_FOR_DELETION", "DELETED", "CANCELLED"):
        raise HTTPException(status_code=400, detail="Trạng thái retention không hợp lệ")
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        visible = """
            (EXISTS (SELECT 1 FROM app_private.user_role_assignments ur WHERE ur.user_id = :user_id
                     AND ur.revoked_at IS NULL AND ur.role_code IN ('ADMIN', 'HR_LEAD'))
             OR EXISTS (SELECT 1 FROM app_private.position_assignments pa WHERE pa.position_id = p.position_id
                        AND pa.user_id = :user_id AND pa.revoked_at IS NULL AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
        """
        rows = db.execute(text(f"""
            SELECT c.retention_case_id, c.application_id, c.position_id, c.application_opaque_id,
                   c.policy_version, c.position_closed_at, c.due_date, c.status,
                   c.confirmed_by, c.confirmed_at, c.created_at,
                   p.title AS position_title, p.position_code
            FROM app_private.application_retention_cases c
            JOIN app_private.positions p ON p.position_id = c.position_id
            WHERE {visible} AND (CAST(:status AS text) IS NULL OR c.status = :status)
            ORDER BY c.due_date, c.created_at, c.retention_case_id
            LIMIT 500
        """), {"user_id": user_id, "status": status}).mappings().all()
        confirm_cache: dict[str, bool] = {}
        cases = []
        for row in rows:
            position_id = str(row["position_id"])
            if position_id not in confirm_cache:
                confirm_cache[position_id] = can_confirm_retention(db, user_id, position_id)
            cases.append({**public_case(dict(row)), "position_title": row["position_title"],
                          "position_code": row["position_code"], "can_confirm": confirm_cache[position_id]})
        positions = db.execute(text(f"""
            SELECT p.position_id, p.title, p.position_code, p.closed_at
            FROM app_private.positions p
            WHERE p.status = 'CLOSED' AND {visible}
            ORDER BY p.closed_at NULLS LAST, p.title
        """), {"user_id": user_id}).mappings().all()
        return {"cases": cases, "closed_positions": [dict(row) for row in positions]}
    finally:
        db.close()


@router.get("/positions/{position_id}/cases")
async def list_retention_cases(position_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_view(db, current_user, str(position_id))
        rows = db.execute(text("""
            SELECT retention_case_id, application_id, position_id, application_opaque_id,
                   policy_version, position_closed_at, due_date, status,
                   confirmed_by, confirmed_at, created_at
            FROM app_private.application_retention_cases
            WHERE position_id = :position_id
            ORDER BY due_date, created_at, retention_case_id
        """), {"position_id": str(position_id)}).mappings().all()
        return [public_case(dict(row)) for row in rows]
    finally:
        db.close()


@router.post("/positions/{position_id}/cases/generate")
async def generate_cases(position_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_view(db, current_user, str(position_id))
        result = generate_retention_cases(
            db, position_id=str(position_id), actor_user_id=current_user["user_id"]
        )
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/confirm")
async def confirm_case(
    case_id: UUID,
    request: RetentionActionRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = confirm_retention_case(db, case_id=str(case_id), actor_user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/cancel")
async def cancel_case(
    case_id: UUID,
    request: RetentionActionRequest | None = None,
    current_user: dict = Depends(get_current_user),
):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
        result = cancel_retention_case(db, case_id=str(case_id), actor_user_id=current_user["user_id"])
        db.commit()
        return result
    except RetentionError as exc:
        db.rollback()
        _raise(exc)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/cases/{case_id}/execute")
async def execute_case(case_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        case = _get_case_or_404(db, case_id)
        _require_confirm(db, current_user, case.get("position_id"))
    finally:
        db.close()
    try:
        return execute_retention_case(case_id=str(case_id), actor_user_id=current_user["user_id"])
    except RetentionError as exc:
        _raise(exc)
