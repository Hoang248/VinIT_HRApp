from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.permissions import check_position_access
from app.schemas.positions import Position, PositionCreate, PositionUpdate, PositionWithStats, PositionStatus
from app.schemas.common import ErrorResponse
from app.db.supabase import get_supabase_client
from app.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.get("", response_model=List[PositionWithStats])
async def list_positions(
    status_filter: Optional[PositionStatus] = Query(None, alias="status"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    """List positions visible to current user based on their assignments"""
    # TODO: Filter positions by user's role assignments (RBAC)
    supabase = get_supabase_client()

    query = supabase.table("positions").select("*")
    if status_filter:
        query = query.eq("status", status_filter.value)

    offset = (page - 1) * page_size
    result = query.range(offset, offset + page_size - 1).order("created_at", desc=True).execute()

    # TODO: Enrich with application counts and criteria status
    return result.data or []


@router.post("", response_model=Position, status_code=status.HTTP_201_CREATED)
async def create_position(
    position_data: PositionCreate,
    current_user: dict = Depends(get_current_user)
):
    """Create new hiring position with initial JD content"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    # Insert position (exclude jd_content and hiring_manager_user_id which are not columns)
    position_dict = position_data.model_dump(exclude={"jd_content", "hiring_manager_user_id"})
    position_dict["created_by"] = user_id
    position_dict["status"] = PositionStatus.OPEN.value

    pos_result = supabase.table("positions").insert(position_dict).execute()
    if not pos_result.data:
        raise HTTPException(status_code=500, detail="Failed to create position")

    new_position = pos_result.data[0]
    position_id = new_position["position_id"]

    # Insert initial JD version
    supabase.table("jd_versions").insert({
        "position_id": position_id,
        "version_number": 1,
        "content_text": position_data.jd_content,
        "language_code": "en",
        "created_by": user_id
    }).execute()

    # Auto-assign creator as HR_RECRUITER on the position
    supabase.table("position_assignments").insert({
        "position_id": position_id,
        "user_id": user_id,
        "position_role": "HR_RECRUITER",
        "assigned_by": user_id
    }).execute()

    # If hiring_manager_user_id was provided, assign them as HIRING_MANAGER
    if position_data.hiring_manager_user_id:
        hm_id = str(position_data.hiring_manager_user_id)
        # Verify the user exists (has a profile)
        profile_check = supabase.table("user_profiles").select("user_id").eq("user_id", hm_id).execute()
        if profile_check.data:
            supabase.table("position_assignments").insert({
                "position_id": position_id,
                "user_id": hm_id,
                "position_role": "HIRING_MANAGER",
                "assigned_by": user_id
            }).execute()
            # Ensure user has HIRING_MANAGER system role if not already
            supabase.table("user_role_assignments").upsert({
                "user_id": hm_id,
                "role_code": "HIRING_MANAGER",
                "granted_by": user_id,
                "granted_at": "now()",
            }, on_conflict="user_id,role_code").execute()
        else:
            logger.warning("Hiring manager user_id not found in profiles", user_id=hm_id)

    logger.info(
        "Position created",
        position_id=position_id,
        created_by=user_id,
        hiring_manager=str(position_data.hiring_manager_user_id) if position_data.hiring_manager_user_id else None
    )
    return new_position


@router.get("/{position_id}", response_model=PositionWithStats)
async def get_position(
    position_id: UUID,
    current_user: dict = Depends(get_current_user)
):
    """Get position details by ID"""
    # RBAC check
    await check_position_access(position_id, current_user)

    supabase = get_supabase_client()
    result = supabase.table("positions").select("*").eq("position_id", str(position_id)).single().execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Position not found")

    return result.data


@router.patch("/{position_id}", response_model=Position)
async def update_position(
    position_id: UUID,
    update: PositionUpdate,
    current_user: dict = Depends(get_current_user)
):
    """Update position information or status"""
    supabase = get_supabase_client()
    user_id = current_user["user_id"]

    update_dict = update.model_dump(exclude_unset=True)
    if "status" in update_dict:
        update_dict["status"] = update_dict["status"].value

    result = supabase.table("positions").update(update_dict).eq("position_id", str(position_id)).execute()

    if not result.data:
        raise HTTPException(status_code=404, detail="Position not found")

    # Log status change event if status was updated
    if "status" in update_dict:
        supabase.table("position_status_events").insert({
            "position_id": str(position_id),
            "new_status": update_dict["status"],
            "changed_by": user_id
        }).execute()

    logger.info("Position updated", position_id=position_id, updated_by=user_id)
    return result.data[0]
