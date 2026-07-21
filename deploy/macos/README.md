# macOS packaging — status: BUILT (Briefcase, unsigned universal2)

macOS packaging tooling now lives in this repo: the `[tool.briefcase]`
config in `pyproject.toml` plus two shim packages (`desktop/`, `tasur/`)
build a per-brand `.app`/`.dmg`. The first real artifacts — universal2
(Apple Silicon + Intel), **ad-hoc signed, not notarized** — were produced
for v0.3.0 on an Apple Silicon Mac and published on the v0.3.0 release. The
build is pure Python/PySide6 and needs a Mac (or a `macos-latest` CI
runner) to run. The sections below record the design as built and the
remaining path to a signed + notarized release.

## Recommended approach

1. **Bundler: [Briefcase](https://beeware.org/project/projects/tools/briefcase/)**
   (preferred over py2app). Rationale: actively maintained, first-class
   PySide6 template support, produces a signed+notarized `.dmg` in one
   flow (`briefcase package macOS --identity "Developer ID Application: …"`),
   and the same `pyproject.toml` config later covers Windows/Linux if the
   per-platform scripts are ever consolidated. py2app works but leaves
   signing/notarization entirely manual; cx_Freeze `bdist_mac` is the
   weakest of its three platforms.
2. **Brand handling** (as built): the brand is baked two ways, matching
   `branding.py` precedence (env > baked > QSettings > default). Each brand
   is a distinct Briefcase app with a tiny shim package (`desktop/`,
   `tasur/`) that `os.environ.setdefault`s `SAEBOOKS_BRAND` — so a terminal
   launch of the bundled binary resolves the right brand — then re-execs
   `saebooks_desktop.main`; the Briefcase config also sets `SAEBOOKS_BRAND`
   via `LSEnvironment` in `Info.plist` for double-click launches. Under
   Briefcase `sys.frozen` is not set, so the `brand.cfg`-beside-executable
   path in `_baked_brand_id()` does not apply here. Two apps, two bundle
   IDs: `com.saebooks.desktop` / `com.saebooks.desktop.tasur` — standardized
   on the `com.saebooks.*` namespace, consistent with the Android app's
   `com.saebooks.cashbook` (the IDs must differ or the apps will fight over
   defaults/caches).
3. **Signing + notarization requirements** (hard requirements on modern
   macOS — an unsigned, un-notarized app is blocked by Gatekeeper with no
   everyday-person override):
   - Apple Developer Program membership (USD 99/yr).
   - A **Developer ID Application** certificate for signing.
   - Notarization via `notarytool` (Apple ID + app-specific password or
     App Store Connect API key), then `stapler staple` the ticket.
   - Hardened runtime enabled (Briefcase does this by default).
4. **Both architectures**: build universal2 or separate arm64 + x86_64
   artifacts; PySide6 provides universal2 wheels, so universal2 is the
   simpler ship.

## Minimum viable first cut

On any Mac with Xcode CLT + Python 3.10+ (v0.3.0 was built with 3.14):

```bash
pip install briefcase
# [tool.briefcase] is already in pyproject.toml (apps: desktop, tasur;
# each sources = ["saebooks_desktop", "<shim>"], min_os_version = "13.0",
# requires = PySide6/httpx/platformdirs/grpcio/protobuf).
for app in desktop tasur; do
  briefcase create  macOS -a "$app"
  briefcase build   macOS -a "$app"
  # Unsigned distributable (no Developer ID): ad-hoc sign, no notarization.
  briefcase package macOS -a "$app" -p dmg --adhoc-sign --no-notarize
done
```

This yields universal2 DMGs (min macOS 13) that run on the build Mac and
can be shared, but macOS Gatekeeper blocks the first open on other Macs
(right-click -> Open). For a friction-free release, swap `--adhoc-sign
--no-notarize` for `--identity "Developer ID Application: <name> (<team>)"`
(requires Apple Developer Program membership + a Developer ID cert, then
notarization via `notarytool` + `stapler staple`). Launch-verify each
`.app` (first-run wizard, correct brand) before publishing.
