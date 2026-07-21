"""Tests for the dashboard service layer — mocked APIClient, no HTTP calls."""
from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from saebooks_desktop.services.api_client import (
    APIError,
    ModuleUnavailableError,
    ServerOfflineError,
)
from saebooks_desktop.services.dashboard import (
    _trailing_12_month_start,
    build_dashboard_model,
    fetch_aged_payables_total,
    fetch_aged_receivables_total,
    fetch_module_health,
    fetch_profit_loss_summary,
)


# ---------------------------------------------------------------------------
# Individual fetch_* wrappers — verify path + params
# ---------------------------------------------------------------------------


class TestFetchWrappers:
    def test_fetch_profit_loss_summary(self) -> None:
        client = MagicMock()
        client.get.return_value = {"net_profit": 1.0}
        result = fetch_profit_loss_summary(client, "2025-07-18", "2026-07-18")
        client.get.assert_called_once_with(
            "/api/v1/reports/profit_loss",
            params={"from_date": "2025-07-18", "to_date": "2026-07-18"},
        )
        assert result == {"net_profit": 1.0}

    def test_fetch_aged_receivables_total(self) -> None:
        client = MagicMock()
        client.get.return_value = {"totals": {"total": 500.0}}
        result = fetch_aged_receivables_total(client, "2026-07-18")
        client.get.assert_called_once_with(
            "/api/v1/reports/aged_receivables", params={"as_of_date": "2026-07-18"}
        )
        assert result == {"totals": {"total": 500.0}}

    def test_fetch_aged_payables_total(self) -> None:
        client = MagicMock()
        client.get.return_value = {"totals": {"total": 250.0}}
        result = fetch_aged_payables_total(client, "2026-07-18")
        client.get.assert_called_once_with(
            "/api/v1/reports/aged_payables", params={"as_of_date": "2026-07-18"}
        )
        assert result == {"totals": {"total": 250.0}}

    def test_fetch_module_health(self) -> None:
        client = MagicMock()
        client.get.return_value = {"modules": []}
        result = fetch_module_health(client)
        client.get.assert_called_once_with("/api/v1/modules/usage")
        assert result == {"modules": []}


# ---------------------------------------------------------------------------
# Date-window computation
# ---------------------------------------------------------------------------


class TestTrailing12MonthStart:
    def test_pinned_date(self) -> None:
        assert _trailing_12_month_start("2026-07-18") == "2025-07-18"

    def test_feb_29_leap_year_falls_back(self) -> None:
        # 2028 is a leap year, 2027 is not — Feb 29 has no exact prior-year match.
        assert _trailing_12_month_start("2028-02-29") == "2027-02-28"


# ---------------------------------------------------------------------------
# build_dashboard_model composition + error isolation
# ---------------------------------------------------------------------------

_PL = {"income": {"total_income": 10.0}, "expenses": {"total_expenses": 4.0}, "net_profit": 6.0}
_AR = {"totals": {"total": 500.0}}
_AP = {"totals": {"total": 250.0}}
_MODULES = {"modules": [{"id": "capture", "kind": "delegated", "entitled": True, "health": "ok"}]}


