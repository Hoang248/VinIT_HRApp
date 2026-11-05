from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import require_admin_role
from app.db.database import SessionLocal
from app.services.ai_config import (
    AIConfigError, allowed_endpoints, allowed_models, canonical_endpoint,
    get_active_runtime, validate_runtime,
)
from app.services.llm_client import LLMError, llm_client

router = APIRouter()


class AIConfigUpdateRequest(BaseModel):
    # In particular, reject api_key rather than accepting/storing it.
    model_config = ConfigDict(extra="forbid")
    provider: Literal["local", "openai", "azure", "compatible"]
    model_name: str = Field(min_length=1, max_length=200)
    api_base: str = Field(min_length=1, max_length=500)
    temperature_default: float = Field(default=0.1, ge=0, le=1)


def _lock_active_admin(db, user_id: str) -> None:
    """Keep account/role revocation from racing a configuration write."""
    account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id=:user FOR SHARE"),
                         {"user": user_id}).scalar_one_or_none()
    roles = db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id=:user AND role_code='ADMIN' AND revoked_at IS NULL FOR SHARE
    """), {"user": user_id}).scalars().all()
    if account != "ACTIVE" or not roles:
        raise HTTPException(status_code=403, detail="Admin role required for this endpoint")


def _validate_choice(runtime: dict) -> None:
    try:
        validate_runtime(runtime)
        # The database/UI cannot override the environment's egress decision.
        llm_client._check_endpoint_policy(runtime["api_base"])
    except (AIConfigError, LLMError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.get("/ai/options")
async def get_ai_options(current_user: dict = Depends(require_admin_role)):
    try:
        return {"models": allowed_models(), "endpoints": allowed_endpoints(),
                "external_api_allowed": settings.ALLOW_EXTERNAL_API}
    except AIConfigError:
        raise HTTPException(status_code=503, detail="Danh sách endpoint của môi trường không hợp lệ") from None


@router.get("/ai/config")
async def list_ai_configs(current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT config_id, provider, model_name, deployment_mode, api_base, temperature_default,
                   status, created_by, created_at, enabled_at, disabled_at
            FROM app_private.ai_configuration_versions ORDER BY created_at DESC, config_id DESC LIMIT 100
        """)).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("/ai/config", status_code=201)
async def create_ai_config(request: AIConfigUpdateRequest, current_user: dict = Depends(require_admin_role)):
    runtime = request.model_dump()
    try:
        runtime["api_base"] = canonical_endpoint(runtime["api_base"])
    except AIConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _validate_choice(runtime)
    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        row = db.execute(text("""
            INSERT INTO app_private.ai_configuration_versions
                (provider, model_name, deployment_mode, api_base, temperature_default, created_by, status)
            VALUES (:provider, :model_name, :provider, :api_base, :temperature_default, :user_id, 'DRAFT')
            RETURNING config_id, provider, model_name, api_base, temperature_default, status, created_at
        """), {**runtime, "user_id": current_user["user_id"]}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'CREATE_AI_CONFIG', 'AI_CONFIG', :id, 'DRAFT')
        """), {"user_id": current_user["user_id"], "id": row["config_id"]})
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/ai/config/{config_id}/enable")
async def enable_ai_config(config_id: UUID, current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        # Serialize activations across all API instances and make the switch
        # atomic. Existing worker attempts keep their already-pinned snapshot.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('hra-ai-activation', 418630021))"))
        row = db.execute(text("""
            SELECT config_id, provider, model_name, api_base, temperature_default, status
            FROM app_private.ai_configuration_versions WHERE config_id = :id FOR UPDATE
        """), {"id": str(config_id)}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên bản cấu hình AI")
        _validate_choice(dict(row))
        db.execute(text("""
            UPDATE app_private.ai_configuration_versions SET status = 'DISABLED', disabled_at = NOW()
            WHERE status = 'ACTIVE' AND config_id != :id
        """), {"id": str(config_id)})
        db.execute(text("""
            UPDATE app_private.ai_configuration_versions SET status = 'ACTIVE', enabled_at = NOW(), disabled_at = NULL
            WHERE config_id = :id
        """), {"id": str(config_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'ENABLE_AI_CONFIG', 'AI_CONFIG', :id, 'ACTIVE')
        """), {"user_id": current_user["user_id"], "id": str(config_id)})
        db.commit()
        return {"config_id": str(config_id), "status": "ACTIVE"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/ai/active-config")
async def get_active_ai_config(current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        runtime = get_active_runtime(db)
    finally:
        db.close()
    try:
        validate_runtime(runtime)
        llm_client._check_endpoint_policy(runtime["api_base"])
        allowed = True
    except (AIConfigError, LLMError):
        allowed = False
    return {"active": True, "source": runtime["source"], "allowed_by_this_process": allowed,
            "config": {**runtime, "external_api_allowed": settings.ALLOW_EXTERNAL_API}}


@router.get("/worker/health")
async def get_worker_health(current_user: dict = Depends(require_admin_role)):
    """Queue indicators, not a substitute for external alerting/liveness probes."""
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING') AS processing,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING' AND
                       (heartbeat_at IS NULL OR heartbeat_at < NOW() - INTERVAL '2 minutes')) AS stale_heartbeat,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING' AND attempt_started_at < NOW() - INTERVAL '30 minutes') AS long_running,
                   COUNT(*) FILTER (WHERE status = 'FAILED' AND completed_at >= NOW() - INTERVAL '24 hours') AS failed_24h,
                   (SELECT COUNT(*) FROM app_private.operation_recovery_events WHERE recovered_at >= NOW() - INTERVAL '24 hours') AS recoveries_24h,
                   COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at) FILTER (WHERE status = 'PENDING'))), 0)::integer AS oldest_pending_seconds
            FROM app_private.operations WHERE capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
        """)).mappings().one()
        return {**dict(row), "stale_after_seconds": 120, "long_running_after_seconds": 1800}
    finally:
        db.close()
