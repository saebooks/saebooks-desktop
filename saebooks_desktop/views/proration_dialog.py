"""Prorate Calculator dialog — three tabs covering all four prorate flows.

Tabs:
  1. Per-line preview         — POST /proration/preview
                                 (also covers deferred-revenue split: the same
                                 endpoint returns the prorated amount and the
                                 caller computes deferred = full - prorated.)
  2. First-period sign-up     — POST /proration/first-period-preview
  3. Plan change (mid-period) — POST /proration/plan-change-preview

All three flows are interactive previews — no DB writes — and are the canonical
way for an operator to sanity-check what a prorate will produce before posting
it. Surface from Tools → Prorate Calculator…
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDoubleSpinBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient
from saebooks_desktop.services.proration import (
    first_period_preview,
    plan_change_preview,
    preview,
)


_BASES = ["DAYS_30_360", "DAYS_ACTUAL", "MONTHS"]


def _date_edit(default: QDate | None = None) -> QDateEdit:
    w = QDateEdit()
    w.setCalendarPopup(True)
    w.setDisplayFormat("yyyy-MM-dd")
    w.setDate(default or QDate.currentDate())
    return w


def _amount_spin(default: float = 0.0) -> QDoubleSpinBox:
    w = QDoubleSpinBox()
    w.setDecimals(2)
    w.setMinimum(0.0)
    w.setMaximum(1_000_000_000.0)
    w.setSingleStep(1.0)
    w.setValue(default)
    return w


def _basis_combo() -> QComboBox:
    w = QComboBox()
    w.addItems(_BASES)
    return w


def _format_result(label: str, data: dict[str, Any]) -> str:
    """Render a prorate-preview result dict as a readable text block."""
    lines = [f"=== {label} ==="]
    # Common fields ordered for readability.
    keys_priority = [
        "prorated_amount",
        "factor",
        "days_used",
        "days_in_full",
        "line_description_suggestion",
        "credit_amount",
        "charge_amount",
        "net_amount",
        "old_prorated",
        "new_prorated",
    ]
    seen: set[str] = set()
    for k in keys_priority:
        if k in data:
            lines.append(f"  {k}: {data[k]}")
            seen.add(k)
    for k, v in data.items():
        if k in seen:
            continue
        lines.append(f"  {k}: {v}")
    return "\n".join(lines)


class ProrationDialog(QDialog):
    """Three-tab prorate calculator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Prorate Calculator")
        self.resize(620, 520)
        self._client = APIClient()

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Preview prorate calculations before posting them. All three previews "
            "call the API — no journals are written."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_preview_tab(), "Per-line preview")
        self._tabs.addTab(self._build_first_period_tab(), "First-period sign-up")
        self._tabs.addTab(self._build_plan_change_tab(), "Plan change")
        layout.addWidget(self._tabs)

        self._result = QTextEdit()
        self._result.setReadOnly(True)
        self._result.setPlaceholderText("Result will appear here after you preview…")
        self._result.setStyleSheet("font-family: monospace; font-size: 11pt;")
        layout.addWidget(self._result, 1)

        close_row = QHBoxLayout()
        close_row.addStretch()
        close_btn = QPushButton("Close")
        close_btn.clicked.connect(self.accept)
        close_row.addWidget(close_btn)
        layout.addLayout(close_row)

    # ------------------------------------------------------------------
    # Tab builders
    # ------------------------------------------------------------------

    def _build_preview_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self._p_amount = _amount_spin(100.0)
        self._p_basis = _basis_combo()
        self._p_start = _date_edit()
        self._p_end = _date_edit(QDate.currentDate().addMonths(1))
        form.addRow("Full period amount:", self._p_amount)
        form.addRow("Basis:", self._p_basis)
        form.addRow("Service start:", self._p_start)
        form.addRow("Service end:", self._p_end)

        btn = QPushButton("Preview")
        btn.clicked.connect(self._do_preview)
        form.addRow("", btn)
        return page

    def _build_first_period_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self._fp_amount = _amount_spin(100.0)
        self._fp_basis = _basis_combo()
        self._fp_start = _date_edit()
        self._fp_end = _date_edit(QDate.currentDate().addMonths(1))
        form.addRow("Full period amount:", self._fp_amount)
        form.addRow("Basis:", self._fp_basis)
        form.addRow("Service start:", self._fp_start)
        form.addRow("Service end:", self._fp_end)

        btn = QPushButton("Preview first period")
        btn.clicked.connect(self._do_first_period)
        form.addRow("", btn)
        return page

    def _build_plan_change_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self._pc_old = _amount_spin(100.0)
        self._pc_new = _amount_spin(150.0)
        self._pc_period_start = _date_edit()
        self._pc_period_end = _date_edit(QDate.currentDate().addMonths(1))
        self._pc_change = _date_edit(QDate.currentDate().addDays(15))
        form.addRow("Old period amount:", self._pc_old)
        form.addRow("New period amount:", self._pc_new)
        form.addRow("Period start:", self._pc_period_start)
        form.addRow("Period end:", self._pc_period_end)
        form.addRow("Change date:", self._pc_change)

        btn = QPushButton("Preview plan change")
        btn.clicked.connect(self._do_plan_change)
        form.addRow("", btn)
        return page

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def _show_error(self, exc: BaseException) -> None:
        self._result.setPlainText(f"Error: {exc}")

    def _do_preview(self) -> None:
        try:
            data = preview(
                self._client,
                full_period_amount=f"{self._p_amount.value():.2f}",
                basis=self._p_basis.currentText(),
                service_start=self._p_start.date().toString("yyyy-MM-dd"),
                service_end=self._p_end.date().toString("yyyy-MM-dd"),
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return
        self._result.setPlainText(_format_result("Per-line preview", data))

    def _do_first_period(self) -> None:
        try:
            data = first_period_preview(
                self._client,
                full_period_amount=f"{self._fp_amount.value():.2f}",
                basis=self._fp_basis.currentText(),
                service_start=self._fp_start.date().toString("yyyy-MM-dd"),
                service_end=self._fp_end.date().toString("yyyy-MM-dd"),
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return
        self._result.setPlainText(_format_result("First-period sign-up", data))

    def _do_plan_change(self) -> None:
        try:
            data = plan_change_preview(
                self._client,
                old_period_amount=f"{self._pc_old.value():.2f}",
                new_period_amount=f"{self._pc_new.value():.2f}",
                period_start=self._pc_period_start.date().toString("yyyy-MM-dd"),
                period_end=self._pc_period_end.date().toString("yyyy-MM-dd"),
                change_date=self._pc_change.date().toString("yyyy-MM-dd"),
            )
        except Exception as exc:  # noqa: BLE001
            self._show_error(exc)
            return
        self._result.setPlainText(_format_result("Plan change", data))
