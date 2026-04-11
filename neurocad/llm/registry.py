"""Adapter registry and factory."""

import os
from typing import Any

try:
    import keyring
except ImportError:
    keyring = None  # type: ignore[assignment]

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


def _resolve_api_key(provider: str) -> str:
    """Retrieve API key from environment or keyring.

    Precedence:
    1. Environment variable NEUROCAD_API_KEY_{PROVIDER_UPPERCASE}
    2. Keyring entry "neurocad", provider
    3. Raise ValueError with clear instructions.
    """
    env_var = f"NEUROCAD_API_KEY_{provider.upper()}"
    key = os.getenv(env_var)
    if key:
        return key
    if keyring is not None:
        key = keyring.get_password("neurocad", provider)
        if key:
            return key
        keyring_hint = "or store it in the system keyring"
    else:
        keyring_hint = (
            "or install the `keyring` package in the FreeCAD Python environment to store it"
        )
    raise ValueError(
        f"No API key found for provider '{provider}'. "
        f"Set the {env_var} environment variable {keyring_hint}."
    )


def load_adapter(config: dict[str, Any]) -> LLMAdapter:
    """Load adapter based on config, resolving API key from environment/keyring."""
    provider = config.get("provider", "openai")
    adapter_cls = ADAPTERS.get(provider)
    if adapter_cls is None:
        raise ValueError(f"Unknown provider: {provider}")
    api_key = _resolve_api_key(provider)
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
