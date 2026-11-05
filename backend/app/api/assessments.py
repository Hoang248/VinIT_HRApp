from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID, uuid4
from app.core.security import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import NotFoundError, CriteriaNotApprovedError
from app.schemas.applications import (
    AssessmentRun,
    CriterionResult,
    RankingItem,
    MatchingStatus
)
from app.schemas.common import OperationResponse
from app.db.supabase import get_supabase_client
from app.services.matching import matching_engine

router = APIRouter()
logger = get_logger(__name__)


@router.post("/run/{position_id}", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
async def run_assessment_for_position(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Trigger AI assessment for all unassessed applications in a position (requires approved criteria)"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    position_id_str = str(position_id)

    # Verify position exists
    pos_result = supabase.table("positions").select("*").eq("position_id", position_id_str).single().execute()
    if not pos_result.data:
        raise NotFoundError("Position")

    # Get latest approved criteria
    criteria_result = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("position_id", position_id_str)\
        .eq("status", "APPROVED")\
        .order("version_number", desc=True)\
        .limit(1)\
        .execute()

    if not criteria_result.data:
        raise CriteriaNotApprovedError()

    approved_cv = criteria_result.data[0]
    criteria_version_id = approved_cv["criteria_version_id"]
    criteria_items = approved_cv.get("criteria", [])

    # Get applications in this position that have completed document processing
    # and either not assessed or assessed on older criteria version
    apps_result = supabase.table("applications")\
        .select("*, documents: application_documents(*)")\
        .eq("position_id", position_id_str)\
        .in_("application_status", ["NEW", "IN_REVIEW", "SHORTLIST"])\
        .execute()

    applications = apps_result.data or []

    if not applications:
        return OperationResponse(
            operation_id=uuid4(),
            status="completed",
            message="Không có hồ sơ nào cần đánh giá"
        )

    # Create operation record
    op_result = supabase.table("operations").insert({
        "capability": "ASSESSMENT",
        "status": "PROCESSING",
        "requested_by": user_id,
    }).execute()
    operation_id = op_result.data[0]["operation_id"]

    # TODO: Queue actual assessment processing to worker
    # For each application:
    # 1. Get extracted CV text
    # 2. Get candidate profile
    # 3. Call LLM matching for each criterion
    # 4. Verify verbatim quotes
    # 5. Calculate scores with matching_engine
    # 6. Save assessment run and criterion results
    # 7. After all assessments complete, generate ranking run

    logger.info(
        "Assessment operation created",
        operation_id=operation_id,
        position_id=position_id_str,
        applications_to_assess=len(applications),
        criteria_version_id=criteria_version_id
    )

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "RUN_ASSESSMENT",
        "object_type": "POSITION",
        "object_id": position_id_str,
        "outcome": "QUEUED",
        "metadata": {"applications_count": len(applications), "criteria_version": criteria_version_id}
    }).execute()

    return OperationResponse(
        operation_id=UUID(operation_id),
        status="processing",
        message=f"Đang đánh giá {len(applications)} hồ sơ theo bộ tiêu chí đã duyệt..."
    )


