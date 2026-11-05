from typing import Optional
from uuid import UUID
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import require_admin_role
from app.db.database import SessionLocal

router = APIRouter()


class AIConfigUpdateRequest(BaseModel):
    provider: str
    model_name: str
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    deployment_mode: str = "local"
    temperature_default: float = 0.1
    external_api_allowed: bool = False


@router.get("/ai/config")
async def list_ai_configs(current_user: dict = Depends(require_admin_role)):
    """List recorded configuration versions, not the worker's live configuration."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT c.config_id, c.provider, c.model_name, c.deployment_mode, c.status, c.enabled_at,
                   p.data_handling_rules, p.external_api_allowed
            FROM app_private.ai_configuration_versions c
            LEFT JOIN app_private.ai_policy_versions p ON p.policy_version = c.ai_policy_version
            ORDER BY c.created_at DESC
        """)).mappings().all()
        result = []
        for row in rows:
            item = dict(row)
            rules = item.pop("data_handling_rules") or {}
            item["api_base"] = rules.get("api_base")
            item["temperature_default"] = rules.get("temperature_default", 0.1)
            item["external_api_allowed"] = bool(item.get("external_api_allowed"))
            item["applied_to_runtime"] = False
            result.append(item)
        return result
    finally:
        db.close()


@router.post("/ai/config", status_code=501)
async def create_ai_config(request: AIConfigUpdateRequest, current_user: dict = Depends(require_admin_role)):
    # The old endpoint recorded settings without applying them and accepted an
    # API key it never saved. Fail closed instead of giving a false guarantee.
    raise HTTPException(status_code=501, detail="Thay đổi cấu hình AI qua giao diện chưa được hỗ trợ; cấu hình bằng biến môi trường và khởi động lại dịch vụ.")


@router.post("/ai/config/{config_id}/enable", status_code=501)
async def enable_ai_config(config_id: UUID, current_user: dict = Depends(require_admin_role)):
    raise HTTPException(status_code=501, detail="Kích hoạt cấu hình AI qua giao diện chưa được hỗ trợ; cấu hình bằng biến môi trường và khởi động lại dịch vụ.")


@router.get("/ai/active-config")
async def get_active_ai_config(current_user: dict = Depends(require_admin_role)):
    """Report the actual environment settings used by this API/worker process."""
    api_base = None
    if settings.LLM_API_BASE:
        parsed = urlsplit(settings.LLM_API_BASE)
        host = parsed.hostname or ""
        if parsed.port:
            host += f":{parsed.port}"
        api_base = urlunsplit((parsed.scheme, host, parsed.path, "", ""))
    return {"active": True, "source": "environment", "config": {
        "provider": settings.LLM_PROVIDER, "model_name": settings.LLM_MODEL_NAME,
        "api_base": api_base, "deployment_mode": settings.LLM_PROVIDER,
        "temperature_default": settings.LLM_TEMPERATURE_DEFAULT,
        "external_api_allowed": settings.ALLOW_EXTERNAL_API,
    }}
