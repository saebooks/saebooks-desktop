"""Purchase-order detail view (read-only) with state-transition actions.

Shows PO header, lines (ordered/received/outstanding), and action buttons:
Send (DRAFT→OPEN), Cancel, Close, Convert-to-bill (full or partial).

Editing the line items is intentionally not exposed here — POs that need
edits can be modified in the web UI; the desktop is the read-and-act surface.

Signals:
    back_requested        — back-to-list clicked
    bill_opened(str)      — convert-to-bill returned a bill id
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QStandardItemModel,
    QTableView,
    QVBoxLayout,
    QWidget,
)
from PySide6.QtGui import QStandardItem

from saebooks_desktop.services.api_client import APIClient
from saebooks_desktop.services.purchase_orders import get_purchase_order


_LINE_COLS = ["#", "Description", "Ordered", "Received", "Outstanding", "Unit Price", "Total"]


class _ConvertDialog(QDialog):
    """Modal: pick receipt qty per line for partial convert-to-bill."""

    def __init__(self, lines: list[dict[str, Any]], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Convert to bill")
        self._spins: dict[int, QDoubleSpinBox] = {}

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            "Leave quantities at zero to convert the full outstanding amount.\n"
            "Otherwise, enter a quantity to bill for that line only."
        ))

        form = QFormLayout()
        for ln in lines:
            line_no = int(ln.get("line_no", 0))
            ordered = float(ln.get("quantity", 0) or 0)
            received = float(ln.get("received_qty", 0) or 0)
            outstanding = ordered - received
            if outstanding <= 0:
                continue
            spin = QDoubleSpinBox()
            spin.setDecimals(3)
            spin.setMinimum(0.0)
            spin.setMaximum(outstanding)
            spin.setSingleStep(1.0)
            spin.setValue(0.0)
            spin.setSpecialValueText("(full)")
            label = f"#{line_no} — {ln.get('description', '')} (out: {outstanding:.3f})"
            form.addRow(label, spin)
            self._spins[line_no] = spin
        layout.addLayout(form)

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        layout.addWidget(bb)

    def quantities(self) -> dict[int, str] | None:
        """Return ``{line_no: "qty"}`` for non-zero entries, or None for full."""
        out: dict[int, str] = {}
        for line_no, spin in self._spins.items():
            v = spin.value()
            if v > 0:
                out[line_no] = f"{v:.3f}"
        return out or None


class PurchaseOrderDetailView(QWidget):
    back_requested = Signal()
    bill_opened = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._client = APIClient()
        self._po: dict[str, Any] | None = None

        layout = QVBoxLayout(self)

        header_row = QHBoxLayout()
        self._title = QLabel("Purchase order")
        self._title.setStyleSheet("font-size: 16pt; font-weight: 600;")
        header_row.addWidget(self._title)
        header_row.addStretch()
        self._back_btn = QPushButton("← Back")
        self._back_btn.clicked.connect(self.back_requested)
        header_row.addWidget(self._back_btn)
        layout.addLayout(header_row)

        # Summary form
        self._summary = QFormLayout()
        self._lbl_status = QLabel("—")
        self._lbl_supplier = QLabel("—")
        self._lbl_issue = QLabel("—")
        self._lbl_expected = QLabel("—")
        self._lbl_subtotal = QLabel("—")
        self._lbl_tax = QLabel("—")
        self._lbl_total = QLabel("—")
        self._summary.addRow("Status:", self._lbl_status)
        self._summary.addRow("Supplier:", self._lbl_supplier)
        self._summary.addRow("Issue date:", self._lbl_issue)
        self._summary.addRow("Expected:", self._lbl_expected)
        self._summary.addRow("Subtotal:", self._lbl_subtotal)
        self._summary.addRow("Tax:", self._lbl_tax)
        self._summary.addRow("Total:", self._lbl_total)
        layout.addLayout(self._summary)

        # Lines table
        self._lines_model = QStandardItemModel(0, len(_LINE_COLS))
        self._lines_model.setHorizontalHeaderLabels(_LINE_COLS)
        self._lines_table = QTableView()
        self._lines_table.setModel(self._lines_model)
        self._lines_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._lines_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._lines_table)

        # Action buttons
        actions_row = QHBoxLayout()
        self._send_btn = QPushButton("Send")
        self._send_btn.clicked.connect(lambda: self._do_state_transition("send"))
        actions_row.addWidget(self._send_btn)

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(lambda: self._do_state_transition("cancel"))
        actions_row.addWidget(self._cancel_btn)

        self._close_btn = QPushButton("Close")
        self._close_btn.clicked.connect(lambda: self._do_state_transition("close"))
        actions_row.addWidget(self._close_btn)

        self._convert_btn = QPushButton("Convert to bill…")
        self._convert_btn.clicked.connect(self._do_convert)
        actions_row.addWidget(self._convert_btn)

        actions_row.addStretch()
        layout.addLayout(actions_row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, po_id: str) -> None:
        try:
            po = get_purchase_order(self._client, po_id)
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Load failed", f"Could not load PO:\n{exc}")
            return
        self._po = po
        self._render()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _render(self) -> None:
        po = self._po or {}
        self._title.setText(f"Purchase order {po.get('number') or '(draft)'}")
        self._lbl_status.setText(str(po.get("status") or ""))
        self._lbl_supplier.setText(str(po.get("supplier_name") or po.get("contact_id") or ""))
        self._lbl_issue.setText(str(po.get("issue_date") or ""))
        self._lbl_expected.setText(str(po.get("expected_date") or "—"))
        currency = po.get("currency") or "AUD"
        self._lbl_subtotal.setText(f"{currency} {float(po.get('subtotal') or 0):.2f}")
        self._lbl_tax.setText(f"{currency} {float(po.get('tax_total') or 0):.2f}")
        self._lbl_total.setText(f"{currency} {float(po.get('total') or 0):.2f}")

        # Lines
        self._lines_model.removeRows(0, self._lines_model.rowCount())
        for ln in po.get("lines", []):
            row = self._lines_model.rowCount()
            self._lines_model.insertRow(row)
            ordered = float(ln.get("quantity", 0) or 0)
            received = float(ln.get("received_qty", 0) or 0)
            outstanding = ordered - received
            self._lines_model.setItem(row, 0, QStandardItem(str(ln.get("line_no", ""))))
            self._lines_model.setItem(row, 1, QStandardItem(ln.get("description", "")))
            self._lines_model.setItem(row, 2, QStandardItem(f"{ordered:.3f}"))
            self._lines_model.setItem(row, 3, QStandardItem(f"{received:.3f}"))
            self._lines_model.setItem(row, 4, QStandardItem(f"{outstanding:.3f}"))
            self._lines_model.setItem(row, 5, QStandardItem(f"{float(ln.get('unit_price') or 0):.2f}"))
            self._lines_model.setItem(row, 6, QStandardItem(f"{float(ln.get('line_total') or 0):.2f}"))

        # Action button enable state
        status = (po.get("status") or "").upper()
        self._send_btn.setEnabled(status == "DRAFT")
        self._cancel_btn.setEnabled(status in ("DRAFT", "OPEN", "PARTIAL"))
        self._close_btn.setEnabled(status in ("OPEN", "PARTIAL", "RECEIVED"))
        self._convert_btn.setEnabled(status in ("OPEN", "PARTIAL"))

    def _do_state_transition(self, action: str) -> None:
        po = self._po or {}
        po_id = po.get("id")
        version = po.get("version")
        if not po_id or version is None:
            return
        confirm = QMessageBox.question(
            self,
            f"{action.capitalize()} purchase order?",
            f"{action.capitalize()} purchase order {po.get('number') or po_id}?",
        )
        if confirm != QMessageBox.StandardButton.Yes:
            return

        # We don't have a generic POST helper with custom headers in api_client;
        # use the underlying httpx-style client. Fallback: rely on raw post.
        try:
            self._client.post(
                f"/api/v1/purchase_orders/{po_id}/{action}",
                json={},
                headers={"If-Match": str(version)},
            )
        except TypeError:
            # Older APIClient.post may not support headers kwarg
            self._client.post(f"/api/v1/purchase_orders/{po_id}/{action}", json={})
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, f"{action} failed", str(exc))
            return
        self.load(po_id)

    def _do_convert(self) -> None:
        po = self._po or {}
        po_id = po.get("id")
        version = po.get("version")
        if not po_id or version is None:
            return
        dlg = _ConvertDialog(po.get("lines", []), parent=self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        quantities = dlg.quantities()
        payload: dict[str, Any] = {}
        if quantities is not None:
            payload["quantities"] = quantities

        try:
            resp = self._client.post(
                f"/api/v1/purchase_orders/{po_id}/convert-to-bill",
                json=payload,
                headers={"If-Match": str(version)},
            )
        except TypeError:
            resp = self._client.post(
                f"/api/v1/purchase_orders/{po_id}/convert-to-bill", json=payload
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(self, "Convert failed", str(exc))
            return
        bill_id = (resp or {}).get("bill_id") if isinstance(resp, dict) else None
        if bill_id:
            QMessageBox.information(
                self, "Converted",
                f"Created draft bill {bill_id}. Switch to the Purchases view to open it.",
            )
            self.bill_opened.emit(str(bill_id))
        self.load(po_id)