@router.get("/{assessment_id}", response_model=AssessmentRun)
async def get_assessment(
    assessment_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get a specific assessment run with all criterion results and evidence"""
    supabase = get_supabase_client()
    assess_id_str = str(assessment_id)

    result = supabase.table("assessment_runs")\
        .select("*, criterion_results: criterion_assessment_results(*, evidence: evidence_items(*))")\
        .eq("assessment_id", assess_id_str)\
        .single()\
        .execute()

    if not result.data:
        raise NotFoundError("Assessment run")

    return result.data


@router.post("/ranking/generate/{position_id}", response_model=OperationResponse, status_code=status.HTTP_202_ACCEPTED)
async def generate_ranking(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Generate new ranking snapshot for a position based on latest completed assessments"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]
    position_id_str = str(position_id)

    # Get position and approved criteria
    pos_result = supabase.table("positions").select("*").eq("position_id", position_id_str).single().execute()
    if not pos_result.data:
        raise NotFoundError("Position")

    criteria_result = supabase.table("criteria_versions")\
        .select("*, criteria: criteria_items(*)")\
        .eq("position_id", position_id_str)\
        .eq("status", "APPROVED")\
        .order("version_number", desc=True)\
        .limit(1)\
        .execute()

    if not criteria_result.data:
        raise CriteriaNotApprovedError()

    approved_cv = criteria_result.data[0]
    criteria_items = approved_cv.get("criteria", [])
    criteria_version_id = approved_cv["criteria_version_id"]

    # Get applications with latest completed assessment
    apps_result = supabase.table("applications")\
        .select(
            "application_id, "
            "identity: application_identities(display_name), "
            "latest_assessment: assessment_runs(*)"
        )\
        .eq("position_id", position_id_str)\
        .in_("application_status", ["NEW", "IN_REVIEW", "SHORTLIST"])\
        .execute()

    applications = apps_result.data or []

    # Build list with latest assessment
    apps_with_assessments = []
    for app in applications:
        assessments = app.get("latest_assessment", [])
        if isinstance(assessments, list):
            completed = [a for a in assessments if a.get("status") == "COMPLETED" and a.get("criteria_version_id") == criteria_version_id]
            if completed:
                latest = sorted(completed, key=lambda x: x.get("created_at", ""))[-1]
                app["latest_assessment"] = latest
                display_name = None
                identity = app.get("identity")
                if isinstance(identity, list) and identity:
                    display_name = identity[0].get("display_name")
                elif isinstance(identity, dict):
                    display_name = identity.get("display_name")
                app["display_name"] = display_name
                apps_with_assessments.append(app)

    if not apps_with_assessments:
        return OperationResponse(
            operation_id=uuid4(),
            status="completed",
            message="Không có hồ sơ đã đánh giá để xếp hạng"
        )

    # Run deterministic ranking
    ranked = matching_engine.rank_applications(apps_with_assessments, criteria_items)

    # Create ranking run
    rank_op_result = supabase.table("operations").insert({
        "capability": "RANKING",
        "status": "COMPLETED",
        "requested_by": user_id,
    }).execute()

    rank_run_result = supabase.table("ranking_runs").insert({
        "position_id": position_id_str,
        "criteria_version_id": criteria_version_id,
        "policy_version": "v1.0",
        "operation_id": rank_op_result.data[0]["operation_id"],
        "status": "COMPLETED"
    }).execute()

    ranking_run_id = rank_run_result.data[0]["ranking_run_id"]

    # Insert ranking items
    ranking_items = []
    for item in ranked:
        assess = item.get("latest_assessment", {})
        ranking_items.append({
            "ranking_run_id": ranking_run_id,
            "position_id": position_id_str,
            "application_id": item["application_id"],
            "assessment_id": assess.get("assessment_id"),
            "rank_number": item["rank_number"],
            "ranking_status": assess.get("matching_status"),
            "matching_score": assess.get("matching_score"),
            "evidence_coverage": assess.get("evidence_coverage"),
            "confidence": assess.get("confidence")
        })

    if ranking_items:
        supabase.table("ranking_items").insert(ranking_items).execute()

    # Detect duplicates
    duplicates = matching_engine.detect_duplicates(applications)
    if duplicates:
        dup_records = []
        for app1_id, app2_id, confidence, signal_type in duplicates:
            dup_records.append({
                "position_id": position_id_str,
                "application_id_1": app1_id,
                "application_id_2": app2_id,
                "signal_type": signal_type,
                "confidence": confidence,
                "detector_version": "v1.0"
            })
        if dup_records:
            supabase.table("duplicate_signals").insert(dup_records).execute()

    # Log audit
    supabase.table("audit_events").insert({
        "actor_user_id": user_id,
        "action_type": "GENERATE_RANKING",
        "object_type": "RANKING_RUN",
        "object_id": ranking_run_id,
        "position_id": position_id_str,
        "outcome": "SUCCESS",
        "metadata": {"ranked_applications": len(ranked), "duplicates_found": len(duplicates)}
    }).execute()

    # Mark operation completed
    supabase.table("operations").update({
        "status": "COMPLETED",
        "completed_at": "now()"
    }).eq("operation_id", rank_op_result.data[0]["operation_id"]).execute()

    logger.info(
        "Ranking generated",
        ranking_run_id=ranking_run_id,
        position_id=position_id_str,
        ranked_count=len(ranked)
    )

    return OperationResponse(
        operation_id=UUID(ranking_run_id),
        status="completed",
        message=f"Đã xếp hạng xong {len(ranked)} hồ sơ"
    )


@router.get("/ranking/latest/{position_id}", response_model=List[RankingItem])
async def get_latest_ranking(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get latest ranking for a position, sorted by rank order"""
    supabase = get_supabase_client()
    position_id_str = str(position_id)

    # Get latest completed ranking run
    run_result = supabase.table("ranking_runs")\
        .select("*")\
        .eq("position_id", position_id_str)\
        .eq("status", "COMPLETED")\
        .order("created_at", desc=True)\
        .limit(1)\
        .execute()

    if not run_result.data:
        return []

    latest_run = run_result.data[0]

    # Get ranking items with application identity
    items_result = supabase.table("ranking_items")\
        .select(
            "*, "
            "application: applications(*, identity: application_identities(*))"
        )\
        .eq("ranking_run_id", latest_run["ranking_run_id"])\
        .order("rank_number", desc=False, nullsfirst=False)\
        .execute()

    items = items_result.data or []
    result_items = []

    for item in items:
        app = item.get("application", {})
        identity = app.get("identity", [])
        candidate_name = None
        if isinstance(identity, list) and identity:
            candidate_name = identity[0].get("display_name")
        elif isinstance(identity, dict):
            candidate_name = identity.get("display_name")

        result_items.append(RankingItem(
            rank_number=item.get("rank_number"),
            application_id=UUID(item["application_id"]),
            candidate_name=candidate_name or "Không có tên",
            matching_status=MatchingStatus(item["ranking_status"]) if item.get("ranking_status") else MatchingStatus.NOT_ASSESSED,
            matching_score=item.get("matching_score"),
            evidence_coverage=item.get("evidence_coverage"),
            needs_verification=item.get("ranking_status") == "NEEDS_HR_VERIFICATION" or (item.get("evidence_coverage") or 0) < settings.MIN_EVIDENCE_COVERAGE,
            has_mismatch=item.get("ranking_status") == "POSSIBLE_MISMATCH"
        ))

    return result_items
