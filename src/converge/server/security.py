"""Security helpers for webhook verification."""

from __future__ import annotations

import hashlib
import hmac


def compute_signature(secret: str, body: bytes) -> str:
    """Compute the SHA-256 hex digest for a raw request body."""
    return hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()


def verify_signature(secret: str, body: bytes, header_value: str) -> bool:
    """Verify a ``sha256=<hexdigest>`` signature header against the raw body."""
    if not header_value.startswith("sha256="):
        return False
    provided_digest = header_value.split("=", 1)[1]
    expected_digest = compute_signature(secret, body)
    return hmac.compare_digest(provided_digest, expected_digest)
