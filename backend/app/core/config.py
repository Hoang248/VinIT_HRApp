from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "VinUni HRA API"
    API_V1_PREFIX: str = "/v1"
    DEBUG: bool = False

    # Database - direct PostgreSQL connection string
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/hra"
    DATABASE_POOL_SIZE: int = 5

    # Supabase (optional - used for Auth and Storage if provided)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    SUPABASE_JWT_SECRET: str = ""

    # Disabled by default. Set a unique random token only during first-admin
    # setup, over HTTPS and a restricted network; remove it afterwards.
    ADMIN_BOOTSTRAP_TOKEN: str = ""

    # Storage (local or Supabase)
    STORAGE_BACKEND: str = "local"  # "local" or "supabase"
    LOCAL_STORAGE_PATH: str = "./storage"
    SUPABASE_STORAGE_BUCKET_CV: str = "cv-originals"
    SUPABASE_STORAGE_BUCKET_EXTRACTED: str = "cv-extracted-text"

    # File upload limits
    MAX_FILE_SIZE_BYTES: int = 10_000_000  # 10 MB
    MAX_FILES_PER_BATCH: int = 50
    MAX_BATCH_SIZE_BYTES: int = 250_000_000  # 250 MB

    # AI/LLM
    # local/openai/azure/compatible labels share the OpenAI-compatible transport.
    # "mock" = built-in synthetic AI for development until AI Core exposes its API.
    LLM_PROVIDER: str = "local"
    LLM_MODEL_NAME: str = "vinuni/hra-llm-7b"
    LLM_API_BASE: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    # Optional JSON arrays. The environment default endpoint/model are always
    # included. These are operator policy, never editable in the UI.
    LLM_ALLOWED_API_BASES: list[str] = []
    LLM_ALLOWED_MODELS: list[str] = []
    LLM_TEMPERATURE_DEFAULT: float = 0.1
    ALLOW_EXTERNAL_API: bool = False

    # Matching/Scoring
    MANDATORY_CRITERIA_WEIGHT_DEFAULT: float = 0.7
    NICE_TO_HAVE_WEIGHT_DEFAULT: float = 0.3
    MIN_EVIDENCE_COVERAGE: float = 0.7
    STRONG_MATCH_SCORE: int = 100
    MATCH_SCORE: int = 80
    NO_MATCH_SCORE: int = 0

    # Retention
    RETENTION_MONTHS: int = 12

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # Authentication backend.
    #   "supabase": Supabase Auth issues tokens (default, unchanged behaviour).
    #   "local":    the backend stores scrypt password hashes in PostgreSQL
    #               (app_private.local_credentials) and signs its own HS256
    #               tokens with SUPABASE_JWT_SECRET, which then acts as the
    #               app's JWT secret. Intended for plain PostgreSQL without Supabase.
    AUTH_BACKEND: Literal["supabase", "local"] = "supabase"
    LOCAL_AUTH_MAX_FAILED_ATTEMPTS: int = 5
    LOCAL_AUTH_LOCKOUT_MINUTES: int = 15

    @model_validator(mode="after")
    def _guard_development_shortcuts(self):
        if self.AUTH_BACKEND == "local" and len(self.SUPABASE_JWT_SECRET) < 32:
            raise ValueError("AUTH_BACKEND=local requires SUPABASE_JWT_SECRET of at least 32 random characters")
        # The mock AI returns synthetic, heuristic results. It must never
        # assess real candidates, so it is refused outside development/testing.
        if self.LLM_PROVIDER == "mock" and self.APP_ENV not in ("development", "testing"):
            raise ValueError("LLM_PROVIDER=mock is only allowed when APP_ENV is development or testing")
        return self


settings = Settings()
