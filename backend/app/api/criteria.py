from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.logging import get_logger
from app.core.exceptions import CriteriaNotApprovedError, NotFoundError
from app.schemas.criteria import (
    CriteriaVersion,
    CriteriaVersionCreate,
    Criterion,
    ApprovalAction,
    CriteriaApprovalRequest
)
from app.schemas.common import OperationResponse
from app.db.supabase import get_supabase_client
from app.services.llm_client import llm_client, LLMError

router = APIRouter()
logger = get_logger(__name__)


@router.get("/position/{position_id}/versions", response_model=List[CriteriaVersion])
async def list_criteria_versions(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """List all criteria versions for a position"""
    supabase = get_supabase_client()

    result = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("position_id", str(position_id))\
        .order("version_number", desc=True)\
        .execute()

    return result.data or []


@router.get("/{criteria_version_id}", response_model=CriteriaVersion)
async def get_criteria_version(
    criteria_version_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific criteria version with all items"""
    supabase = get_supabase_client()

    result = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("criteria_version_id", str(criteria_version_id))\
        .single()\
        .execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Criteria version not found")

    return result.data


@router.post("/generate/{position_id}", response_model=CriteriaVersion, status_code=status.HTTP_202_ACCEPTED)
async def generate_criteria_from_jd(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Trigger AI to generate draft criteria from the latest JD of the position"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    position_id_str = str(position_id)

    # Verify position exists
    pos_result = supabase.table("positions").select("*").eq("position_id", position_id_str).single().execute()
    if not pos_result.data:
        raise NotFoundError("Position")

    position = pos_result.data

    # TODO: Check if user has HR_RECRUITER or HIRING_MANAGER assignment on this position

    # Get latest JD version
    jd_result = supabase.table("jd_versions")\
        .select("*")\
        .eq("position_id", position_id_str)\
        .order("version_number", desc=True)\
        .limit(1)\
        .execute()

    if not jd_result.data:
        raise HTTPException(status_code=400, detail="No JD found for this position. Please create position with JD content first.")
    latest_jd = jd_result.data[0]
    jd_content = latest_jd["content_text"]

    # Get next version number
    existing_versions = supabase.table("criteria_versions")\
        .select("version_number")\
        .eq("position_id", position_id_str)\
        .order("version_number", desc=True)\
        .limit(1)\
        .execute()
    next_version = (existing_versions.data[0]["version_number"] + 1) if existing_versions.data else 1

    # Call LLM to generate criteria draft using JD from database
    try:
        ai_criteria = await llm_client.extract_criteria_from_jd(
            jd_text=jd_content,
            requisition_id=position["position_code"],
            job_title=position["title"]
        )
    except LLMError as e:
        logger.error("Failed to generate criteria via LLM", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"AI criteria generation failed: {str(e)}"
        )

    # Create criteria version record
    cv_result = supabase.table("criteria_versions").insert({
        "position_id": position_id_str,
        "jd_version_id": latest_jd["jd_version_id"],
        "version_number": next_version,
        "origin": "AI_DRAFT",
        "status": "DRAFT",
        "mandatory_weight_total": 70.0,
        "nice_to_have_weight_total": 30.0,
    }).execute()

    if not cv_result.data:
        raise HTTPException(status_code=500, detail="Failed to create criteria version")

    cv = cv_result.data[0]
    cv_id = cv["criteria_version_id"]

    # Insert individual criteria items
    criteria_items = []
    for idx, crit in enumerate(ai_criteria.get("criteria", [])):
        criteria_items.append({
            "criteria_version_id": cv_id,
            "name": crit["name"],
            "description": crit["description"],
            "category": crit["category"],
            "weight_in_group": crit["weight"],
            "expected_evidence_keywords": crit.get("expected_evidence_keywords", []),
            "display_order": idx
        })

    if criteria_items:
        supabase.table("criteria_items").insert(criteria_items).execute()

    # Load created criteria with items
    created = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("criteria_version_id", cv_id)\
        .single()\
        .execute()

    # Log audit event
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "GENERATE_CRITERIA_DRAFT",
        "object_type": "CRITERIA_VERSION",
        "object_id": cv_id,
        "position_id": position_id_str,
        "outcome": "SUCCESS"
    }).execute()

    logger.info("AI draft criteria generated", criteria_version_id=cv_id, position_id=position_id_str)
    # Audit log
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "GENERATE_CRITERIA_DRAFT",
        "object_type": "CRITERIA_VERSION",
        "object_id": cv_id,
        "position_id": position_id_str,
        "outcome": "SUCCESS"
    }).execute()

    logger.info("AI draft criteria generated", criteria_version_id=cv_id, position_id=position_id_str)
    return created.data


@router.post("/{criteria_version_id}/approve", response_model=CriteriaVersion)
async def approve_criteria(
    criteria_version_id: UUID,
    request: CriteriaApprovalRequest,
    current_user: dict = Depends(get_current_user)
):
    """Approve or reject criteria version (HR review / Hiring Manager approval)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    cv_id_str = str(criteria_version_id)

    # Get criteria version
    cv_result = supabase.table("criteria_versions")\
        .select("*, position: positions(*)")\
        .eq("criteria_version_id", cv_id_str)\
        .single()\
        .execute()

    if not cv_result.data:
        raise NotFoundError("Criteria version")

    cv = cv_result.data
    position_id = cv["position_id"]

    # TODO: Check user role on this position (HR_RECRUITER or HIRING_MANAGER)
    # For MVP: determine role based on action flow. If status is DRAFT/PENDING_HR_REVIEW → HR action
    # If status is PENDING_HM_APPROVAL → HM action

    current_status = cv["status"]
    action = request.action
    new_status = current_status

    # Determine reviewer role
    reviewer_role = "HR_RECRUITER"  # Default; in production check against position_assignments

    if action == ApprovalAction.APPROVE:
        if current_status in ["DRAFT", "PENDING_HR_REVIEW"]:
            # HR approves → move to HM approval
            new_status = "PENDING_HM_APPROVAL"
            update_data = {
                "status": new_status,
                "approved_by_hr": user_id,
                "approved_by_hr_at": "now()"
            }
        elif current_status == "PENDING_HM_APPROVAL":
            # HM approves → move to APPROVED
            new_status = "APPROVED"
            reviewer_role = "HIRING_MANAGER"
            update_data = {
                "status": new_status,
                "approved_by_hm": user_id,
                "approved_by_hm_at": "now()"
            }
        elif current_status == "APPROVED":
            raise HTTPException(status_code=400, detail="Criteria already approved")
        else:
            raise HTTPException(status_code=400, detail=f"Cannot approve criteria in status {current_status}")

    elif action == ApprovalAction.REQUEST_CHANGES:
        new_status = "DRAFT"
        update_data = {"status": new_status}

    elif action == ApprovalAction.REJECT:
        new_status = "REJECTED"
        update_data = {"status": new_status}

    # Update criteria version status
    supabase.table("criteria_versions").update(update_data).eq("criteria_version_id", cv_id_str).execute()

    # Record approval event
    supabase.table("criteria_approval_events").insert({
        "criteria_version_id": cv_id_str,
        "reviewed_by": user_id,
        "reviewer_role": reviewer_role,
        "decision": action.value,
        "comment": request.comment
    }).execute()

    # If fully approved, log audit
    if new_status == "APPROVED":
        supabase.table("audit_events").insert({
            "actor_user_id": user_id,
            "action_type": "CRITERIA_APPROVED",
            "object_type": "CRITERIA_VERSION",
            "object_id": cv_id_str,
            "position_id": position_id,
            "outcome": "APPROVED"
        }).execute()
        logger.info("Criteria version fully approved", criteria_version_id=cv_id_str, position_id=position_id)

    # Return updated version
    updated = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("criteria_version_id", cv_id_str)\
        .single()\
        .execute()

    return updated.data


@router.get("/position/{position_id}/approved", response_model=Optional[CriteriaVersion])
async def get_latest_approved_criteria(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get the latest approved criteria for a position"""
    supabase = get_supabase_client()

    result = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("position_id", str(position_id))\
        .eq("status", "APPROVED")\
        .order("version_number", desc=True)\
        .limit(1)\
        .execute()

    return result.data[0] if result.data else None
