#!/bin/sh
# AppRun entry point — called by the AppImage runtime after mounting.
# APPDIR is set by the AppImage runtime to the mount point.
set -e

HERE="$(dirname "$(readlink -f "$0")")"
export APPDIR="${HERE}"

# Prefer the bundled Qt libraries over anything on the host.
export LD_LIBRARY_PATH="${APPDIR}/usr/lib:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="${APPDIR}/usr/plugins"
export QML2_IMPORT_PATH="${APPDIR}/usr/qml"

# Locate bundled Python.
PYTHON="${APPDIR}/usr/bin/python3"

exec "${PYTHON}" -m saebooks_desktop "$@"
