from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


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
    # Legacy HS256 verification only. Projects using asymmetric signing keys
    # (for example ES256) are verified through JWKS derived from SUPABASE_URL.
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_ISSUER: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    SUPABASE_JWKS_CACHE_SECONDS: int = 300

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
    LLM_PROVIDER: str = "local"  # local/openai/azure/compatible labels; same OpenAI-compatible transport
    LLM_PROVIDER_NAME: Optional[str] = None
    LLM_MODEL_NAME: str = "vinuni/hra-llm-7b"
    LLM_API_BASE: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    # Server-only Fernet key used to encrypt API keys entered by an Admin for
    # an OpenAI-compatible provider. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Rotating it makes previously stored provider keys undecryptable.
    AI_CONFIG_ENCRYPTION_KEY: str = ""
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


settings = Settings()
