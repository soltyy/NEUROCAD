"""Adapter registry and factory."""

from typing import Any

from .base import LLMAdapter

ADAPTERS: dict[str, LLMAdapter] = {}


def load_adapter(config: dict[str, Any]) -> LLMAdapter:
    """Load adapter based on config, resolving API key from environment/keyring."""
    # Implementation will be added in Sprint 2
    raise NotImplementedError("load_adapter not implemented")


def load_adapter_with_session_key(
    config: dict[str, Any], session_key: str
) -> LLMAdapter:
    """Load adapter using a temporary session key (does not write to keyring)."""
    # Implementation will be added in Sprint 2
    raise NotImplementedError("load_adapter_with_session_key not implemented")
