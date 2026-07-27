import os
import threading


class _LazySupabaseClient:
    """Proxy that defers Supabase client creation until first use.

    Creating the client at import time crashes any process (management
    commands, tests, a fresh deploy) that loads a Supabase-backed service
    without SUPABASE_URL/SUPABASE_KEY set, even if the code path never
    talks to Supabase. Attribute access transparently builds and delegates
    to the real client, so callers keep using `supabase.table(...)`.
    """

    def __init__(self):
        self._client = None
        self._lock = threading.Lock()

    def _get_client(self):
        if self._client is None:
            with self._lock:
                if self._client is None:
                    url = os.getenv("SUPABASE_URL")
                    key = os.getenv("SUPABASE_KEY")
                    if not url or not key:
                        raise RuntimeError(
                            "SUPABASE_URL and SUPABASE_KEY must be set to use "
                            "Supabase-backed services (feedback/tolerance)."
                        )
                    from supabase import create_client

                    self._client = create_client(url, key)
        return self._client

    def __getattr__(self, name):
        return getattr(self._get_client(), name)


supabase = _LazySupabaseClient()
