"""
Supabase Client Configuration

Provides Supabase client for auth, storage, and realtime features.
"""

from supabase import create_client, Client
from .config import settings


# Supabase client with anon key (for auth, storage, realtime)
supabase_client: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)

# Supabase client with service role key (for admin operations)
supabase_admin: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_SERVICE_KEY
)


async def get_supabase() -> Client:
    """
    Dependency function for FastAPI routes.

    Usage:
        @app.get("/storage/files")
        async def get_files(supabase: Client = Depends(get_supabase)):
            result = supabase.storage.from_("documents").list()
            return result
    """
    return supabase_client


def get_supabase_admin() -> Client:
    """
    Get admin client for privileged operations.

    Use sparingly and only for admin-level operations like:
    - User management
    - Bypassing RLS (Row Level Security)
    - Service-to-service authentication
    """
    return supabase_admin
