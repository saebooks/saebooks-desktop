# Changelog

All notable changes to the SAE Books desktop client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.3] - 2026-05-08

### Changed

- **First-run wizard — server connect page rewritten.** Replaces the old
  two-mode (local / remote) layout with three transport modes:
  - **Local Docker** (default) — auto-fills `http://localhost:8042` for
    REST and `localhost:50051` for gRPC, prefers gRPC.
  - **Cloud / hosted URL** — REST only. Cloud reverse proxies (Caddy,
    nginx, Cloudflare, fly.io) almost never pass gRPC frames through
    transparently, so this mode probes REST only and pins
    `prefer_grpc=False`.
  - **LAN server** — both transports available, gRPC preferred, with an
    inline note explaining why ("3–5× lower latency, long-lived
    streaming for change events"). The user supplies REST URL + gRPC
    `host:port` separately.
  Test connection now probes both REST and gRPC where relevant; the
  page completes when REST works, but the result message tells the user
  whether gRPC was reachable too.
- Persists four QSettings keys: `saebooks/server/{rest_url, grpc_url,
  transport_mode, prefer_grpc}`. The wizard outcome is mirrored into
  `transport/mode` (AUTO/GRPC/REST) so `APIClient.resolve_transport()`
  picks up the right backend without further coupling.

### Added

- **Sign-in — bearer token paste path.** A second mode on the sign-in
  page accepts the JWT printed by `python -m saebooks.cli
  bootstrap-admin` on a fresh self-host install. The token is validated
  by calling `GET /api/v1/me` with it in the Authorization header. This
  closes the chicken-and-egg gap where bootstrap-admin creates an owner
  with no password set yet.
- `services.auth.validate_token(client, token)` helper (used by the new
  paste path).
- `services.settings.{get,set}_transport_mode` and
  `{get,set}_prefer_grpc` accessors.

## [0.1.2] - 2026-05-08

### Changed

- Cut alongside saebooks v0.1.2 to keep the desktop image, REST/gRPC
  contract version, and `bootstrap-admin` CLI in lockstep. No
  user-visible changes since 0.1.1.

## [0.1.1] - 2026-05-08

### Added

- **Purchase Orders** sidebar entry (between Purchases and Journal Entries).
  Filterable list with status colours for `DRAFT`, `OPEN`, `PARTIAL`, `RECEIVED`,
  `CLOSED` and `CANCELLED`. Read-only detail view with status-conditional Send /
  Cancel / Close action buttons.
- **Convert-to-bill modal.** Per-line receipt-quantity picker (or 0 for full
  outstanding); on success, jumps to the Purchases nav and loads the new draft
  bill.
- **Tools → Prorate Calculator…** — three-tab dialog covering the per-line,
  first-period and plan-change preview endpoints. Results render in a monospace
  pane below the form.
- Search routing: `purchase_order` results route to the new Purchase Orders nav.

### Note

PO line-item editing is intentionally not exposed on the desktop. POs that need
edits are modified in the web UI; the desktop is the read-and-act surface.

## [0.1.0] - 2026-05-08

Initial public alpha.
