"""Fixed Assets views — list and detail.

``FixedAssetsView``
    Filterable, paginated QTableView of fixed assets fetched from
    ``GET /api/v1/fixed_assets``.

    Columns: Name | Code | Purchase Date | Purchase Price | Net Book Value | Status

    Signals:
        asset_selected(str)        — emitted on double-click with the asset id.
        new_asset_requested()      — emitted when "New Asset" is clicked.

``FixedAssetDetail``
    Read-only detail panel for a single fixed asset, including a table of
    depreciation runs.

    Action toolbar: Depreciate | Dispose | Back

    Signals:
        depreciate_requested(str)  — emitted with the asset id.
        dispose_requested(str)     — emitted with the asset id.
        back_requested()           — Back button.
"""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QStandardItem, QStandardItemModel
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.fixed_assets import (
    dispose_asset,
    get_fixed_asset,
    list_fixed_assets,
    run_depreciation,
)

# ---------------------------------------------------------------------------
# List view constants
# ---------------------------------------------------------------------------

_COL_NAME = 0
_COL_CODE = 1
_COL_PURCHASE_DATE = 2
_COL_PURCHASE_PRICE = 3
_COL_NBV = 4
_COL_STATUS = 5

_COLUMNS = ["Name", "Code", "Purchase Date", "Purchase Price", "Net Book Value", "Status"]

_STATUS_COLORS: dict[str, QColor] = {
    "active": QColor("#2e7d32"),
    "disposed": QColor("#c62828"),
}

_STATUS_OPTIONS = ["All", "Active", "Disposed"]

_PAGE_SIZE = 50

# ---------------------------------------------------------------------------
# Depreciation runs table constants
# ---------------------------------------------------------------------------

_DRUNC_COL_DATE = 0
_DRUNC_COL_AMOUNT = 1
_DRUNC_COL_NBV_AFTER = 2

_DRUNC_COLUMNS = ["Period Date", "Depreciation Amount", "NBV After"]


class _StatusDelegate(QStyledItemDelegate):
    """Render the Status column with a coloured foreground."""

    def initStyleOption(
        self, option: QStyleOptionViewItem, index: object
    ) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        raw = index.data(Qt.ItemDataRole.DisplayRole) or ""  # type: ignore[union-attr]
        colour = _STATUS_COLORS.get(raw.lower())
        if colour:
            option.palette.setColor(option.palette.ColorRole.Text, colour)  # type: ignore[union-attr]


class FixedAssetsView(QWidget):
    """Fixed assets list view.

    Fetches from ``/api/v1/fixed_assets`` via REST and renders a filterable,
    paginated table.  Emits ``asset_selected(id)`` on double-click.
    """

    asset_selected = Signal(str)
    new_asset_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._current_page = 1
        self._has_more = True

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # --- Filter toolbar ---
        toolbar_widget = QWidget()
        toolbar_layout = QHBoxLayout(toolbar_widget)
        toolbar_layout.setContentsMargins(8, 4, 8, 4)

        toolbar_layout.addWidget(QLabel("Status:"))
        self._status_combo = QComboBox()
        self._status_combo.addItems(_STATUS_OPTIONS)
        self._status_combo.currentIndexChanged.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self._status_combo)

        spacer = QWidget()
        spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(spacer)

        self._new_btn = QPushButton("New Asset")
        self._new_btn.clicked.connect(self.new_asset_requested)
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

        self._table = QTableView()
        self._table.setModel(self._model)
        self._table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._table.horizontalHeader().setStretchLastSection(True)

        # Right-align monetary columns
        for col in (_COL_PURCHASE_PRICE, _COL_NBV):
            self._model.horizontalHeaderItem(col).setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

        self._table.setItemDelegateForColumn(_COL_STATUS, _StatusDelegate(self._table))
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)

        # --- Load more button ---
        self._load_more_btn = QPushButton("Load more")
        self._load_more_btn.clicked.connect(self._on_load_more)
        layout.addWidget(self._load_more_btn)

        self._load_assets(reset=True)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def reload(self) -> None:
        """Re-fetch from page 1, respecting current filter state."""
        self._load_assets(reset=True)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _active_status_filter(self) -> str | None:
        text = self._status_combo.currentText()
        return None if text == "All" else text.lower()

    def _load_assets(self, reset: bool = False) -> None:
        if reset:
            self._current_page = 1
            self._model.removeRows(0, self._model.rowCount())
            self._has_more = True

        self._offline_label.setVisible(False)
        try:
            items = list_fixed_assets(
                self._client,
                page=self._current_page,
                page_size=_PAGE_SIZE,
                status_filter=self._active_status_filter(),
            )
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._append_rows(items)

        if len(items) < _PAGE_SIZE:
            self._has_more = False

        self._load_more_btn.setEnabled(self._has_more)

    def _append_rows(self, assets: list[dict[str, Any]]) -> None:
        for asset in assets:
            row = self._model.rowCount()
            self._model.insertRow(row)

            self._model.setItem(row, _COL_NAME, QStandardItem(asset.get("name") or ""))
            self._model.setItem(row, _COL_CODE, QStandardItem(asset.get("code") or ""))
            self._model.setItem(
                row,
                _COL_PURCHASE_DATE,
                QStandardItem(asset.get("purchase_date") or ""),
            )

            price_item = QStandardItem(str(asset.get("purchase_price") or ""))
            price_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_PURCHASE_PRICE, price_item)

            nbv_item = QStandardItem(str(asset.get("net_book_value") or ""))
            nbv_item.setTextAlignment(
                Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )
            self._model.setItem(row, _COL_NBV, nbv_item)

            self._model.setItem(
                row, _COL_STATUS, QStandardItem(asset.get("status") or "")
            )

            # Store the asset id for double-click signal
            self._model.item(row, _COL_NAME).setData(
                asset.get("id") or "", Qt.ItemDataRole.UserRole
            )

    def _on_filter_changed(self) -> None:
        self._load_assets(reset=True)

    def _on_load_more(self) -> None:
        if not self._has_more:
            return
        self._current_page += 1
        self._load_assets(reset=False)

    def _on_double_click(self, index: object) -> None:
        row = index.row()  # type: ignore[union-attr]
        id_item = self._model.item(row, _COL_NAME)
        if id_item is not None:
            asset_id = id_item.data(Qt.ItemDataRole.UserRole)
            if asset_id:
                self.asset_selected.emit(str(asset_id))


