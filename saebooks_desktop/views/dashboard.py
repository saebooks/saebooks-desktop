"""Dashboard view — landing-page summary of P&L, aged reports and module health.

Composes ``services.dashboard.build_dashboard_model`` into a row of stat
tiles (Revenue / Expenses / Net profit / Receivables / Payables) plus a
"Modules" health strip.  Each report section is fetched independently by the
service layer, so a single degraded module doesn't blank the whole page —
only a fully offline server (``ServerOfflineError``) shows the offline
banner and leaves the tiles at their last-known (or dash) state.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from saebooks_desktop.i18n import tr
from saebooks_desktop.services import period
from saebooks_desktop.services.api_client import APIClient, ServerOfflineError
from saebooks_desktop.services.company_settings import get_company
from saebooks_desktop.services.dashboard import build_dashboard_model
from saebooks_desktop.services.settings import get_company_id

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value extraction helpers (module-level so tests can pin them directly)
# ---------------------------------------------------------------------------


def _to_float(value: Any) -> float | None:
    """Coerce *value* to a float, returning None if it isn't numeric-like."""
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _first_present(d: dict[str, Any], keys: list[str]) -> float | None:
    """Return the first numeric value found in *d* for any key in *keys*."""
    for key in keys:
        if key in d:
            value = _to_float(d[key])
            if value is not None:
                return value
    return None


def _sum_line_amounts(section: dict[str, Any]) -> float | None:
    """Sum the ``amount`` field across every list-valued key in *section*.

    Used as a last-resort fallback when a report section has no total field
    of its own but does carry line items (each ``{"amount": float, ...}``).
    Returns None (not 0.0) when no line items were found at all, so callers
    can tell "no data" apart from "total is genuinely zero".
    """
    total = 0.0
    found = False
    for value in section.values():
        if isinstance(value, list):
            for line in value:
                if isinstance(line, dict) and "amount" in line:
                    amount = _to_float(line["amount"])
                    if amount is not None:
                        total += amount
                        found = True
    return total if found else None


def _extract_pl_totals(pl: dict[str, Any]) -> tuple[float | None, float | None, float | None]:
    """Return ``(revenue, expenses, net_profit)`` pulled defensively from a P&L dict.

    Primary assumption (matches ``services/reports.py`` / the engine's
    documented response shape): totals are nested under
    ``pl["income"]["total_income"]`` / ``pl["expenses"]["total_expenses"]``,
    with ``pl["net_profit"]`` at the top level.  Falls back to flatter key
    names, then to summing line-item ``amount`` fields, in case a deployed
    engine version differs.
    """
    income = pl.get("income") or {}
    expenses_section = pl.get("expenses") or {}

    revenue = _first_present(income, ["total_income", "income_total", "revenue"])
    if revenue is None:
        revenue = _sum_line_amounts(income)
    if revenue is None:
        revenue = _first_present(pl, ["total_income", "income_total", "revenue"])

    expenses = _first_present(
        expenses_section, ["total_expenses", "expense_total", "expenses"]
    )
    if expenses is None:
        expenses = _sum_line_amounts(expenses_section)
    if expenses is None:
        expenses = _first_present(pl, ["total_expenses", "expense_total", "expenses"])

    net_profit = _to_float(pl.get("net_profit"))
    if net_profit is None and revenue is not None and expenses is not None:
        net_profit = revenue - expenses

    return revenue, expenses, net_profit


def _extract_aged_total(rep: dict[str, Any] | None) -> str | None:
    """Return the formatted grand total from an aged receivables/payables dict.

    Primary assumption: ``rep["totals"]["total"]`` (nested, matching the
    engine's documented shape where ``buckets`` is a list of bucket-name
    strings, not a summable list).  Falls back to a flat ``"total"`` /
    ``"grand_total"`` key, then to summing each contact row's ``"total"``.
    Returns None if no total could be extracted at all.
    """
    if not rep:
        return None

    totals = rep.get("totals") or {}
    total = _to_float(totals.get("total"))

    if total is None:
        total = _first_present(rep, ["total", "grand_total"])

    if total is None:
        contacts = rep.get("contacts") or []
        summed = 0.0
        found = False
        for contact in contacts:
            amount = _to_float(contact.get("total"))
            if amount is not None:
                summed += amount
                found = True
        total = summed if found else None

    if total is None:
        return None
    return _format_amount(total)


def _format_amount(value: Any) -> str:
    """Format *value* with thousands separators and 2 decimals, or a dash."""
    v = _to_float(value)
    if v is None:
        return "—"  # em dash
    return f"{v:,.2f}"


# ---------------------------------------------------------------------------
# View
# ---------------------------------------------------------------------------

