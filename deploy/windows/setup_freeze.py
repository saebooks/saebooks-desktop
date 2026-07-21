"""cx_Freeze configuration for the SAE Books / tasur desktop MSI.

Run on Windows (bdist_msi is Windows-only; it cannot cross-compile):
    python deploy/windows/setup_freeze.py bdist_msi                 # SAE Books
    set SAEBOOKS_BRAND=tasur && python deploy/windows/setup_freeze.py bdist_msi

Produces:
    dist/SAEBooks-<version>-win64.msi   (default brand)
    dist/tasur-<version>-win64.msi      (SAEBOOKS_BRAND=tasur)
(before scripts/build_msi.bat renames to the canonical <Brand>-<version>-x64.msi)

Requirements:
    Windows 10/11 x64, Python 3.12 (64-bit), pip install "cx_Freeze>=7.2"

Brand handling: the build brand is chosen by the SAEBOOKS_BRAND env var at
BUILD time and baked into the artifact as a one-line ``brand.cfg`` beside the
frozen executable — ``saebooks_desktop.branding`` reads it at runtime, so a
tasur MSI stays tasur no matter what QSettings on the target machine say.
Each brand has its OWN MSI upgrade_code so the two products install/upgrade
independently and never replace each other.
"""
from __future__ import annotations

import importlib.util
import os
import pathlib
import sys
import tempfile

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
# Resolve the build brand (SAEBOOKS_BRAND env var; default saebooks).
# The registry is loaded straight from source — no Qt import happens because
# the env var short-circuits the QSettings fallback path.
# ---------------------------------------------------------------------------
_branding_path = _here / "saebooks_desktop" / "branding.py"
_bspec = importlib.util.spec_from_file_location("_branding", _branding_path)
_branding = importlib.util.module_from_spec(_bspec)
# Register before exec: @dataclass resolves cls.__module__ via sys.modules.
sys.modules["_branding"] = _branding
_bspec.loader.exec_module(_branding)

BRAND_ID: str = os.environ.get("SAEBOOKS_BRAND", "").strip().lower() or "saebooks"
if BRAND_ID not in _branding.BRANDS:
    raise SystemExit(f"Unknown SAEBOOKS_BRAND: {BRAND_ID!r} (saebooks|tasur)")
BRAND = _branding.BRANDS[BRAND_ID]

# Per-brand MSI facts. upgrade_code must be stable across versions of ONE
# brand (never change it) and MUST differ between brands so the two products
# never upgrade/replace each other.
_MSI_FACTS = {
    "saebooks": {
        "setup_name": "SAEBooks",
        "upgrade_code": "{3D7EB37A-F33F-4484-8BDB-49B89A59DC40}",
        "target_dir": r"[ProgramFilesFolder]\SAEBooks",
    },
    "tasur": {
        "setup_name": "tasur",
        "upgrade_code": "{108EDDEE-9FF7-4AD0-AE67-2675D2060C6E}",
        "target_dir": r"[ProgramFilesFolder]\tasur",
    },
}[BRAND_ID]

# Bake the brand into the artifact: a one-line brand.cfg installed beside
# the frozen executable (read by saebooks_desktop.branding at runtime).
_brand_cfg = pathlib.Path(tempfile.mkdtemp(prefix="saebooks-msi-")) / "brand.cfg"
_brand_cfg.write_text(BRAND_ID + "\n", encoding="utf-8")

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
    "include_files": [
        # Baked brand marker, installed beside the executable.
        (str(_brand_cfg), "brand.cfg"),
        # Runtime window/taskbar icons — the package lives inside the
        # library zip, so saebooks_desktop.app_icon looks for these beside
        # the executable in frozen builds.
        (
            str(_here / "saebooks_desktop" / "assets" / "icons"),
            os.path.join("assets", "icons"),
        ),
    ],
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
# Per-brand installer icon (.ico with 16–256 px, generated from the brand
# SVG — see saebooks_desktop/assets/). Used for the .exe resource, the
# installer dialog, and the Add/Remove Programs entry.
# ---------------------------------------------------------------------------
ICON_PATH = str(_here / "deploy" / "windows" / f"{BRAND_ID}.ico")
if not pathlib.Path(ICON_PATH).is_file():
    raise SystemExit(f"Missing installer icon: {ICON_PATH}")

# ---------------------------------------------------------------------------
# Shortcuts — Start menu + desktop, both pointing at the frozen exe (which
# carries the brand icon as its resource, so both shortcuts show it).
# MSI Shortcut table: (Shortcut, Directory_, Name, Component_, Target,
# Arguments, Description, Hotkey, Icon, IconIndex, ShowCmd, WkDir).
# ---------------------------------------------------------------------------
_shortcut_table = [
    (
        "DesktopShortcut",
        "DesktopFolder",
        BRAND.product_name,
        "TARGETDIR",
        "[TARGETDIR]saebooks-desktop.exe",
        None,
        f"{BRAND.product_name} — {BRAND.tagline}",
        None,
        None,
        None,
        None,
        "TARGETDIR",
    ),
    (
        "StartMenuShortcut",
        "ProgramMenuFolder",
        BRAND.product_name,
        "TARGETDIR",
        "[TARGETDIR]saebooks-desktop.exe",
        None,
        f"{BRAND.product_name} — {BRAND.tagline}",
        None,
        None,
        None,
        None,
        "TARGETDIR",
    ),
]

# ---------------------------------------------------------------------------
# MSI-specific options.
# upgrade_code must be stable across versions (never change it).
# ---------------------------------------------------------------------------
bdist_msi_options: dict = {
    "upgrade_code": _MSI_FACTS["upgrade_code"],
    "add_to_path": True,
    "initial_target_dir": _MSI_FACTS["target_dir"],
    "summary_data": {
        "author": BRAND.org_name,
        "comments": f"{BRAND.product_name} — {BRAND.tagline} desktop client",
    },
    # Install for all users (requires elevation).
    "all_users": True,
    # Product name shown in Add/Remove Programs.
    "product_name": BRAND.product_name,
    # Icon shown by the installer UI and in Add/Remove Programs.
    "install_icon": ICON_PATH,
    "data": {"Shortcut": _shortcut_table},
}

# ---------------------------------------------------------------------------
# Executable definition.
# base="gui" is the cx_Freeze 7 portable alias — it resolves to Win32GUI on
# Windows (suppresses the console window) and lets the spec at least be
# smoke-checked with build_exe on Linux/macOS.
# ---------------------------------------------------------------------------
# Shortcuts are defined via the MSI Shortcut data table above (desktop AND
# Start menu) — no shortcut_name/shortcut_dir here, or we'd get a duplicate
# desktop shortcut.
executables = [
    Executable(
        script=str(_here / "saebooks_desktop" / "__main__.py"),
        base="gui",
        target_name="saebooks-desktop.exe",
        icon=ICON_PATH,
    ),
]

setup(
    name=_MSI_FACTS["setup_name"],
    version=VERSION,
    description=f"{BRAND.product_name} — {BRAND.tagline} desktop client",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
