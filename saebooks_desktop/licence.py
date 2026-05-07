"""Licence JWT loader/verifier — stub implementation.

Full implementation (Ed25519 signature check against embedded portal public
key, offline grace period, heartbeat to portal) is Phase 4.5 / Lane A work.
For now this module returns a Community-tier stub so the UI can display a
tier badge without blocking desktop bootstrap.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

# Default JWT storage path (mirrors planned production location).
_DEFAULT_JWT_PATH = Path.home() / "AppData" / "Roaming" / "SAE Books" / "licence.jwt"
# XDG fallback for Linux/macOS development.
_XDG_JWT_PATH = Path.home() / ".config" / "SAE Books" / "licence.jwt"


@dataclass
class LicenceInfo:
    tier: str = "community"
    holder_name: str = ""
    features: list[str] = field(default_factory=list)
    valid: bool = True
    stub: bool = True  # True until real verification is wired


def load_licence() -> LicenceInfo:
    """Load and (stub-)verify a licence JWT from disk.

    Returns a Community-tier LicenceInfo if no JWT is found or verification
    is not yet implemented. Never raises — the UI must always be able to
    start in Community mode.
    """
    jwt_path = _DEFAULT_JWT_PATH if _DEFAULT_JWT_PATH.exists() else _XDG_JWT_PATH
    env_jwt = os.environ.get("SAEBOOKS_LICENCE_JWT")

    if not env_jwt and not jwt_path.exists():
        # No licence on disk — Community mode.
        return LicenceInfo()

    # TODO (Phase 4.5): decode + verify Ed25519 signature against embedded
    # portal public key, check exp, check offline_grace_days, call heartbeat.
    # For now, return a Community stub unconditionally.
    return LicenceInfo(stub=True)
