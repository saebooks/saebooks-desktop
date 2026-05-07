"""BaseReportWidget — shared scaffold for all report pages.

Every report widget inherits this class, which provides:

- ``_date_header`` area: either a single "as at" QDateEdit (for point-in-time
  reports) or a "From / To" date range pair (for period reports).  Sub-classes
  choose which to use by passing ``date_mode`` to ``__init__``.
- "Run" QPushButton that triggers ``_run_report()``.
- "Export CSV" QPushButton that emits ``export_requested(report_name)``.
- A loading / empty / error ``QLabel`` status area shown *above* the table.
- A ``QTableView`` backed by a ``QStandardItemModel`` that sub-classes
  populate in their ``_run_report()`` implementation.
- Common offline banner.

Usage pattern for sub-classes::

    class MyReport(BaseReportWidget):
        _REPORT_NAME = "my_report"
        _COLUMNS = ["Col A", "Col B"]

        def _build_rows(self) -> None:
            data = get_my_report(self._client, self._as_at_date())
            for item in data["rows"]:
                row = self._model.rowCount()
                self._model.insertRow(row)
                self._model.setItem(row, 0, QStandardItem(item["a"]))
                self._model.setItem(row, 1, QStandardItem(item["b"]))

        def _run_report(self) -> None:
            self._model.removeRows(0, self._model.rowCount())
            self._set_status("")
            try:
                self._build_rows()
            except (ServerOfflineError, Exception):
                self._set_status("error", "Could not load report — server offline.")
                self._offline_label.setVisible(True)
                return
            self._offline_label.setVisible(False)
            if self._model.rowCount() == 0:
                self._set_status("empty", "No data for the selected period.")
"""
from __future__ import annotations

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtGui import QStandardItemModel
from PySide6.QtWidgets import (
    QDateEdit,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

# Date-header modes
DATE_MODE_AS_AT = "as_at"      # single QDateEdit — point-in-time reports
DATE_MODE_RANGE = "range"      # From + To pair — period reports


class BaseReportWidget(QWidget):
    """Common scaffold for all report pages.

    Signals:
        export_requested(str): Emitted when "Export CSV" is clicked.
            Carries the report name (``_REPORT_NAME``).  The actual CSV
            generation is deferred to a later cycle.
    """

    # Sub-classes must set these class-level attributes.
    _REPORT_NAME: str = "report"
    _COLUMNS: list[str] = []

    export_requested = Signal(str)

    def __init__(
        self,
        date_mode: str = DATE_MODE_AS_AT,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._date_mode = date_mode

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # ------------------------------------------------------------------ #
        # Date-header row
        # ------------------------------------------------------------------ #
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        today = QDate.currentDate()

        if date_mode == DATE_MODE_AS_AT:
            header_layout.addWidget(QLabel("As at:"))
            self._date_as_at = QDateEdit()
            self._date_as_at.setCalendarPopup(True)
            self._date_as_at.setDate(today)
            self._date_as_at.setDisplayFormat("dd/MM/yyyy")
            header_layout.addWidget(self._date_as_at)
            # Keep attributes consistent — range attributes not used in as_at mode
            self._date_from: QDateEdit | None = None
            self._date_to: QDateEdit | None = None
        else:
            header_layout.addWidget(QLabel("From:"))
            self._date_from = QDateEdit()
            self._date_from.setCalendarPopup(True)
            self._date_from.setDate(today.addMonths(-1))
            self._date_from.setDisplayFormat("dd/MM/yyyy")
            header_layout.addWidget(self._date_from)

            header_layout.addWidget(QLabel("To:"))
            self._date_to = QDateEdit()
            self._date_to.setCalendarPopup(True)
            self._date_to.setDate(today)
            self._date_to.setDisplayFormat("dd/MM/yyyy")
            header_layout.addWidget(self._date_to)

            self._date_as_at: QDateEdit | None = None  # type: ignore[assignment]

        # Spacer
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(spacer)

        # Run button
        self._run_btn = QPushButton("Run")
        self._run_btn.clicked.connect(self._run_report)
        header_layout.addWidget(self._run_btn)

        # Export CSV button
        self._export_btn = QPushButton("Export CSV")
        self._export_btn.clicked.connect(self._on_export_clicked)
        header_layout.addWidget(self._export_btn)

        layout.addWidget(header_widget)

        # ------------------------------------------------------------------ #
        # Offline banner
        # ------------------------------------------------------------------ #
        self._offline_label = QLabel("Server offline — cannot load report")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # ------------------------------------------------------------------ #
        # Status label (loading / empty / error)
        # ------------------------------------------------------------------ #
        self._status_label = QLabel("")
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setVisible(False)
        layout.addWidget(self._status_label)

        # ------------------------------------------------------------------ #
        # Table
        # ------------------------------------------------------------------ #
        self._model = QStandardItemModel(0, len(self._COLUMNS))
        self._model.setHorizontalHeaderLabels(self._COLUMNS)

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self._table)

    # ---------------------------------------------------------------------- #
    # Public helpers for sub-classes
    # ---------------------------------------------------------------------- #

    def _as_at_date(self) -> str:
        """Return the as-at date as ISO-8601 string.  Only valid in AS_AT mode."""
        assert self._date_as_at is not None, "Not in DATE_MODE_AS_AT"
        return self._date_as_at.date().toString("yyyy-MM-dd")

    def _from_date(self) -> str:
        """Return the from-date as ISO-8601 string.  Only valid in RANGE mode."""
        assert self._date_from is not None, "Not in DATE_MODE_RANGE"
        return self._date_from.date().toString("yyyy-MM-dd")

    def _to_date(self) -> str:
        """Return the to-date as ISO-8601 string.  Only valid in RANGE mode."""
        assert self._date_to is not None, "Not in DATE_MODE_RANGE"
        return self._date_to.date().toString("yyyy-MM-dd")

    def _set_status(self, level: str = "", message: str = "") -> None:
        """Update the status label.

        Args:
            level: ``""``, ``"loading"``, ``"empty"``, or ``"error"``.
            message: Human-readable message to display.
        """
        if not message:
            self._status_label.setVisible(False)
            return

        styles = {
            "loading": "color: #555; font-style: italic;",
            "empty":   "color: #888;",
            "error":   "color: #c62828;",
        }
        self._status_label.setStyleSheet(styles.get(level, ""))
        self._status_label.setText(message)
        self._status_label.setVisible(True)

    # ---------------------------------------------------------------------- #
    # Slots / private
    # ---------------------------------------------------------------------- #

    def _run_report(self) -> None:  # pragma: no cover
        """Sub-classes must override this to fetch data and populate _model."""
        raise NotImplementedError("Sub-classes must implement _run_report()")

    def _choose_export_path(self) -> "str | None":
        """Open a save-file dialog and return the chosen path, or None.

        Extracted into its own method so tests can monkeypatch it without
        having to deal with a blocking QFileDialog in an offscreen environment.
        """
        from saebooks_desktop.services.csv_export import ensure_csv_path

        return ensure_csv_path(self, self._REPORT_NAME)

    def _on_export_clicked(self) -> None:
        """Export the current model data to a CSV file chosen by the user.

        Emits ``export_requested`` both when the user accepts the save dialog
        (for any connected slots) and on write completion.  The signal is
        preserved for back-compat with E/7 tests.
        """
        from PySide6.QtWidgets import QMessageBox

        from saebooks_desktop.services.csv_export import export_model_to_csv

        path = self._choose_export_path()
        if path is None:
            return  # user cancelled

        try:
            n = export_model_to_csv(self._model, path)
        except OSError as exc:
            QMessageBox.critical(self, "Export failed", f"Could not write CSV:\n{exc}")
            return

        self.export_requested.emit(self._REPORT_NAME)
        # Show a confirmation toast using the status label.
        basename = path.split("/")[-1].split("\\")[-1]
        self._status_label.setStyleSheet("color: #2e7d32;")
        self._status_label.setText(f"Exported {n} rows to {basename}")
        self._status_label.setVisible(True)
