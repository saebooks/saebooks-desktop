"""Tests for DashboardView — offscreen Qt, mocked build_dashboard_model."""
from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from saebooks_desktop.services.api_client import ServerOfflineError


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_PATCH_BUILD = "saebooks_desktop.views.dashboard.build_dashboard_model"

_SAMPLE_MODEL = {
    "pl": {
        "income": {"total_income": 120000.0},
        "expenses": {"total_expenses": 80000.0},
        "net_profit": 40000.0,
    },
    "ar": {"totals": {"total": 5000.5}},
    "ap": {"totals": {"total": 2500.25}},
    "modules": {
        "modules": [
            {"id": "capture", "kind": "delegated", "entitled": True, "health": "ok"},
            {"id": "billing", "kind": "delegated", "entitled": True, "health": "degraded"},
        ]
    },
    "errors": {},
}

_HEALTHY_MODULES_MODEL = {
    "pl": None,
    "ar": None,
    "ap": None,
    "modules": {
        "modules": [
            {"id": "capture", "kind": "delegated", "entitled": True, "health": "ok"},
            {"id": "core", "kind": "core", "entitled": True, "health": "ok"},
        ]
    },
    "errors": {},
}


def _make_view_and_load(qapp, model=None, side_effect=None):
    from saebooks_desktop.views.dashboard import DashboardView

    view = DashboardView()
    if side_effect is not None:
        with patch(_PATCH_BUILD, side_effect=side_effect):
            view.load(client=MagicMock())
    else:
        with patch(_PATCH_BUILD, return_value=model):
            view.load(client=MagicMock())
    return view


# ---------------------------------------------------------------------------
# Instantiation
# ---------------------------------------------------------------------------


