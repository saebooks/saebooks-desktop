# Changelog

All notable changes to the SAE Books desktop client will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
