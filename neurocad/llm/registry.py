"""Adapter registry and factory.

API key resolution follows a strict precedence contract (Sprint 5.15):
1. Session key (temporary, supplied via UI "Use once") – highest priority.
2. Environment variable NEUROCAD_API_KEY_{PROVIDER_UPPERCASE}.
3. `neurocad.config.key_storage.load_key(provider)` — tries every available
   backend in priority order: system keyring (pip) → macOS Keychain CLI →
   Linux secret-tool → plaintext-0600 file.
4. If none found, ValueError is raised with a clear guidance message.

This contract is guaranteed across all adapter loading functions.
"""

import os
from typing import Any

from neurocad.config import key_storage

from .anthropic import AnthropicAdapter
from .base import LLMAdapter
from .openai import OpenAIAdapter

ADAPTERS: dict[str, type[LLMAdapter]] = {
    "openai": OpenAIAdapter,
    "anthropic": AnthropicAdapter,
}

_OPENAI_VALID_KEYS = {"api_key", "model", "base_url", "max_tokens", "temperature", "timeout"}
_ANTHROPIC_VALID_KEYS = {"api_key", "model", "max_tokens", "temperature", "timeout"}
_ADAPTER_VALID_KEYS = {
    "openai": _OPENAI_VALID_KEYS,
    "anthropic": _ANTHROPIC_VALID_KEYS,
}


def _resolve_api_key(provider: str, session_key: str | None = None) -> str:
    """Retrieve API key. Precedence: session → env-var → key_storage backends.

    Args:
        provider: LLM provider name (e.g., "openai").
        session_key: Optional temporary key (e.g., via "Use once").
            If present and non-empty, it is used directly, no fallback attempted.

    Returns:
        API key string.

    Raises:
        ValueError: No key could be found in any of the sources.
    """
    if session_key and session_key.strip():
        return session_key.strip()
    env_var = f"NEUROCAD_API_KEY_{provider.upper()}"
    key = os.getenv(env_var)
    if key:
        return key
    stored_key, _backend_name = key_storage.load_key(provider)
    if stored_key:
        return stored_key
    # Compose a useful diagnostic about what backends were actually tried.
    available = ", ".join(b.name for b in key_storage.available_backends()) or "none"
    raise ValueError(
        f"No API key found for provider '{provider}'. "
        f"Set the {env_var} environment variable, or save a key via the "
        f"NeuroCad Settings dialog (available storage backends: {available})."
    )


def load_adapter(config: dict[str, Any], session_key: str | None = None) -> LLMAdapter:
    """Load adapter based on config, resolving API key with precedence.

    Precedence: session_key (if supplied) → environment variable → keyring.
    """
    provider = config.get("provider", "openai")
    adapter_cls = ADAPTERS.get(provider)
    if adapter_cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    api_key = _resolve_api_key(provider, session_key)
    valid_keys = _ADAPTER_VALID_KEYS.get(provider, set())
    adapter_config = {k: v for k, v in config.items() if k in valid_keys}
    adapter_config["api_key"] = api_key
    return adapter_cls(**adapter_config)


def load_adapter_with_session_key(
    config: dict[str, Any], session_key: str
) -> LLMAdapter:
    """Load adapter using a temporary session key (does not write to keyring)."""
    provider = config.get("provider", "openai")
    adapter_cls = ADAPTERS.get(provider)
    if adapter_cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    valid_keys = _ADAPTER_VALID_KEYS.get(provider, set())
    adapter_config = {k: v for k, v in config.items() if k in valid_keys}
    adapter_config["api_key"] = session_key
    return adapter_cls(**adapter_config)
