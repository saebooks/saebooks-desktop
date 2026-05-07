@echo off
REM Build SAE Books MSI installer for Windows x64.
REM
REM Prerequisites:
REM   pip install "cx_Freeze>=7.2"
REM
REM Output:
REM   dist\SAEBooks-<version>-x64.msi
REM
REM Run from the repo root:
REM   scripts\build_msi.bat

setlocal enabledelayedexpansion

set "REPO_ROOT=%~dp0.."
cd /d "%REPO_ROOT%"

echo Building SAE Books MSI...
python deploy\windows\setup_freeze.py bdist_msi
if errorlevel 1 (
    echo MSI build failed.
    exit /b 1
)

REM cx_Freeze names the file <name>-<version>-<platform>.msi inside dist\.
REM Rename to our canonical SAEBooks-<version>-x64.msi convention.
for /f "delims=" %%F in ('dir /b /s dist\*.msi 2^>nul') do (
    set "BUILT_MSI=%%F"
)
if not defined BUILT_MSI (
    echo No .msi found in dist\ after build.
    exit /b 1
)

python -c "
import importlib.util, pathlib
spec = importlib.util.spec_from_file_location('p', 'saebooks_desktop/__init__.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
print(m.__version__)
" > "%TEMP%\saebooks_ver.txt"
set /p VERSION=<"%TEMP%\saebooks_ver.txt"

set "DEST_MSI=dist\SAEBooks-%VERSION%-x64.msi"
if not "%BUILT_MSI%"=="%DEST_MSI%" (
    move /y "%BUILT_MSI%" "%DEST_MSI%"
)

echo.
echo MSI ready: %DEST_MSI%
endlocal
