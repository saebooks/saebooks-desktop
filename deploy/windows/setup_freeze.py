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
        # ProgramFilesFolder resolves to "Program Files (x86)" even inside an
        # x64 package — a 64-bit app must use ProgramFiles64Folder.
        "target_dir": r"[ProgramFiles64Folder]\SAEBooks",
    },
    "tasur": {
        "setup_name": "tasur",
        "upgrade_code": "{108EDDEE-9FF7-4AD0-AE67-2675D2060C6E}",
        "target_dir": r"[ProgramFiles64Folder]\tasur",
    },
}[BRAND_ID]

# Bake the brand into the artifact: a one-line brand.cfg installed beside
# the frozen executable (read by saebooks_desktop.branding at runtime).
_brand_cfg = pathlib.Path(tempfile.mkdtemp(prefix="saebooks-msi-")) / "brand.cfg"
_brand_cfg.write_text(BRAND_ID + "\n", encoding="utf-8")

# ---------------------------------------------------------------------------
# Welcome / licence page (installer's FIRST screen).
#
# cx_Freeze's bdist_msi has no dedicated welcome dialog, but it does render a
# scrollable first page when ``license_file`` is set. We use that as the
# branding + AGPL page so the directory picker is no longer the bare first
# thing a user sees. RTF only, and RTF is ASCII-escaped — keep it plain.
# ---------------------------------------------------------------------------
_WELCOME_TEXT = f"""Welcome to {BRAND.product_name}.

{BRAND.product_name} is {BRAND.tagline}. Your books stay on your own
computer, in your own file. Nothing is uploaded anywhere.

This installer copies the {BRAND.product_name} desktop program onto this
computer and adds it to the Start menu and desktop. It does NOT install a
server. If you do not already have a {BRAND.product_name} server running,
the program will point you to the free one-click server the first time you
open it.

Version {VERSION}. This is beta software: please keep your own backups.

Licence
{BRAND.product_name} is free software published by {BRAND.org_name} under
the GNU Affero General Public License, version 3 or later (AGPL-3.0-or-later).
It comes with ABSOLUTELY NO WARRANTY. You may use, study, share and modify
it under the terms of that licence. The full text is installed alongside the
program and is available at https://www.gnu.org/licenses/agpl-3.0.html
"""


def _rtf_escape(text: str) -> str:
    out = text.replace("\\", r"\\").replace("{", r"\{").replace("}", r"\}")
    # Anything outside ASCII becomes an RTF unicode escape.
    out = "".join(c if ord(c) < 128 else rf"\u{ord(c)}?" for c in out)
    return out.replace("\n", "\\par\n")


_license_rtf = pathlib.Path(tempfile.mkdtemp(prefix="saebooks-msi-lic-")) / "welcome.rtf"
_license_rtf.write_text(
    r"{\rtf1\ansi\deff0{\fonttbl{\f0 Segoe UI;}}\fs20 "
    + _rtf_escape(_WELCOME_TEXT)
    + "}",
    encoding="ascii",
)

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
        "httpx",
        "platformdirs",
        "grpc",
        "google.protobuf",
    ],
    # Qt: name the modules we actually use rather than the whole PySide6
    # package. Listing "PySide6" in `packages` drags in every Qt module
    # (WebEngine, 3D, Quick, Charts, Multimedia, …) — ~90% of the 252 MB
    # v0.3.0 payload for a client that only imports QtCore/QtGui/QtWidgets.
    # QtSvg is kept for the SVG icon fallback in saebooks_desktop.app_icon.
    "includes": [
        "PySide6.QtCore",
        "PySide6.QtGui",
        "PySide6.QtWidgets",
        "PySide6.QtSvg",
    ],
    "excludes": [
        # Test tooling — not needed at runtime.
        "pytest",
        "pytest_qt",
        "unittest",
        "_pytest",
        # Build-time only. The gRPC stubs under saebooks_desktop/grpc_gen/
        # are generated and committed, so protoc (~40 MB of compiler) has no
        # business inside a thin client. grpcio itself stays.
        "grpc_tools",
        # Scientific stack — nothing in the client imports these; they get
        # dragged in transitively and cost tens of MB.
        "numpy",
        "pandas",
        "matplotlib",
        "scipy",
        # Dev/packaging tooling and dead stdlib corners.
        "setuptools",
        "pip",
        "wheel",
        "cx_Freeze",
        "tkinter",
        "lib2to3",
        "pydoc_data",
        "test",
        "idlelib",
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
    # Ship the Microsoft Visual C++ runtime beside the executable. Without
    # it a clean Windows machine (no vc_redist installed) hard-crashes at
    # launch with "VCRUNTIME140.dll was not found" before any UI appears —
    # exactly how the public v0.3.0 MSI shipped. Users must never be asked
    # to install a redistributable by hand.
    "include_msvcr": True,
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
# Belt and braces on the VC++ runtime: copy the DLLs explicitly from the
# CPython installation (they sit beside python.exe) in addition to relying on
# include_msvcr. Whichever mechanism fires, the install dir ends up with them.
# ---------------------------------------------------------------------------
if sys.platform == "win32":
    _py_dir = pathlib.Path(sys.base_prefix)
    _msvcr_names = (
        "vcruntime140.dll",
        "vcruntime140_1.dll",
        "msvcp140.dll",
        "msvcp140_1.dll",
        "msvcp140_2.dll",
        "concrt140.dll",
    )
    _found_msvcr = [
        _py_dir / name for name in _msvcr_names if (_py_dir / name).is_file()
    ]
    for _dll in _found_msvcr:
        build_exe_options["include_files"].append((str(_dll), _dll.name))
    # vcruntime140.dll is the one whose absence killed v0.3.0 — if neither
    # this copy nor include_msvcr can supply it, fail the build loudly rather
    # than shipping another DOA installer.
    if not any(d.name.lower() == "vcruntime140.dll" for d in _found_msvcr):
        print(
            "WARNING: vcruntime140.dll not found beside "
            f"{_py_dir}\\python.exe — relying on include_msvcr alone. "
            "Verify the built exe directory contains it before shipping.",
            file=sys.stderr,
        )

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
    # First screen: branding + what this installs + the AGPL notice, instead
    # of dropping the user straight onto a bare directory picker.
    "license_file": str(_license_rtf),
    # "Launch <product>" checkbox on the Finish page.
    "launch_on_finish": True,
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
    # cx_Freeze derives the MSI Manufacturer property (ARP "Publisher") from
    # distribution metadata — summary_data.author alone leaves it "UNKNOWN".
    author=BRAND.org_name,
    description=f"{BRAND.product_name} — {BRAND.tagline} desktop client",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
