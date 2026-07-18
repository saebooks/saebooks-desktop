"""Tests for saebooks_desktop.services.cashbook — mocked APIClient, no HTTP."""
from __future__ import annotations

from unittest.mock import MagicMock

from saebooks_desktop.services.api_client import APIError, ServerOfflineError

_SAMPLE_ENTRIES = [
    {
        "id": "ce-001",
        "entry_date": "2024-01-10",
        "description": "Cash sale",
        "amount": "150.00",
        "direction": "income",
        "category_code": "sales",
        "category_label": "Sales",
        "gst_amount": "13.64",
        "version": 1,
        "status": "posted",
    }
]

_SAMPLE_CATEGORIES = [
    {
        "code": "sales",
        "label": "Sales",
        "group": "income",
        "direction": "income",
        "gst_default": "0.10",
        "hint_text": None,
    },
    {
        "code": "office_supplies",
        "label": "Office Supplies",
        "group": "expense",
        "direction": "expense",
        "gst_default": "0.10",
        "hint_text": None,
    },
]

_SAMPLE_SUMMARY = {
    "from": "2024-01-01",
    "to": "2024-12-31",
    "income_total": "150.00",
    "expense_total": "0.00",
    "net": "150.00",
    "by_category": [],
    "gst_collected": "13.64",
    "gst_paid": "0.00",
}


class TestListEntriesService:
    def test_calls_correct_endpoint_with_default_limit(self) -> None:
        from saebooks_desktop.services.cashbook import list_entries

        client = MagicMock()
        client.get.return_value = {"items": _SAMPLE_ENTRIES}
        result = list_entries(client)
        client.get.assert_called_once_with(
            "/api/v1/cashbook/entries", params={"limit": 50}
        )
        assert result == _SAMPLE_ENTRIES

    def test_direction_and_category_map_to_query_params(self) -> None:
        from saebooks_desktop.services.cashbook import list_entries

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_entries(client, direction="income", category="sales")
        params = client.get.call_args[1]["params"]
        assert params["direction"] == "income"
        assert params["category"] == "sales"

    def test_date_from_and_date_to_map_to_from_and_to(self) -> None:
        """The engine's query params are literally 'from'/'to', not date_from/date_to."""
        from saebooks_desktop.services.cashbook import list_entries

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_entries(client, date_from="2024-01-01", date_to="2024-01-31")
        params = client.get.call_args[1]["params"]
        assert params["from"] == "2024-01-01"
        assert params["to"] == "2024-01-31"
        assert "date_from" not in params
        assert "date_to" not in params

    def test_limit_passed_through(self) -> None:
        from saebooks_desktop.services.cashbook import list_entries

        client = MagicMock()
        client.get.return_value = {"items": []}
        list_entries(client, limit=200)
        params = client.get.call_args[1]["params"]
        assert params["limit"] == 200

    def test_returns_empty_list_when_no_items(self) -> None:
        from saebooks_desktop.services.cashbook import list_entries

        client = MagicMock()
        client.get.return_value = {}
        assert list_entries(client) == []


class TestGetEntryService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.cashbook import get_entry

        client = MagicMock()
        client.get.return_value = _SAMPLE_ENTRIES[0]
        result = get_entry(client, "ce-001")
        client.get.assert_called_once_with("/api/v1/cashbook/entries/ce-001")
        assert result == _SAMPLE_ENTRIES[0]


