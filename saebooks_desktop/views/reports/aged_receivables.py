"""Aged Receivables report widget.

Displays outstanding invoices grouped by contact and bucketed by days overdue.
Fetches from ``GET /api/v1/reports/aged_receivables``.

Columns: Contact | Current | 30 | 60 | 90+ | Total  (amounts right-aligned)

The bucket labels come from the API response (``data["buckets"]``), so the
column layout is dynamic.  A fixed 5-column default is used when no data is
available (matches the standard [0,30,60,90] bucket configuration).
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItem, QStandardItemModel

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.reports import get_aged_receivables
from saebooks_desktop.views.reports.base import DATE_MODE_AS_AT, BaseReportWidget

# Default column layout — matches API default bucket_days=[0,30,60,90]
_DEFAULT_COLUMNS = ["Contact", "Current", "30", "60", "90+", "Total"]
_COL_CONTACT = 0


class AgedReceivablesReport(BaseReportWidget):
    """Aged Receivables — invoices outstanding by bucket."""

    _REPORT_NAME = "aged_receivables"
    _COLUMNS = _DEFAULT_COLUMNS

    def __init__(self, parent: object = None) -> None:
        super().__init__(date_mode=DATE_MODE_AS_AT, parent=parent)  # type: ignore[arg-type]
        self._client = APIClient()
        self._bucket_labels: list[str] = []

    # ---------------------------------------------------------------------- #

    def _run_report(self) -> None:
        self._model.removeRows(0, self._model.rowCount())
        self._set_status("loading", "Loading\u2026")
        self._offline_label.setVisible(False)

        try:
            data = get_aged_receivables(self._client, self._as_at_date())
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._set_status("error", "Could not load report — server offline.")
            self._offline_label.setVisible(True)
            return

        self._set_status()
        self._populate(data)

    def _populate(self, data: dict) -> None:
        """Rebuild the model from the API response dict."""
        buckets: list[str] = data.get("buckets", [])
        self._bucket_labels = buckets

        # Rebuild column headers dynamically from bucket labels
        columns = ["Contact"] + buckets + ["Total"]
        self._model.clear()
        self._model.setColumnCount(len(columns))
        self._model.setHorizontalHeaderLabels(columns)

        # Right-align all numeric column headers
        for col_idx in range(1, len(columns)):
            hdr = self._model.horizontalHeaderItem(col_idx)
            if hdr:
                hdr.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        contacts = data.get("contacts", [])
        for contact in contacts:
            self._append_contact_row(contact, buckets, columns)

        # Totals row
        totals = data.get("totals", {})
        if totals:
            self._append_contact_row(totals, buckets, columns, label="TOTALS")

        if not contacts:
            self._set_status("empty", "No outstanding items for the selected date.")

    def _append_contact_row(
        self,
        row_data: dict,
        buckets: list[str],
        columns: list[str],
        label: str | None = None,
    ) -> None:
        row = self._model.rowCount()
        self._model.insertRow(row)
        contact_name = label or row_data.get("contact_name") or ""
        self._model.setItem(row, _COL_CONTACT, QStandardItem(contact_name))

        for col_idx, bucket in enumerate(buckets, start=1):
            amount = row_data.get(bucket, 0.0) or 0.0
            item = QStandardItem(f"{amount:,.2f}")
            item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            self._model.setItem(row, col_idx, item)

        total_col = len(buckets) + 1
        total = row_data.get("total", 0.0) or 0.0
        total_item = QStandardItem(f"{total:,.2f}")
        total_item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self._model.setItem(row, total_col, total_item)
