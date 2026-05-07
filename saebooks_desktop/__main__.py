"""Allow ``python -m saebooks_desktop`` invocation."""
import sys

from saebooks_desktop.main import main

if __name__ == "__main__":
    sys.exit(main())
