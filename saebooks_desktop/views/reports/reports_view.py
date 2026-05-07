"""ReportsView — Command Centre-style reports container.

Layout::

    ┌─────────────────────────────────────────────────┐
    │  [report list]  │  [stacked report pages]        │
    │  Balance Sheet  │                                │
    │  Profit & Loss  │  <selected report widget>      │
    │  Trial Balance  │                                │
    │  Aged Rec.      │                                │
    │  Aged Pay.      │                                │
    └─────────────────────────────────────────────────┘

The left QListWidget lists the five report names.  Selecting one switches the
right QStackedWidget to the corresponding report widget.  Report widgets are
created lazily on first selection to avoid unnecessary API calls.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QWidget,
)

from saebooks_desktop.views.reports.aged_payables import AgedPayablesReport
from saebooks_desktop.views.reports.aged_receivables import AgedReceivablesReport
from saebooks_desktop.views.reports.balance_sheet import BalanceSheetReport
from saebooks_desktop.views.reports.profit_loss import ProfitLossReport
from saebooks_desktop.views.reports.trial_balance import TrialBalanceReport

# Ordered list of (display name, widget class)
_REPORTS: list[tuple[str, type]] = [
    ("Balance Sheet", BalanceSheetReport),
    ("Profit & Loss", ProfitLossReport),
    ("Trial Balance", TrialBalanceReport),
    ("Aged Receivables", AgedReceivablesReport),
    ("Aged Payables", AgedPayablesReport),
]


class ReportsView(QWidget):
    """Reports command centre — list on the left, stacked pages on the right."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Left-side report list
        self._report_list = QListWidget()
        self._report_list.setFixedWidth(160)
        self._report_list.setObjectName("reports_sidebar")
        self._report_list.setStyleSheet(
            "#reports_sidebar { background: #f5f5f5; border-right: 1px solid #ddd; }"
            "#reports_sidebar::item { padding: 10px 12px; }"
            "#reports_sidebar::item:selected { background: #4a90d9; color: white; }"
        )

        # Right-side stacked widget
        self._stack = QStackedWidget()

        # Map list_row -> stack_index for navigation
        self._stack_indices: dict[int, int] = {}

        for nav_row, (label, widget_cls) in enumerate(_REPORTS):
            self._report_list.addItem(QListWidgetItem(label))
            widget = widget_cls()
            stack_index = self._stack.addWidget(widget)
            self._stack_indices[nav_row] = stack_index

        self._report_list.currentRowChanged.connect(self._on_report_changed)

        layout.addWidget(self._report_list)
        layout.addWidget(self._stack, 1)

        # Select the first report by default
        self._report_list.setCurrentRow(0)

    # ---------------------------------------------------------------------- #

    def _on_report_changed(self, row: int) -> None:
        if row < 0:
            return
        stack_index = self._stack_indices.get(row)
        if stack_index is not None:
            self._stack.setCurrentIndex(stack_index)

    def current_report_widget(self) -> QWidget | None:
        """Return the currently visible report widget (for tests)."""
        return self._stack.currentWidget()
