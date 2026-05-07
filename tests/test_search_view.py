"""Tests for SearchView.

All tests run without a real API server.  APIClient.get is patched at the
view module level so no HTTP calls are made.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_CLIENT_GET = "saebooks_desktop.views.search_view.APIClient"


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_SAMPLE_RESULTS = [
    {"type": "invoice", "id": "inv-001", "label": "INV-0001", "detail": "Acme Corp"},
    {"type": "contact", "id": "con-001", "label": "Acme Corp", "detail": "customer"},
    {"type": "account", "id": "acct-001", "label": "1000 — Cash", "detail": ""},
]


def _make_view(qapp):
    """Create SearchView — the view doesn't call the API on construction."""
    from saebooks_desktop.views.search_view import SearchView

    return SearchView()


class TestSearchViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        view = _make_view(qapp)
        assert view is not None

    def test_has_search_edit(self, qapp) -> None:
        from PySide6.QtWidgets import QLineEdit

        view = _make_view(qapp)
        assert isinstance(view._search_edit, QLineEdit)

    def test_has_results_list(self, qapp) -> None:
        from PySide6.QtWidgets import QListWidget

        view = _make_view(qapp)
        assert isinstance(view._results_list, QListWidget)

    def test_results_list_empty_on_init(self, qapp) -> None:
        view = _make_view(qapp)
        assert view._results_list.count() == 0

    def test_has_result_selected_signal(self, qapp) -> None:
        view = _make_view(qapp)
        assert hasattr(view, "result_selected")


class TestSearchViewSearch:
    def test_search_populates_results(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()
        assert view._results_list.count() == 3

    def test_search_result_label_shown(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()
        # First item should show the label + detail
        first_text = view._results_list.item(0).text()
        assert "INV-0001" in first_text
        assert "Acme Corp" in first_text

    def test_empty_query_does_nothing(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._search_edit.setText("")
        view._on_search()
        view._client.get.assert_not_called()

    def test_no_results_shows_status(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": []}
        view._search_edit.setText("nothing")
        view._on_search()
        assert view._results_list.count() == 0
        assert "No results" in view._status_label.text()

    def test_result_count_shown_in_status(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()
        assert "3" in view._status_label.text()

    def test_offline_error_shows_status(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.side_effect = ServerOfflineError("offline")
        view._search_edit.setText("acme")
        view._on_search()
        assert "offline" in view._status_label.text().lower()

    def test_clear_text_clears_status(self, qapp) -> None:
        from PySide6.QtWidgets import QApplication

        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()
        view._search_edit.clear()
        QApplication.processEvents()
        assert view._results_list.count() == 0


class TestSearchViewDoubleClick:
    def test_double_click_emits_result_selected(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()

        received: list[tuple[str, str]] = []
        view.result_selected.connect(lambda t, i: received.append((t, i)))

        item = view._results_list.item(0)
        view._on_item_double_clicked(item)
        assert received == [("invoice", "inv-001")]

    def test_double_click_contact_result(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {"results": _SAMPLE_RESULTS}
        view._search_edit.setText("acme")
        view._on_search()

        received: list[tuple[str, str]] = []
        view.result_selected.connect(lambda t, i: received.append((t, i)))

        item = view._results_list.item(1)
        view._on_item_double_clicked(item)
        assert received == [("contact", "con-001")]


class TestSearchViewKeyEncoding:
    def test_encode_decode_roundtrip(self, qapp) -> None:
        from saebooks_desktop.views.search_view import _decode_key, _encode_key

        key = _encode_key("invoice", "inv-abc-123")
        r_type, r_id = _decode_key(key)
        assert r_type == "invoice"
        assert r_id == "inv-abc-123"

    def test_decode_key_with_colon_in_id(self, qapp) -> None:
        from saebooks_desktop.views.search_view import _decode_key, _encode_key

        key = _encode_key("account", "acct:001:v2")
        r_type, r_id = _decode_key(key)
        assert r_type == "account"
        assert r_id == "acct:001:v2"


class TestSearchViewFocusSearch:
    def test_focus_search_method_exists(self, qapp) -> None:
        view = _make_view(qapp)
        assert callable(view.focus_search)

    def test_focus_search_does_not_crash(self, qapp) -> None:
        view = _make_view(qapp)
        view.focus_search()  # must not raise


class TestSearchViewResultDetail:
    def test_result_without_detail_shows_label_only(self, qapp) -> None:
        view = _make_view(qapp)
        view._client = MagicMock()
        view._client.get.return_value = {
            "results": [
                {"type": "account", "id": "acct-001", "label": "1000 — Cash", "detail": ""},
            ]
        }
        view._search_edit.setText("cash")
        view._on_search()
        item_text = view._results_list.item(0).text()
        # Should not contain " — " separator followed by empty detail
        assert "1000 — Cash" in item_text
