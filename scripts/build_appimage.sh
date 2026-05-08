#!/usr/bin/env bash
# Build a self-contained AppImage for SAE Books desktop.
#
# Usage:
#   ./scripts/build_appimage.sh [--arch amd64|arm64]
#
# Requirements (installed by CI or manually):
#   pip install "python-appimage>=1.2"   # or `uv run --with python-appimage>=1.2 ...`
#   libfuse2 on the build host (for AppImage runtime).
#
# Outputs:
#   dist/SAEBooks-<version>-<arch>.AppImage
#
# How it works:
#   python-appimage `build app` consumes an "appdir" containing
#       requirements.txt, entrypoint.sh, <name>.desktop, <name>.{png|svg}
#   We stage those + a freshly built wheel of saebooks_desktop into a temp
#   dir, point pip at the wheel via an absolute path in requirements.txt,
#   then invoke python-appimage. The output AppImage is renamed into dist/.

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
import importlib.util
spec = importlib.util.spec_from_file_location('pkg', '${REPO_ROOT}/saebooks_desktop/__init__.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
print(mod.__version__)
")"
echo "Building SAEBooks ${VERSION} AppImage for ${APPIMAGE_ARCH}"

mkdir -p "${DIST_DIR}"

# --------------------------------------------------------------------------
# Pick the python-appimage runner. Prefer an explicit PYTHON_APPIMAGE env
# (set by callers/CI), else `python -m python_appimage` if importable, else
# `uv run --with python-appimage>=1.2 python -m python_appimage`.
# --------------------------------------------------------------------------
if [[ -n "${PYTHON_APPIMAGE:-}" ]]; then
    PA_RUNNER=( ${PYTHON_APPIMAGE} )
elif python3 -c "import python_appimage" >/dev/null 2>&1; then
    PA_RUNNER=( python3 -m python_appimage )
elif command -v uv >/dev/null 2>&1; then
    PA_RUNNER=( uv run --with "python-appimage>=1.2" python -m python_appimage )
else
    echo "ERROR: python-appimage not importable and uv not available." >&2
    echo "       Install with: pip install 'python-appimage>=1.2'" >&2
    exit 1
fi

# --------------------------------------------------------------------------
# Stage the appdir python-appimage expects.
# --------------------------------------------------------------------------
STAGE_DIR="$(mktemp -d -t saebooks-appimage-XXXXXX)"
WHEEL_DIR="${STAGE_DIR}/wheels"
trap 'rm -rf "${STAGE_DIR}"' EXIT

mkdir -p "${WHEEL_DIR}"

echo "==> Building saebooks_desktop wheel"
python3 -m pip wheel "${REPO_ROOT}" --no-deps -w "${WHEEL_DIR}" \
    >/dev/null

# Locate the freshly built wheel (just one).
WHEEL_PATH="$(ls -1 "${WHEEL_DIR}"/saebooks_desktop-*.whl | head -n1)"
if [[ -z "${WHEEL_PATH}" || ! -f "${WHEEL_PATH}" ]]; then
    echo "ERROR: wheel build produced no saebooks_desktop-*.whl in ${WHEEL_DIR}" >&2
    exit 1
fi
echo "    wheel: ${WHEEL_PATH}"

# Copy the static appimage assets.
cp "${DEPLOY_DIR}/entrypoint.sh"       "${STAGE_DIR}/entrypoint.sh"
chmod +x "${STAGE_DIR}/entrypoint.sh"

# Build a desktop file with a Name= that produces a clean output filename
# (python-appimage uses the desktop's Name= field as the AppImage prefix).
# Also bake the version in so we can rename predictably.
DESKTOP_NAME="SAEBooks-${VERSION}"
sed -E "s/^Name=.*/Name=${DESKTOP_NAME}/" \
    "${DEPLOY_DIR}/saebooks-desktop.desktop" \
    > "${STAGE_DIR}/saebooks-desktop.desktop"

# Icon (SVG preferred; PNG also accepted by python-appimage).
if [[ -f "${DEPLOY_DIR}/saebooks-desktop.svg" ]]; then
    cp "${DEPLOY_DIR}/saebooks-desktop.svg" "${STAGE_DIR}/saebooks-desktop.svg"
elif [[ -f "${DEPLOY_DIR}/saebooks-desktop.png" ]]; then
    cp "${DEPLOY_DIR}/saebooks-desktop.png" "${STAGE_DIR}/saebooks-desktop.png"
else
    echo "ERROR: no icon at ${DEPLOY_DIR}/saebooks-desktop.{svg,png}" >&2
    exit 1
fi

# requirements.txt: PyPI deps + the local wheel by absolute path.
# python-appimage iterates lines and pip-installs each; absolute paths work
# regardless of pip's CWD (which is the python-appimage tmpdir at install time).
{
    grep -vE '^\s*(#|$)' "${DEPLOY_DIR}/requirements.txt"
    echo "${WHEEL_PATH}"
} > "${STAGE_DIR}/requirements.txt"

echo "==> Staged appdir: ${STAGE_DIR}"
echo "    requirements.txt:"
sed 's/^/      /' "${STAGE_DIR}/requirements.txt"

# --------------------------------------------------------------------------
# Invoke python-appimage. It writes <Name>-<arch>.AppImage to CWD.
# Run from a workdir so we can find and move the result.
# --------------------------------------------------------------------------
WORKDIR="$(mktemp -d -t saebooks-appimage-build-XXXXXX)"
trap 'rm -rf "${STAGE_DIR}" "${WORKDIR}"' EXIT

echo "==> Running python-appimage build app"
(
    cd "${WORKDIR}"
    "${PA_RUNNER[@]}" build app \
        -l "manylinux_2_28_${APPIMAGE_ARCH}" \
        -p "3.12" \
        "${STAGE_DIR}"
)

# python-appimage names the output "<Name>-<arch>.AppImage". Find it.
SRC_APPIMAGE="${WORKDIR}/${DESKTOP_NAME}-${APPIMAGE_ARCH}.AppImage"
if [[ ! -f "${SRC_APPIMAGE}" ]]; then
    # Fallback: glob (paranoia in case Name= comes through differently).
    SRC_APPIMAGE="$(ls -1 "${WORKDIR}"/*.AppImage 2>/dev/null | head -n1 || true)"
fi
if [[ -z "${SRC_APPIMAGE}" || ! -f "${SRC_APPIMAGE}" ]]; then
    echo "ERROR: python-appimage produced no .AppImage in ${WORKDIR}" >&2
    ls -la "${WORKDIR}" >&2
    exit 1
fi

DEST_APPIMAGE="${DIST_DIR}/SAEBooks-${VERSION}-${APPIMAGE_ARCH}.AppImage"
mv "${SRC_APPIMAGE}" "${DEST_APPIMAGE}"
chmod +x "${DEST_APPIMAGE}"

echo "Done: ${DEST_APPIMAGE}"
ls -lh "${DEST_APPIMAGE}"
