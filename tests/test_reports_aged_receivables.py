"""Tests for AgedReceivablesReport widget — offscreen Qt, mocked API."""
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

_SAMPLE_AR = {
    "as_of_date": "2024-06-30",
    "buckets": _BUCKETS,
    "contacts": [
        {
            "contact_id": "c1",
            "contact_name": "Acme Corp",
            "current": 5000.0,
            "1-30 days": 2000.0,
            "31-60 days": 0.0,
            "61-90 days": 0.0,
            "90+ days": 0.0,
            "total": 7000.0,
        },
        {
            "contact_id": "c2",
            "contact_name": "Beta Ltd",
            "current": 0.0,
            "1-30 days": 0.0,
            "31-60 days": 1500.0,
            "61-90 days": 800.0,
            "90+ days": 0.0,
            "total": 2300.0,
        },
    ],
    "totals": {
        "current": 5000.0,
        "1-30 days": 2000.0,
        "31-60 days": 1500.0,
        "61-90 days": 800.0,
        "90+ days": 0.0,
        "total": 9300.0,
    },
}


def _run_widget(qapp, data):
    from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

    w = AgedReceivablesReport()
    with patch(
        "saebooks_desktop.views.reports.aged_receivables.get_aged_receivables",
        return_value=data,
    ):
        w._run_report()
    return w


class TestAgedReceivablesReportInstantiation:
    def test_instantiates(self, qapp) -> None:
        from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

        w = AgedReceivablesReport()
        assert w is not None

    def test_report_name(self, qapp) -> None:
        from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

        w = AgedReceivablesReport()
        assert w._REPORT_NAME == "aged_receivables"

    def test_uses_as_at_mode(self, qapp) -> None:
        from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT
        from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

        w = AgedReceivablesReport()
        assert w._date_mode == DATE_MODE_AS_AT


class TestAgedReceivablesReportPopulation:
    def test_columns_built_from_buckets(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        # Contact + 5 buckets + Total = 7
        assert w._model.columnCount() == 7

    def test_contact_column_header(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        assert w._model.horizontalHeaderItem(0).text() == "Contact"

    def test_contact_rows_count(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        # 2 contacts + 1 totals row
        assert w._model.rowCount() == 3

    def test_first_contact_name(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        assert w._model.item(0, 0).text() == "Acme Corp"

    def test_bucket_amounts_formatted(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        # Acme Corp current = 5000.00
        assert "5,000.00" in w._model.item(0, 1).text()

    def test_totals_row_is_last(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        last = w._model.rowCount() - 1
        assert w._model.item(last, 0).text() == "TOTALS"

    def test_totals_grand_total_correct(self, qapp) -> None:
        w = _run_widget(qapp, _SAMPLE_AR)
        last = w._model.rowCount() - 1
        total_col = w._model.columnCount() - 1
        total_text = w._model.item(last, total_col).text().replace(",", "")
        assert float(total_text) == pytest.approx(9300.0)

    def test_offline_on_error(self, qapp) -> None:
        from saebooks_desktop.services.api_client import ServerOfflineError
        from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

        w = AgedReceivablesReport()
        with patch(
            "saebooks_desktop.views.reports.aged_receivables.get_aged_receivables",
            side_effect=ServerOfflineError("down"),
        ):
            w._run_report()
        assert not w._offline_label.isHidden()

    def test_empty_state_on_no_contacts(self, qapp) -> None:
        empty = {**_SAMPLE_AR, "contacts": [], "totals": {}}
        w = _run_widget(qapp, empty)
        assert not w._status_label.isHidden()

    def test_export_signal(self, qapp, tmp_path) -> None:
        from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport

        w = AgedReceivablesReport()
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: str(tmp_path / "aged_receivables.csv")
        w._export_btn.click()
        assert received == ["aged_receivables"]
