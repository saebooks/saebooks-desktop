"""Settings view — Company Settings with a QTabWidget.

Tabs:
    General    — company name, ABN, ACN, financial year start, base currency
    Tax        — default tax codes for sales and purchases
    Connection — server URL, current user, Disconnect button
    About      — product info, version, edition, links

Signals:
    reconnect_requested() — emitted when the user clicks "Disconnect".
                            MainWindow should clear QSettings and re-show the
                            first-run wizard when it receives this signal.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.company_settings import (
    get_company,
    get_current_user,
    get_version,
    list_tax_codes,
    patch_company,
)
from saebooks_desktop.services.settings import get_company_id, get_server_url

_MONTHS = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]


def _offline_banner() -> QLabel:
    lbl = QLabel("Server offline — some settings may be unavailable")
    lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
    lbl.setStyleSheet("background: #fff3cd; color: #856404; padding: 4px;")
    lbl.setVisible(False)
    return lbl


class _GeneralTab(QWidget):
    """General company settings tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._offline_label = _offline_banner()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(12, 12, 12, 12)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)

        self._name_edit = QLineEdit()
        self._abn_edit = QLineEdit()
        self._abn_edit.setReadOnly(True)
        self._acn_edit = QLineEdit()
        self._acn_edit.setReadOnly(True)

        self._fy_start_combo = QComboBox()
        self._fy_start_combo.addItems(_MONTHS)

        self._currency_edit = QLineEdit("AUD")
        self._currency_edit.setReadOnly(True)

        form.addRow("Company name:", self._name_edit)
        form.addRow("ABN:", self._abn_edit)
        form.addRow("ACN:", self._acn_edit)
        form.addRow("Financial year start:", self._fy_start_combo)
        form.addRow("Base currency:", self._currency_edit)

        self._save_btn = QPushButton("Save")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._offline_label)
        layout.addWidget(form_widget)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def populate(self, data: dict[str, Any]) -> None:
        self._name_edit.setText(data.get("name") or "")
        self._abn_edit.setText(data.get("abn") or "")
        self._acn_edit.setText(data.get("acn") or "")
        month = data.get("financial_year_start_month")
        if month and 1 <= int(month) <= 12:
            self._fy_start_combo.setCurrentIndex(int(month) - 1)

    def current_data(self) -> dict[str, Any]:
        return {
            "name": self._name_edit.text().strip(),
            "financial_year_start_month": self._fy_start_combo.currentIndex() + 1,
        }

    def show_offline(self, visible: bool) -> None:
        self._offline_label.setVisible(visible)


class _TaxTab(QWidget):
    """Tax settings tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._offline_label = _offline_banner()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(12, 12, 12, 12)

        self._sales_combo = QComboBox()
        self._purchases_combo = QComboBox()

        form.addRow("Default tax code (sales):", self._sales_combo)
        form.addRow("Default tax code (purchases):", self._purchases_combo)

        self._save_btn = QPushButton("Save")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._offline_label)
        layout.addWidget(form_widget)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._save_btn)
        layout.addLayout(btn_row)

    def populate_tax_codes(self, codes: list[dict[str, Any]]) -> None:
        self._tax_codes = codes
        labels = [c.get("code") or c.get("name") or str(c) for c in codes]
        self._sales_combo.clear()
        self._sales_combo.addItems(labels)
        self._purchases_combo.clear()
        self._purchases_combo.addItems(labels)

    def set_defaults(self, sales_code: str | None, purchases_code: str | None) -> None:
        if sales_code:
            idx = self._sales_combo.findText(sales_code)
            if idx >= 0:
                self._sales_combo.setCurrentIndex(idx)
        if purchases_code:
            idx = self._purchases_combo.findText(purchases_code)
            if idx >= 0:
                self._purchases_combo.setCurrentIndex(idx)

    def current_data(self) -> dict[str, Any]:
        return {
            "default_sales_tax_code": self._sales_combo.currentText(),
            "default_purchases_tax_code": self._purchases_combo.currentText(),
        }

    def show_offline(self, visible: bool) -> None:
        self._offline_label.setVisible(visible)


class _ConnectionTab(QWidget):
    """Connection / server info tab."""

    disconnect_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._offline_label = _offline_banner()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(12, 12, 12, 12)

        self._url_label = QLabel()
        self._url_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._email_label = QLabel()
        self._email_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )

        form.addRow("Server URL:", self._url_label)
        form.addRow("Signed in as:", self._email_label)

        self._disconnect_btn = QPushButton("Disconnect")
        self._disconnect_btn.setStyleSheet("color: #c62828;")
        self._disconnect_btn.clicked.connect(self.disconnect_clicked)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._offline_label)
        layout.addWidget(form_widget)
        layout.addStretch()

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        btn_row.addWidget(self._disconnect_btn)
        layout.addLayout(btn_row)

    def populate(self, server_url: str, user_email: str) -> None:
        self._url_label.setText(server_url or "(not configured)")
        self._email_label.setText(user_email or "(unknown)")

    def show_offline(self, visible: bool) -> None:
        self._offline_label.setVisible(visible)


class _AboutTab(QWidget):
    """About tab."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._offline_label = _offline_banner()

        form_widget = QWidget()
        form = QFormLayout(form_widget)
        form.setContentsMargins(12, 12, 12, 12)

        self._product_label = QLabel("SAE Books")
        self._version_label = QLabel("—")
        self._edition_label = QLabel("—")
        self._source_label = QLabel("Source: github.com/sae-engineering/saebooks")
        self._source_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        self._licence_label = QLabel("Licence: AGPLv3")
        self._build_label = QLabel("—")

        form.addRow("Product:", self._product_label)
        form.addRow("Version:", self._version_label)
        form.addRow("Edition:", self._edition_label)
        form.addRow("Build:", self._build_label)
        form.addRow("", self._source_label)
        form.addRow("", self._licence_label)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._offline_label)
        layout.addWidget(form_widget)
        layout.addStretch()

    def populate(self, version_data: dict[str, Any]) -> None:
        version = version_data.get("version") or version_data.get("server_version") or "—"
        edition = version_data.get("edition") or "Community"
        self._version_label.setText(version)
        self._edition_label.setText(edition)
        self._build_label.setText(version)

    def show_offline(self, visible: bool) -> None:
        self._offline_label.setVisible(visible)


