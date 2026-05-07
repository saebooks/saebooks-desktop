"""AI document extraction service.

Uploads a local file to POST /api/v1/documents/extract and returns the
extracted document fields as a plain dict.

The endpoint accepts multipart/form-data with a single ``file`` part and
returns JSON matching the extraction schema::

    {
        "vendor_name": "...",
        "invoice_number": "...",
        "date": "2026-04-25",
        "due_date": "...",
        "subtotal": "100.00",
        "tax_amount": "10.00",
        "total": "110.00",
        "currency": "AUD",
        "notes": "...",
        "extraction_confidence": 0.92,
        "line_items": [
            {
                "description": "...",
                "qty": 1,
                "unit_price": "100.00",
                "amount": "100.00",
                "tax_code": null
            }
        ]
    }

Design note: synchronous httpx is used intentionally — consistent with the
rest of the service layer (see api_client.py).
"""
from __future__ import annotations

import mimetypes
from pathlib import Path

import httpx

from saebooks_desktop.services.api_client import APIClient, APIError, ServerOfflineError

_EXTRACT_PATH = "/api/v1/documents/extract"

_SUPPORTED_MIME_TYPES = {
    ".pdf": "application/pdf",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
}


def extract_document(client: APIClient, file_path: Path) -> dict:
    """Upload *file_path* to the extraction endpoint and return the result dict.

    Args:
        client: Caller-supplied :class:`~saebooks_desktop.services.api_client.APIClient`.
        file_path: Local path to a PDF, JPEG, or PNG file.

    Returns:
        Extraction result dict from the API (see module docstring for schema).

    Raises:
        ValueError: If the file does not exist or has an unsupported extension.
        ServerOfflineError: If the server is unreachable.
        APIError: On non-2xx HTTP response.
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise ValueError(f"File not found: {file_path}")

    suffix = file_path.suffix.lower()
    mime_type = _SUPPORTED_MIME_TYPES.get(suffix)
    if mime_type is None:
        # Fall back to mimetypes for anything not in our explicit map
        guessed, _ = mimetypes.guess_type(str(file_path))
        mime_type = guessed or "application/octet-stream"

    headers: dict[str, str] = {}
    if client._token:
        headers["Authorization"] = f"Bearer {client._token}"

    try:
        with httpx.Client(
            base_url=client._base_url,
            headers=headers,
            timeout=client._timeout,
        ) as c:
            with file_path.open("rb") as fh:
                r = c.post(
                    _EXTRACT_PATH,
                    files={"file": (file_path.name, fh, mime_type)},
                )
    except httpx.TransportError as exc:
        raise ServerOfflineError(f"Server unreachable: {exc}") from exc

    if not r.is_success:
        raise APIError(
            f"POST {_EXTRACT_PATH} returned {r.status_code}: {r.text[:200]}",
            status_code=r.status_code,
        )

    return r.json()
