"""Tests for AgedPayablesReport widget — offscreen Qt, mocked API."""
from __future__ import annotations

import os
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_BUCKETS = ["current", "1-30 days", "31-60 days", "61-90 days", "90+ days"]

_SAMPLE_AP = {
    "as_of_date": "2024-06-30",
    "buckets": _BUCKETS,
    "contacts": [
        {
            "contact_id": "s1",
            "contact_name": "Supplier A",
            "current": 3000.0,
            "1-30 days": 0.0,
            "31-60 days": 1200.0,
            "61-90 days": 0.0,
            "90+ days": 500.0,
            "total": 4700.0,
        },
    ],
    "totals": {
        "current": 3000.0,
        "1-30 days": 0.0,
        "31-60 days": 1200.0,
        "61-90 days": 0.0,
        "90+ days": 500.0,
        "total": 4700.0,
    },
}


def _run_widget(qapp, data):
    from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

    w = AgedPayablesReport()
    with patch(
        "saebooks_desktop.views.reports.aged_payables.get_aged_payables",
        return_value=data,
    ):
        w._run_report()
    return w


class TestAgedPayablesReportInstantiation:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

        w = AgedPayablesReport()
        assert w is not None

    def test_report_name(self, qapp) -> None:
        from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

        w = AgedPayablesReport()
        assert w._REPORT_NAME == "aged_payables"

    def test_uses_as_at_mode(self, qapp) -> None:
        from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT
        from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

        w = AgedPayablesReport()
        assert w._date_mode == DATE_MODE_AS_AT


class TestAgedPayablesReportPopulation:
    def test_columns_built_from_buckets(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        # Contact + 5 buckets + Total = 7
        assert w._model.columnCount() == 7

    def test_contact_column_header(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        assert w._model.horizontalHeaderItem(0).text() == "Contact"

    def test_contact_rows_count(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        # 1 contact + 1 totals row
        assert w._model.rowCount() == 2

    def test_supplier_name_in_first_row(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        assert w._model.item(0, 0).text() == "Supplier A"

    def test_current_bucket_amount(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        assert "3,000.00" in w._model.item(0, 1).text()

    def test_totals_row_label(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        last = w._model.rowCount() - 1
        assert w._model.item(last, 0).text() == "TOTALS"

    def test_totals_grand_total_correct(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        last = w._model.rowCount() - 1
        total_col = w._model.columnCount() - 1
        total_text = w._model.item(last, total_col).text().replace(",", "")
        assert float(total_text) == pytest.approx(4700.0)

    def test_offline_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError
        from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

        w = AgedPayablesReport()
        with patch(
            "saebooks_desktop.views.reports.aged_payables.get_aged_payables",
            side_effect=ServerOfflineError("down"),
        ):
            w._run_report()
        assert not w._offline_label.isHidden()

    def test_empty_state_on_no_contacts(self, qapp) -> None:
        empty = {**_SAMPLE_AP, "contacts": [], "totals": {}}
        w = _run_widget(qapp, empty)
        assert not w._status_label.isHidden()

    def test_export_signal(self, qapp, tmp_path) -> None:
        from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport

        w = AgedPayablesReport()
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: str(tmp_path / "aged_payables.csv")
        w._export_btn.click()
        assert received == ["aged_payables"]

    def test_90plus_bucket_amount(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AP)
        # "90+ days" is the 5th bucket (index 5 in columns)
        # Find the bucket index
        buckets = _SAMPLE_AP["buckets"]
        col_idx = buckets.index("90+ days") + 1
        assert "500.00" in w._model.item(0, col_idx).text()
