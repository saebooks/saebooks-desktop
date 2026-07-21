"""SAE Books main window — Command Centre-style sidebar navigation.

Navigation is mode-driven (adjudicated navigation verdict, revising PoC
decision #16): the sidebar branches on the selected company's
``bookkeeping_mode`` — never on licence tier.

* Cashbook mode: Cashbook / Reports (cashbook summary) / Settings plus
  exactly one "Full accounting →" doorway (explainer + lossless upgrade).
  Contacts is omitted — cashbook entries are contactless.
* Full mode: the full accounting nav with NO Cashbook item; "Switch to
  cashbook mode" lives in the Settings view.

The mode comes off the company record (``resolve_bookkeeping_mode`` —
409-probe fallback only, not a per-render round-trip). A company switch
or mode flip re-renders the nav via ``apply_bookkeeping_mode`` /
``refresh_company_context``.
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Slot
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QStackedWidget,
    QWidget,
)

from saebooks_desktop.branding import get_brand
from saebooks_desktop.cache.sync import SyncEngine
from saebooks_desktop.i18n import tr
from saebooks_desktop.licence import load_licence
from saebooks_desktop.services.cashbook import resolve_bookkeeping_mode
from saebooks_desktop.views.cashbook import CashbookView
from saebooks_desktop.views.cashbook_report import CashbookReportView
from saebooks_desktop.views.dashboard import DashboardView
from saebooks_desktop.views.full_accounting_door import FullAccountingDoorView
from saebooks_desktop.views.accounts import AccountsView
from saebooks_desktop.views.banking import BankingView
from saebooks_desktop.views.imports import ImportStatementView
from saebooks_desktop.views.reconciliation import ReconciliationView
from saebooks_desktop.views.bill_detail import BillDetailView
from saebooks_desktop.views.bills import BillsView
from saebooks_desktop.views.expenses import ExpensesView
from saebooks_desktop.views.contacts_view import ContactsView
from saebooks_desktop.views.invoice_detail import InvoiceDetailView
from saebooks_desktop.views.bill_form import BillForm
from saebooks_desktop.views.invoice_form import InvoiceForm
from saebooks_desktop.views.invoices import InvoicesView
from saebooks_desktop.views.items_view import ItemsView
from saebooks_desktop.views.journal_entries import JournalEntriesView
from saebooks_desktop.views.journal_entry_form import JournalEntryForm
from saebooks_desktop.views.payment_form import PaymentForm
from saebooks_desktop.views.payments import PaymentsView
from saebooks_desktop.views.purchase_order_detail import PurchaseOrderDetailView
from saebooks_desktop.views.purchase_orders import PurchaseOrdersView
from saebooks_desktop.views.budgets import BudgetsView
from saebooks_desktop.views.credit_notes import CreditNoteForm, CreditNotesView
from saebooks_desktop.views.fixed_assets import FixedAssetDetail, FixedAssetsView
from saebooks_desktop.views.projects import ProjectsView
from saebooks_desktop.views.recurring_invoices import RecurringInvoicesView
from saebooks_desktop.views.account_ranges import AccountRangesView
from saebooks_desktop.views.bank_rules import BankRulesView
from saebooks_desktop.views.journal_templates import JournalTemplatesView
from saebooks_desktop.views.reports.reports_view import ReportsView
from saebooks_desktop.views.search_view import SearchView
from saebooks_desktop.views.settings_view import SettingsView
from saebooks_desktop.views.tax_codes import TaxCodesView

# All views built into the stack: (canonical key, enabled). Every view is
# constructed once (lazy data loading happens on first show); which of them
# appear in the sidebar is decided per bookkeeping mode by _FULL_MODE_NAV /
# _CASHBOOK_MODE_NAV below. Canonical keys stay English (used for routing);
# only displayed text is translated.
_ALL_VIEWS: list[tuple[str, bool]] = [
    ("Dashboard", True),
    ("Cashbook", True),
    ("Cashbook Reports", True),
    ("Full Accounting", True),
    ("Contacts", True),
    ("Items", True),
    ("Accounts", True),
    ("Sales", True),
    ("Purchases", True),
    ("Expenses", True),
    ("Purchase Orders", True),
    ("Journal Entries", True),
    ("Banking", True),
    ("Payments", True),
    ("Fixed Assets", True),
    ("Credit Notes", True),
    ("Budgets", True),
    ("Projects", True),
    ("Recurring Invoices", True),
    ("Reports", True),
    ("Account Ranges", True),
    ("Bank Rules", True),
    ("Journal Templates", True),
    ("Tax Codes", True),
    ("Search", True),
    ("Settings", True),
]

# Keys that only appear in cashbook-mode navigation.
_CASHBOOK_ONLY_KEYS = {"Cashbook", "Cashbook Reports", "Full Accounting"}

# Nav models: (display label, canonical view key) per bookkeeping mode.
# Full mode = full accounting nav, NO Cashbook primary item (the downgrade
# action lives in Settings). Cashbook mode = Cashbook / Reports (cashbook
# summary) / Settings + exactly ONE "Full accounting →" doorway; Contacts
# is omitted (cashbook entries are contactless).
_FULL_MODE_NAV: list[tuple[str, str]] = [
    (key, key) for key, _enabled in _ALL_VIEWS if key not in _CASHBOOK_ONLY_KEYS
]
_CASHBOOK_MODE_NAV: list[tuple[str, str]] = [
    ("Cashbook", "Cashbook"),
    ("Reports", "Cashbook Reports"),
    ("Settings", "Settings"),
    ("Full accounting →", "Full Accounting"),
]


class _PlaceholderView(QWidget):
    """Placeholder shown for nav items not yet implemented."""

    def __init__(self, label: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        lbl = QLabel(f"{label}\n(coming soon)")
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl.setStyleSheet("color: #888; font-size: 16pt;")
        layout.addWidget(lbl)


class MainWindow(QMainWindow):
    """Application main window.

    Layout:
        ┌───────────────────────────────────┐
        │  [sidebar]  │  [stacked views]    │
        │  Dashboard  │                     │
        │  Contacts   │  <active view>      │
        │  Accounts   │                     │
        │  …          │                     │
        ├─────────────────────────────────── ┤
        │  status bar                       │
        └───────────────────────────────────┘
    """

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle(get_brand().product_name)
        self.setMinimumSize(1024, 768)

        self._licence = load_licence()

        # Root widget
        root = QWidget()
        self.setCentralWidget(root)
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # Sidebar
        self._nav = QListWidget()
        self._nav.setFixedWidth(180)
        self._nav.setObjectName("sidebar")
        self._nav.setStyleSheet(
            "#sidebar { background: #2b2b2b; color: #e0e0e0; border: none; font-size: 13pt; }"
            "#sidebar::item { padding: 12px 16px; }"
            "#sidebar::item:selected { background: #4a90d9; color: white; }"
            "#sidebar::item:disabled { color: #666; }"
        )

        self._stack = QStackedWidget()

        # Resolve the selected company's bookkeeping mode once — nav
        # branches on it (never on tier). Company record first; the 409
        # cashbook_not_configured probe is fallback only.
        from saebooks_desktop.services.api_client import APIClient as _APIClient

        self._bookkeeping_mode = resolve_bookkeeping_mode(_APIClient())

        # Build every view into the stack; the sidebar is populated from
        # the mode's nav model afterwards (_apply_nav).
        self._stack_index_by_key: dict[str, int] = {}  # canonical key -> stack_index
        self._view_indices: dict[int, int] = {}  # nav_row -> stack_index
        self._nav_row_by_key: dict[str, int] = {}  # canonical key -> nav_row

        for label, enabled in _ALL_VIEWS:
            if label == "Dashboard" and enabled:
                dashboard_view = DashboardView()
                self._dashboard_view = dashboard_view
                view = dashboard_view
            elif label == "Cashbook" and enabled:
                cashbook_view = CashbookView()
                self._cashbook_view = cashbook_view
                view = cashbook_view
            elif label == "Cashbook Reports" and enabled:
                cashbook_report_view = CashbookReportView()
                self._cashbook_report_view = cashbook_report_view
                view = cashbook_report_view
            elif label == "Full Accounting" and enabled:
                door_view = FullAccountingDoorView()
                door_view.upgraded.connect(self._on_upgraded_to_full)
                self._full_accounting_door = door_view
                view = door_view
            elif label == "Contacts" and enabled:
                view: QWidget = ContactsView()
            elif label == "Items" and enabled:
                view = ItemsView()
            elif label == "Accounts" and enabled:
                view = AccountsView()
            elif label == "Sales" and enabled:
                invoices_view = InvoicesView()
                invoice_detail_view = InvoiceDetailView()
                # Embed list + detail + form in a nested QStackedWidget
                sales_stack = QStackedWidget()
                _inv_list_idx = sales_stack.addWidget(invoices_view)
                _inv_detail_idx = sales_stack.addWidget(invoice_detail_view)

                # Placeholder slot for the form — replaced each time we open it
                _form_placeholder = QWidget()
                _inv_form_idx = sales_stack.addWidget(_form_placeholder)

                def _open_invoice_form(
                    inv_id: str | None,
                    s: QStackedWidget = sales_stack,
                    fi: int = _inv_form_idx,
                    dv: InvoiceDetailView = invoice_detail_view,
                    di: int = _inv_detail_idx,
                    li: int = _inv_list_idx,
                ) -> None:
                    """Replace the form slot with a fresh InvoiceForm and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = InvoiceForm(APIClient(), invoice_id=inv_id)

                    def _on_form_saved(saved_id: str) -> None:
                        dv.load(saved_id)
                        s.setCurrentIndex(di)

                    new_form.invoice_saved.connect(_on_form_saved)
                    new_form.cancelled.connect(
                        lambda: s.setCurrentIndex(di if inv_id else li)
                    )
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                invoices_view.invoice_selected.connect(
                    lambda inv_id, s=sales_stack, dv=invoice_detail_view, di=_inv_detail_idx: (
                        dv.load(inv_id),
                        s.setCurrentIndex(di),
                    )
                )
                invoices_view.new_invoice_requested.connect(
                    lambda: _open_invoice_form(None)
                )
                invoice_detail_view.back_requested.connect(
                    lambda s=sales_stack, li=_inv_list_idx: s.setCurrentIndex(li)
                )
                invoice_detail_view.edit_requested.connect(
                    lambda inv_id: _open_invoice_form(inv_id)
                )
                # Enable the Edit button now that the form is wired
                invoice_detail_view._edit_btn.setEnabled(True)

                # Placeholder slot for the payment form — replaced each time
                _pay_form_placeholder = QWidget()
                _pay_form_idx = sales_stack.addWidget(_pay_form_placeholder)

                def _open_payment_form_for_invoice(
                    inv_id: str,
                    s: QStackedWidget = sales_stack,
                    fi: int = _pay_form_idx,
                    li: int = _inv_list_idx,
                ) -> None:
                    """Replace the payment form slot and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = PaymentForm(
                        APIClient(), direction="in", invoice_id=inv_id
                    )
                    new_form.payment_recorded.connect(lambda _id: s.setCurrentIndex(li))
                    new_form.cancelled.connect(lambda: s.setCurrentIndex(fi - 1))
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                invoice_detail_view.payment_requested.connect(
                    lambda inv_id: _open_payment_form_for_invoice(inv_id)
                )

                self._invoices_view = invoices_view
                self._invoice_detail_view = invoice_detail_view
                self._sales_stack = sales_stack
                self._open_invoice_form = _open_invoice_form
                view = sales_stack
            elif label == "Purchases" and enabled:
                bills_view = BillsView()
                bill_detail_view = BillDetailView()
                purchases_stack = QStackedWidget()
                _bill_list_idx = purchases_stack.addWidget(bills_view)
                _bill_detail_idx = purchases_stack.addWidget(bill_detail_view)

                # Placeholder slot for the bill form — replaced each time
                _bill_form_placeholder = QWidget()
                _bill_form_idx = purchases_stack.addWidget(_bill_form_placeholder)

                def _open_bill_form(
                    bill_id: str | None,
                    s: QStackedWidget = purchases_stack,
                    fi: int = _bill_form_idx,
                    dv: BillDetailView = bill_detail_view,
                    di: int = _bill_detail_idx,
                    li: int = _bill_list_idx,
                ) -> None:
                    """Replace the form slot with a fresh BillForm and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = BillForm(APIClient(), bill_id=bill_id)

                    def _on_form_saved(saved_id: str) -> None:
                        dv.load(saved_id)
                        s.setCurrentIndex(di)

                    new_form.bill_saved.connect(_on_form_saved)
                    new_form.cancelled.connect(
                        lambda: s.setCurrentIndex(di if bill_id else li)
                    )
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                bills_view.bill_selected.connect(
                    lambda bill_id, s=purchases_stack, dv=bill_detail_view, di=_bill_detail_idx: (
                        dv.load(bill_id),
                        s.setCurrentIndex(di),
                    )
                )
                bills_view.new_bill_requested.connect(
                    lambda: _open_bill_form(None)
                )
                bill_detail_view.back_requested.connect(
                    lambda s=purchases_stack, li=_bill_list_idx: s.setCurrentIndex(li)
                )
                bill_detail_view.edit_requested.connect(
                    lambda bill_id: _open_bill_form(bill_id)
                )
                # Enable the Edit button now that the form is wired
                bill_detail_view._edit_btn.setEnabled(True)

                self._bills_view = bills_view
                self._bill_detail_view = bill_detail_view
                self._purchases_stack = purchases_stack
                self._open_bill_form = _open_bill_form
                view = purchases_stack
            elif label == "Expenses" and enabled:
                import os
                import webbrowser

                expenses_view = ExpensesView()
                _web_base = os.environ.get(
                    "SAEBOOKS_WEB_URL", "http://localhost:8043"
                ).rstrip("/")
                # No native detail/form view yet — clicks open the web
                # UI in the user's default browser. Desktop is the
                # read-only list surface for v1; create/edit/post/void
                # live in saebooks-web.
                expenses_view.new_expense_requested.connect(
                    lambda b=_web_base: webbrowser.open(f"{b}/expenses/new")
                )
                expenses_view.expense_selected.connect(
                    lambda eid, b=_web_base: webbrowser.open(f"{b}/expenses/{eid}")
                )
                self._expenses_view = expenses_view
                view = expenses_view
            elif label == "Purchase Orders" and enabled:
                po_list_view = PurchaseOrdersView()
                po_detail_view = PurchaseOrderDetailView()
                po_stack = QStackedWidget()
                _po_list_idx = po_stack.addWidget(po_list_view)
                _po_detail_idx = po_stack.addWidget(po_detail_view)

                po_list_view.po_selected.connect(
                    lambda po_id, s=po_stack, dv=po_detail_view, di=_po_detail_idx: (
                        dv.load(po_id),
                        s.setCurrentIndex(di),
                    )
                )
                po_detail_view.back_requested.connect(
                    lambda s=po_stack, li=_po_list_idx, lv=po_list_view: (
                        lv.reload(),
                        s.setCurrentIndex(li),
                    )
                )

                # When convert-to-bill returns a bill id, jump to Purchases
                # and load that bill in the bill detail view.
                def _on_bill_opened(
                    bill_id: str,
                    win: "MainWindow" = self,
                ) -> None:
                    if win._navigate_to_key("Purchases"):
                        # Show the bill in the purchases stack
                        if hasattr(win, "_bill_detail_view"):
                            win._bill_detail_view.load(bill_id)
                            # Detail is index 1 in the purchases stack
                            win._purchases_stack.setCurrentIndex(1)

                po_detail_view.bill_opened.connect(_on_bill_opened)

                self._po_list_view = po_list_view
                self._po_detail_view = po_detail_view
                self._po_stack = po_stack
                view = po_stack
            elif label == "Journal Entries" and enabled:
                je_list_view = JournalEntriesView()
                je_stack = QStackedWidget()
                _je_list_idx = je_stack.addWidget(je_list_view)

                # Placeholder slot for the form — replaced each time we open it
                _je_form_placeholder = QWidget()
                _je_form_idx = je_stack.addWidget(_je_form_placeholder)

                def _open_je_form(
                    je_id: str | None,
                    s: QStackedWidget = je_stack,
                    fi: int = _je_form_idx,
                    li: int = _je_list_idx,
                ) -> None:
                    """Replace the form slot with a fresh JournalEntryForm and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = JournalEntryForm(APIClient(), je_id=je_id)

                    def _on_je_saved(saved_id: str) -> None:
                        s.setCurrentIndex(li)

                    new_form.journal_saved.connect(_on_je_saved)
                    new_form.cancelled.connect(lambda: s.setCurrentIndex(li))
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                je_list_view.new_journal_requested.connect(
                    lambda: _open_je_form(None)
                )

                self._je_list_view = je_list_view
                self._je_stack = je_stack
                self._open_je_form = _open_je_form
                view = je_stack
            elif label == "Banking" and enabled:
                # Banking is a 3-panel stack: the statement-lines list, the
                # statement importer, and the reconcile screen. The list's
                # "Import Statement" / "Reconcile" buttons drive the stack;
                # each sub-view degrades on its own (per-panel isolation).
                banking_list_view = BankingView()
                import_view = ImportStatementView()
                reconcile_view = ReconciliationView()

                banking_stack = QStackedWidget()
                _bank_list_idx = banking_stack.addWidget(banking_list_view)
                _bank_import_idx = banking_stack.addWidget(import_view)
                _bank_reconcile_idx = banking_stack.addWidget(reconcile_view)

                def _show_bank_list(
                    s: QStackedWidget = banking_stack, i: int = _bank_list_idx,
                    lv: BankingView = banking_list_view,
                ) -> None:
                    lv.reload()
                    s.setCurrentIndex(i)

                def _show_bank_import(
                    s: QStackedWidget = banking_stack, i: int = _bank_import_idx,
                    iv: ImportStatementView = import_view,
                ) -> None:
                    iv.reload()
                    s.setCurrentIndex(i)

                def _show_bank_reconcile(
                    account_id: str = "",
                    s: QStackedWidget = banking_stack, i: int = _bank_reconcile_idx,
                    rv: ReconciliationView = reconcile_view,
                ) -> None:
                    rv.load_account(account_id)
                    s.setCurrentIndex(i)

                banking_list_view.import_requested.connect(_show_bank_import)
                banking_list_view.reconcile_requested.connect(_show_bank_reconcile)
                import_view.import_done.connect(_show_bank_list)
                import_view.cancelled.connect(_show_bank_list)
                reconcile_view.back_requested.connect(_show_bank_list)

                self._banking_list_view = banking_list_view
                self._banking_import_view = import_view
                self._banking_reconcile_view = reconcile_view
                self._banking_stack = banking_stack
                view = banking_stack
            elif label == "Payments" and enabled:
                payments_list_view = PaymentsView()
                payments_stack = QStackedWidget()
                _pmt_list_idx = payments_stack.addWidget(payments_list_view)

                # Placeholder slot for the payment form
                _pmt_form_placeholder = QWidget()
                _pmt_form_idx = payments_stack.addWidget(_pmt_form_placeholder)

                def _open_standalone_payment_form(
                    s: QStackedWidget = payments_stack,
                    fi: int = _pmt_form_idx,
                    li: int = _pmt_list_idx,
                ) -> None:
                    """Replace the payment form slot and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = PaymentForm(APIClient(), direction="in")
                    new_form.payment_recorded.connect(
                        lambda _id: (payments_list_view.reload(), s.setCurrentIndex(li))
                    )
                    new_form.cancelled.connect(lambda: s.setCurrentIndex(li))
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                payments_list_view.new_payment_requested.connect(
                    _open_standalone_payment_form
                )

                self._payments_list_view = payments_list_view
                self._payments_stack = payments_stack
                self._open_standalone_payment_form = _open_standalone_payment_form
                view = payments_stack
            elif label == "Fixed Assets" and enabled:
                fa_list_view = FixedAssetsView()
                fa_detail_view = FixedAssetDetail()
                fa_stack = QStackedWidget()
                _fa_list_idx = fa_stack.addWidget(fa_list_view)
                _fa_detail_idx = fa_stack.addWidget(fa_detail_view)

                fa_list_view.asset_selected.connect(
                    lambda asset_id, s=fa_stack, dv=fa_detail_view, di=_fa_detail_idx: (
                        dv.load(asset_id),
                        s.setCurrentIndex(di),
                    )
                )
                fa_detail_view.back_requested.connect(
                    lambda s=fa_stack, li=_fa_list_idx: s.setCurrentIndex(li)
                )
                # Depreciate and dispose actions reload the detail view
                fa_detail_view.depreciate_requested.connect(
                    lambda asset_id, dv=fa_detail_view: dv.load(asset_id)
                )
                fa_detail_view.dispose_requested.connect(
                    lambda asset_id, dv=fa_detail_view: dv.load(asset_id)
                )

                self._fa_list_view = fa_list_view
                self._fa_detail_view = fa_detail_view
                self._fa_stack = fa_stack
                view = fa_stack
            elif label == "Credit Notes" and enabled:
                cn_list_view = CreditNotesView()
                cn_stack = QStackedWidget()
                _cn_list_idx = cn_stack.addWidget(cn_list_view)

                # Placeholder slot for the form — replaced each time we open it
                _cn_form_placeholder = QWidget()
                _cn_form_idx = cn_stack.addWidget(_cn_form_placeholder)

                def _open_credit_note_form(
                    cn_id: str | None,
                    s: QStackedWidget = cn_stack,
                    fi: int = _cn_form_idx,
                    li: int = _cn_list_idx,
                    lv: CreditNotesView = cn_list_view,
                ) -> None:
                    """Replace the form slot with a fresh CreditNoteForm and show it."""
                    from saebooks_desktop.services.api_client import APIClient

                    new_form = CreditNoteForm(APIClient(), credit_note_id=cn_id)

                    def _on_cn_saved(saved_id: str) -> None:
                        lv.reload()
                        s.setCurrentIndex(li)

                    new_form.credit_note_saved.connect(_on_cn_saved)
                    new_form.cancelled.connect(lambda: s.setCurrentIndex(li))
                    old = s.widget(fi)
                    s.insertWidget(fi, new_form)
                    s.setCurrentIndex(fi)
                    if old is not None:
                        old.setParent(None)

                cn_list_view.new_credit_note_requested.connect(
                    lambda: _open_credit_note_form(None)
                )
                cn_list_view.credit_note_selected.connect(
                    lambda cn_id: _open_credit_note_form(cn_id)
                )

                self._cn_list_view = cn_list_view
                self._cn_stack = cn_stack
                self._open_credit_note_form = _open_credit_note_form
                view = cn_stack
            elif label == "Budgets" and enabled:
                view = BudgetsView()
            elif label == "Projects" and enabled:
                view = ProjectsView()
            elif label == "Recurring Invoices" and enabled:
                view = RecurringInvoicesView()
            elif label == "Reports" and enabled:
                view = ReportsView()
            elif label == "Account Ranges" and enabled:
                view = AccountRangesView()
            elif label == "Bank Rules" and enabled:
                view = BankRulesView()
            elif label == "Journal Templates" and enabled:
                view = JournalTemplatesView()
            elif label == "Tax Codes" and enabled:
                view = TaxCodesView()
            elif label == "Search" and enabled:
                search_view = SearchView()
                search_view.result_selected.connect(self._on_search_result_selected)
                self._search_view = search_view
                view = search_view
            elif label == "Settings" and enabled:
                settings_view = SettingsView()
                settings_view.reconnect_requested.connect(self._on_reconnect_requested)
                settings_view.bookkeeping_mode_changed.connect(
                    self._on_bookkeeping_mode_changed
                )
                self._settings_view = settings_view
                view = settings_view
            else:
                view = _PlaceholderView(label)

            self._stack_index_by_key[label] = self._stack.addWidget(view)

        self._nav.currentRowChanged.connect(self._on_nav_changed)
        root_layout.addWidget(self._nav)
        root_layout.addWidget(self._stack, 1)

        # Menu bar — Edit menu
        edit_menu = self.menuBar().addMenu("&Edit")
        prefs_action = edit_menu.addAction("&Preferences\u2026")
        prefs_action.triggered.connect(self._on_preferences)

        # Menu bar \u2014 Tools menu
        tools_menu = self.menuBar().addMenu("&Tools")
        prorate_action = tools_menu.addAction("&Prorate Calculator\u2026")
        prorate_action.triggered.connect(self._on_prorate_calculator)

        # Search shortcut — Ctrl+F navigates to the Search nav item
        from PySide6.QtGui import QKeySequence, QShortcut

        search_shortcut = QShortcut(QKeySequence("Ctrl+F"), self)
        search_shortcut.activated.connect(self._on_search_shortcut)

        # Status bar
        tier = self._licence.tier.capitalize()
        self._conn_label = QLabel("Connecting…")
        self._transport_label = QLabel("REST")
        self._tier_label = QLabel(f"Licence: {tier}")
        self.statusBar().addWidget(self._conn_label, 1)
        self.statusBar().addPermanentWidget(self._transport_label)
        # Community is the product, not a tier to advertise: the licence
        # badge only appears when a real (verified, non-community) licence
        # is loaded. Community builds show no licence chrome at all.
        if self._licence.stub or self._licence.tier == "community":
            self._tier_label.hide()
        else:
            self.statusBar().addPermanentWidget(self._tier_label)

        # Populate the sidebar for the resolved mode and select the first
        # item (Dashboard in full mode, Cashbook in cashbook mode — loads
        # on first show, not here).
        self._apply_nav()

        self._update_connection_status()

        # SyncEngine is created here but NOT started — call start_sync() after
        # show() to avoid background threads in test scenarios where the window
        # is instantiated but never displayed.
        from saebooks_desktop.services.api_client import APIClient

        self._sync_engine = SyncEngine(APIClient())
        self._sync_engine.sync_completed.connect(self._on_sync_completed)
        self._sync_engine.offline_detected.connect(self._on_offline_detected)
        self._sync_engine.online_detected.connect(self._on_online_detected)
        self._sync_engine.conflict_detected.connect(self._on_conflict_detected)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _on_nav_changed(self, row: int) -> None:
        if row < 0:
            return
        stack_index = self._view_indices.get(row)
        if stack_index is not None:
            self._stack.setCurrentIndex(stack_index)

    def _nav_model(self) -> list[tuple[str, str]]:
        """Return the (display label, canonical key) nav model for the mode."""
        if self._bookkeeping_mode == "cashbook":
            return _CASHBOOK_MODE_NAV
        return _FULL_MODE_NAV

    def _apply_nav(self) -> None:
        """(Re)populate the sidebar from the current bookkeeping mode.

        Every view stays in the stack; only the sidebar entries and the
        nav_row → stack_index routing change. Selects the first item.
        """
        model = self._nav_model()

        self._nav.blockSignals(True)
        self._nav.clear()
        self._view_indices = {}
        self._nav_row_by_key = {}
        for nav_row, (display, key) in enumerate(model):
            self._nav.addItem(QListWidgetItem(tr(display)))
            self._view_indices[nav_row] = self._stack_index_by_key[key]
            self._nav_row_by_key[key] = nav_row
        self._nav.blockSignals(False)

        self._nav.setCurrentRow(0)
        self._stack.setCurrentIndex(self._view_indices[0])

    def _navigate_to_key(self, key: str) -> bool:
        """Select the nav row for *key* if it exists in the current mode."""
        nav_row = self._nav_row_by_key.get(key)
        if nav_row is None:
            return False
        self._nav.setCurrentRow(nav_row)
        self._stack.setCurrentIndex(self._view_indices[nav_row])
        return True

    # ------------------------------------------------------------------
    # Bookkeeping mode (mode-driven navigation)
    # ------------------------------------------------------------------

    def apply_bookkeeping_mode(self, mode: str) -> None:
        """Re-render the navigation for *mode* ("cashbook" or "full")."""
        if mode not in ("cashbook", "full"):
            return
        self._bookkeeping_mode = mode
        self._apply_nav()

    def refresh_company_context(self) -> None:
        """Re-resolve the company's bookkeeping mode and re-render the nav.

        Call after a company switch — navigation branches on the newly
        selected company's ``bookkeeping_mode``.
        """
        from saebooks_desktop.services.api_client import APIClient

        self.apply_bookkeeping_mode(resolve_bookkeeping_mode(APIClient()))

    @Slot()
    def _on_upgraded_to_full(self) -> None:
        """Cashbook company upgraded via the Full accounting doorway."""
        if hasattr(self, "_settings_view"):
            self._settings_view._general_tab.set_mode("full")
        self.apply_bookkeeping_mode("full")

    @Slot(str)
    def _on_bookkeeping_mode_changed(self, mode: str) -> None:
        """SettingsView flipped the mode (full → cashbook downgrade)."""
        self.apply_bookkeeping_mode(mode)

    def start_sync(self) -> None:
        """Start the background sync engine.  Call this after ``show()``."""
        if not self._sync_engine.isRunning():
            self._sync_engine.start()

    def _update_connection_status(self) -> None:
        """Quick non-blocking connectivity probe — updates status bar labels."""
        from saebooks_desktop.services.api_client import APIClient

        client = APIClient()
        transport = client.resolve_transport()
        transport_name = client.active_transport_name
        self._transport_label.setText(transport_name)

        reachable = transport.is_reachable() if hasattr(transport, "is_reachable") else False
        if reachable:
            self._conn_label.setText("Connected")
            self._conn_label.setStyleSheet("color: green;")
        else:
            self._conn_label.setText("Server offline")
            self._conn_label.setStyleSheet("color: #cc4400;")

    @Slot(int)
    def _on_sync_completed(self, changes: int) -> None:
        self._conn_label.setText("Synced just now")
        self._conn_label.setStyleSheet("color: green;")

    @Slot()
    def _on_offline_detected(self) -> None:
        self._conn_label.setText("Offline — showing cached data")
        self._conn_label.setStyleSheet("color: #cc4400;")

    @Slot()
    def _on_online_detected(self) -> None:
        self._conn_label.setText("Back online — syncing\u2026")
        self._conn_label.setStyleSheet("color: #0066cc;")

    @Slot(str, str)
    def _on_conflict_detected(self, entity: str, entity_id: str) -> None:
        """Show the conflict dialog (non-blocking — queued via signal)."""
        from saebooks_desktop.views.conflict_dialog import ConflictDialog

        # We don't have the payloads in the signal — fetch from conflicts table.
        # For now show a minimal placeholder with the entity info we do have.
        dlg = ConflictDialog(
            entity=entity,
            entity_id=entity_id,
            server_data={"note": "server data not available in signal"},
            local_data={"note": "local data not available in signal"},
            parent=self,
        )
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        dlg.show()

    @Slot()
    def _on_preferences(self) -> None:
        """Open the Preferences dialog as a modal."""
        from saebooks_desktop.views.preferences_dialog import PreferencesDialog

        dlg = PreferencesDialog(parent=self)
        dlg.exec()

    @Slot()
    def _on_prorate_calculator(self) -> None:
        """Open the Prorate Calculator dialog (non-modal)."""
        from saebooks_desktop.views.proration_dialog import ProrationDialog

        dlg = ProrationDialog(parent=self)
        dlg.show()

    @Slot()
    def _on_reconnect_requested(self) -> None:
        """Handle disconnect from SettingsView — re-show the first-run wizard."""
        from saebooks_desktop.wizard.first_run import FirstRunWizard

        wizard = FirstRunWizard(parent=None)
        wizard.show()
        self.close()

    @Slot()
    def _on_search_shortcut(self) -> None:
        """Navigate to the Search view and focus the search field.

        No-op in cashbook mode — Search is not part of that nav model.
        """
        if self._navigate_to_key("Search") and hasattr(self, "_search_view"):
            self._search_view.focus_search()

    @Slot(str, str)
    def _on_search_result_selected(self, result_type: str, result_id: str) -> None:
        """Navigate to the appropriate section when a search result is double-clicked."""
        _type_to_nav: dict[str, str] = {
            "invoice": "Sales",
            "bill": "Purchases",
            "purchase_order": "Purchase Orders",
            "contact": "Contacts",
            "account": "Accounts",
            "item": "Items",
            "journal_entry": "Journal Entries",
            "payment": "Payments",
        }
        nav_label = _type_to_nav.get(result_type.lower())
        if nav_label is None:
            return
        self._navigate_to_key(nav_label)

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        """Stop the sync engine cleanly before closing."""
        if hasattr(self, "_sync_engine") and self._sync_engine.isRunning():
            self._sync_engine.requestInterruption()
            self._sync_engine.wait(3000)  # 3s timeout
        super().closeEvent(event)  # type: ignore[misc]
