"""Briefcase entry shim — SAE Books (default) brand.

Bakes the brand as a process-env default so a terminal launch of the
bundled binary reflects the right product, then re-execs the real app.
Env precedence is preserved: an explicit SAEBOOKS_BRAND (or the
Info.plist LSEnvironment value) still wins via setdefault.
"""
import os
import sys

os.environ.setdefault("SAEBOOKS_BRAND", "saebooks")

from saebooks_desktop.main import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main())
