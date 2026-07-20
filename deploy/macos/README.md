# macOS packaging — status: NOT BUILT (gap documented)

There is **no macOS packaging tooling in this repo** as of v0.3.0, and no
macOS artifact has ever been produced. Nothing here is blocked on code —
the app is pure Python/PySide6 and PySide6 ships macOS wheels — but a real
`.app`/`.dmg` can only be built and tested on a Mac, which we do not have
in the fleet. Do not build blind; this file records the recommended path
for when a Mac (or a `macos-latest` CI runner) is available.

## Recommended approach

1. **Bundler: [Briefcase](https://beeware.org/project/projects/tools/briefcase/)**
   (preferred over py2app). Rationale: actively maintained, first-class
   PySide6 template support, produces a signed+notarized `.dmg` in one
   flow (`briefcase package macOS --identity "Developer ID Application: …"`),
   and the same `pyproject.toml` config later covers Windows/Linux if the
   per-platform scripts are ever consolidated. py2app works but leaves
   signing/notarization entirely manual; cx_Freeze `bdist_mac` is the
   weakest of its three platforms.
2. **Brand handling**: reuse the `brand.cfg` mechanism —
   `saebooks_desktop/branding.py` already honours a `brand.cfg` beside a
   frozen executable; for a `.app`, drop it in `Contents/Resources` and
   extend `_baked_brand_id()` to look there (one small patch), or simply
   set `SAEBOOKS_BRAND` via `LSEnvironment` in the generated `Info.plist`.
   Two apps, two bundle IDs: `au.com.saee.saebooks` / `ee.tasur.desktop`
   (bundle IDs must differ or the apps will fight over defaults/caches).
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

On any Mac with Xcode CLT + Python 3.12:

```bash
pip install briefcase
# add the [tool.briefcase] section to pyproject.toml (app name per brand,
# sources = ["saebooks_desktop"], requires = PySide6/httpx/platformdirs/grpcio)
briefcase create macOS && briefcase build macOS
briefcase package macOS --identity "Developer ID Application: <name> (<team>)"
```

Launch-verify the `.app` on that Mac (first-run wizard, correct brand)
before publishing anything.
