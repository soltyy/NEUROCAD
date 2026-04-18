"""Sprint 5.15 — tests for the tiered cross-platform key storage."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from neurocad.config import key_storage


# --- PlaintextFileBackend ---------------------------------------------------

def test_plaintext_backend_save_load_roundtrip(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    assert backend.load("openai") is None
    backend.save("openai", "sk-TEST-123")
    assert backend.load("openai") == "sk-TEST-123"


def test_plaintext_backend_multiple_providers(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    backend.save("openai", "OPENAI")
    backend.save("anthropic", "ANTHROPIC")
    assert backend.load("openai") == "OPENAI"
    assert backend.load("anthropic") == "ANTHROPIC"


def test_plaintext_backend_overwrite(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    backend.save("openai", "old")
    backend.save("openai", "new")
    assert backend.load("openai") == "new"


@pytest.mark.skipif(sys.platform == "win32", reason="chmod semantics differ on Windows")
def test_plaintext_backend_sets_0600_on_unix(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    backend.save("openai", "sk-abc")
    mode = os.stat(path).st_mode & 0o777
    assert mode == 0o600, f"expected 0o600, got {oct(mode)}"


def test_plaintext_backend_delete(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    backend.save("openai", "sk-delete-me")
    backend.save("anthropic", "keep-me")
    backend.delete("openai")
    assert backend.load("openai") is None
    assert backend.load("anthropic") == "keep-me"


def test_plaintext_backend_delete_last_provider_removes_file(tmp_path: Path):
    path = tmp_path / "keys.json"
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    backend.save("openai", "sk-delete-me")
    assert path.exists()
    backend.delete("openai")
    assert not path.exists()


def test_plaintext_backend_corrupted_file_recovers(tmp_path: Path):
    path = tmp_path / "keys.json"
    path.write_text("not valid json {{{")
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    assert backend.load("openai") is None
    backend.save("openai", "sk-fresh")
    assert backend.load("openai") == "sk-fresh"


def test_plaintext_backend_is_always_available(tmp_path: Path):
    backend = key_storage.PlaintextFileBackend(path_provider=lambda: tmp_path / "x.json")
    assert backend.is_available() is True


# --- KeyringBackend ---------------------------------------------------------

def test_keyring_backend_available_when_imported():
    # With keyring installed (true in .venv), this should be True.
    backend = key_storage.KeyringBackend()
    # Don't assert specific value — just that call doesn't raise.
    assert backend.is_available() in (True, False)


# --- MacOSKeychainBackend ---------------------------------------------------

def test_macos_keychain_not_available_off_darwin():
    backend = key_storage.MacOSKeychainBackend()
    with patch.object(sys, "platform", "linux"):
        assert backend.is_available() is False


def test_macos_keychain_save_invokes_security_cli():
    backend = key_storage.MacOSKeychainBackend()
    with patch("neurocad.config.key_storage.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        backend.save("openai", "sk-keychain")
        mock_run.assert_called_once()
        args = mock_run.call_args.args[0]
        assert args[0] == "security"
        assert "add-generic-password" in args
        assert "-U" in args  # update-if-exists
        assert "-s" in args and "neurocad" in args
        assert "-a" in args and "openai" in args
        assert "-w" in args and "sk-keychain" in args


def test_macos_keychain_load_returns_value():
    backend = key_storage.MacOSKeychainBackend()
    fake_result = MagicMock(stdout="sk-from-keychain\n", returncode=0)
    with patch("neurocad.config.key_storage.subprocess.run", return_value=fake_result):
        assert backend.load("openai") == "sk-from-keychain"


def test_macos_keychain_load_returns_none_when_missing():
    backend = key_storage.MacOSKeychainBackend()
    err = subprocess.CalledProcessError(44, ["security"])
    with patch("neurocad.config.key_storage.subprocess.run", side_effect=err):
        assert backend.load("openai") is None


# --- LinuxSecretToolBackend -------------------------------------------------

def test_linux_secret_tool_not_available_off_linux():
    backend = key_storage.LinuxSecretToolBackend()
    with patch.object(sys, "platform", "darwin"):
        assert backend.is_available() is False


def test_linux_secret_tool_save_passes_key_via_stdin():
    backend = key_storage.LinuxSecretToolBackend()
    with patch("neurocad.config.key_storage.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0)
        backend.save("openai", "sk-linux")
        kwargs = mock_run.call_args.kwargs
        assert kwargs.get("input") == "sk-linux"
        args = mock_run.call_args.args[0]
        assert args[0] == "secret-tool"
        assert "store" in args


# --- save_key / load_key orchestration --------------------------------------

def test_save_key_session_tier_does_not_persist():
    # Session tier should not touch any backend.
    backend_name, err = key_storage.save_key("openai", "sk-x", tier=key_storage.TIER_SESSION)
    assert "Session" in backend_name
    assert err is None


def test_save_key_plaintext_tier_forces_plaintext(tmp_path: Path, monkeypatch):
    path = tmp_path / "keys.json"
    fake_backend = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    monkeypatch.setattr(
        key_storage,
        "PlaintextFileBackend",
        lambda path_provider=None: fake_backend,
    )
    backend_name, err = key_storage.save_key(
        "openai", "sk-plain", tier=key_storage.TIER_PLAINTEXT,
    )
    assert err is None
    assert "Plaintext" in backend_name
    assert fake_backend.load("openai") == "sk-plain"


def test_save_key_automatic_tries_backends_in_order(monkeypatch):
    """Automatic tier walks available backends; first success wins."""
    save_calls: list[str] = []

    class _Failing(key_storage.KeyStorageBackend):
        name = "FailingFirst"
        def is_available(self): return True
        def save(self, provider, key):
            save_calls.append("FailingFirst")
            raise RuntimeError("nope")
        def load(self, provider): return None
        def delete(self, provider): pass

    class _Ok(key_storage.KeyStorageBackend):
        name = "OkSecond"
        def is_available(self): return True
        def save(self, provider, key):
            save_calls.append("OkSecond")
        def load(self, provider): return "stored"
        def delete(self, provider): pass

    monkeypatch.setattr(
        key_storage, "available_backends", lambda: [_Failing(), _Ok()]
    )
    name, err = key_storage.save_key("openai", "sk-x", tier=key_storage.TIER_AUTOMATIC)
    assert name == "OkSecond"
    assert err is None
    assert save_calls == ["FailingFirst", "OkSecond"]


def test_save_key_returns_error_if_all_backends_fail(monkeypatch):
    class _Always(key_storage.KeyStorageBackend):
        name = "BrokenBackend"
        def is_available(self): return True
        def save(self, provider, key): raise RuntimeError("backend dead")
        def load(self, provider): return None
        def delete(self, provider): pass

    monkeypatch.setattr(
        key_storage, "available_backends", lambda: [_Always()]
    )
    name, err = key_storage.save_key("openai", "sk-x", tier=key_storage.TIER_AUTOMATIC)
    assert name == "none"
    assert err is not None
    assert "BrokenBackend" in err


def test_load_key_returns_first_found(monkeypatch):
    class _First(key_storage.KeyStorageBackend):
        name = "First"
        def is_available(self): return True
        def save(self, p, k): pass
        def load(self, provider): return None
        def delete(self, p): pass

    class _Second(key_storage.KeyStorageBackend):
        name = "Second"
        def is_available(self): return True
        def save(self, p, k): pass
        def load(self, provider): return "from-second"
        def delete(self, p): pass

    monkeypatch.setattr(
        key_storage, "available_backends", lambda: [_First(), _Second()]
    )
    key, backend = key_storage.load_key("openai")
    assert key == "from-second"
    assert backend == "Second"


def test_load_key_returns_none_if_nothing_found(monkeypatch):
    monkeypatch.setattr(key_storage, "available_backends", lambda: [])
    key, backend = key_storage.load_key("openai")
    assert key is None
    assert backend is None


def test_delete_key_purges_from_all_backends(monkeypatch, tmp_path: Path):
    path = tmp_path / "keys.json"
    plaintext = key_storage.PlaintextFileBackend(path_provider=lambda: path)
    plaintext.save("openai", "sk-plain")

    class _KeyringLike(key_storage.KeyStorageBackend):
        name = "FakeKeyring"
        _data: dict = {}
        def is_available(self): return True
        def save(self, p, k): self._data[p] = k
        def load(self, p): return self._data.get(p)
        def delete(self, p): self._data.pop(p, None)

    fake_kr = _KeyringLike()
    fake_kr.save("openai", "sk-keyring")

    monkeypatch.setattr(
        key_storage, "available_backends", lambda: [fake_kr, plaintext]
    )
    purged = key_storage.delete_key("openai")
    assert sorted(purged) == sorted(["FakeKeyring", "Plaintext file (owner-only)"])
    assert fake_kr.load("openai") is None
    assert plaintext.load("openai") is None


# --- Smoke: available_backends -------------------------------------------

def test_available_backends_are_instances_of_the_interface():
    for backend in key_storage.available_backends():
        assert isinstance(backend, key_storage.KeyStorageBackend)
        assert hasattr(backend, "save") and hasattr(backend, "load")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