class TestBuildDashboardModel:
    def test_all_sections_succeed(self) -> None:
        with mock_dashboard_fetches(pl=_PL, ar=_AR, ap=_AP, modules=_MODULES) as _:
            client = MagicMock()
            model = build_dashboard_model(client, "2026-07-18")

        assert model["pl"] == _PL
        assert model["ar"] == _AR
        assert model["ap"] == _AP
        assert model["modules"] == _MODULES
        assert model["errors"] == {}

    def test_uses_trailing_12_month_window_for_pl(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(pl=_PL, ar=_AR, ap=_AP, modules=_MODULES) as mocks:
            model = build_dashboard_model(client, "2026-07-18")
        mocks["pl"].assert_called_once_with(client, "2025-07-18", "2026-07-18")
        mocks["ar"].assert_called_once_with(client, "2026-07-18")
        mocks["ap"].assert_called_once_with(client, "2026-07-18")
        assert model["pl_active_preset"] == "trailing_12"
        assert model["pl_from_date"] == "2025-07-18"
        assert model["pl_to_date"] == "2026-07-18"

    def test_this_fy_preset_uses_company_fin_year_start_month(self) -> None:
        """A calendar-year-FY company (fin_year_start_month=1) resolves
        'this_fy' to 1 January, not the AU default 1 July."""
        client = MagicMock()
        with mock_dashboard_fetches(pl=_PL, ar=_AR, ap=_AP, modules=_MODULES) as mocks:
            model = build_dashboard_model(
                client, "2026-07-18", preset="this_fy", fin_year_start_month=1
            )
        mocks["pl"].assert_called_once_with(client, "2026-01-01", "2026-07-18")
        assert model["pl_active_preset"] == "this_fy"

    def test_last_fy_preset_ends_at_prior_fy_end_not_today(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(pl=_PL, ar=_AR, ap=_AP, modules=_MODULES) as mocks:
            model = build_dashboard_model(
                client, "2026-07-18", preset="last_fy", fin_year_start_month=7
            )
        mocks["pl"].assert_called_once_with(client, "2025-07-01", "2026-06-30")
        # Aged reports stay "as of today" regardless of the P&L preset.
        mocks["ar"].assert_called_once_with(client, "2026-07-18")
        assert model["pl_active_preset"] == "last_fy"

    def test_module_unavailable_error_isolated_to_its_section(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(
            pl=_PL,
            ar=_AR,
            ap=_AP,
            modules=ModuleUnavailableError("modules module disabled", module="modules"),
        ):
            model = build_dashboard_model(client, "2026-07-18")

        assert model["modules"] is None
        assert "modules" in model["errors"]
        # Other sections still fetched successfully.
        assert model["pl"] == _PL
        assert model["ar"] == _AR
        assert model["ap"] == _AP

    def test_api_error_isolated_to_its_section(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(
            pl=APIError("boom", status_code=500), ar=_AR, ap=_AP, modules=_MODULES
        ):
            model = build_dashboard_model(client, "2026-07-18")

        assert model["pl"] is None
        assert "pl" in model["errors"]
        assert model["ar"] == _AR
        assert model["ap"] == _AP
        assert model["modules"] == _MODULES

    def test_multiple_sections_can_error_independently(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(
            pl=APIError("pl down"),
            ar=ModuleUnavailableError("ar down", module="reports"),
            ap=_AP,
            modules=_MODULES,
        ):
            model = build_dashboard_model(client, "2026-07-18")

        assert set(model["errors"].keys()) == {"pl", "ar"}
        assert model["ap"] == _AP
        assert model["modules"] == _MODULES

    def test_server_offline_error_propagates_out_of_build_dashboard_model(self) -> None:
        client = MagicMock()
        with mock_dashboard_fetches(
            pl=ServerOfflineError("down"), ar=_AR, ap=_AP, modules=_MODULES
        ):
            with pytest.raises(ServerOfflineError):
                build_dashboard_model(client, "2026-07-18")

    def test_server_offline_error_in_later_section_still_propagates(self) -> None:
        """A ServerOfflineError must not be swallowed by the broader APIError
        handling regardless of which section it comes from (exception-order
        regression guard: ServerOfflineError subclasses APIError)."""
        client = MagicMock()
        with mock_dashboard_fetches(
            pl=_PL, ar=_AR, ap=_AP, modules=ServerOfflineError("down")
        ):
            with pytest.raises(ServerOfflineError):
                build_dashboard_model(client, "2026-07-18")


# ---------------------------------------------------------------------------
# Helper: patch the four module-level fetch_* functions used by
# build_dashboard_model, each either returning a value or raising it if
# it's an Exception instance.
# ---------------------------------------------------------------------------


@contextmanager
def mock_dashboard_fetches(pl=None, ar=None, ap=None, modules=None):
    def _side_effect(result):
        if isinstance(result, Exception):
            return MagicMock(side_effect=result)
        return MagicMock(return_value=result)

    with patch(
        "saebooks_desktop.services.dashboard.fetch_profit_loss_summary",
        _side_effect(pl),
    ) as m_pl, patch(
        "saebooks_desktop.services.dashboard.fetch_aged_receivables_total",
        _side_effect(ar),
    ) as m_ar, patch(
        "saebooks_desktop.services.dashboard.fetch_aged_payables_total",
        _side_effect(ap),
    ) as m_ap, patch(
        "saebooks_desktop.services.dashboard.fetch_module_health",
        _side_effect(modules),
    ) as m_modules:
        yield {"pl": m_pl, "ar": m_ar, "ap": m_ap, "modules": m_modules}
