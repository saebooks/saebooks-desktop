#!/usr/bin/env bash
# Build a self-contained AppImage for SAE Books desktop.
#
# Usage:
#   ./scripts/build_appimage.sh [--arch amd64|arm64] [--brand saebooks|tasur]
#
# Requirements (installed by CI or manually):
#   pip install "python-appimage>=1.2"   # or `uv run --with python-appimage>=1.2 ...`
#   libfuse2 on the build host (for AppImage runtime).
#
# Outputs:
#   dist/SAEBooks-<version>-<arch>.AppImage   (--brand saebooks, default)
#   dist/tasur-<version>-<arch>.AppImage      (--brand tasur)
#
# The brand is baked into the AppImage entrypoint as an exported
# SAEBOOKS_BRAND env var, so each artifact is permanently its brand
# (saebooks_desktop.branding: env > baked > QSettings > default).
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
BRAND="saebooks"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --arch)  ARCH="$2";  shift 2 ;;
        --brand) BRAND="$2"; shift 2 ;;
        *)       echo "Unknown arg: $1"; exit 1 ;;
    esac
done

# Per-brand artifact facts. NAME_PREFIX drives the .desktop Name= field,
# which python-appimage uses as the output filename prefix.
case "${BRAND}" in
    saebooks)
        NAME_PREFIX="SAEBooks"
        DESKTOP_SRC="saebooks-desktop.desktop"
        ICON_SRC="saebooks-desktop.svg"
        ICON_DEST="saebooks-desktop.svg"
        ;;
    tasur)
        NAME_PREFIX="tasur"
        DESKTOP_SRC="tasur.desktop"
        ICON_SRC="tasur.svg"
        ICON_DEST="tasur.svg"
        ;;
    *)  echo "Unsupported brand: ${BRAND} (saebooks|tasur)"; exit 1 ;;
esac

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
echo "Building ${NAME_PREFIX} ${VERSION} AppImage for ${APPIMAGE_ARCH} (brand: ${BRAND})"

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

# Copy the static appimage assets, baking the brand into the entrypoint
# (inserted right after `set -e` so it precedes the exec line).
sed "/^set -e/a export SAEBOOKS_BRAND=${BRAND}" \
    "${DEPLOY_DIR}/entrypoint.sh" > "${STAGE_DIR}/entrypoint.sh"
chmod +x "${STAGE_DIR}/entrypoint.sh"

# Build a desktop file with a Name= that produces a clean output filename
# (python-appimage uses the desktop's Name= field as the AppImage prefix).
# Also bake the version in so we can rename predictably.
DESKTOP_NAME="${NAME_PREFIX}-${VERSION}"
sed -E "s/^Name=.*/Name=${DESKTOP_NAME}/" \
    "${DEPLOY_DIR}/${DESKTOP_SRC}" \
    > "${STAGE_DIR}/${DESKTOP_SRC}"

# Icon (SVG preferred; PNG also accepted by python-appimage).
if [[ -f "${DEPLOY_DIR}/${ICON_SRC}" ]]; then
    cp "${DEPLOY_DIR}/${ICON_SRC}" "${STAGE_DIR}/${ICON_DEST}"
else
    echo "ERROR: no icon at ${DEPLOY_DIR}/${ICON_SRC}" >&2
    exit 1
fi

# --------------------------------------------------------------------------
# Bundle libxcb-cursor.so.0.
#
# Qt 6.5+ links its xcb platform plugin against libxcb-cursor, and the PySide6
# wheel does NOT ship it. Every other libxcb-* the plugin needs is common
# enough to be present on a desktop host, but libxcb-cursor0 is not installed
# by default on many distributions (Ubuntu included). Without it the AppImage
# does not degrade -- Qt fails to load the xcb plugin and the process aborts
# before a single window appears:
#
#     qt.qpa.plugin: Could not load the Qt platform plugin "xcb"
#     Aborted (core dumped)
#
# This is the Linux twin of the Windows include_msvcr trap. Verified on skiff
# 2026-08-14: the shipped 0.4.0 AppImage aborted on a host without the
# package, and starting normally required nothing but this one library.
#
# entrypoint.sh already puts ${APPDIR}/usr/lib first on LD_LIBRARY_PATH, so
# dropping the file there is the whole fix. python-appimage merges a staged
# `usr` tree into the AppDir via --extra-data.
# --------------------------------------------------------------------------
EXTRA_DIR="${STAGE_DIR}/extra"
mkdir -p "${EXTRA_DIR}/usr/lib"

XCB_CURSOR_SRC="$(ldconfig -p 2>/dev/null \
    | awk '/libxcb-cursor\.so\.0/ {print $NF; exit}')"

if [[ -z "${XCB_CURSOR_SRC}" || ! -e "${XCB_CURSOR_SRC}" ]]; then
    echo "ERROR: libxcb-cursor.so.0 not found on the build host." >&2
    echo "       It must be bundled or the AppImage aborts before any UI." >&2
    echo "       Install it, then rebuild:  sudo apt-get install -y libxcb-cursor0" >&2
    exit 1
fi

# Dereference: the runtime linker needs the real object, not a build symlink.
cp -L "${XCB_CURSOR_SRC}" "${EXTRA_DIR}/usr/lib/libxcb-cursor.so.0"
echo "    bundling libxcb-cursor.so.0 from ${XCB_CURSOR_SRC}"

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
    # NOTE: the appdir positional MUST come before -x. python-appimage declares
    # --extra-data with nargs='+', so a trailing -x swallows the positional and
    # argparse then aborts with "the following arguments are required: appdir"
    # before any build work happens.
    "${PA_RUNNER[@]}" build app \
        -l "manylinux_2_28_${APPIMAGE_ARCH}" \
        -p "3.12" \
        "${STAGE_DIR}" \
        -x "${EXTRA_DIR}/usr"
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

DEST_APPIMAGE="${DIST_DIR}/${NAME_PREFIX}-${VERSION}-${APPIMAGE_ARCH}.AppImage"
mv "${SRC_APPIMAGE}" "${DEST_APPIMAGE}"
chmod +x "${DEST_APPIMAGE}"

echo "Done: ${DEST_APPIMAGE}"
ls -lh "${DEST_APPIMAGE}"
