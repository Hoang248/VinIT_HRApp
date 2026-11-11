from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.permissions import check_position_access, can_update_application_status
from app.core.logging import get_logger
from app.core.exceptions import CriteriaNotApprovedError, NotFoundError
from app.schemas.criteria import (
    CriteriaVersion,
    CriteriaVersionCreate,
    CriteriaWeightsUpdate,
    Criterion,
    CriterionCreate,
    CriterionUpdate,
    ApprovalAction,
    CriteriaApprovalRequest
)
from app.schemas.common import OperationResponse
from app.db.database import SessionLocal
from sqlalchemy import text
import json
from app.services.criteria_fairness import fairness_warnings
from app.services.llm_client import llm_client, LLMError

router = APIRouter()
logger = get_logger(__name__)

EDITABLE_STATUSES = ("DRAFT", "PENDING_HR_REVIEW")
OPEN_STATUSES = ("DRAFT", "PENDING_HR_REVIEW", "PENDING_HM_APPROVAL")
MAX_CRITERIA = 100
MAX_KEYWORDS = 20


def _load_criteria(db, version_id):
    row = db.execute(text("SELECT * FROM app_private.criteria_versions WHERE criteria_version_id = :id"), {"id": str(version_id)}).mappings().first()
    if not row:
        raise NotFoundError("Criteria version")
    result = dict(row)
    result["criteria"] = [dict(item) for item in db.execute(text("""
        SELECT * FROM app_private.criteria_items WHERE criteria_version_id = :id ORDER BY display_order, criterion_id
    """), {"id": str(version_id)}).mappings().all()]
    result["fairness_warnings"] = fairness_warnings(result["criteria"])
    return result


def _clean_text(value, *, limit: int, required: bool, label: str):
    if value is None:
        if required:
            raise HTTPException(status_code=400, detail=f"{label} không được để trống")
        return None
    value = str(value).strip()
    if not value:
        if required:
            raise HTTPException(status_code=400, detail=f"{label} không được để trống")
        return None
    if len(value) > limit:
        raise HTTPException(status_code=400, detail=f"{label} không được vượt quá {limit} ký tự")
    return value


def _clean_keywords(values) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, list):
        raise HTTPException(status_code=400, detail="Từ khóa bằng chứng phải là danh sách")
    cleaned: list[str] = []
    for value in values:
        keyword = str(value).strip() if value is not None else ""
        if not keyword:
            continue
        if len(keyword) > 100:
            raise HTTPException(status_code=400, detail="Mỗi từ khóa bằng chứng không được vượt quá 100 ký tự")
        if keyword.lower() not in {k.lower() for k in cleaned}:
            cleaned.append(keyword)
    if len(cleaned) > MAX_KEYWORDS:
        raise HTTPException(status_code=400, detail=f"Tối đa {MAX_KEYWORDS} từ khóa bằng chứng cho mỗi tiêu chí")
    return cleaned


def _lock_editable_draft(db, criteria_version_id, current_user: dict, action: str) -> dict:
    """Lock a draft rubric for an HR edit; pending and approved versions are immutable."""
    version = db.execute(text("""
        SELECT position_id, status FROM app_private.criteria_versions
        WHERE criteria_version_id = :id FOR UPDATE
    """), {"id": str(criteria_version_id)}).mappings().first()
    if not version:
        raise NotFoundError("Criteria version")
    if not can_update_application_status(current_user["user_id"], str(version["position_id"])):
        raise HTTPException(status_code=403, detail=f"Chỉ HR phụ trách mới có thể {action}")
    if version["status"] not in EDITABLE_STATUSES:
        raise HTTPException(status_code=400, detail="Chỉ có thể chỉnh sửa tiêu chí ở trạng thái bản nháp")
    return dict(version)


def _audit(db, user_id, action_type: str, object_type: str, object_id, position_id, metadata: Optional[dict] = None):
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:user_id, :action_type, :object_type, :object_id, :position_id, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"user_id": user_id, "action_type": action_type, "object_type": object_type, "object_id": str(object_id),
            "position_id": str(position_id), "metadata": json.dumps(metadata) if metadata is not None else None})


