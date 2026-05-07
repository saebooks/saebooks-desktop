"""First-run setup wizard.

Shown once — before the main window — when ``services.settings.is_first_run()``
returns True.  If the user cancels, the caller should exit the application.

Pages (in order):
  1. WelcomePage
  2. ServerConnectPage
  3. SignInPage
  4. CompanySelectPage
  5. DonePage
"""
from __future__ import annotations

from PySide6.QtWidgets import QWizard

from saebooks_desktop.wizard.pages.company_select import CompanySelectPage
from saebooks_desktop.wizard.pages.done import DonePage
from saebooks_desktop.wizard.pages.server_connect import ServerConnectPage
from saebooks_desktop.wizard.pages.sign_in import SignInPage
from saebooks_desktop.wizard.pages.welcome import WelcomePage


class FirstRunWizard(QWizard):
    """First-run configuration wizard."""

    def __init__(self, parent: object = None) -> None:
        super().__init__(parent)  # type: ignore[arg-type]
        self.setWindowTitle("SAE Books — Setup")
        self.setMinimumSize(520, 380)
        self.setWizardStyle(QWizard.WizardStyle.ModernStyle)

        self.addPage(WelcomePage())
        self.addPage(ServerConnectPage())
        self.addPage(SignInPage())
        self.addPage(CompanySelectPage())
        self.addPage(DonePage())

        # Hide the Help button — no help system yet.
        self.setOption(QWizard.WizardOption.HaveHelpButton, False)
