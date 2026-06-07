"""Privacy gateway for telemetry and evidence attributes."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping  # noqa: TCH003  public annotation with postponed eval
from typing import Any

from tessera.observability.schema import ALLOWED_ATTRIBUTES, FORBIDDEN_ATTRIBUTES

__all__ = [
    "PII_PATTERNS",
    "hash_identifier",
    "privacy_findings",
    "sanitize_attributes",
]


PII_PATTERNS: dict[str, re.Pattern[str]] = {
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b"),
    "email": re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE),
    "pan": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "phone": re.compile(r"\b(?:\+?\d[\d .-]{7,}\d)\b"),
}


def hash_identifier(value: object) -> str:
    """Return a stable non-reversible hash for a correlation identifier."""
    text = str(value).encode("utf-8")
    return "sha256:" + hashlib.sha256(text).hexdigest()


def privacy_findings(value: object) -> list[str]:
    """Return PII finding names detected in ``value``."""
    text = str(value)
    return [name for name, pattern in PII_PATTERNS.items() if pattern.search(text)]


def sanitize_attributes(attributes: Mapping[str, Any]) -> dict[str, Any]:
    """Allowlist and redact telemetry attributes before export.

    Unknown attributes are dropped. Explicitly forbidden attributes are dropped
    even if a caller accidentally reuses a permitted-looking name. Values that
    match PII patterns are replaced with a redaction marker.
    """
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        if key in FORBIDDEN_ATTRIBUTES or key not in ALLOWED_ATTRIBUTES:
            continue
        findings = privacy_findings(value)
        if findings:
            sanitized[key] = "[REDACTED:" + ",".join(sorted(findings)) + "]"
        else:
            sanitized[key] = value
    return sanitized
