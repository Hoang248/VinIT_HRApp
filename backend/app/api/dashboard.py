from fastapi import APIRouter, Depends, Query
from typing import Optional, List, Dict, Any
from uuid import UUID
from app.core.security import get_current_user
from app.db.supabase import get_supabase_client
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("/summary")
async def get_dashboard_summary(
    current_user: dict = Depends(get_current_user)
):
    """Get aggregated dashboard summary for HR Lead/Admin (across all visible positions)"""
    supabase = get_supabase_client()

    # Total open positions
    pos_result = supabase.table("positions").select("position_id", count="exact").eq("status", "OPEN").execute()
    open_positions = pos_result.count if hasattr(pos_result, 'count') else len(pos_result.data or [])

    # Applications by status
    all_apps = supabase.table("applications").select("application_status").execute()
    apps_data = all_apps.data or []

    status_counts = {
        "NEW": 0,
        "IN_REVIEW": 0,
        "SHORTLIST": 0,
        "REJECTED_SCREENING": 0,
        "INTERVIEW": 0,
        "REJECTED_INTERVIEW": 0,
        "OFFERED": 0,
        "ACCEPTED": 0
    }

    for app in apps_data:
        status = app.get("application_status", "NEW")
        if status in status_counts:
            status_counts[status] += 1

    total_applications = len(apps_data)

    # Files needing review
    review_docs = supabase.table("application_documents")\
        .select("document_id", count="exact")\
        .eq("file_processing_status", "NEEDS_HR_REVIEW")\
        .execute()
    needs_review_count = review_docs.count if hasattr(review_docs, 'count') else len(review_docs.data or [])

    # Assessments with HR override (placeholder for future - compare HR status vs AI recommendation)
    # For MVP return 0, will be populated when override tracking is implemented
    override_rate = 0.0

    return {
        "open_positions": open_positions,
        "total_applications": total_applications,
        "applications_by_status": status_counts,
        "files_needing_hr_review": needs_review_count,
        "hr_override_rate": override_rate,
        "average_processing_time_seconds": None  # Will calculate from operation timing in future
    }


@router.get("/position/{position_id}")
async def get_position_dashboard(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get dashboard statistics for a specific position"""
    supabase = get_supabase_client()
    position_id_str = str(position_id)

    # Application status breakdown for this position
    apps_result = supabase.table("applications").select("application_status").eq("position_id", position_id_str).execute()
    apps_data = apps_result.data or []

    status_counts = {
        "NEW": 0,
        "IN_REVIEW": 0,
        "SHORTLIST": 0,
        "REJECTED_SCREENING": 0,
        "INTERVIEW": 0,
        "REJECTED_INTERVIEW": 0,
        "OFFERED": 0,
        "ACCEPTED": 0
    }

    for app in apps_data:
        status = app.get("application_status", "NEW")
        if status in status_counts:
            status_counts[status] += 1

    # Document processing status
    docs_result = supabase.table("application_documents")\
        .select("file_processing_status")\
        .eq("application_id", f"in.({','.join([repr(a) for a in [a['application_id'] for a in apps_data]])})")\
        .execute()
    # This is simplified; actual implementation needs join or proper filtering.
    # For Phase 1 MVP we'll return document stats from applications directly

    # Matching status breakdown from latest assessments
    assess_result = supabase.table("assessment_runs")\
        .select("matching_status")\
        .eq("position_id", position_id_str)\
        .eq("status", "COMPLETED")\
        .execute()

    matching_counts = {
        "NOT_ASSESSED": 0,
        "NEEDS_HR_VERIFICATION": 0,
        "POSSIBLE_MISMATCH": 0,
        "MEETS_MANDATORY": 0
    }

    seen_apps = set()
    for assess in assess_result.data or []:
        app_id = assess.get("application_id")
        if app_id in seen_apps:
            continue
        seen_apps.add(app_id)
        status = assess.get("matching_status", "NOT_ASSESSED")
        if status in matching_counts:
            matching_counts[status] += 1

    total_assessed = len(seen_apps)
    coverage_under_threshold = matching_counts["NEEDS_HR_VERIFICATION"]

    return {
        "position_id": position_id_str,
        "total_applications": len(apps_data),
        "applications_by_status": status_counts,
        "assessments_completed": total_assessed,
        "matching_status_counts": matching_counts,
        "files_needing_review": 0,  # TODO: Calculate from joined documents
        "average_coverage": None,  # TODO: Calculate average evidence coverage
        "duplicate_alerts": 0  # TODO: Count duplicate signals
    }