_TILE_SPECS: list[tuple[str, str]] = [
    ("revenue", "Revenue"),
    ("expenses", "Expenses"),
    ("net_profit", "Net profit"),
    ("receivables", "Receivables outstanding"),
    ("payables", "Payables outstanding"),
]

#: Period-picker presets for the P&L tiles (revenue/expenses/net profit) —
#: same ids + labels as saebooks-web's period picker (period.PRESET_IDS),
#: reusing the same i18n msgids via the shared .mo catalogs (see i18n.py
#: module docstring). "Custom range" isn't offered here — no date-range
#: input widgets on the dashboard; use the full P&L report view for that.
_PERIOD_PRESET_OPTIONS: list[tuple[str, str]] = [
    ("this_fy", "This FY"),
    ("last_fy", "Last FY"),
    ("calendar_ytd", "Calendar year to date"),
    ("trailing_12", "Trailing 12 months"),
    ("this_quarter", "This quarter"),
]


class DashboardView(QWidget):
    """Dashboard landing page — P&L / aged-report summary tiles + module health.

    Call ``load(client=None)`` to fetch and populate; the constructor only
    builds the (empty) UI so instantiating the view never makes a network
    call.  ``load()`` never raises — a ``ServerOfflineError`` (or any other
    unexpected failure) shows the offline banner instead.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self._client: APIClient | None = None
        self._tile_values: dict[str, QLabel] = {}
        self._tile_captions: dict[str, QLabel] = {}
        self._fin_year_start_month = 7

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        # --- Header row ---
        header_widget = QWidget()
        header_layout = QHBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel("Dashboard")
        title.setStyleSheet("font-size: 18px; font-weight: bold;")
        header_layout.addWidget(title)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        header_layout.addWidget(spacer)

        # --- Period picker (drives the Revenue/Expenses/Net profit tiles) ---
        self._period_combo = QComboBox()
        self._period_combo.setObjectName("period_combo")
        for preset_id, label in _PERIOD_PRESET_OPTIONS:
            self._period_combo.addItem(tr(label), preset_id)
        self._period_combo.setCurrentIndex(3)  # "Trailing 12 months" — prior default
        self._period_combo.currentIndexChanged.connect(self._on_period_changed)
        header_layout.addWidget(self._period_combo)

        self._refresh_btn = QPushButton("Refresh")
        self._refresh_btn.setObjectName("refresh_btn")
        self._refresh_btn.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self._refresh_btn)

        layout.addWidget(header_widget)

        # --- Resolved period subtitle (e.g. "2025-07-21 → 2026-07-21") ---
        self._period_label = QLabel("")
        self._period_label.setObjectName("period_label")
        self._period_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(self._period_label)

        # --- Offline banner ---
        self._offline_banner = QLabel("Server offline — dashboard data unavailable")
        self._offline_banner.setObjectName("offline_banner")
        self._offline_banner.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._offline_banner.setStyleSheet(
            "background: #fff3cd; color: #856404; padding: 4px;"
        )
        self._offline_banner.setVisible(False)
        layout.addWidget(self._offline_banner)

        # --- Stat tiles ---
        tiles_widget = QWidget()
        tiles_layout = QHBoxLayout(tiles_widget)
        tiles_layout.setContentsMargins(0, 0, 0, 0)
        for key, caption in _TILE_SPECS:
            frame, value_label, caption_label = self._make_tile(tr(caption))
            self._tile_values[key] = value_label
            self._tile_captions[key] = caption_label
            tiles_layout.addWidget(frame)
        layout.addWidget(tiles_widget)

        # --- Modules strip ---
        modules_widget = QWidget()
        modules_layout = QHBoxLayout(modules_widget)
        modules_layout.setContentsMargins(0, 0, 0, 0)
        modules_layout.addWidget(QLabel("Modules:"))
        self._modules_label = QLabel("")
        modules_layout.addWidget(self._modules_label)
        modules_spacer = QWidget()
        modules_spacer.setSizePolicy(
            QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred
        )
        modules_layout.addWidget(modules_spacer)
        layout.addWidget(modules_widget)

        layout.addStretch(1)

    # ------------------------------------------------------------------
    # UI construction helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_tile(caption: str) -> tuple[QFrame, QLabel, QLabel]:
        """Build a stat tile: a QFrame with a big value QLabel + caption QLabel."""
        frame = QFrame()
        frame.setFrameShape(QFrame.Shape.StyledPanel)

        tile_layout = QVBoxLayout(frame)
        tile_layout.setContentsMargins(12, 8, 12, 8)

        value_label = QLabel("—")
        value_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        value_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tile_layout.addWidget(value_label)

        caption_label = QLabel(caption)
        caption_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        caption_label.setStyleSheet("color: #666;")
        tile_layout.addWidget(caption_label)

        return frame, value_label, caption_label

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def showEvent(self, event) -> None:  # type: ignore[override]
        """First display triggers the initial load (keeps construction
        network-free for tests and window startup)."""
        super().showEvent(event)
        if not getattr(self, "_loaded_once", False):
            self._loaded_once = True
            self.load()

    def load(self, client: APIClient | None = None) -> None:
        """Fetch the dashboard model and populate the tiles.

        Args:
            client: Optional APIClient to use for this (and future refresh)
                calls; if omitted, the client from the previous call is
                reused, or a new ``APIClient()`` is created.

        Never raises: a ``ServerOfflineError`` shows the offline banner and
        any other unexpected exception is logged and swallowed.
        """
        self._offline_banner.setVisible(False)
        # Marks the view as loaded so _on_period_changed knows a later
        # combo change is a real user interaction, not construction-time
        # signal noise — set here too (not only in showEvent) since callers
        # (including tests) may call load() directly without ever showing
        # the widget.
        self._loaded_once = True

        today = date.today().isoformat()
        preset = self._period_combo.currentData() or "trailing_12"
        try:
            self._client = client or self._client or APIClient()
            self._fin_year_start_month = self._fetch_fin_year_start_month(self._client)
            model = build_dashboard_model(
                self._client, today, preset=preset,
                fin_year_start_month=self._fin_year_start_month,
            )
        except ServerOfflineError:
            self._offline_banner.setVisible(True)
            return
        except Exception:  # noqa: BLE001 — load() must never raise
            logger.exception("Dashboard load failed unexpectedly")
            return

        self._populate(model)

    def _fetch_fin_year_start_month(self, client: APIClient) -> int:
        """Best-effort fetch of the active company's fin_year_start_month.

        Returns 7 (AU default) if no company is configured yet, the fetch
        fails, or the field is missing/unparseable — same "degrade softly"
        contract as every other tile fetch in this view.
        """
        company_id = get_company_id()
        if not company_id:
            return 7
        try:
            company = get_company(client, company_id)
            value = company.get("fin_year_start_month")
            return int(value) if value else 7
        except Exception:  # noqa: BLE001 — never block the dashboard load
            return 7

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_refresh_clicked(self) -> None:
        self.load()

    def _on_period_changed(self, _index: int) -> None:
        # Only reload once the view has actually been shown once — the
        # combo box's initial addItem() calls each fire currentIndexChanged
        # too, and load() before showEvent would make a network call from
        # the constructor (breaks the "construction is network-free"
        # contract other tests rely on).
        if getattr(self, "_loaded_once", False):
            self.load()

    def _populate(self, model: dict[str, Any]) -> None:
        errors: dict[str, str] = model.get("errors", {})

        pl = model.get("pl")
        if pl is not None and "pl" not in errors:
            revenue, expenses, net_profit = _extract_pl_totals(pl)
        else:
            revenue = expenses = net_profit = None
        self._tile_values["revenue"].setText(_format_amount(revenue))
        self._tile_values["expenses"].setText(_format_amount(expenses))
        self._tile_values["net_profit"].setText(_format_amount(net_profit))

        pl_from = model.get("pl_from_date")
        pl_to = model.get("pl_to_date")
        if pl_from and pl_to:
            self._period_label.setText(f"{pl_from} → {pl_to}")
        else:
            self._period_label.setText("")

        ar = model.get("ar")
        ar_text = _extract_aged_total(ar) if "ar" not in errors else None
        self._tile_values["receivables"].setText(
            ar_text if ar_text is not None else "—"
        )

        ap = model.get("ap")
        ap_text = _extract_aged_total(ap) if "ap" not in errors else None
        self._tile_values["payables"].setText(
            ap_text if ap_text is not None else "—"
        )

        self._populate_modules(model)

    def _populate_modules(self, model: dict[str, Any]) -> None:
        errors: dict[str, str] = model.get("errors", {})

        if "modules" in errors:
            self._modules_label.setText(errors["modules"])
            return

        modules_data = model.get("modules")
        module_list: list[dict[str, Any]] = (
            (modules_data or {}).get("modules", []) if modules_data else []
        )

        degraded = [
            m
            for m in module_list
            if (m.get("kind") == "delegated" and m.get("health") != "ok")
            or m.get("entitled") is False
        ]

        if not degraded:
            self._modules_label.setText("All modules healthy")
            return

        lines = [f"{m.get('id')}: {m.get('health')}" for m in degraded]
        self._modules_label.setText("\n".join(lines))
