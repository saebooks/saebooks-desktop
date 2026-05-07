"""Tests for saebooks_desktop.services.csv_export.

Uses a QStandardItemModel as the model under test — no real API calls.
"""
from __future__ import annotations

import csv
import io
import os
import tempfile

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_model(qapp, rows: list[list[str]], headers: list[str]):
    """Return a QStandardItemModel populated with *rows* and *headers*."""
    from PySide6.QtGui import QStandardItem, QStandardItemModel

    model = QStandardItemModel(0, len(headers))
    model.setHorizontalHeaderLabels(headers)
    for row_data in rows:
        row = model.rowCount()
        model.insertRow(row)
        for col, text in enumerate(row_data):
            model.setItem(row, col, QStandardItem(text))
    return model


def _read_csv(path: str) -> list[list[str]]:
    """Parse a CSV file and return all rows (including header)."""
    with open(path, newline="", encoding="utf-8") as fh:
        return list(csv.reader(fh))


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


class TestExportModelToCsv:
    def test_three_rows_written(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        rows = [["a1", "b1"], ["a2", "b2"], ["a3", "b3"]]
        model = _make_model(qapp, rows, ["A", "B"])
        path = str(tmp_path / "out.csv")
        n = export_model_to_csv(model, path)
        assert n == 3
        parsed = _read_csv(path)
        assert len(parsed) == 4  # header + 3 data rows
        assert parsed[0] == ["A", "B"]
        assert parsed[1] == ["a1", "b1"]

    def test_empty_model_writes_header_only(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = _make_model(qapp, [], ["X", "Y", "Z"])
        path = str(tmp_path / "empty.csv")
        n = export_model_to_csv(model, path)
        assert n == 0
        parsed = _read_csv(path)
        assert len(parsed) == 1
        assert parsed[0] == ["X", "Y", "Z"]

    def test_returns_row_count(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = _make_model(qapp, [["x"]] * 7, ["Col"])
        path = str(tmp_path / "seven.csv")
        n = export_model_to_csv(model, path)
        assert n == 7

    def test_special_chars_escaped_by_csv_module(self, qapp, tmp_path) -> None:
        """Values with commas/quotes/newlines must be properly CSV-quoted."""
        from saebooks_desktop.services.csv_export import export_model_to_csv

        rows = [['say "hello"', "a,b,c"], ["line1\nline2", "normal"]]
        model = _make_model(qapp, rows, ["Text", "Value"])
        path = str(tmp_path / "special.csv")
        export_model_to_csv(model, path)
        parsed = _read_csv(path)
        # csv.reader should reconstruct the original strings.
        assert parsed[1][0] == 'say "hello"'
        assert parsed[1][1] == "a,b,c"

    def test_single_column_model(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = _make_model(qapp, [["alpha"], ["beta"]], ["Name"])
        path = str(tmp_path / "single.csv")
        n = export_model_to_csv(model, path)
        assert n == 2
        parsed = _read_csv(path)
        assert parsed[0] == ["Name"]
        assert parsed[2] == ["beta"]

    def test_user_role_id_not_in_output(self, qapp, tmp_path) -> None:
        """UserRole data (internal ids) must NOT appear in the CSV."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QStandardItem, QStandardItemModel

        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = QStandardItemModel(0, 2)
        model.setHorizontalHeaderLabels(["Number", "Name"])
        model.insertRow(0)
        number_item = QStandardItem("INV-001")
        number_item.setData("uuid-secret-id", Qt.ItemDataRole.UserRole)
        model.setItem(0, 0, number_item)
        model.setItem(0, 1, QStandardItem("Acme"))

        path = str(tmp_path / "user_role.csv")
        export_model_to_csv(model, path)
        content = open(path).read()
        assert "uuid-secret-id" not in content
        assert "INV-001" in content

    def test_alignment_role_not_in_output(self, qapp, tmp_path) -> None:
        """Text alignment hints stored on items should not appear in CSV."""
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QStandardItem, QStandardItemModel

        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = QStandardItemModel(0, 1)
        model.setHorizontalHeaderLabels(["Amount"])
        model.insertRow(0)
        item = QStandardItem("1500.00")
        item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        model.setItem(0, 0, item)

        path = str(tmp_path / "align.csv")
        export_model_to_csv(model, path)
        parsed = _read_csv(path)
        assert parsed[1][0] == "1500.00"

    def test_file_written_to_correct_path(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = _make_model(qapp, [["foo"]], ["Col"])
        path = str(tmp_path / "subdir" / "out.csv")
        export_model_to_csv(model, path)
        assert os.path.exists(path)

    def test_unicode_content_written_correctly(self, qapp, tmp_path) -> None:
        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = _make_model(qapp, [["Acme Pty \u2014 Ltd", "\u00e9l\u00e8ve"]], ["Name", "Word"])
        path = str(tmp_path / "unicode.csv")
        export_model_to_csv(model, path)
        parsed = _read_csv(path)
        assert parsed[1][0] == "Acme Pty \u2014 Ltd"
        assert parsed[1][1] == "\u00e9l\u00e8ve"

    def test_none_cell_written_as_empty_string(self, qapp, tmp_path) -> None:
        """A cell with no data (None DisplayRole) should yield an empty string."""
        from PySide6.QtGui import QStandardItemModel

        from saebooks_desktop.services.csv_export import export_model_to_csv

        model = QStandardItemModel(1, 1)
        model.setHorizontalHeaderLabels(["Col"])
        # Do NOT set any item — data() returns None by default.
        path = str(tmp_path / "none_cell.csv")
        export_model_to_csv(model, path)
        parsed = _read_csv(path)
        assert parsed[1] == [""]
