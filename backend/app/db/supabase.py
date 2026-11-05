from supabase import create_client, Client
from functools import lru_cache
from app.core.config import settings


@lru_cache()
def get_supabase_client() -> Client:
    """Get Supabase client using service role key (for backend/worker operations)"""
    return create_client(
        settings.SUPABASE_URL,
        settings.SUPABASE_SERVICE_ROLE_KEY
    )


def get_supabase_client_from_token(access_token: str) -> Client:
    """Get Supabase client authenticated with user's access token (for user-facing operations)"""
    client = create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    client.auth.set_session(access_token=access_token, refresh_token="")
    return client
