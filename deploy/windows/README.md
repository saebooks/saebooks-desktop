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

## Not done yet (known gaps)

- No `.ico` icons — the Executable's `icon=` line is commented out; the
  MSI installs with the default icon. Convert the brand SVGs before 1.0.
- The MSI is unsigned. Windows SmartScreen will warn on download/run
  ("Windows protected your PC → More info → Run anyway") until the MSI is
  signed with a code-signing certificate (EV cert removes the warning
  immediately; a standard cert ages out of it via reputation).
