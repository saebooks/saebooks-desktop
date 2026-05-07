"""Tests for ReportsView — offscreen Qt, no API calls.

Tests the list+stack container: correct list items, navigation, widget types.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from unittest.mock import patch


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_reports_view(qapp):
    """Create ReportsView with all report service calls patched to avoid HTTP."""
    patches = [
        patch("saebooks_desktop.views.reports.balance_sheet.get_balance_sheet", return_value={}),
        patch("saebooks_desktop.views.reports.profit_loss.get_profit_loss", return_value={}),
        patch("saebooks_desktop.views.reports.trial_balance.get_trial_balance", return_value={}),
        patch("saebooks_desktop.views.reports.aged_receivables.get_aged_receivables", return_value={}),
        patch("saebooks_desktop.views.reports.aged_payables.get_aged_payables", return_value={}),
    ]
    for p in patches:
        p.start()
    try:
        from saebooks_desktop.views.reports.reports_view import ReportsView
        view = ReportsView()
    finally:
        for p in patches:
            p.stop()
    return view


class TestReportsViewInstantiation:
    def test_instantiates_without_crash(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert view is not None

    def test_has_report_list(self, qapp) -> None:
        from PySide6.QtWidgets import QListWidget
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert isinstance(view._report_list, QListWidget)

    def test_has_stacked_widget(self, qapp) -> None:
        from PySide6.QtWidgets import QStackedWidget
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert isinstance(view._stack, QStackedWidget)


class TestReportsViewListItems:
    def test_list_has_five_items(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert view._report_list.count() == 5

    def test_list_contains_balance_sheet(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        labels = [view._report_list.item(i).text() for i in range(view._report_list.count())]
        assert "Balance Sheet" in labels

    def test_list_contains_profit_loss(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        labels = [view._report_list.item(i).text() for i in range(view._report_list.count())]
        assert "Profit & Loss" in labels

    def test_list_contains_trial_balance(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        labels = [view._report_list.item(i).text() for i in range(view._report_list.count())]
        assert "Trial Balance" in labels

    def test_list_contains_aged_receivables(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        labels = [view._report_list.item(i).text() for i in range(view._report_list.count())]
        assert "Aged Receivables" in labels

    def test_list_contains_aged_payables(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        labels = [view._report_list.item(i).text() for i in range(view._report_list.count())]
        assert "Aged Payables" in labels


class TestReportsViewNavigation:
    def test_stack_has_five_pages(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert view._stack.count() == 5

    def test_selecting_row_changes_stack(self, qapp) -> None:
        from PySide6.QtWidgets import QApplication
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        view._report_list.setCurrentRow(0)
        QApplication.processEvents()
        idx_0 = view._stack.currentIndex()

        view._report_list.setCurrentRow(2)
        QApplication.processEvents()
        idx_2 = view._stack.currentIndex()

        assert idx_0 != idx_2

    def test_first_item_selected_by_default(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        assert view._report_list.currentRow() == 0

    def test_current_report_widget_returns_widget(self, qapp) -> None:
        from PySide6.QtWidgets import QWidget
        from saebooks_desktop.views.reports.reports_view import ReportsView

        view = ReportsView()
        w = view.current_report_widget()
        assert isinstance(w, QWidget)
