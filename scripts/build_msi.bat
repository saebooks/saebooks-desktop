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

echo Building %MSI_PREFIX% MSI...
python deploy\windows\setup_freeze.py bdist_msi
if errorlevel 1 (
    echo MSI build failed.
    exit /b 1
)

REM cx_Freeze names the file <name>-<version>-<platform>.msi inside dist\.
REM Rename to our canonical <Brand>-<version>-x64.msi convention.
for /f "delims=" %%F in ('dir /b /s dist\*.msi 2^>nul') do (
    set "BUILT_MSI=%%F"
)
if not defined BUILT_MSI (
    echo No .msi found in dist\ after build.
    exit /b 1
)

REM Resolve version on a single python -c line — cmd.exe terminates a multi-line
REM `python -c "..."` at the first newline, which silently produces an empty
REM version and an MSI named "SAEBooks--x64.msi". Keep this on one line.
python -c "import importlib.util as u;s=u.spec_from_file_location('p','saebooks_desktop/__init__.py');m=u.module_from_spec(s);s.loader.exec_module(m);print(m.__version__)" > "%TEMP%\saebooks_ver.txt"
set /p VERSION=<"%TEMP%\saebooks_ver.txt"

set "DEST_MSI=dist\%MSI_PREFIX%-%VERSION%-x64.msi"
if not "%BUILT_MSI%"=="%DEST_MSI%" (
    move /y "%BUILT_MSI%" "%DEST_MSI%"
)

echo.
echo MSI ready: %DEST_MSI%
endlocal
