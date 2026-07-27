"""Lazy Supabase client (backend/services/supabase_client.py).

The client must not be built at import time: a process without
SUPABASE_URL/SUPABASE_KEY (fresh deploy, management command, test run)
must be able to import Supabase-backed services as long as it never
actually calls Supabase.

The module is loaded from its file path under a private name so these
tests don't fight with the sys.modules stub in test_supabase_services.py.
"""
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "services" / "supabase_client.py"


def _load_module():
    spec = importlib.util.spec_from_file_location(
        "_supabase_client_under_test", MODULE_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class TestLazySupabaseClient:
    def test_import_succeeds_without_env(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        mod = _load_module()  # must not raise
        assert mod.supabase is not None

    def test_first_use_without_env_raises_clear_error(self, monkeypatch):
        monkeypatch.delenv("SUPABASE_URL", raising=False)
        monkeypatch.delenv("SUPABASE_KEY", raising=False)
        mod = _load_module()
        with pytest.raises(RuntimeError, match="SUPABASE_URL"):
            mod.supabase.table("tolerances")

    @pytest.mark.parametrize("missing", ["SUPABASE_URL", "SUPABASE_KEY"])
    def test_partial_env_still_raises(self, monkeypatch, missing):
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-key")
        monkeypatch.delenv(missing)
        mod = _load_module()
        with pytest.raises(RuntimeError):
            mod.supabase.table("tolerances")

    def test_client_created_once_and_delegates(self, monkeypatch):
        monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
        monkeypatch.setenv("SUPABASE_KEY", "test-key")
        mod = _load_module()
        fake_client = MagicMock()
        with patch("supabase.create_client", return_value=fake_client) as factory:
            mod.supabase.table("tolerances")
            mod.supabase.table("user_feedback")
        factory.assert_called_once_with("https://example.supabase.co", "test-key")
        assert fake_client.table.call_count == 2
