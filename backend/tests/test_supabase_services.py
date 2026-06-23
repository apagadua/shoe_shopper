"""Tests for tolerance_storage and feedback_service.

backend.services.supabase_client builds a real client at import time, so a
fake module is installed in sys.modules before importing the services.
"""

import sys
import types
from unittest.mock import MagicMock, patch

_fake_client_module = types.ModuleType("backend.services.supabase_client")
_fake_client_module.supabase = MagicMock()
sys.modules.setdefault("backend.services.supabase_client", _fake_client_module)

from backend.services import feedback_service, tolerance_storage  # noqa: E402


def make_supabase(select_data=None):
    """A supabase stub whose terminal .execute() returns .data == select_data."""
    sb = MagicMock()
    chain = sb.table.return_value
    for method in ("select", "eq", "gt", "order", "update", "insert", "in_"):
        getattr(chain, method).return_value = chain
    chain.execute.return_value = MagicMock(data=select_data or [])
    return sb


# ---------------------------------------------------------------------------
# tolerance_storage.load_tolerances
# ---------------------------------------------------------------------------

class TestLoadTolerances:
    def test_no_active_rows_returns_none(self):
        sb = make_supabase([])
        with patch.object(tolerance_storage, "supabase", sb):
            assert tolerance_storage.load_tolerances() is None

    def test_single_active_row_returned_without_deactivation(self):
        row = {"id": 1, "tolerances": {}, "active": True}
        sb = make_supabase([row])
        with patch.object(tolerance_storage, "supabase", sb):
            assert tolerance_storage.load_tolerances() == row
        sb.table.return_value.update.assert_not_called()

    def test_multiple_active_rows_keeps_most_recent_and_deactivates_rest(self):
        rows = [{"id": 3}, {"id": 2}, {"id": 1}]
        sb = make_supabase(rows)
        with patch.object(tolerance_storage, "supabase", sb):
            result = tolerance_storage.load_tolerances()
        assert result == {"id": 3}
        chain = sb.table.return_value
        chain.update.assert_called_once_with({"active": False})
        chain.in_.assert_called_once_with("id", [2, 1])


# ---------------------------------------------------------------------------
# tolerance_storage.save_tolerances
# ---------------------------------------------------------------------------

class TestSaveTolerances:
    def test_deactivates_then_inserts_with_timestamp(self):
        sb = make_supabase()
        tolerances = {"width": {"opt_low": 0.1}}
        with patch.object(tolerance_storage, "supabase", sb):
            tolerance_storage.save_tolerances(tolerances, 7, "2026-06-01T00:00:00+00:00")

        chain = sb.table.return_value
        chain.update.assert_called_once_with({"active": False})
        chain.insert.assert_called_once_with({
            "tolerances": tolerances,
            "total_feedback_count": 7,
            "active": True,
            "created_at": "2026-06-01T00:00:00+00:00",
            "last_feedback_timestamp": "2026-06-01T00:00:00+00:00",
        })

    def test_none_timestamp_generates_one(self):
        sb = make_supabase()
        with patch.object(tolerance_storage, "supabase", sb):
            tolerance_storage.save_tolerances({}, 0, None)
        payload = sb.table.return_value.insert.call_args.args[0]
        assert isinstance(payload["created_at"], str)
        assert payload["created_at"] == payload["last_feedback_timestamp"]


# ---------------------------------------------------------------------------
# feedback_service.get_feedback_rows
# ---------------------------------------------------------------------------

class TestGetFeedbackRows:
    def test_without_timestamp_fetches_all(self):
        rows = [{"created_at": "t1"}, {"created_at": "t2"}]
        sb = make_supabase(rows)
        with patch.object(feedback_service, "supabase", sb):
            result, new_ts = feedback_service.get_feedback_rows()
        assert result == rows
        assert new_ts == "t2"
        sb.table.return_value.gt.assert_not_called()

    def test_with_timestamp_filters_newer_rows(self):
        rows = [{"created_at": "t3"}]
        sb = make_supabase(rows)
        with patch.object(feedback_service, "supabase", sb):
            result, new_ts = feedback_service.get_feedback_rows("t2")
        assert new_ts == "t3"
        sb.table.return_value.gt.assert_called_once_with("created_at", "t2")

    def test_no_rows_keeps_previous_timestamp(self):
        sb = make_supabase([])
        with patch.object(feedback_service, "supabase", sb):
            result, new_ts = feedback_service.get_feedback_rows("t9")
        assert result == []
        assert new_ts == "t9"
