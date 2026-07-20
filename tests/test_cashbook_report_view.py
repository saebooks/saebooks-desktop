"""Tests for CashbookReportView — the cashbook-mode Reports view.

All API calls are mocked; no server needed.
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

_PATCH_GET_SUMMARY = "saebooks_desktop.views.cashbook_report.get_summary"

_SAMPLE_SUMMARY = {
    "from": "2024-01-01",
    "to": "2024-12-31",
    "income_total": "150.00",
    "expense_total": "40.00",
    "net": "110.00",
    "by_category": [
        {
            "code": "sales",
            "label": "Sales",
            "direction": "income",
            "amount": "150.00",
            "count": 3,
        },
        {
            "code": "office_supplies",
            "label": "Office Supplies",
            "direction": "expense",
            "amount": "40.00",
            "count": 1,
        },
    ],
    "gst_collected": "13.64",
    "gst_paid": "3.64",
}


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_view(qapp, summary=None, summary_side_effect=None):
    from saebooks_desktop.views.cashbook_report import CashbookReportView

    view = CashbookReportView()
    if summary_side_effect is not None:
        with patch(_PATCH_GET_SUMMARY, side_effect=summary_side_effect):
            view.load()
    else:
        with patch(
            _PATCH_GET_SUMMARY,
            return_value=summary if summary is not None else {},
        ):
            view.load()
    return view


class TestCashbookReportTotals:
    def test_totals_populated(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert "150.00" in view._money_in_label.text()
        assert "40.00" in view._money_out_label.text()
        assert "110.00" in view._net_label.text()

    def test_tax_labels_use_brand_tax_label(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert view._gst_collected_label.text() == "GST collected: 13.64"
        assert view._gst_paid_label.text() == "GST paid: 3.64"

    def test_tasur_brand_tax_label(self, qapp, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_BRAND", "tasur")
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert view._gst_collected_label.text() == "käibemaks collected: 13.64"
        assert view._gst_paid_label.text() == "käibemaks paid: 3.64"


class TestCashbookReportCategories:
    def test_by_category_rows(self, qapp) -> None:
        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        assert view._table.rowCount() == 2
        assert view._table.item(0, 0).text() == "Sales"
        assert view._table.item(0, 1).text() == "In"
        assert view._table.item(0, 2).text() == "3"
        assert view._table.item(0, 3).text() == "150.00"
        assert view._table.item(1, 0).text() == "Office Supplies"
        assert view._table.item(1, 1).text() == "Out"

    def test_empty_by_category(self, qapp) -> None:
        view = _make_view(qapp, summary={"income_total": "0"})
        assert view._table.rowCount() == 0


class TestCashbookReportDegrade:
    def test_offline_banner(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError

        view = _make_view(qapp, summary_side_effect=ServerOfflineError("offline"))
        assert view._offline_banner.isVisibleTo(view)

    def test_module_banner_carries_engine_message(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ModuleUnavailableError

        view = _make_view(
            qapp,
            summary_side_effect=ModuleUnavailableError(
                "cashbook module unavailable", module="cashbook"
            ),
        )
        assert view._module_banner.isVisibleTo(view)
        assert "cashbook module unavailable" in view._module_banner.text()

    def test_plain_api_error_does_not_raise(self, qapp) -> None:
        from saebooks_desktop.services.api_client import APIError

        view = _make_view(qapp, summary_side_effect=APIError("boom", status_code=500))
        assert not view._offline_banner.isVisibleTo(view)
        assert not view._module_banner.isVisibleTo(view)

    def test_range_defaults_to_calendar_ytd(self, qapp) -> None:
        import datetime

        from PySide6.QtCore import QDate

        view = _make_view(qapp, summary=_SAMPLE_SUMMARY)
        today = datetime.date.today()
        assert view._from_edit.date() == QDate(today.year, 1, 1)
        assert view._to_edit.date() == QDate.currentDate()
