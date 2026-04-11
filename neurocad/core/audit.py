"""Audit logging for NeuroCad operations (JSONL sink with rotation)."""

import json
import logging
import logging.handlers
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from neurocad.config.config import _get_config_dir
from neurocad.config.defaults import (
    AUDIT_LOG_MAX_PREVIEW_CHARS,
    AUDIT_LOG_MAX_OBJECT_NAMES,
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


def init_audit_log(config: dict[str, Any]) -> None:
    """Initialize audit logging based on configuration.
    
    If audit_log_enabled is True, sets up a rotating file handler
    writing JSONL to <config_dir>/logs/neurocad-audit.log.
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
    log_file = log_dir / "neurocad-audit.log"

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
    according to the defaults.
    """
    if not _AUDIT_ENABLED or _AUDIT_LOGGER is None:
        return

    # Apply caps to certain known fields
    sanitized = data.copy()
    if "preview" in sanitized and isinstance(sanitized["preview"], str):
        sanitized["preview"] = _cap_preview(sanitized["preview"])
    if "new_object_names" in sanitized and isinstance(sanitized["new_object_names"], list):
        sanitized["new_object_names"] = _cap_object_names(sanitized["new_object_names"])

    # Remove any key that looks like a secret (best‑effort)
    for key in list(sanitized.keys()):
        if any(secret in key.lower() for secret in ("key", "token", "secret", "password")):
            sanitized.pop(key)

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
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