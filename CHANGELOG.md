# Changelog

All notable changes to the SAE Books desktop client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-07-20

### Changed

- **Mode-driven navigation** (adjudicated navigation verdict — revises
  PoC decision #16). The sidebar now branches on the selected company's
  `bookkeeping_mode`, never on licence tier:
  - *Cashbook mode*: primary nav is Cashbook (entries), Reports
    (cashbook summary), Settings, plus exactly one "Full accounting →"
    doorway. Contacts is omitted — cashbook entries are contactless.
  - *Full mode*: the full accounting nav with NO Cashbook primary item;
    "Switch to cashbook mode" lives in Settings → General.
  - Mode resolution reads `bookkeeping_mode` off the company record;
    the 409 `cashbook_not_configured` probe is fallback only (no
    per-render round-trip). A company switch or mode flip re-renders
    the nav (`refresh_company_context` / `apply_bookkeeping_mode`).
    Per-panel degrade behaviour is unchanged.

### Added

- **Full accounting doorway** — explainer view ("you own a complete
  double-entry ledger — your entries are real journal entries; switch
  on the full suite anytime, nothing is re-keyed") with a confirmed
  upgrade action against
  `POST /api/v1/companies/{id}/bookkeeping-mode` (`mode=full`,
  the engine's `upgrade_cashbook_to_full`).
- **Switch to cashbook mode** in Settings → General (full mode only) —
  calls the same endpoint with `mode=cashbook`
  (`downgrade_full_to_cashbook`); the engine gates on zero open AR and
  its 422 refusal message is surfaced verbatim.
- **Cashbook Reports view** — date-ranged rendering of
  `GET /api/v1/cashbook/summary` (totals + by-category table) backing
  the Reports nav item in cashbook mode.
- **Brand `tax_label` in cashbook summary strips** — "GST" (saebooks)
  vs "käibemaks" (tasur) collected/paid labels on the Cashbook view and
  the Cashbook Reports view (closes a deferred item from 0.2.0).

## [0.2.0] - 2026-07-18

### Changed

- **Aligned with the pure engine API** (embedded engine UI retired in
  engine #32). Token validation moved `/api/v1/me` → `/api/v1/auth/me`;
  `bank-statement-lines` → `bank_statement_lines`; `journal-entries` →
  `journal_entries`; fixed-asset archive → `DELETE`, depreciate →
  `post_depreciation`; recurring-invoice run → `generate`; reachability
  probe `GET /` → `GET /api/v1/healthz`.
- `X-Company-Id` is now sent on every REST call (multi-company tenants;
  the engine's "first active company" fallback is unsafe past one company).

### Added

- **Dashboard** — stat tiles (revenue / expenses / net over trailing
  12 months, AR/AP outstanding) plus a module-health strip from
  `GET /api/v1/modules/usage`; per-section error isolation.
- **Cashbook mode** — full native view (summary strip, entries table,
  add-entry form with direction-filtered categories, delete) against
  `/api/v1/cashbook/*`; auto-detected via the company's
  `bookkeeping_mode` and the 409 `cashbook_not_configured` probe.
- **Module-outage degradation** — `ModuleUnavailableError` parses the
  engine's three module-unavailable 503 shapes (circuit-breaker
  problem+json, fail-closed gate, guarded-import stub); affected panels
  degrade with a banner instead of the whole app going "offline".
- **tasur variant** — brand registry (`SAEBOOKS_BRAND=tasur`: product
  name, Estonian-blue placeholder logo, EUR default, käibemaks tax
  label, `et` default locale) and gettext i18n reusing the saebooks-web
  ET/RU catalogs (2,684 msgids each) with English fallthrough.

## [0.1.5] - 2026-05-08

### Fixed

- **MSI filename in CI release.** `scripts/build_msi.bat` had a multi-line
  `python -c "..."` to resolve the version, but cmd.exe terminates a
  multi-line `python -c` at the first newline, so the version came back
  empty and the artefact attached to the v0.1.4 release was named
  `SAEBooks--x64.msi`. Collapsed to a single-line `python -c` so the
  version resolves correctly. v0.1.5 ships as `SAEBooks-0.1.5-x64.msi`.

## [0.1.4] - 2026-05-08

### Fixed

- **AppImage build.** `scripts/build_appimage.sh` was calling
  `python-appimage build app` with flags that don't exist
  (`--requirements`, `--app-dir`, `--entrypoint`, `--output-filename`),
  so v0.1.1 / v0.1.2 / v0.1.3 release builds failed at the AppImage
  step. Rewritten to match the real CLI: stage a temp appdir with
  `entrypoint.sh`, per-version `.desktop`, SVG icon, and a
  `requirements.txt` that references a freshly-built `saebooks_desktop`
  wheel by absolute path; invoke `python -m python_appimage build app
  -l manylinux_2_28_<arch> -p 3.12 <appdir>`.
  - `deploy/appimage/AppRun.sh` → renamed `entrypoint.sh`
  - `deploy/appimage/saebooks-desktop.svg` — placeholder icon (replace
    before public 1.0)
- **`QStandardItemModel` import in `purchase_order_detail.py`.** Imported
  from `PySide6.QtWidgets` (where it does not exist in current PySide6)
  instead of `PySide6.QtGui`. This broke 36 tests in
  `test_main_window_navigation.py` and `test_smoke.py` with
  `ImportError: cannot import name 'QStandardItemModel'`. All other
  views were already importing correctly. Pure import correction, no
  behaviour change.

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
