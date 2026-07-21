"""Briefcase entry shim — tasur (Estonia) brand. See desktop/__main__.py."""
import os
import sys

os.environ.setdefault("SAEBOOKS_BRAND", "tasur")

from saebooks_desktop.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
