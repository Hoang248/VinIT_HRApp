"""F2.04 QA sample inspection: queue, side-by-side review data, flags and summary.

Access (decision D-3): HR_LEAD and ADMIN review and flag; recruiters assigned to
a position may read the queue and results of that position only.
"""
from datetime import datetime, timedelta, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services import qa_sampling

logger = get_logger(__name__)
router = APIRouter()

REVIEW_OVERDUE_DAYS = 7  # D-6: show items older than one week, no reminders yet.
REVIEWER_ROLES = ("HR_LEAD", "ADMIN")


class SampleRunCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    batch_id: UUID


class FlagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    flag_type: Literal["INCORRECT_EVIDENCE", "MISSED_CONTENT", "OCR_ERROR"]
    criterion_result_id: UUID | None = None
    evidence_id: UUID | None = None
    expected_outcome: Literal["STRONG_MATCH", "MATCH", "UNCLEAR", "NO_MATCH"] | None = None
    note: str | None = Field(default=None, max_length=2000)


class ReviewDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["PASSED"]


def _active_roles(db, user_id: str) -> set[str]:
    account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id = :id"),
                         {"id": user_id}).scalar_one_or_none()
    if account != "ACTIVE":
        raise HTTPException(status_code=403, detail="Tài khoản chưa được kích hoạt hoặc đã bị khóa")
    return set(db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments WHERE user_id = :id AND revoked_at IS NULL
    """), {"id": user_id}).scalars().all())


def _is_reviewer(db, user_id: str) -> bool:
    return bool(_active_roles(db, user_id) & set(REVIEWER_ROLES))


def _require_reviewer(db, user_id: str) -> None:
    if not _is_reviewer(db, user_id):
        raise HTTPException(status_code=403, detail="Chỉ HR Lead hoặc Admin mới được kiểm định mẫu")


def _require_read(db, user_id: str, position_id: str) -> None:
    if _is_reviewer(db, user_id):
        return
    assigned = db.execute(text("""
        SELECT 1 FROM app_private.position_assignments
        WHERE position_id = :position AND user_id = :user AND revoked_at IS NULL
          AND position_role IN ('HR_RECRUITER', 'HR_LEAD')
    """), {"position": position_id, "user": user_id}).first()
    if not assigned:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem kết quả kiểm định của vị trí này")


def _item_row(db, sample_item_id: UUID):
    row = db.execute(text("""
        SELECT i.*, r.position_id, r.batch_id, r.criteria_version_id, r.sampling_rules_version
        FROM app_private.qa_sample_items i
        JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
        WHERE i.sample_item_id = :id
    """), {"id": str(sample_item_id)}).mappings().first()
    if not row:
        raise NotFoundError("QA sample item")
    return row


def _audit(db, user_id: str, action: str, object_type: str, object_id: str, position_id: str) -> None:
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, position_id, outcome)
        VALUES (:user, :action, :object_type, :object_id, :position, 'SUCCESS')
    """), {"user": user_id, "action": action, "object_type": object_type, "object_id": object_id,
           "position": position_id})


