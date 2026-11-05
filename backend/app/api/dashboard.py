from typing import Any, Mapping
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

APPLICATION_STATUSES = (
    "NEW", "IN_REVIEW", "SHORTLIST", "REJECTED_SCREENING",
    "INTERVIEW", "REJECTED_INTERVIEW", "OFFERED", "ACCEPTED",
)
MATCHING_STATUSES = ("NOT_ASSESSED", "NEEDS_HR_VERIFICATION", "POSSIBLE_MISMATCH", "MEETS_MANDATORY")

# Service-role/PostgREST requests bypass RLS. Explicitly scope both position and
# application aggregates here: HR sees assigned positions, while an HM only
# sees applications actually shared with them. Revoked roles/shares never count.
_SCOPE_CTE = """
    WITH privileges AS (
        SELECT EXISTS (
            SELECT 1 FROM app_private.user_role_assignments
            WHERE user_id = :user_id AND revoked_at IS NULL
              AND role_code IN ('ADMIN', 'HR_LEAD')
        ) AS global_access
    ), visible_positions AS (
        SELECT p.position_id, p.status
        FROM app_private.positions p, privileges priv
        WHERE (CAST(:position_id AS uuid) IS NULL OR p.position_id = CAST(:position_id AS uuid))
          AND (priv.global_access OR EXISTS (
              SELECT 1 FROM app_private.position_assignments pa
              WHERE pa.position_id = p.position_id AND pa.user_id = :user_id AND pa.revoked_at IS NULL
          ))
    )
"""

_APPLICATIONS_QUERY = _SCOPE_CTE + """
    SELECT a.application_id, a.application_status,
        EXISTS (SELECT 1 FROM app_private.application_documents d
                WHERE d.application_id = a.application_id
                  AND d.file_processing_status IN ('RECEIVED', 'PROCESSING')) AS processing,
        EXISTS (SELECT 1 FROM app_private.application_documents d
                WHERE d.application_id = a.application_id
                  AND (d.file_processing_status IN ('NEEDS_HR_REVIEW', 'ERROR_UNSUPPORTED')
                       OR d.processing_error IS NOT NULL)) AS needs_review,
        EXISTS (SELECT 1 FROM app_private.duplicate_signals ds
                WHERE ds.position_id = a.position_id AND ds.review_status = 'PENDING'
                  AND (ds.application_id_1 = a.application_id OR ds.application_id_2 = a.application_id)) AS duplicate,
        latest.matching_status, latest.evidence_coverage
    FROM app_private.applications a
    JOIN visible_positions p ON p.position_id = a.position_id
    CROSS JOIN privileges priv
    LEFT JOIN LATERAL (
        SELECT ar.matching_status, ar.evidence_coverage
        FROM app_private.assessment_runs ar
        WHERE ar.application_id = a.application_id AND ar.status = 'COMPLETED'
                  AND ar.profile_version_id = (SELECT profile_version_id FROM app_private.profile_versions
                      WHERE application_id = a.application_id AND status = 'COMPLETED' ORDER BY version_number DESC LIMIT 1)
                  AND ar.criteria_version_id = (SELECT c.criteria_version_id FROM app_private.criteria_versions c
                      WHERE c.position_id = a.position_id AND c.status = 'APPROVED'
                        AND c.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                            WHERE position_id = a.position_id ORDER BY version_number DESC LIMIT 1)
                      ORDER BY c.version_number DESC LIMIT 1)
        ORDER BY ar.created_at DESC, ar.assessment_id DESC LIMIT 1
    ) latest ON TRUE
    WHERE priv.global_access OR EXISTS (
        SELECT 1 FROM app_private.position_assignments pa
        WHERE pa.position_id = a.position_id AND pa.user_id = :user_id
          AND pa.position_role IN ('HR_RECRUITER', 'HR_LEAD') AND pa.revoked_at IS NULL
    ) OR EXISTS (
        SELECT 1 FROM app_private.shortlist_shares s
        JOIN app_private.shortlist_share_items si ON si.share_id = s.share_id
        WHERE s.position_id = a.position_id AND s.shared_with = :user_id
          AND s.status = 'ACTIVE' AND si.application_id = a.application_id
          AND EXISTS (SELECT 1 FROM app_private.position_assignments hm
                      WHERE hm.position_id = s.position_id AND hm.user_id = :user_id
                        AND hm.position_role = 'HIRING_MANAGER' AND hm.revoked_at IS NULL)
    )
"""


def build_dashboard(positions: list[Mapping[str, Any]], applications: list[Mapping[str, Any]]) -> dict:
    """Aggregate one row per visible application, with its latest completed assessment."""
    statuses = {key: 0 for key in APPLICATION_STATUSES}
    matching = {key: 0 for key in MATCHING_STATUSES}
    coverages: list[float] = []
    assessed = processing = needs_review = duplicates = 0

    for app in applications:
        status = app.get("application_status")
        if status in statuses:
            statuses[status] += 1
        processing += bool(app.get("processing"))
        needs_review += bool(app.get("needs_review"))
        duplicates += bool(app.get("duplicate"))
        match = app.get("matching_status")
        if match:
            assessed += 1
        matching[match if match in matching else "NOT_ASSESSED"] += 1
        if app.get("evidence_coverage") is not None:
            coverages.append(float(app["evidence_coverage"]))

    total = len(applications)
    return {
        "open_positions": sum(p.get("status") == "OPEN" for p in positions),
        "total_applications": total,
        "applications_by_status": statuses,
        "applications_processing": processing,
        "files_needing_hr_review": needs_review,
        "files_needing_review": needs_review,  # backward-compatible position endpoint
        "files_needing_review_rate": needs_review / total if total else None,
        "duplicate_alerts": duplicates,  # applications with at least one pending signal
        "assessments_completed": assessed,
        "matching_status_counts": matching,
        "average_coverage": sum(coverages) / len(coverages) if coverages else None,
        "coverage_sample_size": len(coverages),
        "coverage_under_threshold": sum(value < 0.7 for value in coverages),
        # No reliable baseline/override events are stored yet. Do not invent a zero.
        "hr_override_rate": None,
        "average_processing_time_seconds": None,
    }


def _load_dashboard(user_id: str, position_id: UUID | None = None) -> dict:
    params = {"user_id": user_id, "position_id": str(position_id) if position_id else None}
    db = SessionLocal()
    try:
        positions = db.execute(text(_SCOPE_CTE + " SELECT * FROM visible_positions"), params).mappings().all()
        if position_id and not positions:
            raise HTTPException(status_code=403, detail="Bạn không có quyền xem thống kê vị trí này")
        applications = db.execute(text(_APPLICATIONS_QUERY), params).mappings().all()
        result = build_dashboard(positions, applications)
        if position_id:
            result["position_id"] = str(position_id)
        return result
    finally:
        db.close()


@router.get("/summary")
async def get_dashboard_summary(current_user: dict = Depends(get_current_user)):
    """Dashboard for the current user's active position assignments and shares."""
    return _load_dashboard(current_user["user_id"])


@router.get("/position/{position_id}")
async def get_position_dashboard(position_id: UUID, current_user: dict = Depends(get_current_user)):
    """Statistics for one visible position, using the same application-level scope."""
    return _load_dashboard(current_user["user_id"], position_id)
