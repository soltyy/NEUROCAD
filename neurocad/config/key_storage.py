"""Tiered, cross-platform API-key storage backends.

Sprint 5.15: the previous code relied on the `keyring` pip package, which is
NOT present in FreeCAD's bundled Python interpreter. When it was missing, the
Settings dialog raised a scary modal and the user had to re-enter the key on
every session. This module introduces a tiered fallback chain:

    1. KeyringBackend           — Python `keyring` pip (if installed)
    2. MacOSKeychainBackend     — `security` CLI (macOS, no pip deps)
    3. LinuxSecretToolBackend   — `secret-tool` CLI (Linux / GNOME Keyring)
    4. PlaintextFileBackend     — JSON file with chmod 0600 (universal)

Each backend exposes the same interface: `is_available()`, `save()`, `load()`,
`delete()`. The module-level `save_key()` / `load_key()` walk the available
backends in order and return `(backend_name, error)` so the UI can show the
user where the key actually ended up.

Secrets never appear in logs — callers must NOT print / audit the key value.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

try:
    import keyring as _keyring_mod  # noqa: F401 — presence check only
    _HAS_KEYRING = True
except ImportError:
    _HAS_KEYRING = False


SERVICE_NAME = "neurocad"


class KeyStorageBackend:
    """Interface for a key storage backend. Concrete subclasses override all four methods."""

    name: str = "Unknown"
    description: str = ""

    def is_available(self) -> bool:
        raise NotImplementedError

    def save(self, provider: str, key: str) -> None:
        """Persist `key` under the given `provider`. Raises on failure."""
        raise NotImplementedError

    def load(self, provider: str) -> str | None:
        """Return the stored key for `provider`, or None if not found."""
        raise NotImplementedError

    def delete(self, provider: str) -> None:
        """Remove the stored key for `provider`. Silent no-op if not present."""
        raise NotImplementedError


# --- Concrete backends -----------------------------------------------------

class KeyringBackend(KeyStorageBackend):
    name = "System keyring"
    description = "Secure OS keychain via Python `keyring` package"

    def is_available(self) -> bool:
        return _HAS_KEYRING

    def save(self, provider: str, key: str) -> None:
        import keyring
        keyring.set_password(SERVICE_NAME, provider, key)

    def load(self, provider: str) -> str | None:
        import keyring
        return keyring.get_password(SERVICE_NAME, provider)

    def delete(self, provider: str) -> None:
        import keyring
        try:
            keyring.delete_password(SERVICE_NAME, provider)
        except Exception:
            pass


class MacOSKeychainBackend(KeyStorageBackend):
    name = "macOS Keychain"
    description = "macOS Keychain via `security` CLI (no pip deps)"

    def is_available(self) -> bool:
        return sys.platform == "darwin" and shutil.which("security") is not None

    def save(self, provider: str, key: str) -> None:
        # -U updates if a matching entry exists (otherwise it would fail).
        subprocess.run(
            ["security", "add-generic-password", "-U",
             "-s", SERVICE_NAME, "-a", provider, "-w", key],
            check=True, capture_output=True, text=True,
        )

    def load(self, provider: str) -> str | None:
        try:
            out = subprocess.run(
                ["security", "find-generic-password",
                 "-s", SERVICE_NAME, "-a", provider, "-w"],
                check=True, capture_output=True, text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        value = out.stdout.strip()
        return value or None

    def delete(self, provider: str) -> None:
        subprocess.run(
            ["security", "delete-generic-password",
             "-s", SERVICE_NAME, "-a", provider],
            capture_output=True, text=True,
        )


class LinuxSecretToolBackend(KeyStorageBackend):
    name = "GNOME Keyring (libsecret)"
    description = "libsecret via `secret-tool` CLI (Linux, no pip deps)"

    def is_available(self) -> bool:
        return sys.platform.startswith("linux") and shutil.which("secret-tool") is not None

    def save(self, provider: str, key: str) -> None:
        # `secret-tool store` reads the secret from stdin.
        subprocess.run(
            ["secret-tool", "store", "--label", f"{SERVICE_NAME}-{provider}",
             "service", SERVICE_NAME, "account", provider],
            input=key, text=True, check=True, capture_output=True,
        )

    def load(self, provider: str) -> str | None:
        try:
            out = subprocess.run(
                ["secret-tool", "lookup", "service", SERVICE_NAME, "account", provider],
                check=True, capture_output=True, text=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        value = out.stdout.strip()
        return value or None

    def delete(self, provider: str) -> None:
        subprocess.run(
            ["secret-tool", "clear", "service", SERVICE_NAME, "account", provider],
            capture_output=True, text=True,
        )


class PlaintextFileBackend(KeyStorageBackend):
    name = "Plaintext file (owner-only)"
    description = (
        "JSON file in the config dir, chmod 0600 on Unix. Readable only by the "
        "owner; use only if no OS-native keychain is available."
    )

    def __init__(self, path_provider=None):
        # `path_provider` is a callable returning the file path — injectable for tests.
        self._path_provider = path_provider

    def _path(self) -> Path:
        if self._path_provider is not None:
            return Path(self._path_provider())
        # Lazy import to avoid circular import with config.py.
        from neurocad.config.config import _get_config_dir
        return _get_config_dir() / "api_keys.json"

    def is_available(self) -> bool:
        return True  # always works — last-resort fallback

    def _load_all(self) -> dict[str, str]:
        p = self._path()
        if not p.exists():
            return {}
        try:
            with open(p, encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}

    def save(self, provider: str, key: str) -> None:
        p = self._path()
        p.parent.mkdir(parents=True, exist_ok=True)
        data = self._load_all()
        data[provider] = key
        # Atomic write: write to tmp, chmod, rename.
        tmp = p.with_suffix(p.suffix + ".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        if sys.platform != "win32":
            os.chmod(tmp, 0o600)
        os.replace(tmp, p)

    def load(self, provider: str) -> str | None:
        return self._load_all().get(provider) or None

    def delete(self, provider: str) -> None:
        data = self._load_all()
        if provider not in data:
            return
        data.pop(provider)
        p = self._path()
        if data:
            with open(p, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            if sys.platform != "win32":
                os.chmod(p, 0o600)
        elif p.exists():
            p.unlink()


# --- Orchestration --------------------------------------------------------

# Tier codes used in the UI radio-button:
TIER_AUTOMATIC = "auto"
TIER_SESSION = "session"
TIER_PLAINTEXT = "plaintext"


def _all_backends() -> list[KeyStorageBackend]:
    """All candidate backends in preference order (most secure first)."""
    return [
        KeyringBackend(),
        MacOSKeychainBackend(),
        LinuxSecretToolBackend(),
        PlaintextFileBackend(),
    ]


def available_backends() -> list[KeyStorageBackend]:
    """Backends that are actually usable on the current host."""
    return [b for b in _all_backends() if b.is_available()]


def save_key(
    provider: str,
    key: str,
    tier: str = TIER_AUTOMATIC,
) -> tuple[str, str | None]:
    """Save `key` for `provider`.

    Returns `(backend_name, error_message_or_None)`.

    tier:
      - TIER_AUTOMATIC — try secure backends first, fall back to plaintext.
      - TIER_PLAINTEXT — force the plaintext file backend (skip keyring/OS).
      - TIER_SESSION   — return without saving; caller stores in memory only.
    """
    if tier == TIER_SESSION:
        return ("Session only (not persisted)", None)

    if tier == TIER_PLAINTEXT:
        candidates: list[KeyStorageBackend] = [PlaintextFileBackend()]
    else:
        candidates = available_backends()

    last_error: str | None = None
    for backend in candidates:
        try:
            backend.save(provider, key)
            return (backend.name, None)
        except Exception as exc:
            last_error = f"{backend.name}: {exc}"
            continue

    return ("none", last_error or "no storage backend available")


def load_key(provider: str) -> tuple[str | None, str | None]:
    """Try every available backend; return `(key, backend_name)` on the first hit."""
    for backend in available_backends():
        try:
            value = backend.load(provider)
        except Exception:
            continue
        if value:
            return (value, backend.name)
    return (None, None)


def delete_key(provider: str) -> list[str]:
    """Delete `provider` key from EVERY available backend. Returns names purged."""
    purged: list[str] = []
    for backend in available_backends():
        try:
            before = backend.load(provider)
        except Exception:
            before = None
        if before:
            try:
                backend.delete(provider)
                purged.append(backend.name)
            except Exception:
                pass
    return purged
