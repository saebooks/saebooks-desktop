# Windows MSI build

## What must run where — plainly

`cx_Freeze bdist_msi` **only runs on Windows**. It drives the Windows
Installer machinery (MSI database creation) through Windows-only APIs and
cannot cross-compile from Linux or macOS. There is no supported way to
produce the MSI from scada/bosun; a Windows host (physical, VM, or a
`windows-latest` CI runner) is required.

What CAN be verified on Linux — and is, in this repo:

- Brand resolution and MSI option assembly:
  `uv run python deploy/windows/setup_freeze.py --name --version`
  (both brands, plus rejection of unknown brands).
- The full freeze spec: `SAEBOOKS_BRAND=tasur uv run python
  deploy/windows/setup_freeze.py build_exe` produces a working frozen
  Linux build with `brand.cfg` beside the executable (smoke-launched
  offscreen). Only the final `bdist_msi` step is Windows-bound.

## Building on a Windows host

1. Windows 10/11 x64, Python **3.12** (64-bit) on PATH.
   (3.12 is the tested baseline; if you try 3.13+ confirm your cx_Freeze
   version supports `bdist_msi` there before trusting the artifact.)
2. From a clone of this repo, in `cmd.exe` at the repo root:

   ```bat
   pip install -e . "cx_Freeze>=7.2"
   scripts\build_msi.bat           :: SAE Books  -> dist\SAEBooks-<ver>-x64.msi
   scripts\build_msi.bat tasur     :: tasur      -> dist\tasur-<ver>-x64.msi
   ```

3. Sanity checks before shipping:
   - `dist\<Brand>-<ver>-x64.msi` exists and the version is not empty
     (the `SAEBooks--x64.msi` failure mode from v0.1.4 is fixed but cheap
     to confirm).
   - Install it, launch from the desktop shortcut, and confirm the window
     title / first-run wizard shows the right brand (`brand.cfg` sits next
     to `saebooks-desktop.exe` in the install dir).
   - The two brands install side-by-side: each has its own MSI
     `upgrade_code` (see `setup_freeze.py`), so one must never
     upgrade/remove the other.

## Brand mechanics

`SAEBOOKS_BRAND` at **build** time selects the brand. `setup_freeze.py`
bakes it into the artifact as a one-line `brand.cfg` installed beside the
frozen executable; `saebooks_desktop.branding` reads that at runtime with
precedence env var > baked artifact > QSettings > default.

## What the installer does (v0.4)

- **Ships the VC++ runtime.** `include_msvcr=True` plus an explicit copy of
  `vcruntime140*.dll` / `msvcp140*.dll` from the CPython install. v0.3.0
  shipped without them and hard-crashed on every clean Windows machine with
  "VCRUNTIME140.dll was not found" before any UI appeared. `build_msi.bat`
  now **fails the build** if `vcruntime140.dll` is missing from the frozen
  directory — never ship an MSI that skips this check.
- **Installs to `[ProgramFiles64Folder]`.** `ProgramFilesFolder` resolves to
  `Program Files (x86)` even inside an x64 package.
- **Start-menu + desktop shortcuts**, both carrying the brand icon (the exe
  has the `.ico` as a resource; the installer and Add/Remove Programs use
  the same file).
- **Welcome/AGPL first page** (`license_file`, generated RTF) before the
  directory picker, and a **"Launch on finish" checkbox** on the last page.
- **Qt is trimmed to the modules actually imported** (QtCore/QtGui/QtWidgets
  +QtSvg). Listing `PySide6` in `packages` pulls in WebEngine, Quick, 3D,
  Charts and friends — that was ~90% of the 252 MB v0.3.0 payload.
  `grpc_tools` (protoc, a build-time compiler) is excluded outright; the
  gRPC stubs in `saebooks_desktop/grpc_gen/` are generated and committed.

## Not done yet (known gaps)

- The MSI is unsigned. Windows SmartScreen will warn on download/run
  ("Windows protected your PC → More info → Run anyway") until the MSI is
  signed with a code-signing certificate (EV cert removes the warning
  immediately; a standard cert ages out of it via reputation).
