"""Redaction of request/response payloads before they are audited.

The legacy system logged raw request bodies - including plaintext passwords
(see roadmap §5). That must never happen here. Any key in `AUDIT_REDACTED_FIELDS`
is replaced with a fixed marker, recursively, at every nesting level.
"""

from __future__ import annotations

import json
from copy import deepcopy
from typing import Any

from app.config.settings import settings

_REDACTED_MARKER = "[REDACTED]"


def _redact_inplace(value: Any, fields: set[str]) -> Any:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in fields:
                value[key] = _REDACTED_MARKER
            else:
                value[key] = _redact_inplace(child, fields)
        return value
    if isinstance(value, list):
        return [_redact_inplace(item, fields) for item in value]
    return value


def redact_payload(payload: Any) -> Any:
    """Return a redacted deep copy of a JSON-serializable payload."""
    fields = set(settings.AUDIT_REDACTED_FIELDS)
    try:
        return _redact_inplace(deepcopy(payload), fields)
    except Exception:  # pragma: no cover - defensive; never break the pipeline
        return {"_redact_error": _REDACTED_MARKER}


def redact_json(text: str, max_bytes: int | None = None) -> str | None:
    """Redact a raw JSON body string; return None for empty/invalid input."""
    if not text:
        return None
    if max_bytes is not None and len(text.encode("utf-8")) > max_bytes:
        return None
    try:
        data = json.loads(text)
    except (ValueError, TypeError):
        return None
    return json.dumps(redact_payload(data), sort_keys=True, separators=(",", ":"))