@router.get("/position/{position_id}/versions", response_model=List[CriteriaVersion])
async def list_criteria_versions(position_id: UUID, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        ids = db.execute(text("SELECT criteria_version_id FROM app_private.criteria_versions WHERE position_id = :id ORDER BY version_number DESC"), {"id": str(position_id)}).scalars().all()
        return [_load_criteria(db, item) for item in ids]
    finally:
        db.close()


@router.get("/{criteria_version_id}", response_model=CriteriaVersion)
async def get_criteria_version(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        result = _load_criteria(db, criteria_version_id)
        await check_position_access(result["position_id"], current_user)
        return result
    finally:
        db.close()


@router.post("/generate/{position_id}", response_model=CriteriaVersion, status_code=status.HTTP_202_ACCEPTED)
async def generate_criteria_from_jd(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Generate a draft only; HR and HM still have to approve it."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    db = SessionLocal()
    try:
        position = db.execute(text("SELECT position_code, title FROM app_private.positions WHERE position_id = :id"), {"id": str(position_id)}).mappings().first()
        if not position:
            raise NotFoundError("Position")
        jd = db.execute(text("""
            SELECT jd_version_id, content_text FROM app_private.jd_versions WHERE position_id = :id
            ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).mappings().first()
        if not jd:
            raise HTTPException(status_code=400, detail="Vị trí chưa có mô tả công việc")
        position, jd = dict(position), dict(jd)
    finally:
        db.close()
    try:
        draft = await llm_client.extract_criteria_from_jd(jd_text=jd["content_text"], requisition_id=position["position_code"], job_title=position["title"])
    except LLMError as exc:
        logger.error("Criteria generation failed", error_type=type(exc).__name__)
        raise HTTPException(status_code=503, detail="Không thể tạo tiêu chí bằng AI. Vui lòng kiểm tra cấu hình và thử lại.")
    try:
        raw = draft["criteria"]
        if not isinstance(raw, list) or not raw or len(raw) > 100:
            raise ValueError("Empty or oversized rubric")
        items = []
        for criterion in raw:
            name, description = criterion["name"].strip(), criterion["description"].strip()
            category, weight = criterion["category"], float(criterion["weight"])
            keywords = criterion.get("expected_evidence_keywords", [])
            if not name or len(name) > 200 or not description or len(description) > 4000 or category not in ("MUST_HAVE", "NICE_TO_HAVE") or not 0 <= weight <= 100 or not isinstance(keywords, list):
                raise ValueError("Invalid criterion")
            # Optional provenance: the JD excerpt behind the criterion and how
            # HR should recognise evidence. Malformed values are dropped, not fatal.
            optional = {}
            for key in ("jd_reference_text", "evidence_guidance"):
                value = criterion.get(key)
                optional[key] = value.strip()[:4000] or None if isinstance(value, str) else None
            items.append({"name": name, "description": description, "category": category, "weight": weight,
                          "keywords": [str(k).strip()[:100] for k in keywords if str(k).strip()][:MAX_KEYWORDS],
                          **optional})
        if not any(c["category"] == "MUST_HAVE" and c["weight"] > 0 for c in items):
            raise ValueError("No weighted mandatory criterion")
        if any(sum(c["weight"] for c in items if c["category"] == category) <= 0
               for category in {c["category"] for c in items}):
            raise ValueError("A criterion group has no weight")
    except (KeyError, TypeError, ValueError, AttributeError):
        raise HTTPException(status_code=502, detail="AI trả về bộ tiêu chí không hợp lệ. Vui lòng thử lại.")
    db = SessionLocal()
    try:
        db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": str(position_id)})
        latest_jd = db.execute(text("SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1"), {"id": str(position_id)}).scalar_one_or_none()
        if str(latest_jd) != str(jd["jd_version_id"]):
            raise HTTPException(status_code=409, detail="JD đã thay đổi trong lúc tạo tiêu chí. Vui lòng thử lại.")
        version = db.execute(text("SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.criteria_versions WHERE position_id = :id"), {"id": str(position_id)}).scalar_one()
        version_id = db.execute(text("""
            INSERT INTO app_private.criteria_versions (position_id, jd_version_id, version_number, origin, status)
            VALUES (:position, :jd, :version, 'AI_DRAFT', 'DRAFT') RETURNING criteria_version_id
        """), {"position": str(position_id), "jd": jd["jd_version_id"], "version": version}).scalar_one()
        for index, item in enumerate(items):
            db.execute(text("""
                INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                    expected_evidence_keywords, evidence_guidance, jd_reference_text, display_order)
                VALUES (:id, :name, :description, :category, :weight, CAST(:keywords AS jsonb),
                    :evidence_guidance, :jd_reference_text, :display_order)
            """), {**item, "id": version_id, "keywords": json.dumps(item["keywords"]), "display_order": index})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
            VALUES (:user_id, 'GENERATE_CRITERIA_DRAFT', 'CRITERIA_VERSION', :id, :position, 'SUCCESS')
        """), {"user_id": current_user["user_id"], "id": version_id, "position": str(position_id)})
        result = _load_criteria(db, version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def criteria_decision(current_status: str, action: ApprovalAction, position_roles: set[str], system_roles: set[str]) -> tuple[str, str]:
    """Return the next state and reviewer capacity after checking the actor's active roles."""
    is_hr = bool({"HR_RECRUITER", "HR_LEAD"} & position_roles) or bool({"ADMIN", "HR_LEAD"} & system_roles)
    is_hm = "HIRING_MANAGER" in position_roles
    # The approval trail records the capacity used; system roles are preserved
    # separately in audit metadata (the approval enum has no ADMIN value).
    hr_role = "HR_LEAD" if "HR_LEAD" in (system_roles | position_roles) and "HR_RECRUITER" not in position_roles else "HR_RECRUITER"

    if action == ApprovalAction.APPROVE:
        if current_status in ("DRAFT", "PENDING_HR_REVIEW"):
            if not is_hr:
                raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể duyệt và gửi tiêu chí cho Hiring Manager")
            return "PENDING_HM_APPROVAL", hr_role
        if current_status == "PENDING_HM_APPROVAL":
            if not is_hm:
                raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được phân công mới có thể duyệt chuyên môn")
            return "APPROVED", "HIRING_MANAGER"
    elif action == ApprovalAction.REQUEST_CHANGES and current_status == "PENDING_HM_APPROVAL":
        if not is_hm:
            raise HTTPException(status_code=403, detail="Chỉ Hiring Manager được phân công mới có thể yêu cầu chỉnh sửa")
        return "DRAFT", "HIRING_MANAGER"
    elif action == ApprovalAction.REJECT and current_status in ("DRAFT", "PENDING_HR_REVIEW"):
        if not is_hr:
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể từ chối tiêu chí")
        return "REJECTED", hr_role

    raise HTTPException(status_code=400, detail=f"Không thể thực hiện thao tác này khi tiêu chí ở trạng thái {current_status}")


@router.post("/{criteria_version_id}/approve", response_model=CriteriaVersion)
async def approve_criteria(
    criteria_version_id: UUID,
    request: CriteriaApprovalRequest,
    current_user: dict = Depends(get_current_user)
):
    """Record the HR and HM decisions atomically, without an HR-only bypass."""
    user_id = current_user["user_id"]
    cv_id_str = str(criteria_version_id)
    comment = (request.comment or "").strip() or None
    if request.action in (ApprovalAction.REJECT, ApprovalAction.REQUEST_CHANGES) and not comment:
        raise HTTPException(status_code=400, detail="Vui lòng nhập lý do từ chối hoặc yêu cầu chỉnh sửa")
    if comment and len(comment) > 2000:
        raise HTTPException(status_code=400, detail="Nội dung phản hồi không được vượt quá 2000 ký tự")
    db = SessionLocal()
    try:
        # Acquire the position lock in the same order as the upload/queue APIs.
        # A new approval cannot become active halfway through an assessment and
        # change the rubric used by its ranking snapshot.
        position = db.execute(text("""
            SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :cv_id
        """), {"cv_id": cv_id_str}).scalar_one_or_none()
        if not position or not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"), {"id": str(position)}).first():
            raise NotFoundError("Criteria version")
        cv = db.execute(text("""
            SELECT position_id, jd_version_id, status, mandatory_weight_total, nice_to_have_weight_total, approved_by_hr
            FROM app_private.criteria_versions WHERE criteria_version_id = :cv_id FOR UPDATE
        """), {"cv_id": cv_id_str}).mappings().first()
        if not cv:
            raise NotFoundError("Criteria version")
        position_id = str(cv["position_id"])
        account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id FOR SHARE"), {"id": user_id}).scalar_one_or_none()
        if account != 'ACTIVE':
            raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
        position_roles = set(db.execute(text("""
            SELECT position_role FROM app_private.position_assignments
            WHERE position_id = :position_id AND user_id = :user_id AND revoked_at IS NULL FOR SHARE
        """), {"position_id": position_id, "user_id": user_id}).scalars())
        system_roles = set(db.execute(text("""
            SELECT role_code FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL FOR SHARE
        """), {"user_id": user_id}).scalars())
        new_status, reviewer_role = criteria_decision(cv["status"], request.action, position_roles, system_roles)
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            latest_jd = db.execute(text("SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1"), {"id": position_id}).scalar_one_or_none()
            if str(latest_jd) != str(cv["jd_version_id"]):
                raise HTTPException(status_code=409, detail="JD đã thay đổi. Vui lòng tạo và duyệt tiêu chí cho phiên bản JD mới nhất.")
        if new_status == "APPROVED":
            # One account may hold both roles.  The position and criteria rows
            # are locked above so this check and the decision are indivisible.
            if not cv["approved_by_hr"] or str(cv["approved_by_hr"]) == str(user_id):
                raise HTTPException(status_code=409, detail="Hai bước duyệt phải do hai tài khoản khác nhau thực hiện")
        if new_status == "APPROVED" and db.execute(text("""
            SELECT 1 FROM app_private.operations WHERE position_id = :position_id
              AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
              AND status IN ('PENDING', 'PROCESSING') LIMIT 1
        """), {"position_id": position_id}).first():
            raise HTTPException(status_code=409, detail="Vị trí đang xử lý hồ sơ. Vui lòng đợi tác vụ hoàn tất trước khi duyệt phiên bản mới.")
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            if (cv["mandatory_weight_total"] <= 0 or cv["nice_to_have_weight_total"] < 0
                    or cv["mandatory_weight_total"] + cv["nice_to_have_weight_total"] != 100):
                raise HTTPException(status_code=400, detail="Trọng số hai nhóm không hợp lệ hoặc không bằng 100%")
        if new_status == "PENDING_HM_APPROVAL":
            groups = db.execute(text("""
                SELECT category, SUM(weight_in_group) AS total FROM app_private.criteria_items
                WHERE criteria_version_id = :id GROUP BY category
            """), {"id": cv_id_str}).mappings().all()
            if not any(g["category"] == "MUST_HAVE" and g["total"] > 0 for g in groups) or any(g["total"] <= 0 for g in groups):
                raise HTTPException(status_code=400, detail="Cần có tiêu chí bắt buộc và trọng số dương trong mỗi nhóm")
        if new_status in ("PENDING_HM_APPROVAL", "APPROVED"):
            # F1.02: criteria must not rely on age, gender, appearance, marital
            # status, personality or culture fit. Checked at both steps so a
            # version flagged by a newer rule cannot be approved by the HM.
            items = db.execute(text("""
                SELECT criterion_id, name, description, evidence_guidance, expected_evidence_keywords
                FROM app_private.criteria_items WHERE criteria_version_id = :id
            """), {"id": cv_id_str}).mappings().all()
            flagged = fairness_warnings([dict(item) for item in items])
            if flagged:
                names = ", ".join(str(w["name"]) for w in flagged[:5])
                raise HTTPException(status_code=400, detail=(
                    "Tiêu chí có dấu hiệu dựa trên thông tin cá nhân không liên quan đến công việc "
                    f"(tuổi, giới tính, ngoại hình, hôn nhân, tính cách, văn hóa...): {names}. "
                    "Vui lòng sửa hoặc xóa trước khi duyệt."))

        db.execute(text("""
            UPDATE app_private.criteria_versions
            SET status = :new_status,
                approved_by_hr = CASE WHEN :new_status = 'PENDING_HM_APPROVAL' THEN :user_id
                                      WHEN :new_status = 'DRAFT' THEN NULL ELSE approved_by_hr END,
                approved_by_hr_at = CASE WHEN :new_status = 'PENDING_HM_APPROVAL' THEN NOW()
                                         WHEN :new_status = 'DRAFT' THEN NULL ELSE approved_by_hr_at END,
                approved_by_hm = CASE WHEN :new_status = 'APPROVED' THEN CAST(:user_id AS uuid) ELSE NULL END,
                approved_by_hm_at = CASE WHEN :new_status = 'APPROVED' THEN NOW() ELSE NULL END,
                updated_at = NOW()
            WHERE criteria_version_id = :cv_id
        """), {"new_status": new_status, "user_id": user_id, "cv_id": cv_id_str})
        db.execute(text("""
            INSERT INTO app_private.criteria_approval_events
                (criteria_version_id, reviewed_by, reviewer_role, decision, comment)
            VALUES (:cv_id, :user_id, :reviewer_role, :decision, :comment)
        """), {"cv_id": cv_id_str, "user_id": user_id, "reviewer_role": reviewer_role,
                "decision": request.action.value, "comment": comment})
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'REVIEW_CRITERIA', 'CRITERIA_VERSION', :cv_id, :position_id,
                    :outcome, CAST(:metadata AS jsonb))
        """), {"user_id": user_id, "cv_id": cv_id_str, "position_id": position_id,
                "outcome": new_status, "metadata": json.dumps({"decision": request.action.value,
                    "reviewer_role": reviewer_role, "system_roles": sorted(system_roles),
                    "position_roles": sorted(position_roles)})})
        updated = _load_criteria(db, cv_id_str)
        db.commit()
        return updated
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/{criteria_version_id}/approval-events")
async def list_approval_events(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        position_id = db.execute(text("SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :id"),
                                 {"id": str(criteria_version_id)}).scalar_one_or_none()
        if not position_id:
            raise NotFoundError("Criteria version")
        await check_position_access(position_id, current_user)
        rows = db.execute(text("""
            SELECT e.event_id, e.reviewed_by, e.reviewer_role, e.decision, e.comment, e.decided_at,
                   p.display_name AS reviewer_name
            FROM app_private.criteria_approval_events e
            LEFT JOIN app_private.user_profiles p ON p.user_id = e.reviewed_by
            WHERE e.criteria_version_id = :id ORDER BY e.decided_at, e.event_id
        """), {"id": str(criteria_version_id)}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.patch("/{criteria_version_id}/weights", response_model=CriteriaVersion)
async def update_criteria_weights(criteria_version_id: UUID, update: CriteriaWeightsUpdate,
                                  current_user: dict = Depends(get_current_user)):
    """Edit group weights only on a draft; the approved version remains immutable."""
    db = SessionLocal()
    try:
        version = db.execute(text("""
            SELECT position_id, status FROM app_private.criteria_versions
            WHERE criteria_version_id = :id FOR UPDATE
        """), {"id": str(criteria_version_id)}).mappings().first()
        if not version:
            raise NotFoundError("Criteria version")
        if not can_update_application_status(current_user["user_id"], str(version["position_id"])):
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể sửa trọng số")
        if version["status"] not in ("DRAFT", "PENDING_HR_REVIEW"):
            raise HTTPException(status_code=400, detail="Chỉ có thể sửa trọng số của bản nháp")
        db.execute(text("""
            UPDATE app_private.criteria_versions
            SET mandatory_weight_total = :mandatory, nice_to_have_weight_total = :nice, updated_at = NOW()
            WHERE criteria_version_id = :id
        """), {"mandatory": update.mandatory_weight_total, "nice": update.nice_to_have_weight_total,
                "id": str(criteria_version_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES (:user_id, 'UPDATE_CRITERIA_WEIGHTS', 'CRITERIA_VERSION', :id, :position_id, 'SUCCESS', CAST(:metadata AS jsonb))
        """), {"user_id": current_user["user_id"], "id": str(criteria_version_id),
                "position_id": str(version["position_id"]), "metadata": json.dumps({
                    "mandatory_weight_total": str(update.mandatory_weight_total),
                    "nice_to_have_weight_total": str(update.nice_to_have_weight_total)})})
        result = _load_criteria(db, criteria_version_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{criteria_version_id}/items/{criterion_id}")
async def update_criterion(criteria_version_id: UUID, criterion_id: UUID, update: CriterionUpdate,
                           current_user: dict = Depends(get_current_user)):
    """HR may revise a draft; approved and pending versions are immutable."""
    fields = update.model_dump(exclude_unset=True)
    allowed: dict = {}
    if fields.get("name") is not None:
        allowed["name"] = _clean_text(fields["name"], limit=200, required=True, label="Tên tiêu chí")
    if fields.get("description") is not None:
        allowed["description"] = _clean_text(fields["description"], limit=4000, required=True, label="Mô tả tiêu chí")
    if fields.get("category") is not None:
        allowed["category"] = fields["category"].value
    if fields.get("weight_in_group") is not None:
        allowed["weight_in_group"] = fields["weight_in_group"]
    if "expected_evidence_keywords" in fields:
        allowed["expected_evidence_keywords"] = json.dumps(_clean_keywords(fields["expected_evidence_keywords"]))
    for key, label in (("evidence_guidance", "Hướng dẫn bằng chứng"), ("jd_reference_text", "Đoạn JD căn cứ")):
        if key in fields:  # an explicit null/blank clears the field
            allowed[key] = _clean_text(fields[key], limit=4000, required=False, label=label)
    if not allowed:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        version = _lock_editable_draft(db, criteria_version_id, current_user, "sửa tiêu chí")
        sets = ", ".join(
            f"{name} = CAST(:{name} AS jsonb)" if name == "expected_evidence_keywords" else f"{name} = :{name}"
            for name in allowed)
        result = db.execute(text(f"""
            UPDATE app_private.criteria_items SET {sets}
            WHERE criterion_id = :criterion_id AND criteria_version_id = :version_id RETURNING criterion_id
        """), {**allowed, "criterion_id": str(criterion_id), "version_id": str(criteria_version_id)}).first()
        if not result:
            raise NotFoundError("Criterion")
        _audit(db, current_user["user_id"], "UPDATE_CRITERION", "CRITERION", criterion_id, version["position_id"],
               {"fields": sorted(allowed)})
        db.commit()
        return {"status": "updated"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{criteria_version_id}/items", response_model=Criterion, status_code=status.HTTP_201_CREATED)
async def add_criterion(criteria_version_id: UUID, request: CriterionCreate,
                        current_user: dict = Depends(get_current_user)):
    """HR adds a criterion to a draft rubric ("Thêm tiêu chí" on S-06)."""
    values = {
        "name": _clean_text(request.name, limit=200, required=True, label="Tên tiêu chí"),
        "description": _clean_text(request.description, limit=4000, required=True, label="Mô tả tiêu chí"),
        "category": request.category.value,
        "weight_in_group": request.weight_in_group,
        "keywords": json.dumps(_clean_keywords(request.expected_evidence_keywords)),
        "evidence_guidance": _clean_text(request.evidence_guidance, limit=4000, required=False, label="Hướng dẫn bằng chứng"),
        "jd_reference_text": _clean_text(request.jd_reference_text, limit=4000, required=False, label="Đoạn JD căn cứ"),
    }
    db = SessionLocal()
    try:
        version = _lock_editable_draft(db, criteria_version_id, current_user, "thêm tiêu chí")
        stats = db.execute(text("""
            SELECT COUNT(*) AS total, COALESCE(MAX(display_order), -1) AS last_order
            FROM app_private.criteria_items WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).mappings().one()
        if stats["total"] >= MAX_CRITERIA:
            raise HTTPException(status_code=400, detail=f"Một bộ tiêu chí có tối đa {MAX_CRITERIA} tiêu chí")
        row = db.execute(text("""
            INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, jd_reference_text, display_order)
            VALUES (:id, :name, :description, :category, :weight_in_group, CAST(:keywords AS jsonb),
                :evidence_guidance, :jd_reference_text, :display_order)
            RETURNING *
        """), {**values, "id": str(criteria_version_id), "display_order": stats["last_order"] + 1}).mappings().one()
        _audit(db, current_user["user_id"], "ADD_CRITERION", "CRITERION", row["criterion_id"], version["position_id"],
               {"criteria_version_id": str(criteria_version_id), "category": values["category"]})
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.delete("/{criteria_version_id}/items/{criterion_id}")
async def delete_criterion(criteria_version_id: UUID, criterion_id: UUID,
                           current_user: dict = Depends(get_current_user)):
    """Remove a criterion from a draft; a rubric always keeps at least one criterion."""
    db = SessionLocal()
    try:
        version = _lock_editable_draft(db, criteria_version_id, current_user, "xóa tiêu chí")
        total = db.execute(text("SELECT COUNT(*) FROM app_private.criteria_items WHERE criteria_version_id = :id"),
                           {"id": str(criteria_version_id)}).scalar_one()
        if total <= 1:
            raise HTTPException(status_code=400, detail="Bộ tiêu chí phải còn ít nhất một tiêu chí")
        deleted = db.execute(text("""
            DELETE FROM app_private.criteria_items
            WHERE criterion_id = :criterion_id AND criteria_version_id = :version_id
            RETURNING name, category
        """), {"criterion_id": str(criterion_id), "version_id": str(criteria_version_id)}).mappings().first()
        if not deleted:
            raise NotFoundError("Criterion")
        _audit(db, current_user["user_id"], "DELETE_CRITERION", "CRITERION", criterion_id, version["position_id"],
               {"criteria_version_id": str(criteria_version_id), "category": deleted["category"]})
        db.commit()
        return {"status": "deleted"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/{criteria_version_id}/new-version", response_model=CriteriaVersion, status_code=status.HTTP_201_CREATED)
async def create_new_criteria_version(criteria_version_id: UUID, current_user: dict = Depends(get_current_user)):
    """Copy an approved or rejected rubric into a new HR draft for the latest JD.

    Approved versions stay immutable, so later edits always produce a new
    version ("Tạo phiên bản mới" on S-06). The copy restarts the HR + HM
    approval flow and never inherits any approval.
    """
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        position_id = db.execute(text("""
            SELECT position_id FROM app_private.criteria_versions WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).scalar_one_or_none()
        # Same lock order as approval and upload: position first, then versions.
        if not position_id or not db.execute(text("SELECT 1 FROM app_private.positions WHERE position_id = :id FOR UPDATE"),
                                             {"id": str(position_id)}).first():
            raise NotFoundError("Criteria version")
        if not can_update_application_status(user_id, str(position_id)):
            raise HTTPException(status_code=403, detail="Chỉ HR phụ trách mới có thể tạo phiên bản tiêu chí mới")
        source = db.execute(text("""
            SELECT status, mandatory_weight_total, nice_to_have_weight_total
            FROM app_private.criteria_versions WHERE criteria_version_id = :id
        """), {"id": str(criteria_version_id)}).mappings().one()
        if source["status"] not in ("APPROVED", "REJECTED"):
            raise HTTPException(status_code=400, detail="Chỉ tạo phiên bản mới từ bộ tiêu chí đã duyệt hoặc đã từ chối; bản nháp hãy sửa trực tiếp")
        if db.execute(text("""
            SELECT 1 FROM app_private.criteria_versions
            WHERE position_id = :id AND status IN ('DRAFT', 'PENDING_HR_REVIEW', 'PENDING_HM_APPROVAL') LIMIT 1
        """), {"id": str(position_id)}).first():
            raise HTTPException(status_code=409, detail="Vị trí đang có bộ tiêu chí chưa hoàn tất duyệt. Vui lòng xử lý bản đó trước.")
        latest_jd = db.execute(text("""
            SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).scalar_one_or_none()
        if not latest_jd:
            raise HTTPException(status_code=400, detail="Vị trí chưa có mô tả công việc")
        version_number = db.execute(text("""
            SELECT COALESCE(MAX(version_number), 0) + 1 FROM app_private.criteria_versions WHERE position_id = :id
        """), {"id": str(position_id)}).scalar_one()
        new_id = db.execute(text("""
            INSERT INTO app_private.criteria_versions (position_id, jd_version_id, version_number, origin, status,
                mandatory_weight_total, nice_to_have_weight_total)
            VALUES (:position, :jd, :version, 'HR_CREATED', 'DRAFT', :mandatory, :nice)
            RETURNING criteria_version_id
        """), {"position": str(position_id), "jd": str(latest_jd), "version": version_number,
                "mandatory": source["mandatory_weight_total"], "nice": source["nice_to_have_weight_total"]}).scalar_one()
        db.execute(text("""
            INSERT INTO app_private.criteria_items (criteria_version_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, jd_reference_text, display_order)
            SELECT :new_id, name, description, category, weight_in_group,
                expected_evidence_keywords, evidence_guidance, jd_reference_text, display_order
            FROM app_private.criteria_items WHERE criteria_version_id = :source_id
        """), {"new_id": str(new_id), "source_id": str(criteria_version_id)})
        _audit(db, user_id, "CREATE_CRITERIA_VERSION", "CRITERIA_VERSION", new_id, position_id,
               {"source_criteria_version_id": str(criteria_version_id), "version_number": version_number})
        result = _load_criteria(db, new_id)
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/position/{position_id}/approved", response_model=Optional[CriteriaVersion])
async def get_latest_approved_criteria(position_id: UUID, current_user: dict = Depends(get_current_user)):
    await check_position_access(position_id, current_user)
    db = SessionLocal()
    try:
        version_id = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions WHERE position_id = :id AND status = 'APPROVED'
              AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :id ORDER BY version_number DESC LIMIT 1)
            ORDER BY version_number DESC LIMIT 1
        """), {"id": str(position_id)}).scalar_one_or_none()
        return _load_criteria(db, version_id) if version_id else None
    finally:
        db.close()
