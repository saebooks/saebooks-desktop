"""Tax Codes list view.

Displays a QTableView of tax codes fetched from ``GET /api/v1/tax_codes``.

Columns: Code | Name | Rate (%) | Type

Toolbar:
  - "New Tax Code" QPushButton  (opens create/edit dialog)

Signals:
  - ``code_selected(str)``      — emitted on double-click with the tax code id.
  - ``new_code_requested()``    — emitted after a new tax code is created.

Note: The Settings view also shows tax codes in a combo-box via
``company_settings.list_tax_codes``.  This view is the full management table.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QComboBox,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.tax_codes import create_tax_code, list_tax_codes

# Column indices
_COL_CODE = 0
_COL_NAME = 1
_COL_RATE = 2
_COL_TYPE = 3

_COLUMNS = ["Code", "Name", "Rate (%)", "Type"]

_TAX_TYPES = ["GST", "FRE", "INP", "ITS", "CAP", "WET", "LCT", "GNR", "OTHER"]


class TaxCodeDialog(QDialog):
    """Modal dialog for creating or editing a tax code."""

    def __init__(
        self,
        parent: QWidget | None = None,
        existing: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self._existing = existing
        title = "Edit Tax Code" if existing else "New Tax Code"
        self.setWindowTitle(title)
        self.setMinimumWidth(340)

        form = QFormLayout()
        form.setContentsMargins(12, 12, 12, 12)

        self._code_edit = QLineEdit()
        self._name_edit = QLineEdit()
        self._rate_edit = QLineEdit()
        self._rate_edit.setPlaceholderText("e.g. 10.0")
        self._type_combo = QComboBox()
        self._type_combo.addItems(_TAX_TYPES)

        form.addRow("Code:", self._code_edit)
        form.addRow("Name:", self._name_edit)
        form.addRow("Rate (%):", self._rate_edit)
        form.addRow("Tax Type:", self._type_combo)

        if existing:
            self._code_edit.setText(existing.get("code") or "")
            self._name_edit.setText(existing.get("name") or "")
            self._rate_edit.setText(str(existing.get("rate") or ""))
            tax_type = existing.get("tax_type") or ""
            idx = self._type_combo.findText(tax_type)
            if idx >= 0:
                self._type_combo.setCurrentIndex(idx)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        if not self._code_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Code is required.")
            return
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Validation", "Name is required.")
            return
        rate_text = self._rate_edit.text().strip()
        if rate_text:
            try:
                float(rate_text)
            except ValueError:
                QMessageBox.warning(self, "Validation", "Rate must be a number.")
                return
        self.accept()

    def current_data(self) -> dict[str, Any]:
        rate_text = self._rate_edit.text().strip()
        return {
            "code": self._code_edit.text().strip(),
            "name": self._name_edit.text().strip(),
            "rate": float(rate_text) if rate_text else 0.0,
            "tax_type": self._type_combo.currentText(),
        }


class TaxCodesView(QWidget):
    """Tax Codes list view.

    Fetches from ``/api/v1/tax_codes`` via REST and renders a table.
    Emits ``code_selected(id)`` on double-click.
    """

    code_selected = Signal(str)
    new_code_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Tax Code")
        self._new_btn.clicked.connect(self._on_new_clicked)
        toolbar_layout.addWidget(self._new_btn)

        layout.addWidget(toolbar_widget)

        # --- Offline banner ---
        self._offline_label = QLabel("Server offline — showing cached data")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # --- Table ---
        self._model = QStandardItemModel(0, len(_COLUMNS))
        self._model.setHorizontalHeaderLabels(_COLUMNS)

        # Right-align Rate column header
        self._model.horizontalHeaderItem(_COL_RATE).setTextAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        self._load_codes()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch all tax codes."""
        self._load_codes()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_codes(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._offline_label.setVisible(False)
        try:
            items = list_tax_codes(self._client)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return
        self._append_rows(items)

    def _append_rows(self, codes: list[dict[str, Any]]) -> None:
        for code in codes:
            row = self._model.rowCount()
            self._model.insertRow(row)

            code_item = QStandardItem(code.get("code") or "")
            code_item.setData(code.get("id") or "", Qt.ItemDataRole.UserRole)
            self._model.setItem(row, _COL_CODE, code_item)
            self._model.setItem(row, _COL_NAME, QStandardItem(code.get("name") or ""))

            rate_val = code.get("rate")
            rate_text = str(rate_val) if rate_val is not None else ""
            rate_item = QStandardItem(rate_text)
            rate_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_RATE, rate_item)
            self._model.setItem(row, _COL_TYPE, QStandardItem(code.get("tax_type") or ""))

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_CODE)
        if id_item is not None:
            code_id = id_item.data(Qt.ItemDataRole.UserRole)
            if code_id:
                self.code_selected.emit(str(code_id))

    def _on_new_clicked(self) -> None:
        dlg = TaxCodeDialog(self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        data = dlg.current_data()
        try:
            create_tax_code(self._client, data)
        except ServerOfflineError:
            QMessageBox.critical(self, "Offline", "Cannot create — server is offline.")
            return
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Create failed:\n{exc}")
            return
        self._load_codes()
        self.new_code_requested.emit()
