from typing import Optional
from supabase import create_client, Client
from functools import lru_cache
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache()
def get_supabase_client() -> Optional[Client]:
    """Get Supabase client using service role key (for backend/worker operations).
    Returns None if Supabase is not configured.
    """
    if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_ROLE_KEY:
        logger.warning("Supabase not configured. Running with local storage/database only.")
        return None

    try:
        return create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SERVICE_ROLE_KEY
        )
    except Exception as e:
        logger.error("Failed to initialize Supabase client", error_type=type(e).__name__)
        return None


def get_supabase_client_from_token(access_token: str) -> Optional[Client]:
    """Get Supabase client authenticated with user's access token (for user-facing operations)"""
    if not settings.SUPABASE_URL or not settings.SUPABASE_ANON_KEY:
        return None
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(access_token=access_token, refresh_token="")
    return client
