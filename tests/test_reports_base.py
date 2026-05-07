"""Tests for BaseReportWidget — offscreen Qt, no API calls.

Covers loading/empty/error states, date controls, signals, and the common
scaffold shared by all report widgets.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Concrete sub-class used for testing
# ---------------------------------------------------------------------------


def _make_as_at_widget(qapp):
    from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT, BaseReportWidget

    class _ConcreteAsAt(BaseReportWidget):
        _REPORT_NAME = "test_report"
        _COLUMNS = ["Col A", "Col B"]

        def _run_report(self) -> None:
            pass  # do nothing — tests call _set_status / manipulate model directly

    return _ConcreteAsAt(date_mode=DATE_MODE_AS_AT)


def _make_range_widget(qapp):
    from saebooks_desktop.views.reports.base import DATE_MODE_RANGE, BaseReportWidget

    class _ConcreteRange(BaseReportWidget):
        _REPORT_NAME = "range_report"
        _COLUMNS = ["X", "Y", "Z"]

        def _run_report(self) -> None:
            pass

    return _ConcreteRange(date_mode=DATE_MODE_RANGE)


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestBaseReportWidgetInstantiation:
    def test_as_at_mode_instantiates(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        assert w is not None

    def test_range_mode_instantiates(self, qapp) -> None:
        w = _make_range_widget(qapp)
        assert w is not None

    def test_has_run_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        w = _make_as_at_widget(qapp)
        assert isinstance(w._run_btn, QPushButton)
        assert w._run_btn.text() == "Run"

    def test_has_export_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton

        w = _make_as_at_widget(qapp)
        assert isinstance(w._export_btn, QPushButton)
        assert "Export" in w._export_btn.text()

    def test_has_table_view(self, qapp) -> None:
        from PySide6.QtWidgets import QTableView

        w = _make_as_at_widget(qapp)
        assert isinstance(w._table, QTableView)

    def test_has_model_with_correct_columns(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        assert w._model.columnCount() == 2

    def test_range_model_has_correct_columns(self, qapp) -> None:
        w = _make_range_widget(qapp)
        assert w._model.columnCount() == 3

    def test_offline_banner_hidden_on_init(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        assert w._offline_label.isHidden()

    def test_status_label_hidden_on_init(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        assert w._status_label.isHidden()


# ---------------------------------------------------------------------------
# Date controls
# ---------------------------------------------------------------------------


class TestBaseReportWidgetDateControls:
    def test_as_at_mode_has_date_as_at(self, qapp) -> None:
        from PySide6.QtWidgets import QDateEdit

        w = _make_as_at_widget(qapp)
        assert isinstance(w._date_as_at, QDateEdit)

    def test_as_at_mode_no_from_to(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        assert w._date_from is None
        assert w._date_to is None

    def test_range_mode_has_from_and_to(self, qapp) -> None:
        from PySide6.QtWidgets import QDateEdit

        w = _make_range_widget(qapp)
        assert isinstance(w._date_from, QDateEdit)
        assert isinstance(w._date_to, QDateEdit)

    def test_range_mode_no_as_at(self, qapp) -> None:
        w = _make_range_widget(qapp)
        assert w._date_as_at is None

    def test_as_at_date_returns_iso_string(self, qapp) -> None:
        from PySide6.QtCore import QDate

        w = _make_as_at_widget(qapp)
        w._date_as_at.setDate(QDate(2024, 6, 30))
        assert w._as_at_date() == "2024-06-30"

    def test_from_to_dates_return_iso_strings(self, qapp) -> None:
        from PySide6.QtCore import QDate

        w = _make_range_widget(qapp)
        w._date_from.setDate(QDate(2024, 7, 1))
        w._date_to.setDate(QDate(2024, 12, 31))
        assert w._from_date() == "2024-07-01"
        assert w._to_date() == "2024-12-31"


# ---------------------------------------------------------------------------
# Status label
# ---------------------------------------------------------------------------


class TestBaseReportWidgetStatusLabel:
    def test_set_status_loading_shows_label(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._set_status("loading", "Loading\u2026")
        assert not w._status_label.isHidden()
        assert "Loading" in w._status_label.text()

    def test_set_status_empty_shows_label(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._set_status("empty", "No data.")
        assert not w._status_label.isHidden()

    def test_set_status_error_shows_label(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._set_status("error", "Server offline.")
        assert not w._status_label.isHidden()

    def test_set_status_empty_args_hides_label(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._set_status("loading", "Loading\u2026")
        w._set_status()
        assert w._status_label.isHidden()


# ---------------------------------------------------------------------------
# Offline banner
# ---------------------------------------------------------------------------


class TestBaseReportWidgetOfflineBanner:
    def test_offline_banner_can_be_shown(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._offline_label.setVisible(True)
        assert not w._offline_label.isHidden()

    def test_offline_banner_can_be_hidden(self, qapp) -> None:
        w = _make_as_at_widget(qapp)
        w._offline_label.setVisible(True)
        w._offline_label.setVisible(False)
        assert w._offline_label.isHidden()


# ---------------------------------------------------------------------------
# Export signal
# ---------------------------------------------------------------------------


class TestBaseReportWidgetExportSignal:
    def test_export_button_emits_signal_with_report_name(self, qapp, tmp_path) -> None:
        """E/8: signal is emitted after a successful CSV write (not just on click)."""
        w = _make_as_at_widget(qapp)
        received: list[str] = []
        w.export_requested.connect(received.append)
        # Patch _choose_export_path to avoid QFileDialog in offscreen mode.
        export_path = str(tmp_path / "test_report.csv")
        w._choose_export_path = lambda: export_path
        w._export_btn.click()
        assert received == ["test_report"]

    def test_export_signal_carries_range_report_name(self, qapp, tmp_path) -> None:
        w = _make_range_widget(qapp)
        received: list[str] = []
        w.export_requested.connect(received.append)
        export_path = str(tmp_path / "range_report.csv")
        w._choose_export_path = lambda: export_path
        w._export_btn.click()
        assert received == ["range_report"]

    def test_export_cancelled_does_not_emit_signal(self, qapp) -> None:
        """When the user cancels the dialog (None path), no signal emitted."""
        w = _make_as_at_widget(qapp)
        received: list[str] = []
        w.export_requested.connect(received.append)
        w._choose_export_path = lambda: None
        w._export_btn.click()
        assert received == []
