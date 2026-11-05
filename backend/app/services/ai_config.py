"""Versioned, non-secret AI runtime choices, bounded by deployment policy."""
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import text

from app.core.config import settings


class AIConfigError(ValueError):
    pass


# Worker operations pin one version across all calls and across crash recovery.
# A synchronous API call without a pinned operation resolves the current version.
runtime_context: ContextVar[dict[str, Any] | None] = ContextVar("ai_runtime", default=None)


def canonical_endpoint(value: str) -> str:
    try:
        parsed = urlsplit(value.strip())
        port = parsed.port
        if (parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password
                or parsed.query or parsed.fragment or any(x in parsed.path for x in ("%", "..", "\\"))):
            raise ValueError()
        host = parsed.hostname.lower()
        if ":" in host:
            host = f"[{host}]"
        if port:
            host += f":{port}"
        return urlunsplit((parsed.scheme.lower(), host, parsed.path.rstrip("/"), "", ""))
    except (AttributeError, ValueError):
        raise AIConfigError("Endpoint không hợp lệ; không được chứa credential, query hoặc fragment") from None


def allowed_endpoints() -> list[str]:
    values = list(settings.LLM_ALLOWED_API_BASES)
    if settings.LLM_API_BASE:
        values.append(settings.LLM_API_BASE)
    return sorted({canonical_endpoint(value) for value in values})


def allowed_models() -> list[str]:
    return sorted(set(settings.LLM_ALLOWED_MODELS + [settings.LLM_MODEL_NAME]))


def validate_runtime(runtime: dict[str, Any]) -> None:
    """The UI cannot extend the deployment's model/endpoint allowlists."""
    if runtime.get("provider") not in {"local", "openai", "azure", "compatible"}:
        raise AIConfigError("Nhà cung cấp AI không hợp lệ")
    if runtime.get("model_name") not in allowed_models():
        raise AIConfigError("Model không nằm trong danh sách được phép của môi trường")
    base = runtime.get("api_base")
    if not base or canonical_endpoint(base) not in allowed_endpoints():
        raise AIConfigError("Endpoint không nằm trong danh sách được phép của môi trường")
    try:
        temperature = float(runtime.get("temperature_default"))
    except (TypeError, ValueError):
        raise AIConfigError("Temperature không hợp lệ") from None
    if not 0 <= temperature <= 1:
        raise AIConfigError("Temperature phải nằm trong khoảng 0–1")


def environment_runtime() -> dict[str, Any]:
    return {"source": "environment", "config_id": None, "provider": settings.LLM_PROVIDER,
            "model_name": settings.LLM_MODEL_NAME, "api_base": settings.LLM_API_BASE,
            "temperature_default": settings.LLM_TEMPERATURE_DEFAULT}


def get_active_runtime(db) -> dict[str, Any]:
    row = db.execute(text("""
        SELECT config_id, provider, model_name, api_base, temperature_default
        FROM app_private.ai_configuration_versions WHERE status = 'ACTIVE'
        ORDER BY enabled_at DESC NULLS LAST LIMIT 1
    """)).mappings().first()
    if not row:
        return environment_runtime()
    return {"source": "database", "config_id": str(row["config_id"]), "provider": row["provider"],
            "model_name": row["model_name"], "api_base": row["api_base"],
            "temperature_default": float(row["temperature_default"]) if row["temperature_default"] is not None else None}