# ---------------------------------------------------------------------------
# Detail view
# ---------------------------------------------------------------------------


class FixedAssetDetail(QWidget):
    """Read-only detail view for a single fixed asset.

    Call ``load(asset_id)`` to populate.
    """

    depreciate_requested = Signal(str)
    dispose_requested = Signal(str)
    back_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client = APIClient()
        self._asset_id: str = ""
        self._asset_status: str = ""

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        # --- Offline banner ---
        self._offline_label = QLabel("Server offline — showing cached data")
        self._offline_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_label.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_label.setVisible(False)
        layout.addWidget(self._offline_label)

        # --- Header section ---
        header_frame = QFrame()
        header_frame.setFrameShape(QFrame.Shape.StyledPanel)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setSpacing(4)

        # Row 1: name + status badge
        top_row = QWidget()
        top_row_layout = QHBoxLayout(top_row)
        top_row_layout.setContentsMargins(0, 0, 0, 0)

        self._name_label = QLabel()
        name_font = QFont()
        name_font.setBold(True)
        name_font.setPointSize(16)
        self._name_label.setFont(name_font)
        top_row_layout.addWidget(self._name_label)

        self._status_badge = QLabel()
        self._status_badge.setFixedHeight(24)
        self._status_badge.setAlignment(
            Qt.AlignmentFlag.AlignCenter | Qt.AlignmentFlag.AlignVCenter
        )
        self._status_badge.setStyleSheet(
            "border-radius: 4px; padding: 2px 8px; font-weight: bold;"
        )
        top_row_layout.addWidget(self._status_badge)

        badge_spacer = QWidget()
        badge_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        top_row_layout.addWidget(badge_spacer)
        header_layout.addWidget(top_row)

        # Row 2: meta fields
        meta_row = QWidget()
        meta_layout = QHBoxLayout(meta_row)
        meta_layout.setContentsMargins(0, 0, 0, 0)
        meta_layout.setSpacing(24)

        meta_layout.addWidget(QLabel("Code:"))
        self._code_label = QLabel()
        meta_layout.addWidget(self._code_label)

        meta_layout.addWidget(QLabel("Purchase Date:"))
        self._purchase_date_label = QLabel()
        meta_layout.addWidget(self._purchase_date_label)

        meta_layout.addWidget(QLabel("Purchase Price:"))
        self._purchase_price_label = QLabel()
        meta_layout.addWidget(self._purchase_price_label)

        meta_layout.addWidget(QLabel("Net Book Value:"))
        self._nbv_label = QLabel()
        meta_layout.addWidget(self._nbv_label)

        meta_spacer = QWidget()
        meta_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        meta_layout.addWidget(meta_spacer)
        header_layout.addWidget(meta_row)
        layout.addWidget(header_frame)

        # --- Depreciation runs table ---
        runs_label = QLabel("Depreciation Runs")
        runs_font = QFont()
        runs_font.setBold(True)
        runs_label.setFont(runs_font)
        layout.addWidget(runs_label)

        self._runs_model = QStandardItemModel(0, len(_DRUNC_COLUMNS))
        self._runs_model.setHorizontalHeaderLabels(_DRUNC_COLUMNS)

        self._runs_table = QTableView()
        self._runs_table.setModel(self._runs_model)
        self._runs_table.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self._runs_table.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self._runs_table.horizontalHeader().setStretchLastSection(True)

        # Right-align monetary columns in depreciation runs table
        _right = _RightAlignDelegate(self._runs_table)
        self._runs_table.setItemDelegateForColumn(_DRUNC_COL_AMOUNT, _right)
        self._runs_table.setItemDelegateForColumn(_DRUNC_COL_NBV_AFTER, _right)

        layout.addWidget(self._runs_table, 1)

        # --- Action toolbar ---
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 4, 0, 0)

        toolbar_spacer = QWidget()
        toolbar_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        toolbar_layout.addWidget(toolbar_spacer)

        self._depreciate_btn = QPushButton("Depreciate")
        self._depreciate_btn.setEnabled(False)
        self._depreciate_btn.clicked.connect(self._on_depreciate_clicked)
        toolbar_layout.addWidget(self._depreciate_btn)

        self._dispose_btn = QPushButton("Dispose")
        self._dispose_btn.setEnabled(False)
        self._dispose_btn.clicked.connect(self._on_dispose_clicked)
        toolbar_layout.addWidget(self._dispose_btn)

        self._back_btn = QPushButton("Back")
        self._back_btn.clicked.connect(self.back_requested)
        toolbar_layout.addWidget(self._back_btn)

        layout.addWidget(toolbar)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def load(self, asset_id: str) -> None:
        """Fetch and display the fixed asset identified by *asset_id*."""
        self._asset_id = asset_id
        self._offline_label.setVisible(False)

        try:
            data = get_fixed_asset(self._client, asset_id)
        except (ServerOfflineError, Exception):  # noqa: BLE001
            self._offline_label.setVisible(True)
            return

        self._populate(data)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _populate(self, data: dict[str, Any]) -> None:
        self._asset_status = (data.get("status") or "").lower()

        self._name_label.setText(data.get("name") or "")
        self._set_status_badge(self._asset_status)
        self._code_label.setText(data.get("code") or "")
        self._purchase_date_label.setText(str(data.get("purchase_date") or ""))
        self._purchase_price_label.setText(str(data.get("purchase_price") or ""))
        self._nbv_label.setText(str(data.get("net_book_value") or ""))

        # Depreciation runs
        self._runs_model.removeRows(0, self._runs_model.rowCount())
        for run in data.get("depreciation_runs") or []:
            self._append_run(run)

        # Buttons: active only for active assets
        is_active = self._asset_status == "active"
        self._depreciate_btn.setEnabled(is_active)
        self._dispose_btn.setEnabled(is_active)

    def _append_run(self, run: dict[str, Any]) -> None:
        row = self._runs_model.rowCount()
        self._runs_model.insertRow(row)
        self._runs_model.setItem(
            row, _DRUNC_COL_DATE, QStandardItem(str(run.get("period_date") or ""))
        )
        self._runs_model.setItem(
            row, _DRUNC_COL_AMOUNT, _num_item(run.get("depreciation_amount"))
        )
        self._runs_model.setItem(
            row, _DRUNC_COL_NBV_AFTER, _num_item(run.get("nbv_after"))
        )

    def _set_status_badge(self, status: str) -> None:
        colour_map = {"active": "#2e7d32", "disposed": "#c62828"}
        colour = colour_map.get(status, "#888888")
        self._status_badge.setText(status.upper() if status else "")
        bg = QColor(colour)
        r, g, b = bg.red(), bg.green(), bg.blue()
        self._status_badge.setStyleSheet(
            f"border-radius: 4px; padding: 2px 8px; font-weight: bold;"
            f" background: rgba({r},{g},{b},30); color: {colour};"
        )

    def _on_depreciate_clicked(self) -> None:
        if not self._asset_id:
            return
        reply = QMessageBox.question(
            self,
            "Run Depreciation",
            "Run a depreciation period for this asset?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.depreciate_requested.emit(self._asset_id)

    def _on_dispose_clicked(self) -> None:
        if not self._asset_id:
            return
        reply = QMessageBox.question(
            self,
            "Dispose Asset",
            "Are you sure you want to dispose of this asset? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.dispose_requested.emit(self._asset_id)


# ---------------------------------------------------------------------------
# Layout helpers
# ---------------------------------------------------------------------------


class _RightAlignDelegate(QStyledItemDelegate):
    """Right-align numeric columns."""

    def initStyleOption(self, option: QStyleOptionViewItem, index: object) -> None:
        super().initStyleOption(option, index)  # type: ignore[arg-type]
        option.displayAlignment = (  # type: ignore[union-attr]
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )


def _num_item(value: Any) -> QStandardItem:
    item = QStandardItem("" if value is None else str(value))
    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
    return item
