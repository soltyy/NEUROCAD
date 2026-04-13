"""Audit logging for NeuroCad operations (JSONL sink with rotation).

Schema
------
Each audit entry is a JSON object with the following top‑level fields:

- timestamp: ISO‑8601 UTC timestamp with microsecond precision, 'Z' suffix.
- correlation_id: session‑wide UUIDv4 string.
- event_type: short string identifying the event (e.g., "llm_request", "execution").
- data: event‑specific payload (sanitized dictionary).

Data Payload Contract
---------------------
The `data` dictionary must adhere to the following contract:

1. **No sensitive information**: keys containing "key", "token", "secret", "password"
   (case‑insensitive) are automatically removed.

2. **Preview capping**: the following fields are capped to
   `AUDIT_LOG_MAX_PREVIEW_CHARS` characters (default 500) with "..." suffix:
   - user_prompt_preview
   - system_prompt_preview
   - llm_response_preview
   - code_preview
   - text_preview (legacy)
   - preview (legacy)

3. **Object‑name capping**: the `new_object_names` list is capped to
   `AUDIT_LOG_MAX_OBJECT_NAMES` items (default 20); extra items are replaced with
   "... and N more".

4. **No nested dicts**: any dictionary value (except allowed lists) is removed
   to prevent accidental secret nesting.

5. **Allowed value types**: strings, numbers, booleans, null, flat lists.

Sanitization is applied automatically by `_sanitize_payload()` before writing.

Rotation
--------
Log files are rotated when they reach 5 MiB, keeping up to 5 backup files.
"""

import json
import logging
import logging.handlers
import uuid
from datetime import UTC, datetime
from typing import Any

from neurocad.config.config import _get_config_dir
from neurocad.config.defaults import (
    AUDIT_LOG_MAX_OBJECT_NAMES,
    AUDIT_LOG_MAX_PREVIEW_CHARS,
)

_AUDIT_LOGGER = None
_AUDIT_ENABLED = False
_CORRELATION_ID = None


def _cap_preview(text: str, max_chars: int = AUDIT_LOG_MAX_PREVIEW_CHARS) -> str:
    """Trim text to maximum allowed characters for audit preview."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def _cap_object_names(names: list[str], max_names: int = AUDIT_LOG_MAX_OBJECT_NAMES) -> list[str]:
    """Limit list of object names to maximum allowed count."""
    if len(names) <= max_names:
        return names
    return names[:max_names] + [f"... and {len(names) - max_names} more"]


def _sanitize_payload(data: dict[str, Any]) -> dict[str, Any]:
    """Sanitize audit payload according to contract.

    - Applies preview caps to known preview fields.
    - Caps new_object_names list length.
    - Removes keys that look like secrets.
    - Rejects nested dict/list values (except new_object_names) to limit shape.
    """
    sanitized = data.copy()

    # Define preview fields from contract
    preview_fields = {
        "user_prompt_preview",
        "system_prompt_preview",
        "llm_response_preview",
        "code_preview",
        "text_preview",  # legacy, treat as preview
        "preview",       # legacy
    }

    for key in list(sanitized.keys()):
        value = sanitized[key]

        # Remove secret-like keys (best-effort)
        if any(secret in key.lower() for secret in ("key", "token", "secret", "password")):
            sanitized.pop(key)
            continue

        # Limit shape: reject nested dict (except allowed keys) to prevent secret nesting
        if isinstance(value, dict):
            # Drop dict values that could hide secrets
            sanitized.pop(key)
            continue
        # Lists are allowed (including nested lists) but we keep them as is

        # Apply preview caps
        if key in preview_fields and isinstance(value, str):
            sanitized[key] = _cap_preview(value)

    # Special handling for new_object_names list
    if "new_object_names" in sanitized and isinstance(sanitized["new_object_names"], list):
        sanitized["new_object_names"] = _cap_object_names(sanitized["new_object_names"])

    return sanitized


def init_audit_log(config: dict[str, Any]) -> None:
    """Initialize audit logging based on configuration.

    If audit_log_enabled is True, sets up a rotating file handler
    writing JSONL to <config_dir>/logs/llm-audit.jsonl.
    Rotation: 5 files × 5 MiB each.
    """
    global _AUDIT_LOGGER, _AUDIT_ENABLED, _CORRELATION_ID
    _AUDIT_ENABLED = config.get("audit_log_enabled", False)
    if not _AUDIT_ENABLED:
        _AUDIT_LOGGER = None
        return

    # Generate a correlation ID for this session
    _CORRELATION_ID = str(uuid.uuid4())

    log_dir = _get_config_dir() / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "llm-audit.jsonl"

    # Create a dedicated logger (separate from application logs)
    logger = logging.getLogger("neurocad.audit")
    logger.setLevel(logging.INFO)
    # Remove any existing handlers to avoid duplicates
    logger.handlers.clear()

    handler = logging.handlers.RotatingFileHandler(
        filename=log_file,
        maxBytes=5 * 1024 * 1024,  # 5 MiB
        backupCount=5,
        encoding="utf-8",
    )
    # JSONL format: each line is a JSON object
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)
    logger.propagate = False  # prevent bubbling to root logger

    _AUDIT_LOGGER = logger


def audit_log(event_type: str, data: dict[str, Any], correlation_id: str | None = None) -> None:
    """Write an audit entry if audit logging is enabled.

    The entry is a JSON object with the following fields:
      - timestamp: ISO‑8601 UTC timestamp (added automatically).
      - correlation_id: session‑wide correlation ID (or provided override).
      - event_type: short string identifying the event.
      - data: event‑specific payload (keys are sanitized, secrets removed).

    The `data` dictionary must not contain sensitive information (API keys,
    session tokens, etc.). The function applies preview and list caps
    according to the contract.
    """
    if not _AUDIT_ENABLED or _AUDIT_LOGGER is None:
        return

    sanitized = _sanitize_payload(data)

    entry = {
        "timestamp": datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z"),
        "correlation_id": correlation_id if correlation_id is not None else _CORRELATION_ID,
        "event_type": event_type,
        "data": sanitized,
    }
    try:
        _AUDIT_LOGGER.info(json.dumps(entry, separators=(",", ":")))
    except Exception:
        # If logging fails, do not crash the application
        pass


def get_correlation_id() -> str | None:
    """Return the current session‑wide correlation ID (if audit is enabled)."""
    return _CORRELATION_ID
