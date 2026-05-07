"""SAE Books main window — Command Centre-style sidebar navigation."""
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

from saebooks_desktop.cache.sync import SyncEngine
from saebooks_desktop.licence import load_licence
from saebooks_desktop.views.accounts import AccountsView
from saebooks_desktop.views.banking import BankingView
from saebooks_desktop.views.bill_detail import BillDetailView
from saebooks_desktop.views.bills import BillsView
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

# Nav items: (label, enabled, view_factory_or_None)
# Disabled entries show greyed out; factories are callables that create a
# QWidget on first selection (lazy init to avoid constructing views that
# need the API before the window is visible).
_NAV_ITEMS: list[tuple[str, bool]] = [
    ("Dashboard", False),
    ("Contacts", True),
    ("Items", True),
    ("Accounts", True),
    ("Sales", True),
    ("Purchases", True),
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
        self.setWindowTitle("SAE Books")
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

        # Build nav + stack in sync
        self._view_indices: dict[int, int] = {}  # nav_row -> stack_index
        contacts_row: int | None = None

        for nav_row, (label, enabled) in enumerate(_NAV_ITEMS):
            item = QListWidgetItem(label)
            if not enabled:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            self._nav.addItem(item)

            if label == "Contacts" and enabled:
                view: QWidget = ContactsView()
                contacts_row = nav_row
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
                view = BankingView()
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
                view = settings_view
            else:
                view = _PlaceholderView(label)

            stack_index = self._stack.addWidget(view)
            self._view_indices[nav_row] = stack_index

        self._nav.currentRowChanged.connect(self._on_nav_changed)
        root_layout.addWidget(self._nav)
        root_layout.addWidget(self._stack, 1)

        # Menu bar — Edit menu
        edit_menu = self.menuBar().addMenu("&Edit")
        prefs_action = edit_menu.addAction("&Preferences\u2026")
        prefs_action.triggered.connect(self._on_preferences)

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
        self.statusBar().addPermanentWidget(self._tier_label)

        # Select Contacts by default (it's enabled)
        if contacts_row is not None:
            self._nav.setCurrentRow(contacts_row)
            self._stack.setCurrentIndex(self._view_indices[contacts_row])

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
    def _on_reconnect_requested(self) -> None:
        """Handle disconnect from SettingsView — re-show the first-run wizard."""
        from saebooks_desktop.wizard.first_run import FirstRunWizard

        wizard = FirstRunWizard(parent=None)
        wizard.show()
        self.close()

    @Slot()
    def _on_search_shortcut(self) -> None:
        """Navigate to the Search view and focus the search field."""
        for nav_row, (label, _enabled) in enumerate(_NAV_ITEMS):
            if label == "Search":
                self._nav.setCurrentRow(nav_row)
                self._stack.setCurrentIndex(self._view_indices[nav_row])
                if hasattr(self, "_search_view"):
                    self._search_view.focus_search()
                break

    @Slot(str, str)
    def _on_search_result_selected(self, result_type: str, result_id: str) -> None:
        """Navigate to the appropriate section when a search result is double-clicked."""
        _type_to_nav: dict[str, str] = {
            "invoice": "Sales",
            "bill": "Purchases",
            "contact": "Contacts",
            "account": "Accounts",
            "item": "Items",
            "journal_entry": "Journal Entries",
            "payment": "Payments",
        }
        nav_label = _type_to_nav.get(result_type.lower())
        if nav_label is None:
            return
        for nav_row, (label, _enabled) in enumerate(_NAV_ITEMS):
            if label == nav_label:
                self._nav.setCurrentRow(nav_row)
                self._stack.setCurrentIndex(self._view_indices[nav_row])
                break

    def closeEvent(self, event: object) -> None:  # type: ignore[override]
        """Stop the sync engine cleanly before closing."""
        if hasattr(self, "_sync_engine") and self._sync_engine.isRunning():
            self._sync_engine.requestInterruption()
            self._sync_engine.wait(3000)  # 3s timeout
        super().closeEvent(event)  # type: ignore[misc]
