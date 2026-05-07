# saebooks-desktop

Native desktop client for
[saebooks](https://github.com/saebooks/saebooks). PySide6/Qt thin
client that talks gRPC to a saebooks API server.

> **Status:** v0.1 — public alpha, **untested in the wild**. Released
> early so adventurous self-hosters can poke at it. Bug reports
> welcome. AGPL-3.0.

## What it is

A native Qt application for users who want a desktop experience over
the saebooks ledger instead of (or alongside) the web UI. It connects
to a running saebooks API instance via gRPC on port 50051.

## Requirements

* Python 3.10+
* A reachable [saebooks](https://github.com/saebooks/saebooks) API
  instance with the gRPC port (50051) exposed.

## Installing

### From source

```bash
git clone https://github.com/saebooks/saebooks-desktop.git
cd saebooks-desktop
uv sync
uv run saebooks-desktop
```

### Pre-built

Pre-built binaries (Windows MSI and Linux AppImage) are attached to
the [v0.1 release](../../releases). These are alpha builds — please
file an issue if anything breaks.

## First run

On first launch the app asks for:

1. The API URL (e.g. `https://books.example.com` or
   `http://localhost:8042`).
2. Your API bearer token (or, when portal SSO lands, your portal
   credentials).
3. A licence key if you want to unlock features above the Community
   edition.

Settings are persisted via `platformdirs` to your OS user-config
directory.

## Project layout

```
saebooks_desktop/
  main.py            entry point
  main_window.py     top-level Qt window
  settings.py        persisted config
  licence.py         licence-key validation
  views/             per-domain Qt views
  wizard/            first-run wizard
  services/          API + gRPC clients
  grpc_gen/          generated protobuf stubs
proto/               .proto sources
deploy/
  windows/           cx_Freeze setup
  appimage/          python-appimage build inputs
```

## Building installers

```bash
# Windows (run on Windows host with Python 3.10+)
uv run python deploy/windows/setup_freeze.py bdist_msi

# Linux AppImage
uv pip install python-appimage
python -m python_appimage build app deploy/appimage
```

## Licence

AGPL-3.0. See <https://github.com/saebooks/saebooks> for the
top-level project, charter, and commercial licensing options.
