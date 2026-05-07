"""Stripe payment link service — generates a Stripe payment link for a posted invoice.

Returns the payment link URL from
``POST /api/v1/invoices/{invoice_id}/stripe-payment-link``.

Callers should catch ``APIError`` and ``ServerOfflineError`` from
``api_client`` if they want custom error handling.

Status codes of interest:
- 200: link generated, response body contains ``{"url": "..."}``
- 503: Stripe not configured (STRIPE_SECRET_KEY absent from server config)
- 422: Invoice not in a valid state (not POSTED or already fully paid)
"""
from __future__ import annotations

from saebooks_desktop.services.api_client import APIClient


def generate_payment_link(client: APIClient, invoice_id: str) -> str:
    """Generate a Stripe payment link for *invoice_id*.

    Args:
        client: Caller-supplied APIClient instance.
        invoice_id: Invoice UUID string.

    Returns:
        The Stripe payment link URL as a string.

    Raises:
        ServerOfflineError: If the server cannot be reached.
        APIError: On non-2xx response (includes 503 and 422).
                  Check ``exc.status_code`` to distinguish error types.
    """
    data = client.post(f"/api/v1/invoices/{invoice_id}/stripe-payment-link")
    return str(data.get("url", ""))
