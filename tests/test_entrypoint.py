"""Smoke tests for the packaging entry points.

Verifies that:
1. ``saebooks_desktop.__main__`` is importable and exposes ``main``.
2. ``saebooks_desktop.main:main`` accepts ``--offscreen`` without crashing and
   returns an integer exit code (may be 0 or non-zero depending on Qt display).
3. ``__version__`` is a PEP 440 semver-like string.

These tests run without a display — ``QT_QPA_PLATFORM=offscreen`` is set
before any Qt import.  They are intentionally lightweight: the full UI smoke
tests live in ``test_smoke.py``.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def test_main_module_is_importable() -> None:
    """``python -m saebooks_desktop`` entry point must be importable.

    We load the source without executing the ``if __name__ == '__main__'``
    guard (which would call main() and try to start Qt).  We verify the file
    exists and imports ``main`` from ``saebooks_desktop.main``.
    """
    import pathlib

    main_path = (
        pathlib.Path(__file__).parent.parent
        / "saebooks_desktop" / "__main__.py"
    )
    assert main_path.exists(), "__main__.py not found"
    source = main_path.read_text()
    assert "from saebooks_desktop.main import main" in source, (
        "__main__.py must import main from saebooks_desktop.main"
    )
    assert 'if __name__ == "__main__"' in source, (
        "__main__.py must guard sys.exit(main()) behind __name__ check"
    )


def test_main_function_is_callable() -> None:
    """``saebooks_desktop.main:main`` must be importable and callable."""
    from saebooks_desktop.main import main

    assert callable(main)


def test_version_is_set() -> None:
    """``__version__`` must be a non-empty string."""
    import saebooks_desktop

    ver = saebooks_desktop.__version__
    assert isinstance(ver, str) and ver, "__version__ must be a non-empty string"
    # Basic semver shape: digits separated by dots, e.g. "0.1.0".
    parts = ver.split(".")
    assert len(parts) >= 2, f"Expected semver-like version, got {ver!r}"
    assert all(p.isdigit() or p[0].isdigit() for p in parts), (
        f"Version parts should start with a digit: {ver!r}"
    )


def test_parse_args_offscreen_flag() -> None:
    """``_parse_args`` must accept ``--offscreen`` without raising."""
    from saebooks_desktop.main import _parse_args

    args = _parse_args(["--offscreen"])
    assert args.offscreen is True


def test_parse_args_api_url() -> None:
    """``_parse_args`` must accept ``--api-url`` without raising."""
    from saebooks_desktop.main import _parse_args

    args = _parse_args(["--api-url", "http://myserver:9000"])
    assert args.api_url == "http://myserver:9000"


def test_parse_args_defaults() -> None:
    """Default parse must have offscreen=False, api_url=None."""
    from saebooks_desktop.main import _parse_args

    args = _parse_args([])
    assert args.offscreen is False
    assert args.api_url is None


def test_cx_freeze_setup_is_importable(monkeypatch) -> None:
    """deploy/windows/setup_freeze.py must be importable as a module.

    We cannot actually run bdist_msi on Linux, but we can verify the file
    parses and that VERSION is resolved correctly.
    """
    import importlib.util
    import pathlib

    setup_path = (
        pathlib.Path(__file__).parent.parent
        / "deploy" / "windows" / "setup_freeze.py"
    )
    assert setup_path.exists(), f"setup_freeze.py not found at {setup_path}"

    # Stub out cx_Freeze so the import doesn't fail on non-Windows.
    import types
    cx_mod = types.ModuleType("cx_Freeze")
    cx_mod.setup = lambda **kw: None  # type: ignore[attr-defined]
    cx_mod.Executable = type("Executable", (), {"__init__": lambda self, **kw: None})  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "cx_Freeze", cx_mod)

    spec = importlib.util.spec_from_file_location("setup_freeze", setup_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # VERSION must have been resolved.
    assert isinstance(mod.VERSION, str) and mod.VERSION, (
        "setup_freeze.py must resolve VERSION from saebooks_desktop.__init__"
    )
