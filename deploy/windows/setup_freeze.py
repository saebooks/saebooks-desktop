"""cx_Freeze configuration for SAE Books desktop MSI.

Run on Windows:
    python deploy/windows/setup_freeze.py bdist_msi

Produces:
    dist/SAEBooks-<version>-x64.msi

Requirements:
    pip install "cx_Freeze>=7.2"

cx_Freeze bdist_msi only runs on Windows; it cannot cross-compile.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys

# ---------------------------------------------------------------------------
# Resolve version from package source (no import of the full package needed).
# ---------------------------------------------------------------------------
_here = pathlib.Path(__file__).parent.parent.parent
_init = _here / "saebooks_desktop" / "__init__.py"
spec = importlib.util.spec_from_file_location("_pkg_init", _init)
_mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(_mod)
VERSION: str = _mod.__version__

# ---------------------------------------------------------------------------
# cx_Freeze imports — only available after pip install cx_Freeze
# ---------------------------------------------------------------------------
from cx_Freeze import setup, Executable  # noqa: E402

# ---------------------------------------------------------------------------
# Runtime dependencies to include explicitly.
# cx_Freeze auto-discovers most, but Qt/PySide6 plugins need help.
# ---------------------------------------------------------------------------
build_exe_options: dict = {
    "packages": [
        "saebooks_desktop",
        "PySide6",
        "httpx",
        "platformdirs",
        "grpc",
        "google.protobuf",
    ],
    "excludes": [
        # Test tooling — not needed at runtime.
        "pytest",
        "pytest_qt",
        "unittest",
        "_pytest",
    ],
    "include_files": [],
    "zip_include_packages": ["*"],
    "zip_exclude_packages": [
        # These must stay as real files for Qt to load plugins correctly.
        "PySide6",
        "shiboken6",
    ],
    # Silence noisy DLL copy warnings from cx_Freeze.
    "silent": True,
}

# ---------------------------------------------------------------------------
# MSI-specific options.
# upgrade_code must be stable across versions (never change it).
# ---------------------------------------------------------------------------
bdist_msi_options: dict = {
    "upgrade_code": "{3D7EB37A-F33F-4484-8BDB-49B89A59DC40}",
    "add_to_path": True,
    "initial_target_dir": r"[ProgramFilesFolder]\SAEBooks",
    "summary_data": {
        "author": "SAE Engineering",
        "comments": "SAE Books — self-hosted accounting desktop client",
    },
    # Install for all users (requires elevation).
    "all_users": True,
    # Product name shown in Add/Remove Programs.
    "product_name": "SAE Books",
}

# ---------------------------------------------------------------------------
# Executable definition.
# base="Win32GUI" suppresses the console window for a GUI app.
# ---------------------------------------------------------------------------
executables = [
    Executable(
        script=str(_here / "saebooks_desktop" / "__main__.py"),
        base="Win32GUI",
        target_name="saebooks-desktop.exe",
        shortcut_name="SAE Books",
        shortcut_dir="DesktopFolder",
        # icon="deploy/windows/saebooks.ico",  # Uncomment when icon is added.
    ),
]

setup(
    name="SAEBooks",
    version=VERSION,
    description="SAE Books — self-hosted accounting desktop client",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
