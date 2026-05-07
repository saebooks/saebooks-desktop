"""Tests for the first-run wizard CompanySelectPage.

API calls are mocked so no real server is needed.
"""
from __future__ import annotations

import os
from unittest.mock import patch, MagicMock

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


@pytest.fixture(autouse=True)
def isolated_settings(monkeypatch, tmp_path):
    from PySide6.QtCore import QSettings
    QSettings.setPath(
        QSettings.Format.IniFormat, QSettings.Scope.UserScope, str(tmp_path)
    )
    monkeypatch.setenv("SAEBOOKS_API_URL", "http://localhost:8042")
    monkeypatch.setenv("SAEBOOKS_API_TOKEN", "tok_test")
    yield
    s = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope, "SAE Engineering", "SAE Books")
    s.clear()
    s.sync()


_TWO_COMPANIES = [
    {"id": "co-001", "name": "Acme Pty Ltd"},
    {"id": "co-002", "name": "Beta Corp"},
]

_ONE_COMPANY = [
    {"id": "co-solo", "name": "Solo Corp"},
]


def _make_page():
    from saebooks_desktop.wizard.pages.company_select import CompanySelectPage
    return CompanySelectPage()


class TestCompanySelectPageStructure:
    def test_instantiates(self, qapp) -> None:
        page = _make_page()
        assert page is not None

    def test_not_complete_before_initialize(self, qapp) -> None:
        page = _make_page()
        assert not page.isComplete()


class TestCompanySelectMultiple:
    def test_list_populated_with_two_companies(self, qapp) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _TWO_COMPANIES

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        assert page._list.count() == 2

    def test_company_names_in_list(self, qapp) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _TWO_COMPANIES

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        names = [page._list.item(i).text() for i in range(page._list.count())]
        assert "Acme Pty Ltd" in names
        assert "Beta Corp" in names

    def test_selection_saves_company_id(self, qapp, isolated_settings) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _TWO_COMPANIES

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        page._list.setCurrentRow(1)

        import importlib
        import saebooks_desktop.services.settings as sm
        importlib.reload(sm)
        assert sm.get_company_id() == "co-002"

    def test_not_complete_without_selection(self, qapp) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _TWO_COMPANIES

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        # No row selected yet
        assert not page.isComplete()

    def test_complete_after_selection(self, qapp) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _TWO_COMPANIES

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        page._list.setCurrentRow(0)
        assert page.isComplete()


class TestCompanySelectSingle:
    def test_single_company_auto_selects(self, qapp, isolated_settings) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _ONE_COMPANY

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        assert page.isComplete()
        assert page._selected_id == "co-solo"

    def test_single_company_persisted(self, qapp, isolated_settings) -> None:
        page = _make_page()
        mock_client = MagicMock()
        mock_client.get.return_value = _ONE_COMPANY

        with patch("saebooks_desktop.services.api_client.APIClient", return_value=mock_client):
            page.initializePage()

        import importlib
        import saebooks_desktop.services.settings as sm
        importlib.reload(sm)
        assert sm.get_company_id() == "co-solo"
