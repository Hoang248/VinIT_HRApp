from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, List
from uuid import UUID, uuid4
from app.core.security import get_current_user
from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal
from app.schemas.common import OperationResponse
from datetime import datetime

router = APIRouter()
logger = get_logger(__name__)


# TODO: Add actual RBAC decorator to require ADMIN role
def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    # In Phase 1 MVP, all authenticated users can access admin endpoints for development
    # Production will check user_role_assignments for ADMIN role
    return current_user


class AIConfigUpdateRequest(BaseModel):
    provider: str  # "local" or "openai_compatible"
    model_name: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None  # Will be stored encrypted in production
    deployment_mode: str = "local"  # "local", "cloud"
    temperature_default: float = 0.1
    external_api_allowed: bool = False


class AIConfigResponse(BaseModel):
    config_id: UUID
    provider: str
    model_name: str
    api_base: Optional[str] = None
    deployment_mode: str
    temperature_default: float
    external_api_allowed: bool
    status: str
    enabled_at: Optional[datetime] = None


@router.get("/ai/config", response_model=List[AIConfigResponse])
async def list_ai_configs(
    current_user: dict = Depends(require_admin)
):
    """List all approved AI model configurations"""
    db = SessionLocal()
    try:
        result = db.execute(
            """
            SELECT config_id, provider, model_name, api_base, deployment_mode,
                   temperature_default, external_api_allowed, status, enabled_at
            FROM app_private.ai_configuration_versions
            ORDER BY created_at DESC
            """
        )
        configs = []
        for row in result.fetchall():
            configs.append(dict(row))
        return configs
    finally:
        db.close()


@router.post("/ai/config", response_model=AIConfigResponse, status_code=status.HTTP_201_CREATED)
async def create_ai_config(
    request: AIConfigUpdateRequest,
    current_user: dict = Depends(require_admin)
):
    """Create new AI model configuration (Admin only)"""
    user_id = current_user["user_id"]

    # Validate provider
    if request.provider not in ["local", "openai_compatible", "openai", "azure"]:
        raise HTTPException(
            status_code=400,
            detail="Provider must be one of: local, openai_compatible, openai, azure"
        )

    # If using external API, ensure allowed flag is set
    if request.provider in ["openai", "azure"] and not request.external_api_allowed:
        raise HTTPException(
            status_code=400,
            detail="External providers require external_api_allowed = true (must be approved per policy)"
        )

    db = SessionLocal()
    try:
        from sqlalchemy import text
        config_id = uuid4()

        # Insert new config (disabled by default, needs explicit enable)
        db.execute(
            text("""
                INSERT INTO app_private.ai_configuration_versions
                (config_id, provider, model_name, model_version, deployment_mode,
                 ai_policy_version, status, created_at)
                VALUES
                (:config_id, :provider, :model_name, :model_version, :deployment_mode,
                 (SELECT policy_version FROM app_private.ai_policy_versions WHERE status = 'APPROVED' ORDER BY created_at DESC LIMIT 1),
                 'DRAFT', NOW())
            """),
            {
                "config_id": str(config_id),
                "provider": request.provider,
                "model_name": request.model_name,
                "model_version": "1.0",
                "deployment_mode": request.deployment_mode
            }
        )

        # Store API configuration metadata in policy version (MVP: plaintext; production: encrypted column / secret manager)
        # Use json.dumps for safe JSON construction (prevents any injection via provider/api_base strings)
        import json as _json
        allowed_providers_json = _json.dumps([request.provider])
        data_rules_json = _json.dumps({
            "api_base": request.api_base or "",
            "api_key_set": bool(request.api_key),
            "temperature_default": request.temperature_default,
            "model_name": request.model_name,
        })

        db.execute(
            text("""
                INSERT INTO app_private.ai_policy_versions
                (policy_version, allowed_providers, data_handling_rules,
                 external_api_allowed, training_opt_out, status, approved_by, created_at)
                VALUES
                (:policy_version, :allowed_providers::jsonb, :data_rules::jsonb,
                 :external_allowed, TRUE, 'APPROVED', :approved_by, NOW())
            """),
            {
                "policy_version": f"custom-{config_id}",
                "allowed_providers": allowed_providers_json,
                "data_rules": data_rules_json,
                "external_allowed": request.external_api_allowed,
                "approved_by": user_id
            }
        )

        db.commit()

        logger.info("AI configuration created", config_id=config_id, provider=request.provider, model=request.model_name)

        return AIConfigResponse(
            config_id=config_id,
            provider=request.provider,
            model_name=request.model_name,
            api_base=request.api_base,
            deployment_mode=request.deployment_mode,
            temperature_default=request.temperature_default,
            external_api_allowed=request.external_api_allowed,
            status="DRAFT"
        )
    finally:
        db.close()


@router.post("/ai/config/{config_id}/enable")
async def enable_ai_config(
    config_id: UUID,
    current_user: dict = Depends(require_admin)
):
    """Enable an AI configuration (disable all others at the same time)"""
    db = SessionLocal()
    try:
        from sqlalchemy import text

        # Disable all existing active configs
        db.execute(
            text("""
                UPDATE app_private.ai_configuration_versions
                SET status = 'DISABLED', disabled_at = NOW()
                WHERE status = 'ACTIVE'
            """)
        )

        # Enable selected config
        result = db.execute(
            text("""
                UPDATE app_private.ai_configuration_versions
                SET status = 'ACTIVE', enabled_at = NOW()
                WHERE config_id = :config_id
                RETURNING config_id, provider, model_name, deployment_mode, status, enabled_at
            """),
            {"config_id": str(config_id)}
        )

        row = result.fetchone()
        db.commit()
        if not row:
            db.rollback()
            raise HTTPException(status_code=404, detail="AI Configuration not found")

        db.commit()

        logger.info("AI configuration enabled", config_id=config_id)

        # TODO: Trigger reload of LLM client configuration in running API/worker instances

        return {"status": "enabled", "config": dict(row)}
    finally:
        db.close()


@router.get("/ai/active-config")
async def get_active_ai_config(
    current_user: dict = Depends(require_admin)
):
    """Get currently active AI configuration"""
    db = SessionLocal()
    try:
        from sqlalchemy import text
        result = db.execute(
            text("""
                SELECT config_id, provider, model_name, api_base, deployment_mode, status, enabled_at
                FROM app_private.ai_configuration_versions
                WHERE status = 'ACTIVE'
                ORDER BY enabled_at DESC LIMIT 1
            """)
        )
        row = result.fetchone()
        if not row:
            return {"active": False, "message": "No active AI configuration. Using defaults."}
        return {"active": True, "config": dict(row)}
    finally:
        db.close()
