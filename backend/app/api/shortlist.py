from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID, uuid4
from pydantic import BaseModel
from app.core.security import get_current_user
from app.core.logging import get_logger
from app.core.exceptions import NotFoundError
from app.core.permissions import check_position_access
from app.db.supabase import get_supabase_client

router = APIRouter()
logger = get_logger(__name__)


class CreateShortlistShareRequest(BaseModel):
    position_id: UUID
    shared_with_user_id: UUID
    application_ids: List[UUID]
    note: Optional[str] = None
    allow_cv_view: bool = False


class ShortlistFeedbackRequest(BaseModel):
    application_id: Optional[UUID] = None
    content: str


@router.get("/potential-recipients/{position_id}")
async def get_potential_recipients(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """List users who can receive shortlist shares for a position (HIRING_MANAGER assigned)."""
    await check_position_access(position_id, current_user)
    supabase = get_supabase_client()
    position_id_str = str(position_id)

    # Get HIRING_MANAGER assignments for this position, plus their profiles
    result = supabase.table("position_assignments")\
        .select("user_id, position_role, profile: user_profiles(display_name, preferred_locale)")\
        .eq("position_id", position_id_str)\
        .eq("position_role", "HIRING_MANAGER")\
        .is_("revoked_at", "null")\
        .execute()

    recipients = []
    for row in (result.data or []):
        profile = row.get("profile") or {}
        recipients.append({
            "user_id": row["user_id"],
            "display_name": profile.get("display_name") or "Hiring Manager",
            "role": row["position_role"],
        })

    # Also allow sharing back to HR_RECRUITERS on the position
    hr_result = supabase.table("position_assignments")\
        .select("user_id, position_role, profile: user_profiles(display_name)")\
        .eq("position_id", position_id_str)\
        .eq("position_role", "HR_RECRUITER")\
        .is_("revoked_at", "null")\
        .neq("user_id", current_user["user_id"])\
        .execute()

    for row in (hr_result.data or []):
        profile = row.get("profile") or {}
        recipients.append({
            "user_id": row["user_id"],
            "display_name": profile.get("display_name") or "HR Recruiter",
            "role": row["position_role"],
        })

    return recipients


@router.get("/shortlisted-applications/{position_id}")
async def list_shortlisted_applications(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """List applications currently in SHORTLIST status for a position (to share with HM)."""
    await check_position_access(position_id, current_user, required_roles=["HR_RECRUITER"])
    supabase = get_supabase_client()
    position_id_str = str(position_id)

    result = supabase.table("applications")\
        .select(
            "application_id, application_status, created_at, "
            "identity: application_identities(display_name), "
            "latest_assessment: assessment_runs(matching_status, matching_score, evidence_coverage)"
        )\
        .eq("position_id", position_id_str)\
        .eq("application_status", "SHORTLIST")\
        .order("created_at", desc=True)\
        .execute()

    apps = []
    for a in (result.data or []):
        assessments = a.get("latest_assessment", [])
        latest = None
        if isinstance(assessments, list) and assessments:
            completed = [x for x in assessments if x.get("status") == "COMPLETED"]
            if completed:
                latest = sorted(completed, key=lambda x: x.get("created_at", ""))[-1]
        identity = a.get("identity")
        display_name = None
        if isinstance(identity, list) and identity:
            display_name = identity[0].get("display_name")
        elif isinstance(identity, dict):
            display_name = identity.get("display_name")
        apps.append({
            "application_id": a["application_id"],
            "candidate_name": display_name or "Chưa có tên",
            "application_status": a["application_status"],
            "matching_status": latest.get("matching_status") if latest else None,
            "matching_score": latest.get("matching_score") if latest else None,
            "evidence_coverage": latest.get("evidence_coverage") if latest else None,
        })

    return apps


@router.post("/share", status_code=status.HTTP_201_CREATED)
async def create_shortlist_share(
    request: CreateShortlistShareRequest,
    current_user: dict = Depends(get_current_user)
):
    """Share selected applications as shortlist with a Hiring Manager"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    position_id_str = str(request.position_id)

    # Verify position exists
    pos_result = supabase.table("positions").select("*").eq("position_id", position_id_str).single().execute()
    if not pos_result.data:
        raise NotFoundError("Position")

    # Create share record
    share_result = supabase.table("shortlist_shares").insert({
        "position_id": position_id_str,
        "created_by": user_id,
        "shared_with": str(request.shared_with_user_id),
        "note": request.note,
        "status": "ACTIVE",
        "allow_cv_view": request.allow_cv_view
    }).execute()

    if not share_result.data:
        raise HTTPException(status_code=500, detail="Failed to create shortlist share")

    share_id = share_result.data[0]["share_id"]

    # Get latest ranking run for reference
    rank_result = supabase.table("ranking_runs")\
        .select("ranking_run_id")\
        .eq("position_id", position_id_str)\
        .eq("status", "COMPLETED")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()
    latest_ranking_id = rank_result.data[0]["ranking_run_id"] if rank_result.data else None

    # Create share items
    share_items = []
    for app_id in request.application_ids:
        app_id_str = str(app_id)
        # Get latest assessment for this app
        assess_result = supabase.table("assessment_runs")\
            .select("assessment_id")\
            .eq("application_id", app_id_str)\
            .eq("status", "COMPLETED")\
            .order("created_at", desc=True)\
            .limit(1)\
            .execute()
        assess_id = assess_result.data[0]["assessment_id"] if assess_result.data else None

        # Get ranking item if exists
        rank_item_id = None
        if latest_ranking_id:
            ri_result = supabase.table("ranking_items")\
                .select("ranking_item_id")\
                .eq("ranking_run_id", latest_ranking_id)\
                .eq("application_id", app_id_str)\
                .limit(1)\
                .execute()
            if ri_result.data:
                rank_item_id = ri_result.data[0]["ranking_item_id"]

        share_items.append({
            "share_id": share_id,
            "position_id": position_id_str,
            "application_id": app_id_str,
            "assessment_id": assess_id,
            "ranking_item_id": rank_item_id
        })

    if share_items:
        supabase.table("shortlist_share_items").insert(share_items).execute()

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "SHARE_SHORTLIST",
        "object_type": "SHORTLIST_SHARE",
        "object_id": share_id,
        "position_id": position_id_str,
        "outcome": "SUCCESS",
        "metadata": {
            "shared_with": str(request.shared_with_user_id),
            "applications_count": len(request.application_ids),
            "allow_cv_view": request.allow_cv_view
        }
    }).execute()

    logger.info("Shortlist shared", share_id=share_id, to=request.shared_with_user_id, count=len(request.application_ids))

    return {
        "share_id": share_id,
        "status": "ACTIVE",
        "position_id": position_id_str,
        "shared_with": str(request.shared_with_user_id),
        "applications_count": len(share_items)
    }


@router.get("/shared-with-me")
async def get_shortlists_shared_with_me(
    current_user: dict = Depends(get_current_user)
):
    """Get list of shortlists shared with current user (Hiring Manager view)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    result = supabase.table("shortlist_shares")\
        .select(
            "*, "
            "position: positions(title, position_code), "
            "created_by_profile: user_profiles!shortlist_shares_created_by_fkey(display_name)"
        )\
        .eq("shared_with", user_id)\
        .eq("status", "ACTIVE")\
        .order("created_at", desc=True)\
        .execute()

    shares = result.data or []

    # Enrich with application count
    for share in shares:
        items_result = supabase.table("shortlist_share_items")\
            .select("share_item_id", count="exact")\
            .eq("share_id", share["share_id"])\
            .execute()
        share["application_count"] = items_result.count if hasattr(items_result, 'count') else len(items_result.data or [])

    return shares


@router.get("/{share_id}")
async def get_shortlist_detail(
    share_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get shortlist share details with items (for HR owner or shared Hiring Manager)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    share_id_str = str(share_id)

    # Get share record
    share_result = supabase.table("shortlist_shares")\
        .select("*")\
        .eq("share_id", share_id_str)\
        .single()\
        .execute()

    if not share_result.data:
        raise NotFoundError("Shortlist share")

    share = share_result.data

    # Permission check: must be creator or recipient
    if share["created_by"] != user_id and share["shared_with"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to view this shortlist"
        )

    # Get share items with application details and assessments
    items_result = supabase.table("shortlist_share_items")\
        .select(
            "*, "
            "application: applications(*, identity: application_identities(*)), "
            "assessment: assessment_runs(*, criterion_results: criterion_assessment_results(*))"
        )\
        .eq("share_id", share_id_str)\
        .execute()

    items = items_result.data or []

    # Get existing feedback
    feedback_result = supabase.table("shortlist_feedback")\
        .select("*")\
        .eq("share_id", share_id_str)\
        .order("created_at", desc=True)\
        .execute()

    feedback = feedback_result.data or []

    return {
        **share,
        "items": items,
        "feedback": feedback
    }


@router.post("/{share_id}/feedback", status_code=status.HTTP_201_CREATED)
async def add_shortlist_feedback(
    share_id: UUID,
    request: ShortlistFeedbackRequest,
    current_user: dict = Depends(get_current_user)
):
    """Add feedback to a shortlist (by Hiring Manager or HR)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    share_id_str = str(share_id)

    # Verify share exists and user has access
    share_result = supabase.table("shortlist_shares").select("*").eq("share_id", share_id_str).single().execute()
    if not share_result.data:
        raise NotFoundError("Shortlist share")

    share = share_result.data
    if share["created_by"] != user_id and share["shared_with"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have permission to give feedback on this shortlist"
        )

    # Insert feedback
    fb_result = supabase.table("shortlist_feedback").insert({
        "share_id": share_id_str,
        "application_id": str(request.application_id) if request.application_id else None,
        "feedback_from": user_id,
        "content": request.content
    }).execute()

    logger.info("Shortlist feedback added", share_id=share_id_str, from_user=user_id)

    return fb_result.data[0]


@router.post("/{share_id}/revoke", status_code=status.HTTP_200_OK)
async def revoke_shortlist(
    share_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Revoke an active shortlist share (by creator only)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    share_id_str = str(share_id)

    share_result = supabase.table("shortlist_shares").select("*").eq("share_id", share_id_str).single().execute()
    if not share_result.data:
        raise NotFoundError("Shortlist share")

    if share_result.data["created_by"] != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the creator can revoke a shortlist share"
        )

    supabase.table("shortlist_shares").update({
        "status": "REVOKED",
        "revoked_at": "now()"
    }).eq("share_id", share_id_str).execute()

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "REVOKE_SHORTLIST",
        "object_type": "SHORTLIST_SHARE",
        "object_id": share_id_str,
        "outcome": "SUCCESS"
    }).execute()

    return {"status": "REVOKED", "share_id": share_id_str}
