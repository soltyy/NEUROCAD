"""Adapter registry and factory.

Sprint 5.17: the config stores a concrete `model_id` (registry key from
`llm.models.MODELS`). `load_adapter` resolves that to a `ModelSpec`, picks
the right adapter class, and instantiates it with the spec's `model_id`,
`base_url`, and an API key looked up under `spec.key_slug`.

API-key precedence (per adapter load):
1. Session key (UI "Use once" / "Session only") – highest priority.
2. Environment variable `NEUROCAD_API_KEY_{KEY_SLUG_UPPERCASE}`
   (e.g. `NEUROCAD_API_KEY_DEEPSEEK`, `NEUROCAD_API_KEY_OPENAI`).
3. `key_storage.load_key(key_slug)` — tries every available backend.
4. If none found, ValueError with a clear diagnostic.
"""

import os
from typing import Any

from neurocad.config import key_storage

from . import models as _models
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


def _resolve_api_key(key_slug: str, session_key: str | None = None) -> str:
    """Retrieve API key by its storage slug. Precedence per the module docstring.

    `key_slug` is the `ModelSpec.key_slug` value (e.g. `"openai"`, `"deepseek"`).
    """
    if session_key and session_key.strip():
        return session_key.strip()
    env_var = f"NEUROCAD_API_KEY_{key_slug.upper()}"
    key = os.getenv(env_var)
    if key:
        return key
    stored_key, _backend_name = key_storage.load_key(key_slug)
    if stored_key:
        return stored_key
    available = ", ".join(b.name for b in key_storage.available_backends()) or "none"
    raise ValueError(
        f"No API key found for '{key_slug}'. "
        f"Set the {env_var} environment variable, or save a key via the "
        f"NeuroCad Settings dialog (available storage backends: {available})."
    )


def _resolve_spec(config: dict[str, Any]) -> _models.ModelSpec:
    """Find the ModelSpec referenced by the config.

    Preference: explicit `model_id` registry key → legacy
    `provider`+`model`+`base_url` inference → the registry default.

    An explicitly set but unknown `model_id` raises ValueError — typos
    should fail loud instead of silently falling back to the default.
    """
    mid = config.get("model_id")
    if mid:
        spec = _models.get_model(mid)
        if spec is None:
            available = ", ".join(s.id for s in _models.list_models())
            raise ValueError(
                f"Unknown model_id '{mid}'. Known models: {available}"
            )
        return spec
    inferred = _models.infer_from_legacy_config(config)
    if inferred is not None:
        return inferred
    default = _models.get_model(_models.default_model_id())
    assert default is not None, "default model must exist in the registry"
    return default


def _spec_to_adapter_kwargs(
    spec: _models.ModelSpec, config: dict[str, Any]
) -> dict[str, Any]:
    """Build kwargs for the adapter constructor from a ModelSpec + config.

    The spec drives `model` + `base_url`. Numeric / generation-side fields
    (`timeout`, `max_tokens`, `temperature`) may still come from the config.
    """
    valid = _ADAPTER_VALID_KEYS.get(spec.adapter, set())
    kwargs: dict[str, Any] = {k: v for k, v in config.items() if k in valid}
    # Spec overrides config for identity fields.
    kwargs["model"] = spec.model_id
    if spec.base_url is not None:
        kwargs["base_url"] = spec.base_url
    elif "base_url" in kwargs:
        # Ensure we do NOT accidentally inherit a stale legacy base_url
        # when the chosen spec expects the adapter default.
        kwargs.pop("base_url")
    return kwargs


def load_adapter(config: dict[str, Any], session_key: str | None = None) -> LLMAdapter:
    """Instantiate the adapter for ``config["model_id"]`` (or legacy fields).

    Session key wins over env var which wins over key_storage lookup. The
    looked-up key is stored under `ModelSpec.key_slug`, not the adapter type.
    """
    spec = _resolve_spec(config)
    adapter_cls = ADAPTERS.get(spec.adapter)
    if adapter_cls is None:
        raise ValueError(
            f"Model '{spec.id}' uses adapter '{spec.adapter}' which is not registered."
        )
    api_key = _resolve_api_key(spec.key_slug, session_key)
    kwargs = _spec_to_adapter_kwargs(spec, config)
    kwargs["api_key"] = api_key
    return adapter_cls(**kwargs)


def load_adapter_with_session_key(
    config: dict[str, Any], session_key: str
) -> LLMAdapter:
    """Instantiate the adapter using a temporary session key (no persistence)."""
    spec = _resolve_spec(config)
    adapter_cls = ADAPTERS.get(spec.adapter)
    if adapter_cls is None:
        raise ValueError(
            f"Model '{spec.id}' uses adapter '{spec.adapter}' which is not registered."
        )
    kwargs = _spec_to_adapter_kwargs(spec, config)
    kwargs["api_key"] = session_key
    return adapter_cls(**kwargs)
