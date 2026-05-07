"""Tests for SettingsView (views/settings_view.py).

All tests run offscreen — no display server required.
API calls are intercepted via monkeypatching the service layer.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("SAEBOOKS_API_URL", "http://127.0.0.1:19999")
os.environ.setdefault("SAEBOOKS_API_TOKEN", "test-token")

import pytest


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


_COMPANY_PAYLOAD = {
    "id": "company-001",
    "name": "ACME Pty Ltd",
    "abn": "12 345 678 901",
    "acn": "123 456 789",
    "financial_year_start_month": 7,
}

_TAX_CODES = [
    {"code": "GST", "name": "Goods and Services Tax"},
    {"code": "FRE", "name": "GST Free"},
    {"code": "IMP", "name": "Input Taxed"},
]

_VERSION_PAYLOAD = {
    "version": "0.9.0",
    "edition": "Community",
}

_ME_PAYLOAD = {"email": "admin@saebooks.local", "username": "admin"}


@pytest.fixture()
def patched_services(monkeypatch):
    """Patch company_settings service functions to return mock data."""
    import saebooks_desktop.views.settings_view as m

    monkeypatch.setattr(m, "get_company", lambda client, company_id: _COMPANY_PAYLOAD)
    monkeypatch.setattr(m, "list_tax_codes", lambda client: _TAX_CODES)
    monkeypatch.setattr(m, "get_current_user", lambda client: _ME_PAYLOAD)
    monkeypatch.setattr(m, "get_version", lambda client: _VERSION_PAYLOAD)
    monkeypatch.setattr(m, "patch_company", lambda client, cid, data: data)
    monkeypatch.setattr(m, "get_company_id", lambda: "company-001")
    monkeypatch.setattr(m, "get_server_url", lambda: "http://saebooks.local:8042")


@pytest.fixture()
def view(qapp, patched_services):
    from saebooks_desktop.views.settings_view import SettingsView

    return SettingsView()


# ---------------------------------------------------------------------------
# Tab structure
# ---------------------------------------------------------------------------

class TestTabStructure:
    def test_has_four_tabs(self, view) -> None:
        assert view._tabs.count() == 4

    def test_tab_0_label_general(self, view) -> None:
        assert view._tabs.tabText(0) == "General"

    def test_tab_1_label_tax(self, view) -> None:
        assert view._tabs.tabText(1) == "Tax"

    def test_tab_2_label_connection(self, view) -> None:
        assert view._tabs.tabText(2) == "Connection"

    def test_tab_3_label_about(self, view) -> None:
        assert view._tabs.tabText(3) == "About"


# ---------------------------------------------------------------------------
# General tab
# ---------------------------------------------------------------------------

class TestGeneralTab:
    def test_company_name_populated(self, view) -> None:
        assert view._general_tab._name_edit.text() == "ACME Pty Ltd"

    def test_abn_populated(self, view) -> None:
        assert view._general_tab._abn_edit.text() == "12 345 678 901"

    def test_acn_populated(self, view) -> None:
        assert view._general_tab._acn_edit.text() == "123 456 789"

    def test_abn_is_readonly(self, view) -> None:
        assert view._general_tab._abn_edit.isReadOnly()

    def test_acn_is_readonly(self, view) -> None:
        assert view._general_tab._acn_edit.isReadOnly()

    def test_fy_start_month_set(self, view) -> None:
        # Month 7 = July = index 6
        assert view._general_tab._fy_start_combo.currentIndex() == 6

    def test_fy_combo_has_12_months(self, view) -> None:
        assert view._general_tab._fy_start_combo.count() == 12

    def test_currency_is_aud(self, view) -> None:
        assert view._general_tab._currency_edit.text() == "AUD"

    def test_currency_is_readonly(self, view) -> None:
        assert view._general_tab._currency_edit.isReadOnly()

    def test_save_button_exists(self, view) -> None:
        assert view._general_tab._save_btn is not None

    def test_save_calls_patch(self, qapp, monkeypatch) -> None:
        """Clicking Save calls patch_company with the form data."""
        import saebooks_desktop.views.settings_view as m

        calls: list[dict] = []

        monkeypatch.setattr(m, "get_company", lambda client, cid: _COMPANY_PAYLOAD)
        monkeypatch.setattr(m, "list_tax_codes", lambda client: _TAX_CODES)
        monkeypatch.setattr(m, "get_current_user", lambda client: _ME_PAYLOAD)
        monkeypatch.setattr(m, "get_version", lambda client: _VERSION_PAYLOAD)
        monkeypatch.setattr(m, "get_company_id", lambda: "company-001")
        monkeypatch.setattr(m, "get_server_url", lambda: "http://saebooks.local:8042")

        def _capture_patch(client, cid, data):
            calls.append(data)
            return data

        monkeypatch.setattr(m, "patch_company", _capture_patch)

        # Suppress the QMessageBox that follows a successful save
        from PySide6.QtWidgets import QMessageBox
        monkeypatch.setattr(QMessageBox, "information", lambda *a, **kw: None)

        from saebooks_desktop.views.settings_view import SettingsView

        v = SettingsView()
        v._general_tab._save_btn.click()

        assert len(calls) == 1
        assert "name" in calls[0]


# ---------------------------------------------------------------------------
# Tax tab
# ---------------------------------------------------------------------------

class TestTaxTab:
    def test_sales_combo_populated(self, view) -> None:
        assert view._tax_tab._sales_combo.count() == 3

    def test_purchases_combo_populated(self, view) -> None:
        assert view._tax_tab._purchases_combo.count() == 3

    def test_sales_combo_labels(self, view) -> None:
        labels = [view._tax_tab._sales_combo.itemText(i)
                  for i in range(view._tax_tab._sales_combo.count())]
        assert "GST" in labels

    def test_save_button_exists(self, view) -> None:
        assert view._tax_tab._save_btn is not None


# ---------------------------------------------------------------------------
# Connection tab
# ---------------------------------------------------------------------------

class TestConnectionTab:
    def test_server_url_shown(self, view) -> None:
        assert "saebooks.local" in view._connection_tab._url_label.text()

    def test_user_email_shown(self, view) -> None:
        assert "admin@saebooks.local" in view._connection_tab._email_label.text()

    def test_disconnect_button_exists(self, view) -> None:
        assert view._connection_tab._disconnect_btn is not None

    def test_disconnect_emits_signal(self, qapp, monkeypatch) -> None:
        """Clicking Disconnect emits reconnect_requested after confirmation."""
        import saebooks_desktop.views.settings_view as m

        monkeypatch.setattr(m, "get_company", lambda client, cid: _COMPANY_PAYLOAD)
        monkeypatch.setattr(m, "list_tax_codes", lambda client: _TAX_CODES)
        monkeypatch.setattr(m, "get_current_user", lambda client: _ME_PAYLOAD)
        monkeypatch.setattr(m, "get_version", lambda client: _VERSION_PAYLOAD)
        monkeypatch.setattr(m, "patch_company", lambda client, cid, data: data)
        monkeypatch.setattr(m, "get_company_id", lambda: "company-001")
        monkeypatch.setattr(m, "get_server_url", lambda: "http://saebooks.local:8042")

        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.Yes,
        )
        import saebooks_desktop.services.settings as svc_settings
        monkeypatch.setattr(svc_settings, "set_auth_token", lambda v: None)
        monkeypatch.setattr(svc_settings, "set_company_id", lambda v: None)
        monkeypatch.setattr(svc_settings, "set_server_url", lambda v: None)

        from saebooks_desktop.views.settings_view import SettingsView

        v = SettingsView()
        received: list[bool] = []
        v.reconnect_requested.connect(lambda: received.append(True))
        v._connection_tab._disconnect_btn.click()

        assert received == [True]

    def test_disconnect_cancel_does_not_emit(self, qapp, monkeypatch) -> None:
        """Cancelling the Disconnect dialog does NOT emit reconnect_requested."""
        import saebooks_desktop.views.settings_view as m

        monkeypatch.setattr(m, "get_company", lambda client, cid: _COMPANY_PAYLOAD)
        monkeypatch.setattr(m, "list_tax_codes", lambda client: _TAX_CODES)
        monkeypatch.setattr(m, "get_current_user", lambda client: _ME_PAYLOAD)
        monkeypatch.setattr(m, "get_version", lambda client: _VERSION_PAYLOAD)
        monkeypatch.setattr(m, "patch_company", lambda client, cid, data: data)
        monkeypatch.setattr(m, "get_company_id", lambda: "company-001")
        monkeypatch.setattr(m, "get_server_url", lambda: "http://saebooks.local:8042")

        from PySide6.QtWidgets import QMessageBox

        monkeypatch.setattr(
            QMessageBox,
            "question",
            lambda *a, **kw: QMessageBox.StandardButton.No,
        )

        from saebooks_desktop.views.settings_view import SettingsView

        v = SettingsView()
        received: list[bool] = []
        v.reconnect_requested.connect(lambda: received.append(True))
        v._connection_tab._disconnect_btn.click()

        assert received == []


# ---------------------------------------------------------------------------
# About tab
# ---------------------------------------------------------------------------

class TestAboutTab:
    def test_version_shown(self, view) -> None:
        assert "0.9.0" in view._about_tab._version_label.text()

    def test_edition_shown(self, view) -> None:
        assert "Community" in view._about_tab._edition_label.text()

    def test_source_link_text(self, view) -> None:
        assert "github.com/sae-engineering/saebooks" in view._about_tab._source_label.text()

    def test_licence_text(self, view) -> None:
        assert "AGPLv3" in view._about_tab._licence_label.text()


# ---------------------------------------------------------------------------
# Offline behaviour
# ---------------------------------------------------------------------------

class TestOfflineBehaviour:
    def test_offline_banner_shown_when_api_raises(self, qapp, monkeypatch) -> None:
        """When all service calls fail, offline banner is shown on general tab."""
        import saebooks_desktop.views.settings_view as m
        from saebooks_desktop.services.api_client import ServerOfflineError

        monkeypatch.setattr(
            m, "get_company", lambda *a: (_ for _ in ()).throw(ServerOfflineError("offline"))
        )
        monkeypatch.setattr(
            m, "list_tax_codes", lambda *a: (_ for _ in ()).throw(ServerOfflineError("offline"))
        )
        monkeypatch.setattr(
            m, "get_current_user", lambda *a: (_ for _ in ()).throw(ServerOfflineError("offline"))
        )
        monkeypatch.setattr(
            m, "get_version", lambda *a: (_ for _ in ()).throw(ServerOfflineError("offline"))
        )
        monkeypatch.setattr(m, "get_company_id", lambda: "company-001")
        monkeypatch.setattr(m, "get_server_url", lambda: "http://saebooks.local:8042")

        from saebooks_desktop.views.settings_view import SettingsView

        v = SettingsView()
        assert not v._general_tab._offline_label.isHidden()
