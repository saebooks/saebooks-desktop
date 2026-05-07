"""Tests for saebooks_desktop.services.settings.

Uses a throw-away QSettings org/app pair (via monkeypatching `_s`) to avoid
touching real user settings.  Pattern borrowed from test_smoke.py.
"""
from __future__ import annotations

import importlib
import os

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
def isolated_settings(monkeypatch):
    """Redirect _s() to an isolated QSettings store and strip env overrides."""
    monkeypatch.delenv("SAEBOOKS_API_URL", raising=False)
    monkeypatch.delenv("SAEBOOKS_API_TOKEN", raising=False)

    import saebooks_desktop.services.settings as m

    def _test_settings():
        from PySide6.QtCore import QSettings
        return QSettings("_saebooks_test_", "_saebooks_settings_test_")

    # Reload first to get a clean slate, THEN patch _s.
    importlib.reload(m)
    monkeypatch.setattr(m, "_s", _test_settings)
    yield
    # Clean up the throw-away store
    from PySide6.QtCore import QSettings
    s = QSettings("_saebooks_test_", "_saebooks_settings_test_")
    s.clear()
    s.sync()


def _m():
    import saebooks_desktop.services.settings as m
    return m


# ---------------------------------------------------------------------------
# Server URL
# ---------------------------------------------------------------------------


class TestServerUrl:
    def test_default_is_empty(self, qapp, isolated_settings) -> None:
        assert _m().get_server_url() == ""

    def test_set_and_get_round_trip(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_server_url("http://saebooks.local:8042")
        assert m.get_server_url() == "http://saebooks.local:8042"

    def test_trailing_slash_stripped(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_server_url("http://saebooks.local:8042/")
        assert m.get_server_url() == "http://saebooks.local:8042"

    def test_set_server_url_also_sets_api_url(self, qapp, isolated_settings) -> None:
        """set_server_url must keep api/url in sync for APIClient."""
        m = _m()
        m.set_server_url("http://sync-test:8042")
        # Read back via _s() which is now the test store
        s = m._s()
        assert str(s.value("api/url", "")) == "http://sync-test:8042"


# ---------------------------------------------------------------------------
# Auth token
# ---------------------------------------------------------------------------


class TestAuthToken:
    def test_default_is_empty(self, qapp, isolated_settings) -> None:
        assert _m().get_auth_token() == ""

    def test_set_and_get_round_trip(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_auth_token("tok_abc123")
        assert m.get_auth_token() == "tok_abc123"

    def test_set_auth_token_also_sets_api_token(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_auth_token("tok_xyz")
        s = m._s()
        assert str(s.value("api/token", "")) == "tok_xyz"


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


class TestCompanyId:
    def test_default_is_empty(self, qapp, isolated_settings) -> None:
        assert _m().get_company_id() == ""

    def test_set_and_get_round_trip(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_company_id("company-uuid-001")
        assert m.get_company_id() == "company-uuid-001"


# ---------------------------------------------------------------------------
# is_first_run
# ---------------------------------------------------------------------------


class TestIsFirstRun:
    def test_is_first_run_when_no_url_saved(self, qapp, isolated_settings) -> None:
        assert _m().is_first_run() is True

    def test_not_first_run_after_url_set(self, qapp, isolated_settings) -> None:
        m = _m()
        m.set_server_url("http://saebooks.local:8042")
        assert m.is_first_run() is False

    def test_env_var_bypasses_first_run(self, qapp, isolated_settings, monkeypatch) -> None:
        monkeypatch.setenv("SAEBOOKS_API_URL", "http://env-server:8042")
        assert _m().is_first_run() is False