@router.post("/positions/{position_id}/sample-runs", status_code=status.HTTP_201_CREATED)
async def create_manual_sample_run(position_id: UUID, request: SampleRunCreate,
                                   current_user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_reviewer(db, current_user["user_id"])
        batch = db.execute(text("""
            SELECT batch_id FROM app_private.cv_batches WHERE batch_id = :batch AND position_id = :position
        """), {"batch": str(request.batch_id), "position": str(position_id)}).first()
        if not batch:
            raise NotFoundError("CV batch")
        criteria_version_id = db.execute(text("""
            SELECT criteria_version_id FROM app_private.criteria_versions
            WHERE position_id = :position AND status = 'APPROVED'
            ORDER BY version_number DESC LIMIT 1
        """), {"position": str(position_id)}).scalar_one_or_none()
        if not criteria_version_id:
            raise HTTPException(status_code=409, detail="Vị trí chưa có bộ tiêu chí đã duyệt")
        run = qa_sampling.create_sample_run(
            db, position_id=str(position_id), batch_id=str(request.batch_id),
            criteria_version_id=str(criteria_version_id), trigger_type="MANUAL",
            actor_user_id=current_user["user_id"])
        if not run:
            raise HTTPException(status_code=409, detail="Đợt CV này chưa có hồ sơ được đánh giá xong")
        db.commit()
        return run
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/queue")
async def list_queue(position_id: UUID | None = None,
                     item_status: Literal["PENDING", "PASSED", "FLAGGED"] | None = Query(default=None, alias="status"),
                     reason: Literal["RANDOM", "SINGLE_MUST_HAVE_FAIL", "COVERAGE_NEAR_THRESHOLD"] | None = None,
                     limit: int = Query(default=100, ge=1, le=500),
                     current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        reviewer = _is_reviewer(db, user_id)
        if position_id:
            _require_read(db, user_id, str(position_id))
        rows = db.execute(text("""
            SELECT i.sample_item_id, i.sample_run_id, i.application_id, i.assessment_id, i.reasons, i.status,
                   i.reviewer_id, i.reviewed_at, i.created_at, r.position_id, r.batch_id,
                   p.title AS position_title, idn.display_name,
                   ar.matching_status, ar.evidence_coverage,
                   (SELECT COUNT(*) FROM app_private.qa_flags f WHERE f.sample_item_id = i.sample_item_id) AS flag_count,
                   (i.status = 'PENDING' AND i.created_at < :overdue_before) AS overdue
            FROM app_private.qa_sample_items i
            JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
            JOIN app_private.positions p ON p.position_id = r.position_id
            LEFT JOIN app_private.application_identities idn ON idn.application_id = i.application_id
            LEFT JOIN app_private.assessment_runs ar ON ar.assessment_id = i.assessment_id
            WHERE (CAST(:position AS UUID) IS NULL OR r.position_id = CAST(:position AS UUID))
              AND (CAST(:status AS TEXT) IS NULL OR i.status = CAST(:status AS TEXT))
              AND (CAST(:reason AS TEXT) IS NULL OR CAST(:reason AS TEXT) = ANY(i.reasons))
              AND (:reviewer OR EXISTS (
                  SELECT 1 FROM app_private.position_assignments pa
                  WHERE pa.position_id = r.position_id AND pa.user_id = :user AND pa.revoked_at IS NULL
                    AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD')))
            ORDER BY (i.status = 'PENDING') DESC, i.created_at, i.sample_item_id
            LIMIT :limit
        """), {"position": str(position_id) if position_id else None, "status": item_status, "reason": reason,
               "reviewer": reviewer, "user": user_id, "limit": limit,
               "overdue_before": datetime.now(timezone.utc) - timedelta(days=REVIEW_OVERDUE_DAYS)}).mappings().all()
        items = []
        for row in rows:
            item = dict(row)
            item["reasons"] = list(item["reasons"] or [])
            if item.get("evidence_coverage") is not None:
                item["evidence_coverage"] = float(item["evidence_coverage"])
            items.append(item)
        return {"items": items, "can_review": reviewer}
    finally:
        db.close()


@router.get("/items/{sample_item_id}")
async def get_item(sample_item_id: UUID, current_user: dict = Depends(get_current_user)):
    """Data for the side-by-side view: extracted text, findings with evidence, flags."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        row = _item_row(db, sample_item_id)
        _require_read(db, user_id, str(row["position_id"]))
        item = dict(row)
        item["reasons"] = list(item["reasons"] or [])
        item["can_review"] = _is_reviewer(db, user_id)
        assessment = db.execute(text("""
            SELECT assessment_id, matching_status, matching_score, evidence_coverage, confidence, summary, profile_version_id
            FROM app_private.assessment_runs WHERE assessment_id = :id
        """), {"id": str(row["assessment_id"])}).mappings().first()
        item["assessment"] = dict(assessment) if assessment else None
        criterion_rows = db.execute(text("""
            SELECT r.result_id, r.criterion_id, r.outcome, r.score, r.confidence, r.requires_hr_verification,
                   r.reasoning, c.name AS criterion_name, c.category
            FROM app_private.criterion_assessment_results r
            JOIN app_private.criteria_items c ON c.criterion_id = r.criterion_id
            WHERE r.assessment_id = :id ORDER BY c.display_order, c.criterion_id
        """), {"id": str(row["assessment_id"])}).mappings().all()
        criteria = []
        for criterion in criterion_rows:
            entry = dict(criterion)
            entry["evidence"] = [dict(e) for e in db.execute(text("""
                SELECT evidence_id, source_document_id, verbatim_quote, page_number, position_in_text, verification_status
                FROM app_private.evidence_items WHERE criterion_result_id = :id ORDER BY created_at
            """), {"id": str(criterion["result_id"])}).mappings().all()]
            criteria.append(entry)
        item["criterion_results"] = criteria
        document = db.execute(text("""
            SELECT d.document_id, d.original_filename, d.mime_type, d.file_processing_status,
                   pr.extraction_type, pr.processor_version, pr.extracted_text_storage_path
            FROM app_private.application_documents d
            LEFT JOIN LATERAL (
                SELECT extraction_type, processor_version, extracted_text_storage_path
                FROM app_private.document_processing_runs
                WHERE document_id = d.document_id AND status = 'COMPLETED'
                ORDER BY created_at DESC LIMIT 1
            ) pr ON TRUE
            WHERE d.application_id = :id ORDER BY d.created_at DESC LIMIT 1
        """), {"id": str(row["application_id"])}).mappings().first()
        item["document"] = None
        item["extracted_text"] = None
        if document:
            doc = dict(document)
            path = doc.pop("extracted_text_storage_path", None)
            item["document"] = doc
            if path:
                try:
                    from app.workers.processor import worker
                    item["extracted_text"] = worker._load_extracted_text(path)
                except Exception as exc:  # side-by-side view still works with the original file
                    logger.warning("QA extracted text unavailable", error_type=type(exc).__name__)
        item["flags"] = [dict(f) for f in db.execute(text("""
            SELECT f.flag_id, f.criterion_result_id, f.evidence_id, f.flag_type, f.expected_outcome, f.note,
                   f.created_by, f.created_at, p.display_name AS author_name
            FROM app_private.qa_flags f LEFT JOIN app_private.user_profiles p ON p.user_id = f.created_by
            WHERE f.sample_item_id = :id ORDER BY f.created_at
        """), {"id": str(sample_item_id)}).mappings().all()]
        return item
    finally:
        db.close()


@router.post("/items/{sample_item_id}/flags", status_code=status.HTTP_201_CREATED)
async def add_flag(sample_item_id: UUID, request: FlagCreate, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require_reviewer(db, user_id)
        row = db.execute(text("""
            SELECT i.sample_item_id, i.assessment_id, r.position_id
            FROM app_private.qa_sample_items i
            JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
            WHERE i.sample_item_id = :id FOR UPDATE OF i
        """), {"id": str(sample_item_id)}).mappings().first()
        if not row:
            raise NotFoundError("QA sample item")
        criterion_result_id = str(request.criterion_result_id) if request.criterion_result_id else None
        evidence_id = str(request.evidence_id) if request.evidence_id else None
        if criterion_result_id and not db.execute(text("""
            SELECT 1 FROM app_private.criterion_assessment_results WHERE result_id = :r AND assessment_id = :a
        """), {"r": criterion_result_id, "a": str(row["assessment_id"])}).first():
            raise HTTPException(status_code=400, detail="Tiêu chí không thuộc lần đánh giá được kiểm định")
        if evidence_id:
            owner = db.execute(text("""
                SELECT e.criterion_result_id FROM app_private.evidence_items e
                JOIN app_private.criterion_assessment_results r ON r.result_id = e.criterion_result_id
                WHERE e.evidence_id = :e AND r.assessment_id = :a
            """), {"e": evidence_id, "a": str(row["assessment_id"])}).scalar_one_or_none()
            if not owner:
                raise HTTPException(status_code=400, detail="Bằng chứng không thuộc lần đánh giá được kiểm định")
            criterion_result_id = criterion_result_id or str(owner)
        note = request.note.strip() if request.note else None
        flag = db.execute(text("""
            INSERT INTO app_private.qa_flags
                (sample_item_id, criterion_result_id, evidence_id, flag_type, expected_outcome, note, created_by)
            VALUES (:item, :criterion, :evidence, :flag_type, :expected, :note, :user)
            RETURNING flag_id, created_at
        """), {"item": str(sample_item_id), "criterion": criterion_result_id, "evidence": evidence_id,
               "flag_type": request.flag_type, "expected": request.expected_outcome, "note": note or None,
               "user": user_id}).mappings().one()
        db.execute(text("""
            UPDATE app_private.qa_sample_items SET status = 'FLAGGED', reviewer_id = :user, reviewed_at = NOW()
            WHERE sample_item_id = :id
        """), {"id": str(sample_item_id), "user": user_id})
        _audit(db, user_id, "ADD_QA_FLAG", "QA_FLAG", str(flag["flag_id"]), str(row["position_id"]))
        db.commit()
        return dict(flag)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/items/{sample_item_id}/review")
async def review_item(sample_item_id: UUID, request: ReviewDecision, current_user: dict = Depends(get_current_user)):
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        _require_reviewer(db, user_id)
        row = db.execute(text("""
            SELECT i.status, r.position_id,
                   EXISTS (SELECT 1 FROM app_private.qa_flags f WHERE f.sample_item_id = i.sample_item_id) AS has_flags
            FROM app_private.qa_sample_items i
            JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
            WHERE i.sample_item_id = :id FOR UPDATE OF i
        """), {"id": str(sample_item_id)}).mappings().first()
        if not row:
            raise NotFoundError("QA sample item")
        if row["has_flags"]:
            raise HTTPException(status_code=409, detail="Hồ sơ đã có cờ lỗi, không thể đánh dấu Đạt")
        db.execute(text("""
            UPDATE app_private.qa_sample_items SET status = 'PASSED', reviewer_id = :user, reviewed_at = NOW()
            WHERE sample_item_id = :id
        """), {"id": str(sample_item_id), "user": user_id})
        _audit(db, user_id, "PASS_QA_SAMPLE", "QA_SAMPLE_ITEM", str(sample_item_id), str(row["position_id"]))
        db.commit()
        return {"sample_item_id": str(sample_item_id), "status": "PASSED"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/summary")
async def summary(position_id: UUID | None = None, current_user: dict = Depends(get_current_user)):
    """Flag rates with Wilson 95% intervals; warns when fewer than 30 items were reviewed."""
    user_id = current_user["user_id"]
    db = SessionLocal()
    try:
        reviewer = _is_reviewer(db, user_id)
        if position_id:
            _require_read(db, user_id, str(position_id))
        elif not reviewer:
            raise HTTPException(status_code=403, detail="Chọn vị trí để xem kết quả kiểm định")
        params = {"position": str(position_id) if position_id else None,
                  "overdue_before": datetime.now(timezone.utc) - timedelta(days=REVIEW_OVERDUE_DAYS)}
        scope = "(CAST(:position AS UUID) IS NULL OR r.position_id = CAST(:position AS UUID))"
        counts = db.execute(text(f"""
            SELECT COUNT(*) FILTER (WHERE i.status = 'PENDING') AS pending,
                   COUNT(*) FILTER (WHERE i.status = 'PENDING' AND i.created_at < :overdue_before) AS overdue,
                   COUNT(*) FILTER (WHERE i.status IN ('PASSED', 'FLAGGED')) AS reviewed,
                   COUNT(*) FILTER (WHERE i.status = 'FLAGGED') AS flagged
            FROM app_private.qa_sample_items i
            JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
            WHERE {scope}
        """), params).mappings().one()
        by_type = {row["flag_type"]: int(row["items"]) for row in db.execute(text(f"""
            SELECT f.flag_type, COUNT(DISTINCT f.sample_item_id) AS items
            FROM app_private.qa_flags f
            JOIN app_private.qa_sample_items i ON i.sample_item_id = f.sample_item_id
            JOIN app_private.qa_sample_runs r ON r.sample_run_id = i.sample_run_id
            WHERE {scope}
            GROUP BY f.flag_type
        """), params).mappings().all()}
        result = qa_sampling.flag_rate_summary(int(counts["reviewed"]), by_type, int(counts["flagged"]))
        result.update({"pending_items": int(counts["pending"]), "overdue_items": int(counts["overdue"]),
                       "overdue_after_days": REVIEW_OVERDUE_DAYS})
        return result
    finally:
        db.close()
