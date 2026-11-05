from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.exceptions import NotFoundError
from app.core.permissions import check_position_access, can_update_application_status
from app.schemas.positions import Position, PositionCreate, PositionUpdate, PositionWithStats, PositionStatus, JDVersionCreate
from app.schemas.common import ErrorResponse
from app.db.supabase import get_supabase_client
from app.db.database import SessionLocal
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
import json
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)

# Return real metrics, scoped to applications the caller may see. In particular,
# an assigned hiring manager can see only applications actively shared with them.
_POSITION_WITH_STATS = """
    WITH privileges AS (
        SELECT EXISTS (
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL
              AND role_code IN ('ADMIN', 'HR_LEAD')
        ) AS global_access
    )
    SELECT p.*, latest.status AS criteria_status,
        EXISTS (SELECT 1 FROM app_private.criteria_versions approved
                WHERE approved.position_id = p.position_id AND approved.status = 'APPROVED'
                  AND approved.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                      WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1)) AS criteria_approved,
        stats.total_applications, stats.new_applications, stats.in_review, stats.shortlisted
    FROM app_private.positions p
    CROSS JOIN privileges priv
    LEFT JOIN LATERAL (
        SELECT status FROM app_private.criteria_versions
        WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1
    ) latest ON TRUE
    LEFT JOIN LATERAL (
        SELECT COUNT(*) AS total_applications,
            COUNT(*) FILTER (WHERE a.application_status = 'NEW') AS new_applications,
            COUNT(*) FILTER (WHERE a.application_status = 'IN_REVIEW') AS in_review,
            COUNT(*) FILTER (WHERE a.application_status = 'SHORTLIST') AS shortlisted
        FROM app_private.applications a
        WHERE a.position_id = p.position_id AND (
            priv.global_access OR EXISTS (
                SELECT 1 FROM app_private.position_assignments hr
                WHERE hr.position_id = p.position_id AND hr.user_id = :user_id
                  AND hr.position_role IN ('HR_RECRUITER', 'HR_LEAD') AND hr.revoked_at IS NULL
            ) OR EXISTS (
                SELECT 1 FROM app_private.shortlist_shares share
                JOIN app_private.shortlist_share_items item ON item.share_id = share.share_id
                WHERE share.position_id = p.position_id AND share.shared_with = :user_id
                  AND share.status = 'ACTIVE' AND item.application_id = a.application_id
                  AND EXISTS (SELECT 1 FROM app_private.position_assignments hm
                              WHERE hm.position_id = p.position_id AND hm.user_id = :user_id
                                AND hm.position_role = 'HIRING_MANAGER' AND hm.revoked_at IS NULL)
            )
        )
    ) stats ON TRUE
"""


