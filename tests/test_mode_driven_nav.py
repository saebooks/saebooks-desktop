"""Mode-driven navigation — the adjudicated verdict revising PoC decision #16.

Navigation branches on the selected company's ``bookkeeping_mode``, never
on tier:

* Cashbook mode: Cashbook / Reports (cashbook summary) / Settings + exactly
  one "Full accounting →" doorway. Contacts omitted (entries are contactless).
* Full mode: full accounting nav, NO Cashbook primary item; "Switch to
  cashbook mode" lives in the Settings view.
* Mode flips (doorway upgrade, Settings downgrade) re-render the nav.

All API calls are mocked so no server is needed.
"""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_window(qapp, mode: str):
    """Build MainWindow with the bookkeeping mode forced and HTTP mocked."""
    from saebooks_desktop.main_window import MainWindow

    mock_transport = MagicMock()
    mock_transport.is_reachable.return_value = False

    with (
        patch(
            "saebooks_desktop.main_window.resolve_bookkeeping_mode",
            return_value=mode,
        ),
        patch("saebooks_desktop.views.invoices.list_invoices", return_value=[]),
        patch("saebooks_desktop.views.bills.list_bills", return_value=[]),
        patch(
            "saebooks_desktop.services.api_client.APIClient.resolve_transport",
            return_value=mock_transport,
        ),
        patch("saebooks_desktop.cache.sync.SyncEngine.isRunning", return_value=False),
    ):
        window = MainWindow()
    return window


def _nav_labels(window) -> list[str]:
    return [window._nav.item(i).text() for i in range(window._nav.count())]


# ---------------------------------------------------------------------------
# Full mode
# ---------------------------------------------------------------------------


