@echo off
REM Build the SAE Books / tasur MSI installer for Windows x64.
REM
REM Usage (from the repo root, on Windows):
REM   scripts\build_msi.bat            -- SAE Books brand (default)
REM   scripts\build_msi.bat tasur      -- tasur brand
REM
REM Prerequisites:
REM   Windows 10/11 x64, Python 3.12 (64-bit)
REM   pip install "cx_Freeze>=7.2"
REM
REM Output:
REM   dist\SAEBooks-<version>-x64.msi   (default brand)
REM   dist\tasur-<version>-x64.msi      (tasur brand)
REM
REM NOTE: cx_Freeze bdist_msi runs ONLY on Windows — it cannot cross-compile
REM from Linux/macOS. Each brand bakes a brand.cfg beside the executable and
REM carries its own MSI upgrade_code (see deploy\windows\setup_freeze.py).

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

REM Brand selection (arg 1; default saebooks).
set "BRAND=%~1"
if "%BRAND%"=="" set "BRAND=saebooks"
if /i not "%BRAND%"=="saebooks" if /i not "%BRAND%"=="tasur" (
    echo Unknown brand "%BRAND%" ^(saebooks^|tasur^).
    exit /b 1
)
set "SAEBOOKS_BRAND=%BRAND%"

if /i "%BRAND%"=="tasur" (
    set "MSI_PREFIX=tasur"
) else (
    set "MSI_PREFIX=SAEBooks"
)

REM Build into a per-brand scratch directory, NOT straight into dist\.
REM Picking up "the .msi in dist\" after the fact is how a stale 264 MB
REM v0.3.0-era artifact got reported as the fresh 50 MB v0.4.0 build on
REM 2026-07-22 — and clearing dist\ instead would delete the other brand's
REM MSI when both are built in sequence. A scratch dir per brand has exactly
REM one MSI in it, always this build's.
set "STAGE_DIR=build\msi-stage-%BRAND%"
if exist "%STAGE_DIR%" rmdir /s /q "%STAGE_DIR%"

echo Building %MSI_PREFIX% MSI...
python deploy\windows\setup_freeze.py bdist_msi --dist-dir "%STAGE_DIR%"
if errorlevel 1 (
    echo MSI build failed.
    exit /b 1
)

REM Guard: v0.3.0 shipped without the VC++ runtime and hard-crashed on every
REM clean Windows machine ("VCRUNTIME140.dll was not found"). The frozen
REM directory bdist_msi packaged is under build\exe.*; refuse to hand over an
REM MSI whose payload lacks the runtime.
set "VCRT_FOUND="
REM NOTE: `dir /s` recurses from the named directory; a wildcard in the
REM directory part (build\exe.*\...) does NOT match, so search from build\.
for /f "delims=" %%F in ('dir /b /s build\vcruntime140.dll 2^>nul') do (
    set "VCRT_FOUND=%%F"
)
if not defined VCRT_FOUND (
    echo.
    echo ERROR: vcruntime140.dll is NOT in the frozen build directory.
    echo The MSI would be dead on arrival on a clean Windows machine.
    echo Check include_msvcr / the CPython install in deploy\windows\setup_freeze.py.
    exit /b 1
)
echo VC++ runtime present: %VCRT_FOUND%

REM cx_Freeze names the file <name>-<version>-<platform>.msi inside dist\.
REM Rename to our canonical <Brand>-<version>-x64.msi convention.
set "BUILT_MSI="
set "MSI_COUNT=0"
for /f "delims=" %%F in ('dir /b /s "%STAGE_DIR%\*.msi" 2^>nul') do (
    set "BUILT_MSI=%%F"
    set /a MSI_COUNT+=1
)
if not defined BUILT_MSI (
    echo No .msi found in %STAGE_DIR%\ after build.
    exit /b 1
)
if not "%MSI_COUNT%"=="1" (
    echo ERROR: %MSI_COUNT% .msi files in %STAGE_DIR%\ — expected exactly 1.
    exit /b 1
)

REM Resolve version on a single python -c line — cmd.exe terminates a multi-line
REM `python -c "..."` at the first newline, which silently produces an empty
REM version and an MSI named "SAEBooks--x64.msi". Keep this on one line.
python -c "import importlib.util as u;s=u.spec_from_file_location('p','saebooks_desktop/__init__.py');m=u.module_from_spec(s);s.loader.exec_module(m);print(m.__version__)" > "%TEMP%\saebooks_ver.txt"
set /p VERSION=<"%TEMP%\saebooks_ver.txt"

if not exist dist mkdir dist
set "DEST_MSI=dist\%MSI_PREFIX%-%VERSION%-x64.msi"
move /y "%BUILT_MSI%" "%DEST_MSI%" >nul
if errorlevel 1 (
    echo Could not move %BUILT_MSI% to %DEST_MSI%.
    exit /b 1
)
rmdir /s /q "%STAGE_DIR%"

echo.
echo MSI ready: %DEST_MSI%
endlocal