@router.get("", response_model=List[PositionWithStats])
async def list_positions(
    status_filter: Optional[PositionStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List only positions assigned to the user or shared with them."""
    db = SessionLocal()
    try:
        rows = db.execute(text(_POSITION_WITH_STATS + """
            WHERE (CAST(:status_filter AS text) IS NULL OR p.status = :status_filter)
              AND (priv.global_access OR EXISTS (
                  SELECT 1 FROM app_private.position_assignments pa
                  WHERE pa.position_id = p.position_id AND pa.user_id = :user_id AND pa.revoked_at IS NULL
              ))
            ORDER BY p.created_at DESC, p.position_id DESC LIMIT :page_size OFFSET :offset
        """), {"user_id": current_user["user_id"], "status_filter": status_filter.value if status_filter else None,
                "page_size": page_size, "offset": (page - 1) * page_size}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("", response_model=Position, status_code=status.HTTP_201_CREATED)
async def create_position(
    position_data: PositionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create the position, JD and assignments atomically."""
    user_id = current_user["user_id"]
    for field in ("position_code", "title", "jd_content"):
        value = getattr(position_data, field).strip()
        if not value or (field != "jd_content" and len(value) > 200):
            raise HTTPException(status_code=400, detail="Mã vị trí, tên vị trí và nội dung JD không được để trống")
        setattr(position_data, field, value)
    if not position_data.hiring_manager_user_id:
        raise HTTPException(status_code=400, detail="Vui lòng chọn Hiring Manager phụ trách vị trí")
    db = SessionLocal()
    try:
        can_create = db.execute(text("""
            SELECT EXISTS (SELECT 1 FROM app_private.user_role_assignments
                           WHERE user_id = :user_id AND revoked_at IS NULL
                             AND role_code IN ('ADMIN', 'HR_LEAD', 'HR_RECRUITER'))
                OR EXISTS (SELECT 1 FROM app_private.position_assignments
                           WHERE user_id = :user_id AND revoked_at IS NULL AND position_role IN ('HR_RECRUITER', 'HR_LEAD'))
        """), {"user_id": user_id}).scalar_one()
        if not can_create:
            raise HTTPException(status_code=403, detail="Chỉ HR được phép tạo vị trí tuyển dụng")
        hm_id = str(position_data.hiring_manager_user_id)
        if not db.execute(text("""
            SELECT 1 FROM app_private.user_profiles WHERE user_id = :user_id AND account_status = 'ACTIVE'
        """), {"user_id": hm_id}).first():
            raise HTTPException(status_code=400, detail="Hiring Manager không tồn tại hoặc không còn hoạt động")
        params = position_data.model_dump(exclude={"jd_content", "hiring_manager_user_id"})
        params["created_by"] = user_id
        new_position = db.execute(text("""
            INSERT INTO app_private.positions (position_code, title, job_family, org_unit, level, work_location,
                work_mode, employment_type, headcount, created_by)
            VALUES (:position_code, :title, :job_family, :org_unit, :level, :work_location,
                :work_mode, :employment_type, :headcount, :created_by) RETURNING *
        """), params).mappings().one()
        position_id = new_position["position_id"]
        db.execute(text("""
            INSERT INTO app_private.jd_versions (position_id, version_number, content_text, language_code, created_by)
            VALUES (:position_id, 1, :content, 'en', :user_id)
        """), {"position_id": position_id, "content": position_data.jd_content, "user_id": user_id})
        for assigned_user, role in ((user_id, "HR_RECRUITER"), (hm_id, "HIRING_MANAGER")):
            db.execute(text("""
                INSERT INTO app_private.position_assignments (position_id, user_id, position_role, assigned_by)
                VALUES (:position_id, :assigned_user, :role, :user_id)
            """), {"position_id": position_id, "assigned_user": assigned_user, "role": role, "user_id": user_id})
        db.commit()
        return dict(new_position)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã vị trí đã tồn tại hoặc dữ liệu vị trí không hợp lệ")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{position_id}", response_model=PositionWithStats)
async def get_position(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get details for a position visible to the current user."""
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        result = db.execute(text(_POSITION_WITH_STATS + " WHERE p.position_id = :id"),
                            {"id": str(position_id), "user_id": current_user["user_id"]}).mappings().first()
        if not result:
            raise NotFoundError("Position")
        return dict(result)
    finally:
        db.close()


@router.patch("/{position_id}", response_model=Position)
async def update_position(position_id: UUID, update: PositionUpdate, current_user: dict = Depends(get_current_user)):
    """Update a position and record its status change in the same transaction."""
    user_id = current_user["user_id"]
    if not can_update_application_status(user_id, str(position_id)):
        raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể cập nhật vị trí")
    values = update.model_dump(exclude_unset=True)
    if "status" in values and values["status"] is not None:
        values["status"] = values["status"].value
    allowed = {k: v for k, v in values.items() if k in {"title", "job_family", "org_unit", "level", "work_location", "work_mode", "employment_type", "headcount", "status"} and v is not None}
    if not allowed:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    if "title" in allowed:
        allowed["title"] = allowed["title"].strip()
        if not allowed["title"] or len(allowed["title"]) > 200:
            raise HTTPException(status_code=400, detail="Tên vị trí phải có từ 1 đến 200 ký tự")
    db = SessionLocal()
    try:
        previous = db.execute(text("SELECT status FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": str(position_id)}).scalar_one_or_none()
        if not previous:
            raise NotFoundError("Position")
        sets = ", ".join(f"{key} = :{key}" for key in allowed)
        if "status" in allowed:
            # closed_at represents the current closure; the status-event trail
            # preserves earlier closures when a position is reopened.
            sets += ", closed_at = CASE WHEN :status = 'CLOSED' AND status <> 'CLOSED' THEN NOW() WHEN :status <> 'CLOSED' THEN NULL ELSE closed_at END"
        updated = db.execute(text(f"UPDATE app_private.positions SET {sets}, updated_at = NOW() WHERE position_id = :id RETURNING *"),
                             {**allowed, "id": str(position_id)}).mappings().one()
        if "status" in allowed and previous != allowed["status"]:
            db.execute(text("""
                INSERT INTO app_private.position_status_events (position_id, previous_status, new_status, changed_by)
                VALUES (:id, :previous, :new_status, :user_id)
            """), {"id": str(position_id), "previous": previous, "new_status": allowed["status"], "user_id": user_id})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'UPDATE_POSITION', 'POSITION', :id, :id, 'SUCCESS', CAST(:metadata AS jsonb))
        """), {"user_id": user_id, "id": str(position_id), "metadata": json.dumps({"fields": sorted(allowed)})})
        db.commit()
        return dict(updated)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{position_id}/jd-versions")
