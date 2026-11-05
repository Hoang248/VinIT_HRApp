from fastapi import APIRouter, Depends, Query
from typing import List, Optional
from uuid import UUID
from app.core.security import get_current_user
from app.core.logging import get_logger
from app.db.supabase import get_supabase_client

router = APIRouter()
logger = get_logger(__name__)


@router.get("")
async def list_users(
    search: Optional[str] = Query(None, description="Search by display_name"),
    position_id: Optional[UUID] = Query(None, description="List users assigned to a position"),
    current_user: dict = Depends(get_current_user)
):
    """List users (display_name, roles, assignments) for autocomplete in dialogs."""
    supabase = get_supabase_client()

    if position_id:
        # Get users assigned to the position
        assign_result = supabase.table("position_assignments")\
            .select("user_id, position_role, profile: user_profiles(user_id, display_name)")\
            .eq("position_id", str(position_id))\
            .is_("revoked_at", "null")\
            .execute()
        users_dict = {}
        for row in (assign_result.data or []):
            profile = row.get("profile") or {}
            uid = row["user_id"]
            if uid not in users_dict:
                users_dict[uid] = {
                    "user_id": uid,
                    "display_name": profile.get("display_name") or "Unknown",
                    "position_roles": [],
                }
            users_dict[uid]["position_roles"].append(row["position_role"])
        users = list(users_dict.values())
        if search:
            q = search.lower()
            users = [u for u in users if q in (u["display_name"] or "").lower()]
        return users[:50]

    # Global user search
    query = supabase.table("user_profiles")\
        .select("user_id, display_name, preferred_locale")\

    if search:
        query = query.ilike("display_name", f"%{search}%")

    result = query.limit(30).order("display_name").execute()
    users = [dict(u) for u in (result.data or [])]
    for u in users:
        u["position_roles"] = []
    return users
