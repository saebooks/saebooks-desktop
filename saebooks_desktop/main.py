"""Entry point — parse args, create QApplication, show MainWindow."""
from __future__ import annotations

import argparse
import os
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="saebooks-desktop",
        description="SAE Books — self-hosted accounting desktop client",
    )
    parser.add_argument(
        "--api-url",
        metavar="URL",
        help="Override the saebooks-api base URL (default: http://localhost:8042)",
    )
    parser.add_argument(
        "--offscreen",
        action="store_true",
        help="Force offscreen Qt platform (useful for CI/testing)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    if args.offscreen:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    if args.api_url:
        os.environ["SAEBOOKS_API_URL"] = args.api_url

    # Import Qt only after platform env var is set so offscreen mode works.
    from PySide6.QtWidgets import QApplication

    from saebooks_desktop.main_window import MainWindow

    app = QApplication.instance() or QApplication(sys.argv)

    # Apply the stored theme preference before showing any window.
    from saebooks_desktop.services.theme import apply_theme_from_settings
    apply_theme_from_settings()

    # Show the first-run wizard when no server URL has been configured yet.
    from saebooks_desktop.services.settings import is_first_run
    if is_first_run():
        from saebooks_desktop.wizard.first_run import FirstRunWizard
        wizard = FirstRunWizard()
        result = wizard.exec()
        if result != wizard.DialogCode.Accepted:
            # User cancelled — exit cleanly without showing the main window.
            return 0

    window = MainWindow()
    window.show()
    window.start_sync()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