async def list_jd_versions(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """All immutable JD versions for users assigned to the position."""
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        return [dict(row) for row in db.execute(text("""
            SELECT jd_version_id, position_id, version_number, content_text, language_code, created_by, created_at
            FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC
        """), {"id": str(position_id)}).mappings().all()]
    finally:
        db.close()


@router.post("/{position_id}/jd-versions", status_code=status.HTTP_201_CREATED)
async def create_jd_version(position_id: UUID, request: JDVersionCreate, current_user: dict = Depends(get_current_user)):
    """Save an immutable version with optimistic concurrency and audit history."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    content = request.content_text.strip()
    if not content:
        raise HTTPException(status_code=400, detail="Nội dung JD không được để trống")
    db = SessionLocal()
    try:
        position = str(position_id)
        if not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": position}).first():
            raise NotFoundError("Position")
        latest = db.execute(text("""
            SELECT jd_version_id, version_number, content_text FROM app_private.jd_versions
            WHERE position_id = :id ORDER BY version_number DESC LIMIT 1
        """), {"id": position}).mappings().first()
        if not latest or str(latest["jd_version_id"]) != str(request.expected_jd_version_id):
            raise HTTPException(status_code=409, detail="JD đã thay đổi. Vui lòng tải lại trước khi lưu phiên bản mới.")
        if latest["content_text"] == content:
            raise HTTPException(status_code=400, detail="Nội dung JD không có thay đổi")
        if db.execute(text("""
            SELECT 1 FROM app_private.operations WHERE position_id = :id
              AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
              AND status IN ('PENDING', 'PROCESSING') LIMIT 1
        """), {"id": position}).first():
            raise HTTPException(status_code=409, detail="Vị trí đang xử lý hồ sơ. Vui lòng đợi tác vụ hoàn tất trước khi sửa JD.")
        row = db.execute(text("""
            INSERT INTO app_private.jd_versions (position_id, version_number, content_text, language_code, created_by)
            VALUES (:position, :version, :content, :language, :user_id) RETURNING *
        """), {"position": position, "version": latest["version_number"] + 1, "content": content,
                "language": request.language_code, "user_id": current_user["user_id"]}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'CREATE_JD_VERSION', 'JD_VERSION', :id, :position, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": row["jd_version_id"], "position": position})
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