class SettingsView(QWidget):
    """Company Settings view — tabbed interface for company configuration.

    Signals:
        reconnect_requested(): emitted when the user clicks "Disconnect" on
            the Connection tab.  MainWindow handles this by clearing
            QSettings and re-showing the first-run wizard.
    """

    reconnect_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._company_id = get_company_id()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._tabs = QTabWidget()

        self._general_tab = _GeneralTab()
        self._tax_tab = _TaxTab()
        self._connection_tab = _ConnectionTab()
        self._about_tab = _AboutTab()

        self._tabs.addTab(self._general_tab, "General")
        self._tabs.addTab(self._tax_tab, "Tax")
        self._tabs.addTab(self._connection_tab, "Connection")
        self._tabs.addTab(self._about_tab, "About")

        layout.addWidget(self._tabs)

        # Wire save buttons
        self._general_tab._save_btn.clicked.connect(self._on_save_general)
        self._tax_tab._save_btn.clicked.connect(self._on_save_tax)
        self._connection_tab.disconnect_clicked.connect(self._on_disconnect)

        self._load_all()

    # ------------------------------------------------------------------
    # Data loading
    # ------------------------------------------------------------------

    def _load_all(self) -> None:
        offline = False

        # General tab
        if self._company_id:
            try:
                company = get_company(self._client, self._company_id)
                self._general_tab.populate(company)
                # Carry over defaults to tax tab if present
                self._general_tab.show_offline(False)
            except (ServerOfflineError, Exception):  # noqa: BLE001
                offline = True
                self._general_tab.show_offline(True)
        else:
            self._general_tab.show_offline(True)

        # Tax tab — load codes
        try:
            codes = list_tax_codes(self._client)
            self._tax_tab.populate_tax_codes(codes)
            self._tax_tab.show_offline(False)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            offline = True
            self._tax_tab.show_offline(True)

        # Connection tab
        server_url = get_server_url()
        user_email = ""
        try:
            me = get_current_user(self._client)
            user_email = me.get("email") or me.get("username") or ""
        except (ServerOfflineError, Exception):  # noqa: BLE001
            offline = True
            # Fall back to stored email if API/me doesn't exist yet
            from PySide6.QtCore import QSettings
            s = QSettings("SAE Engineering", "SAE Books")
            user_email = str(s.value("saebooks/auth/email", ""))

        self._connection_tab.populate(server_url, user_email)
        self._connection_tab.show_offline(offline)

        # About tab
        try:
            version_data = get_version(self._client)
            self._about_tab.populate(version_data)
            self._about_tab.show_offline(False)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._about_tab.show_offline(True)

    # ------------------------------------------------------------------
    # Slot handlers
    # ------------------------------------------------------------------

    def _on_save_general(self) -> None:
        if not self._company_id:
            QMessageBox.warning(self, "No company", "No company is selected.")
            return
        data = self._general_tab.current_data()
        try:
            patch_company(self._client, self._company_id, data)
            QMessageBox.information(self, "Saved", "General settings saved.")
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot save — server is offline.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")

    def _on_save_tax(self) -> None:
        if not self._company_id:
            QMessageBox.warning(self, "No company", "No company is selected.")
            return
        data = self._tax_tab.current_data()
        try:
            patch_company(self._client, self._company_id, data)
            QMessageBox.information(self, "Saved", "Tax settings saved.")
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot save — server is offline.")
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Save failed:\n{exc}")

    def _on_disconnect(self) -> None:
        from saebooks_desktop.services.settings import (
            set_auth_token,
            set_company_id,
            set_server_url,
        )

        confirm = QMessageBox.question(
            self,
            "Disconnect",
            "This will clear your saved connection details and return to the "
            "setup wizard. Continue?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        set_auth_token("")
        set_company_id("")
        set_server_url("")
        self.reconnect_requested.emit()