class TestFullModeNav:
    def test_no_cashbook_primary_item(self, qapp) -> None:
        """Full mode must NOT carry a Cashbook primary nav item."""
        window = _make_window(qapp, "full")
        assert "Cashbook" not in _nav_labels(window)

    def test_no_full_accounting_doorway(self, qapp) -> None:
        window = _make_window(qapp, "full")
        assert not any("Full accounting" in lbl for lbl in _nav_labels(window))

    def test_full_nav_keeps_accounting_sections(self, qapp) -> None:
        labels = _nav_labels(_make_window(qapp, "full"))
        for expected in (
            "Dashboard",
            "Contacts",
            "Sales",
            "Purchases",
            "Reports",
            "Settings",
        ):
            assert expected in labels, f"{expected} missing from full-mode nav"

    def test_full_mode_reports_routes_to_full_reports_view(self, qapp) -> None:
        from saebooks_desktop.views.reports.reports_view import ReportsView

        window = _make_window(qapp, "full")
        row = window._nav_row_by_key["Reports"]
        window._nav.setCurrentRow(row)
        assert isinstance(window._stack.currentWidget(), ReportsView)

    def test_full_mode_starts_on_dashboard(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        window = _make_window(qapp, "full")
        assert window._nav.currentRow() == 0
        assert isinstance(window._stack.currentWidget(), DashboardView)

    def test_switch_to_cashbook_lives_in_settings(self, qapp) -> None:
        """The downgrade action is a Settings affordance, not a nav item."""
        window = _make_window(qapp, "full")
        assert "Settings" in _nav_labels(window)
        assert hasattr(window._settings_view._general_tab, "_switch_to_cashbook_btn")


# ---------------------------------------------------------------------------
# Cashbook mode
# ---------------------------------------------------------------------------


class TestCashbookModeNav:
    def test_exact_nav_items(self, qapp) -> None:
        """Cashbook nav is exactly Cashbook / Reports / Settings / doorway."""
        window = _make_window(qapp, "cashbook")
        assert _nav_labels(window) == [
            "Cashbook",
            "Reports",
            "Settings",
            "Full accounting →",
        ]

    def test_contacts_omitted(self, qapp) -> None:
        """Cashbook entries are contactless — no Contacts nav item."""
        window = _make_window(qapp, "cashbook")
        assert "Contacts" not in _nav_labels(window)

    def test_exactly_one_doorway_item(self, qapp) -> None:
        labels = _nav_labels(_make_window(qapp, "cashbook"))
        doorways = [lbl for lbl in labels if "Full accounting" in lbl]
        assert len(doorways) == 1

    def test_starts_on_cashbook_view(self, qapp) -> None:
        from saebooks_desktop.views.cashbook import CashbookView

        window = _make_window(qapp, "cashbook")
        assert window._nav.currentRow() == 0
        assert isinstance(window._stack.currentWidget(), CashbookView)

    def test_reports_routes_to_cashbook_summary(self, qapp) -> None:
        """The Reports item shows the cashbook summary, not the full suite."""
        from saebooks_desktop.views.cashbook_report import CashbookReportView

        window = _make_window(qapp, "cashbook")
        row = window._nav_row_by_key["Cashbook Reports"]
        assert window._nav.item(row).text() == "Reports"
        window._nav.setCurrentRow(row)
        assert isinstance(window._stack.currentWidget(), CashbookReportView)

    def test_doorway_routes_to_explainer(self, qapp) -> None:
        """The doorway opens the explainer view — no mode flip on click."""
        from saebooks_desktop.views.full_accounting_door import (
            FullAccountingDoorView,
        )

        window = _make_window(qapp, "cashbook")
        row = window._nav_row_by_key["Full Accounting"]
        window._nav.setCurrentRow(row)
        assert isinstance(window._stack.currentWidget(), FullAccountingDoorView)
        # Navigating to the doorway alone must not change the mode.
        assert window._bookkeeping_mode == "cashbook"

    def test_search_shortcut_is_noop(self, qapp) -> None:
        """Ctrl+F must not crash or navigate — Search is not in this nav."""
        window = _make_window(qapp, "cashbook")
        before = window._stack.currentIndex()
        window._on_search_shortcut()
        assert window._stack.currentIndex() == before

    def test_search_result_routing_is_noop(self, qapp) -> None:
        window = _make_window(qapp, "cashbook")
        before = window._stack.currentIndex()
        window._on_search_result_selected("invoice", "inv-1")
        assert window._stack.currentIndex() == before


# ---------------------------------------------------------------------------
# Mode flips re-render the nav
# ---------------------------------------------------------------------------


class TestModeFlipRerendersNav:
    def test_doorway_upgrade_rerenders_to_full(self, qapp) -> None:
        """upgraded signal from the doorway flips the nav to full mode."""
        window = _make_window(qapp, "cashbook")
        window._full_accounting_door.upgraded.emit()
        labels = _nav_labels(window)
        assert "Cashbook" not in labels
        assert "Contacts" in labels
        assert window._bookkeeping_mode == "full"

    def test_settings_downgrade_rerenders_to_cashbook(self, qapp) -> None:
        """bookkeeping_mode_changed('cashbook') flips the nav to cashbook."""
        window = _make_window(qapp, "full")
        window._settings_view.bookkeeping_mode_changed.emit("cashbook")
        assert _nav_labels(window) == [
            "Cashbook",
            "Reports",
            "Settings",
            "Full accounting →",
        ]
        assert window._bookkeeping_mode == "cashbook"

    def test_apply_bookkeeping_mode_ignores_invalid(self, qapp) -> None:
        window = _make_window(qapp, "full")
        before = _nav_labels(window)
        window.apply_bookkeeping_mode("hybrid")
        assert _nav_labels(window) == before
        assert window._bookkeeping_mode == "full"

    def test_refresh_company_context_rerenders(self, qapp) -> None:
        """Company switch path: re-resolve mode and re-render the nav."""
        window = _make_window(qapp, "full")
        with patch(
            "saebooks_desktop.main_window.resolve_bookkeeping_mode",
            return_value="cashbook",
        ):
            window.refresh_company_context()
        assert window._bookkeeping_mode == "cashbook"
        assert "Contacts" not in _nav_labels(window)

    def test_flip_selects_first_item(self, qapp) -> None:
        from saebooks_desktop.views.cashbook import CashbookView

        window = _make_window(qapp, "full")
        window.apply_bookkeeping_mode("cashbook")
        assert window._nav.currentRow() == 0
        assert isinstance(window._stack.currentWidget(), CashbookView)


# ---------------------------------------------------------------------------
# Full-accounting doorway (explainer + upgrade action)
# ---------------------------------------------------------------------------


class TestFullAccountingDoorView:
    def _make_view(self, qapp):
        from saebooks_desktop.views.full_accounting_door import (
            FullAccountingDoorView,
        )

        return FullAccountingDoorView()

    def test_explainer_text_promises_lossless_upgrade(self, qapp) -> None:
        view = self._make_view(qapp)
        text = view.findChild(type(view._error_label), "door_body").text()
        assert "double-entry ledger" in text
        assert "real journal" in text
        assert "Nothing is re-keyed" in text

    def test_upgrade_confirms_then_calls_engine(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = self._make_view(qapp)
        emitted: list[bool] = []
        view.upgraded.connect(lambda: emitted.append(True))

        with (
            patch(
                "saebooks_desktop.views.full_accounting_door.get_company_id",
                return_value="co-1",
            ),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ) as mock_q,
            patch(
                "saebooks_desktop.views.full_accounting_door.set_bookkeeping_mode",
                return_value={"bookkeeping_mode": "full"},
            ) as mock_set,
        ):
            view._upgrade_btn.click()

        mock_q.assert_called_once()
        assert mock_set.call_args[0][1] == "co-1"
        assert mock_set.call_args[0][2] == "full"
        assert emitted == [True]

    def test_upgrade_cancelled_makes_no_call(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = self._make_view(qapp)
        emitted: list[bool] = []
        view.upgraded.connect(lambda: emitted.append(True))

        with (
            patch(
                "saebooks_desktop.views.full_accounting_door.get_company_id",
                return_value="co-1",
            ),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.No,
            ),
            patch(
                "saebooks_desktop.views.full_accounting_door.set_bookkeeping_mode"
            ) as mock_set,
        ):
            view._upgrade_btn.click()

        mock_set.assert_not_called()
        assert emitted == []

    def test_engine_error_surfaced_no_signal(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.api_client import APIError

        view = self._make_view(qapp)
        emitted: list[bool] = []
        view.upgraded.connect(lambda: emitted.append(True))

        with (
            patch(
                "saebooks_desktop.views.full_accounting_door.get_company_id",
                return_value="co-1",
            ),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "saebooks_desktop.views.full_accounting_door.set_bookkeeping_mode",
                side_effect=APIError("engine says no", status_code=422),
            ),
        ):
            view._upgrade_btn.click()

        assert view._error_label.isVisibleTo(view)
        assert "engine says no" in view._error_label.text()
        assert emitted == []

    def test_offline_error_surfaced(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.api_client import ServerOfflineError

        view = self._make_view(qapp)

        with (
            patch(
                "saebooks_desktop.views.full_accounting_door.get_company_id",
                return_value="co-1",
            ),
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch(
                "saebooks_desktop.views.full_accounting_door.set_bookkeeping_mode",
                side_effect=ServerOfflineError("offline"),
            ),
        ):
            view._upgrade_btn.click()

        assert view._error_label.isVisibleTo(view)
        assert "offline" in view._error_label.text()

    def test_no_company_selected_error(self, qapp) -> None:
        view = self._make_view(qapp)
        with patch(
            "saebooks_desktop.views.full_accounting_door.get_company_id",
            return_value="",
        ):
            view._upgrade_btn.click()
        assert view._error_label.isVisibleTo(view)


# ---------------------------------------------------------------------------
# Settings: switch to cashbook mode (downgrade)
# ---------------------------------------------------------------------------


class TestSettingsSwitchToCashbook:
    def _make_view(self, qapp, company: dict | None = None):
        from saebooks_desktop.views.settings_view import SettingsView

        with (
            patch(
                "saebooks_desktop.views.settings_view.get_company_id",
                return_value="co-1",
            ),
            patch(
                "saebooks_desktop.views.settings_view.get_company",
                return_value=company
                or {"name": "ACME", "bookkeeping_mode": "full"},
            ),
            patch(
                "saebooks_desktop.views.settings_view.list_tax_codes",
                return_value=[],
            ),
            patch(
                "saebooks_desktop.views.settings_view.get_current_user",
                return_value={"email": "a@b.c"},
            ),
            patch(
                "saebooks_desktop.views.settings_view.get_version",
                return_value={"version": "1.0"},
            ),
            patch(
                "saebooks_desktop.views.settings_view.get_server_url",
                return_value="http://x",
            ),
        ):
            view = SettingsView()
        return view

    def test_button_visible_in_full_mode(self, qapp) -> None:
        view = self._make_view(qapp)
        btn = view._general_tab._switch_to_cashbook_btn
        assert btn.isVisibleTo(view._general_tab)
        assert view._general_tab._mode_label.text() == "Full accounting"

    def test_button_hidden_in_cashbook_mode(self, qapp) -> None:
        view = self._make_view(
            qapp, company={"name": "ACME", "bookkeeping_mode": "cashbook"}
        )
        btn = view._general_tab._switch_to_cashbook_btn
        assert not btn.isVisibleTo(view._general_tab)
        assert view._general_tab._mode_label.text() == "Cashbook (simplified)"

    def test_successful_downgrade_emits_mode_changed(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = self._make_view(qapp)
        emitted: list[str] = []
        view.bookkeeping_mode_changed.connect(emitted.append)

        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(QMessageBox, "information"),
            patch(
                "saebooks_desktop.services.cashbook.set_bookkeeping_mode",
                return_value={"bookkeeping_mode": "cashbook"},
            ) as mock_set,
        ):
            view._general_tab._switch_to_cashbook_btn.click()

        assert mock_set.call_args[0][1] == "co-1"
        assert mock_set.call_args[0][2] == "cashbook"
        assert emitted == ["cashbook"]
        # Button hides and label updates once the company is in cashbook mode.
        assert not view._general_tab._switch_to_cashbook_btn.isVisibleTo(
            view._general_tab
        )

    def test_engine_refusal_surfaces_message_no_signal(self, qapp) -> None:
        """Open-AR refusal: the engine's 422 message reaches the user."""
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.api_client import APIError

        view = self._make_view(qapp)
        emitted: list[str] = []
        view.bookkeeping_mode_changed.connect(emitted.append)

        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.Yes,
            ),
            patch.object(QMessageBox, "critical") as mock_crit,
            patch(
                "saebooks_desktop.services.cashbook.set_bookkeeping_mode",
                side_effect=APIError(
                    "cannot downgrade: 2 open invoices", status_code=422
                ),
            ),
        ):
            view._general_tab._switch_to_cashbook_btn.click()

        assert emitted == []
        # The engine's message is surfaced verbatim in the dialog body.
        assert "2 open invoices" in mock_crit.call_args[0][2]

    def test_cancel_makes_no_call(self, qapp) -> None:
        from PySide6.QtWidgets import QMessageBox

        view = self._make_view(qapp)

        with (
            patch.object(
                QMessageBox,
                "question",
                return_value=QMessageBox.StandardButton.No,
            ),
            patch(
                "saebooks_desktop.services.cashbook.set_bookkeeping_mode"
            ) as mock_set,
        ):
            view._general_tab._switch_to_cashbook_btn.click()

        mock_set.assert_not_called()
