#! /bin/bash
# Entry point for the SAE Books desktop AppImage.
# Inlined by python-appimage into AppRun; APPDIR is set by the AppImage runtime.
set -e

# Prefer bundled Qt libs over anything on the host.
export LD_LIBRARY_PATH="${APPDIR}/usr/lib:${LD_LIBRARY_PATH:-}"
export QT_PLUGIN_PATH="${APPDIR}/usr/plugins"
export QML2_IMPORT_PATH="${APPDIR}/usr/qml"

exec "{{ python-executable }}" -m saebooks_desktop "$@"
