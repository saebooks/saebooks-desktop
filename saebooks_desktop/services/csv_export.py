"""CSV export helpers for Qt model views.

``export_model_to_csv`` serialises the visible rows of any QAbstractItemModel
to a CSV file using only the stdlib ``csv`` module.  ``ensure_csv_path`` wraps
QFileDialog to get a save path with a dated default filename.

Design notes:
- DisplayRole text is used for every cell — UserRole ids (internal keys) are
  intentionally skipped because they should never appear in an exported file.
- Alignment hints stored on items (TextAlignmentRole) are silently dropped —
  they are presentation metadata, not data.
- The ``exclude_user_role`` parameter exists for testing; in production it
  should always be True.
"""
from __future__ import annotations

import csv
import datetime
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from PySide6.QtWidgets import QWidget


def export_model_to_csv(
    model: object,
    path: str,
    exclude_user_role: bool = True,
) -> int:
    """Write the visible rows of *model* to *path* as CSV.

    The first row written is the header (``model.headerData`` for each column).
    Subsequent rows come from ``model.data(index, DisplayRole)`` — alignment
    and UserRole data are ignored.

    Args:
        model: Any ``QAbstractItemModel`` instance.
        path: Absolute filesystem path for the output ``.csv`` file.
        exclude_user_role: Ignored in the current implementation (kept for API
            compatibility) — UserRole data is never written regardless.

    Returns:
        Number of data rows written (not counting the header).

    Raises:
        OSError: if the file cannot be opened for writing.
    """
    from PySide6.QtCore import Qt

    col_count: int = model.columnCount()  # type: ignore[union-attr]
    row_count: int = model.rowCount()  # type: ignore[union-attr]

    # Build header row from horizontal header labels.
    headers: list[str] = []
    for col in range(col_count):
        raw = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)  # type: ignore[union-attr]
        headers.append(str(raw) if raw is not None else "")

    # Build data rows — display text only.
    rows: list[list[str]] = []
    for row in range(row_count):
        cells: list[str] = []
        for col in range(col_count):
            index = model.index(row, col)  # type: ignore[union-attr]
            raw = model.data(index, Qt.ItemDataRole.DisplayRole)  # type: ignore[union-attr]
            cells.append(str(raw) if raw is not None else "")
        rows.append(cells)

    # Write — ensure the parent directory exists.
    parent_dir = os.path.dirname(path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(headers)
        writer.writerows(rows)

    return len(rows)


def ensure_csv_path(
    parent_widget: "QWidget | None",
    default_basename: str,
) -> "str | None":
    """Open a Save File dialog and return the chosen path, or None if cancelled.

    The dialog defaults to ``<default_basename>-YYYY-MM-DD.csv`` in the user's
    home directory.  The ``.csv`` extension is appended automatically if the
    user omits it.

    Args:
        parent_widget: Parent widget for the dialog (may be None).
        default_basename: Stem of the suggested filename (e.g. ``"balance_sheet"``).

    Returns:
        Absolute path string if the user confirmed, ``None`` if cancelled.
    """
    from PySide6.QtWidgets import QFileDialog

    today = datetime.date.today().strftime("%Y-%m-%d")
    default_name = f"{default_basename}-{today}.csv"
    default_path = os.path.join(os.path.expanduser("~"), default_name)

    path, _ = QFileDialog.getSaveFileName(
        parent_widget,
        "Export CSV",
        default_path,
        "CSV files (*.csv);;All files (*)",
    )

    if not path:
        return None

    # Append .csv if the user removed it.
    if not path.lower().endswith(".csv"):
        path = path + ".csv"

    return path
