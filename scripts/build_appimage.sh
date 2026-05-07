#!/usr/bin/env bash
# Build a self-contained AppImage for SAE Books desktop.
#
# Usage:
#   ./scripts/build_appimage.sh [--arch amd64|arm64]
#
# Requirements (installed by CI or manually):
#   pip install "python-appimage>=1.2"
#   # appimagetool is downloaded automatically by python-appimage
#
# Outputs:
#   dist/SAEBooks-<version>-<arch>.AppImage
#
# The AppImage bundles CPython 3.12 + all runtime deps.  No pre-built native
# wheels are fetched — pip resolves from sdist/pure-wheel on the build host.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEPLOY_DIR="${REPO_ROOT}/deploy/appimage"
DIST_DIR="${REPO_ROOT}/dist"

# --------------------------------------------------------------------------
# Parse args
# --------------------------------------------------------------------------
ARCH="amd64"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch) ARCH="$2"; shift 2 ;;
        *)      echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Normalise to AppImage convention (x86_64 / aarch64).
case "${ARCH}" in
    amd64|x86_64)   APPIMAGE_ARCH="x86_64"  ;;
    arm64|aarch64)  APPIMAGE_ARCH="aarch64" ;;
    *)  echo "Unsupported arch: ${ARCH}"; exit 1 ;;
esac

# --------------------------------------------------------------------------
# Resolve version
# --------------------------------------------------------------------------
VERSION="$(python3 -c "
import importlib.util, pathlib, sys
spec = importlib.util.spec_from_file_location('pkg', '${REPO_ROOT}/saebooks_desktop/__init__.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.__version__)
")"
echo "Building SAEBooks ${VERSION} AppImage for ${APPIMAGE_ARCH}"

mkdir -p "${DIST_DIR}"

# --------------------------------------------------------------------------
# python-appimage build
#
# Invocation:
#   python -m python_appimage build app \
#       --linux-tag  manylinux_2_28_<arch>  \  # glibc compat floor
#       --python-version 3.12               \
#       --requirements <req file>           \
#       --app-dir     <directory>           \
#       --output-filename <name>.AppImage
#
# --app-dir points at the package source root so the app itself is included.
# --------------------------------------------------------------------------
python3 -m python_appimage build app \
    --linux-tag "manylinux_2_28_${APPIMAGE_ARCH}" \
    --python-version "3.12" \
    --requirements "${DEPLOY_DIR}/requirements.txt" \
    --app-dir "${REPO_ROOT}" \
    --entrypoint "saebooks_desktop.main:main" \
    --output-filename "${DIST_DIR}/SAEBooks-${VERSION}-${APPIMAGE_ARCH}.AppImage"

echo "Done: ${DIST_DIR}/SAEBooks-${VERSION}-${APPIMAGE_ARCH}.AppImage"
