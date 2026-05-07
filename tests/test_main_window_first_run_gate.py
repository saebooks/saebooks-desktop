"""Tests for the first-run wizard gate in main.py.

Tests that:
  - The wizard is shown when is_first_run() returns True.
  - Cancelling the wizard returns 0 without showing the main window.
  - Accepting the wizard proceeds to show the main window.

main() calls app.exec() which would block, so the entire Qt app layer is
mocked.  We verify the control flow by checking which constructors were called.
"""
from __future__ import annotations

import importlib
import os
from unittest.mock import MagicMock, patch

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _run_main_patched(is_first_run_val: bool, wizard_result: int = 1):
    """Run main() with Qt + MainWindow + FirstRunWizard all mocked.

    Returns (return_code, mock_mw_cls, mock_wiz_cls, mock_wiz_inst).
    """
    mock_wiz_inst = MagicMock()
    mock_wiz_inst.exec.return_value = wizard_result
    mock_wiz_inst.DialogCode = MagicMock()
    mock_wiz_inst.DialogCode.Accepted = 1

    mock_win_inst = MagicMock()
    mock_app_inst = MagicMock()
    mock_app_inst.exec.return_value = 0

    with (
        patch("saebooks_desktop.services.settings.is_first_run", return_value=is_first_run_val),
        patch("saebooks_desktop.wizard.first_run.FirstRunWizard", return_value=mock_wiz_inst) as mock_wiz_cls,
        patch("saebooks_desktop.main_window.MainWindow", return_value=mock_win_inst) as mock_mw_cls,
        # Patch QApplication to avoid real event loop
        patch("PySide6.QtWidgets.QApplication") as mock_qa,
    ):
        mock_qa.instance.return_value = mock_app_inst
        mock_qa.return_value = mock_app_inst
        mock_app_inst.exec.return_value = 0

        import saebooks_desktop.main as m
        importlib.reload(m)
        rc = m.main(["--offscreen"])

    return rc, mock_mw_cls, mock_wiz_cls, mock_wiz_inst


class TestFirstRunGate:
    def test_is_first_run_false_when_url_set(self, qapp) -> None:
        """Verify is_first_run returns False after a URL is stored."""
        with patch("saebooks_desktop.services.settings.get_server_url", return_value="http://srv:8042"):
            with patch.dict(os.environ, {}, clear=False):
                # Ensure env var doesn't interfere
                env_backup = os.environ.pop("SAEBOOKS_API_URL", None)
                try:
                    import saebooks_desktop.services.settings as sm
                    result = sm.is_first_run()
                    assert result is False
                finally:
                    if env_backup is not None:
                        os.environ["SAEBOOKS_API_URL"] = env_backup

    def test_wizard_shown_when_first_run_and_accepted(self, qapp) -> None:
        """Wizard is exec'd when is_first_run is True and user accepts."""
        rc, mock_mw_cls, mock_wiz_cls, mock_wiz_inst = _run_main_patched(
            is_first_run_val=True, wizard_result=1
        )
        mock_wiz_cls.assert_called_once()
        mock_wiz_inst.exec.assert_called_once()
        mock_mw_cls.assert_called_once()

    def test_cancel_wizard_returns_zero_without_main_window(self, qapp) -> None:
        """Cancelling (result 0 != Accepted 1) must not open MainWindow."""
        rc, mock_mw_cls, mock_wiz_cls, mock_wiz_inst = _run_main_patched(
            is_first_run_val=True, wizard_result=0
        )
        assert rc == 0
        mock_mw_cls.assert_not_called()

    def test_wizard_skipped_when_not_first_run(self, qapp) -> None:
        """When is_first_run is False the wizard is never constructed."""
        rc, mock_mw_cls, mock_wiz_cls, mock_wiz_inst = _run_main_patched(
            is_first_run_val=False
        )
        mock_wiz_cls.assert_not_called()
        mock_mw_cls.assert_called_once()