class TestCreateEntryService:
    def test_calls_post_endpoint_with_body(self) -> None:
        from saebooks_desktop.services.cashbook import create_entry

        client = MagicMock()
        client.post.return_value = {"id": "ce-new"}
        data = {
            "entry_date": "2024-02-01",
            "amount": "50.00",
            "direction": "expense",
            "category_code": "office_supplies",
        }
        result = create_entry(client, data)

        assert client.post.call_count == 1
        args, kwargs = client.post.call_args
        assert args[0] == "/api/v1/cashbook/entries"
        assert kwargs["json"] == data
        assert result == {"id": "ce-new"}

    def test_attaches_idempotency_key_header(self) -> None:
        from saebooks_desktop.services.cashbook import create_entry

        client = MagicMock()
        client.post.return_value = {"id": "ce-new"}
        create_entry(client, {"entry_date": "2024-02-01"})

        headers = client.post.call_args[1]["headers"]
        assert "X-Idempotency-Key" in headers
        assert len(headers["X-Idempotency-Key"]) > 0

    def test_idempotency_key_is_unique_per_call(self) -> None:
        from saebooks_desktop.services.cashbook import create_entry

        client = MagicMock()
        client.post.return_value = {"id": "ce-new"}

        create_entry(client, {"entry_date": "2024-02-01"})
        create_entry(client, {"entry_date": "2024-02-01"})

        key_1 = client.post.call_args_list[0][1]["headers"]["X-Idempotency-Key"]
        key_2 = client.post.call_args_list[1][1]["headers"]["X-Idempotency-Key"]
        assert key_1 != key_2


class TestDeleteEntryService:
    def test_calls_delete_endpoint_and_returns_status(self) -> None:
        from saebooks_desktop.services.cashbook import delete_entry

        client = MagicMock()
        client.delete.return_value = 204
        result = delete_entry(client, "ce-001")
        client.delete.assert_called_once_with("/api/v1/cashbook/entries/ce-001")
        assert result == 204


class TestListCategoriesService:
    def test_calls_correct_endpoint(self) -> None:
        from saebooks_desktop.services.cashbook import list_categories

        client = MagicMock()
        client.get.return_value = _SAMPLE_CATEGORIES
        result = list_categories(client)
        client.get.assert_called_once_with("/api/v1/cashbook/categories")
        assert result == _SAMPLE_CATEGORIES


class TestGetSummaryService:
    def test_calls_correct_endpoint_with_default_date_range(self) -> None:
        from saebooks_desktop.services.cashbook import get_summary

        client = MagicMock()
        client.get.return_value = _SAMPLE_SUMMARY
        result = get_summary(client)

        assert client.get.call_count == 1
        args, kwargs = client.get.call_args
        assert args[0] == "/api/v1/cashbook/summary"
        assert "from" in kwargs["params"]
        assert "to" in kwargs["params"]
        assert result == _SAMPLE_SUMMARY

    def test_explicit_date_range_passed_through(self) -> None:
        from saebooks_desktop.services.cashbook import get_summary

        client = MagicMock()
        client.get.return_value = _SAMPLE_SUMMARY
        get_summary(client, date_from="2024-01-01", date_to="2024-06-30")
        params = client.get.call_args[1]["params"]
        assert params == {"from": "2024-01-01", "to": "2024-06-30"}


class TestIsCashbookCompany:
    def test_returns_true_on_success(self) -> None:
        from saebooks_desktop.services.cashbook import is_cashbook_company

        client = MagicMock()
        client.get.return_value = _SAMPLE_CATEGORIES
        assert is_cashbook_company(client) is True

    def test_returns_false_on_409(self) -> None:
        from saebooks_desktop.services.cashbook import is_cashbook_company

        client = MagicMock()
        client.get.side_effect = APIError("conflict", status_code=409)
        assert is_cashbook_company(client) is False

    def test_reraises_non_409_api_error(self) -> None:
        from saebooks_desktop.services.cashbook import is_cashbook_company

        client = MagicMock()
        client.get.side_effect = APIError("boom", status_code=500)
        try:
            is_cashbook_company(client)
        except APIError as exc:
            assert exc.status_code == 500
        else:
            raise AssertionError("expected APIError to propagate")

    def test_reraises_server_offline_error(self) -> None:
        from saebooks_desktop.services.cashbook import is_cashbook_company

        client = MagicMock()
        client.get.side_effect = ServerOfflineError("offline")
        try:
            is_cashbook_company(client)
        except ServerOfflineError:
            pass
        else:
            raise AssertionError("expected ServerOfflineError to propagate")