class TestDashboardViewInstantiation:
    def test_instantiates_without_network_call(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        with patch(_PATCH_BUILD) as mocked:
            view = DashboardView()
        assert view is not None
        mocked.assert_not_called()

    def test_has_refresh_button(self, qapp) -> None:
        from PySide6.QtWidgets import QPushButton
        from saebooks_desktop.views.dashboard import DashboardView

        view = DashboardView()
        assert isinstance(view._refresh_btn, QPushButton)
        assert view._refresh_btn.objectName() == "refresh_btn"

    def test_has_offline_banner_hidden_by_default(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        view = DashboardView()
        assert view._offline_banner.objectName() == "offline_banner"
        assert view._offline_banner.isHidden()

    def test_all_five_tiles_present(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        view = DashboardView()
        assert set(view._tile_values.keys()) == {
            "revenue",
            "expenses",
            "net_profit",
            "receivables",
            "payables",
        }


# ---------------------------------------------------------------------------
# Population
# ---------------------------------------------------------------------------


class TestDashboardViewPopulation:
    def test_revenue_tile_formatted(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._tile_values["revenue"].text() == "120,000.00"

    def test_expenses_tile_formatted(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._tile_values["expenses"].text() == "80,000.00"

    def test_net_profit_tile_formatted(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._tile_values["net_profit"].text() == "40,000.00"

    def test_receivables_tile_formatted(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._tile_values["receivables"].text() == "5,000.50"

    def test_payables_tile_formatted(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._tile_values["payables"].text() == "2,500.25"

    def test_offline_banner_hidden_when_data_loads(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert view._offline_banner.isHidden()

    def test_section_error_shows_dash_on_tile(self, qapp) -> None:
        model = dict(_SAMPLE_MODEL)
        model["pl"] = None
        model["errors"] = {"pl": "reports module unavailable"}
        view = _make_view_and_load(qapp, model=model)
        assert view._tile_values["revenue"].text() == "—"
        assert view._tile_values["expenses"].text() == "—"
        assert view._tile_values["net_profit"].text() == "—"
        # Unaffected tiles still populated.
        assert view._tile_values["receivables"].text() == "5,000.50"

    def test_aged_section_error_shows_dash(self, qapp) -> None:
        model = dict(_SAMPLE_MODEL)
        model["ar"] = None
        model["errors"] = {"ar": "reports module unavailable"}
        view = _make_view_and_load(qapp, model=model)
        assert view._tile_values["receivables"].text() == "—"
        assert view._tile_values["payables"].text() == "2,500.25"


# ---------------------------------------------------------------------------
# Offline
# ---------------------------------------------------------------------------


class TestDashboardViewOffline:
    def test_offline_banner_shown_on_server_offline_error(self, qapp) -> None:
        view = _make_view_and_load(qapp, side_effect=ServerOfflineError("down"))
        assert not view._offline_banner.isHidden()

    def test_load_never_raises_on_unexpected_exception(self, qapp) -> None:
        # load() must swallow any exception, not just ServerOfflineError.
        view = _make_view_and_load(qapp, side_effect=RuntimeError("boom"))
        assert view is not None

    def test_load_creates_default_api_client_when_none_passed(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        view = DashboardView()
        with patch(_PATCH_BUILD, return_value=_SAMPLE_MODEL) as mocked, patch(
            "saebooks_desktop.views.dashboard.APIClient"
        ) as mock_client_cls:
            mock_client_cls.return_value = MagicMock()
            view.load()
        mock_client_cls.assert_called_once()
        mocked.assert_called_once()


# ---------------------------------------------------------------------------
# Refresh button
# ---------------------------------------------------------------------------


class TestDashboardViewRefresh:
    def test_refresh_button_re_calls_load(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)

        with patch(_PATCH_BUILD, return_value=_SAMPLE_MODEL) as mocked:
            view._refresh_btn.click()

        mocked.assert_called_once()

    def test_refresh_reuses_last_client(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import DashboardView

        view = DashboardView()
        client = MagicMock()
        with patch(_PATCH_BUILD, return_value=_SAMPLE_MODEL):
            view.load(client=client)

        with patch(_PATCH_BUILD, return_value=_SAMPLE_MODEL) as mocked:
            view._refresh_btn.click()

        # Same client instance used on refresh (no client passed explicitly).
        assert mocked.call_args[0][0] is client


# ---------------------------------------------------------------------------
# Modules strip
# ---------------------------------------------------------------------------


class TestExtractPlTotals:
    """Pure-function tests for the P&L fallback chain — no Qt required."""

    def test_nested_primary_shape(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_pl_totals

        pl = {
            "income": {"total_income": 100.0},
            "expenses": {"total_expenses": 40.0},
            "net_profit": 60.0,
        }
        assert _extract_pl_totals(pl) == (100.0, 40.0, 60.0)

    def test_flat_fallback_keys(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_pl_totals

        pl = {"income_total": 100.0, "expense_total": 40.0}
        revenue, expenses, net_profit = _extract_pl_totals(pl)
        assert revenue == 100.0
        assert expenses == 40.0
        # net_profit derived from revenue - expenses when absent.
        assert net_profit == 60.0

    def test_sum_line_amounts_fallback(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_pl_totals

        pl = {
            "income": {"INCOME": [{"amount": 30.0}, {"amount": 20.0}]},
            "expenses": {"EXPENSE": [{"amount": 15.0}]},
        }
        revenue, expenses, net_profit = _extract_pl_totals(pl)
        assert revenue == 50.0
        assert expenses == 15.0
        assert net_profit == 35.0

    def test_no_data_returns_all_none(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_pl_totals

        assert _extract_pl_totals({}) == (None, None, None)

    def test_string_totals_coerced_to_float(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_pl_totals

        pl = {
            "income": {"total_income": "100.00"},
            "expenses": {"total_expenses": "40.00"},
            "net_profit": "60.00",
        }
        assert _extract_pl_totals(pl) == (100.0, 40.0, 60.0)


class TestExtractAgedTotal:
    """Pure-function tests for the aged-report fallback chain — no Qt required."""

    def test_nested_primary_shape(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_aged_total

        assert _extract_aged_total({"totals": {"total": 500.0}}) == "500.00"

    def test_flat_grand_total_fallback(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_aged_total

        assert _extract_aged_total({"grand_total": 250.5}) == "250.50"

    def test_flat_total_fallback(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_aged_total

        assert _extract_aged_total({"total": 99.9}) == "99.90"

    def test_sum_over_contacts_fallback(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_aged_total

        rep = {
            "contacts": [
                {"contact_name": "Acme", "total": 100.0},
                {"contact_name": "Beta", "total": 50.0},
            ]
        }
        assert _extract_aged_total(rep) == "150.00"

    def test_no_data_returns_none(self, qapp) -> None:
        from saebooks_desktop.views.dashboard import _extract_aged_total

        assert _extract_aged_total({}) is None
        assert _extract_aged_total(None) is None

    def test_buckets_list_of_names_is_not_summed(self, qapp) -> None:
        """Regression guard: 'buckets' is bucket-name strings, not summable
        amounts — must not be treated as a fallback total source."""
        from saebooks_desktop.views.dashboard import _extract_aged_total

        rep = {"buckets": ["current", "1-30 days", "31-60 days"]}
        assert _extract_aged_total(rep) is None


class TestDashboardViewModulesStrip:
    def test_degraded_delegated_module_shown(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_SAMPLE_MODEL)
        assert "billing" in view._modules_label.text()
        assert "degraded" in view._modules_label.text()
        assert "capture" not in view._modules_label.text()

    def test_all_healthy_shows_message(self, qapp) -> None:
        view = _make_view_and_load(qapp, model=_HEALTHY_MODULES_MODEL)
        assert view._modules_label.text() == "All modules healthy"

    def test_not_entitled_module_shown_even_if_healthy(self, qapp) -> None:
        model = dict(_SAMPLE_MODEL)
        model["modules"] = {
            "modules": [
                {"id": "payroll", "kind": "delegated", "entitled": False, "health": "ok"},
            ]
        }
        view = _make_view_and_load(qapp, model=model)
        assert "payroll" in view._modules_label.text()

    def test_modules_section_error_shows_message(self, qapp) -> None:
        model = dict(_SAMPLE_MODEL)
        model["modules"] = None
        model["errors"] = {"modules": "modules module unavailable"}
        view = _make_view_and_load(qapp, model=model)
        assert view._modules_label.text() == "modules module unavailable"

    def test_core_module_degraded_not_flagged(self, qapp) -> None:
        """Only kind == 'delegated' modules are surfaced for health degradation."""
        model = dict(_SAMPLE_MODEL)
        model["modules"] = {
            "modules": [
                {"id": "core-engine", "kind": "core", "entitled": True, "health": "degraded"},
            ]
        }
        view = _make_view_and_load(qapp, model=model)
        assert view._modules_label.text() == "All modules healthy"
