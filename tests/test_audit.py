"""Dedicated regression tests for NeuroCad audit logging contract.

Covers the acceptance criteria of NC‑DEV‑TEST‑005C:
- file creation only when audit_log_enabled=True
- JSONL schema and mandatory fields
- redaction / preview caps / object‑name cap
- correlation IDs and timestamps
- absence of API key / secrets in logs
- rotation behavior (mocked)
- adapter‑init failures audit coverage
"""

import json
import logging
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

from neurocad.core.audit import (
    init_audit_log,
    audit_log,
    get_correlation_id,
    _cap_preview,
    _cap_object_names,
)
from neurocad.config.defaults import AUDIT_LOG_MAX_PREVIEW_CHARS, AUDIT_LOG_MAX_OBJECT_NAMES


def test_cap_preview():
    """Preview capping respects the default limit."""
    long_text = "a" * (AUDIT_LOG_MAX_PREVIEW_CHARS + 10)
    capped = _cap_preview(long_text)
    assert len(capped) == AUDIT_LOG_MAX_PREVIEW_CHARS + 3  # + "..."
    assert capped.endswith("...")
    assert capped.startswith("a" * AUDIT_LOG_MAX_PREVIEW_CHARS)

    short_text = "hello"
    assert _cap_preview(short_text) == short_text

    empty = ""
    assert _cap_preview(empty) == ""

    none_text = None
    assert _cap_preview(none_text) == ""


def test_cap_object_names():
    """Object‑name list capping respects the default limit."""
    many_names = [f"obj{i}" for i in range(AUDIT_LOG_MAX_OBJECT_NAMES + 5)]
    capped = _cap_object_names(many_names)
    assert len(capped) == AUDIT_LOG_MAX_OBJECT_NAMES + 1
    assert capped[-1] == f"... and 5 more"
    assert capped[:AUDIT_LOG_MAX_OBJECT_NAMES] == many_names[:AUDIT_LOG_MAX_OBJECT_NAMES]

    few_names = ["obj1", "obj2"]
    assert _cap_object_names(few_names) == few_names


def test_init_audit_log_enabled_creates_file():
    """Audit log file is created only when audit_log_enabled=True."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            # Enable audit logging
            init_audit_log({"audit_log_enabled": True})
            log_file = config_dir / "logs" / "neurocad-audit.log"
            assert log_file.exists()
            # Write a test entry
            audit_log("test_event", {"foo": "bar"})
            # Ensure the file contains JSONL
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            assert len(lines) == 1
            entry = json.loads(lines[0])
            assert entry["event_type"] == "test_event"
            assert entry["data"]["foo"] == "bar"
            assert "timestamp" in entry
            assert "correlation_id" in entry
            # Cleanup global state for other tests
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_init_audit_log_disabled_no_file():
    """No log file is created when audit_log_enabled=False."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": False})
            log_file = config_dir / "logs" / "neurocad-audit.log"
            assert not log_file.exists()
            # audit_log should be a no‑op
            audit_log("test_event", {"foo": "bar"})
            assert not log_file.exists()
            # Ensure global state is disabled
            from neurocad.core.audit import _AUDIT_ENABLED, _AUDIT_LOGGER
            assert _AUDIT_ENABLED is False
            assert _AUDIT_LOGGER is None


def test_audit_log_jsonl_schema():
    """Each audit entry is a valid JSON object with mandatory fields."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": True})
            audit_log("test_schema", {"number": 42, "list": [1, 2, 3]})
            log_file = config_dir / "logs" / "neurocad-audit.log"
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            entry = json.loads(lines[0])
            # Mandatory top‑level fields
            assert "timestamp" in entry
            assert isinstance(entry["timestamp"], str)
            assert "correlation_id" in entry
            assert isinstance(entry["correlation_id"], str)
            assert entry["event_type"] == "test_schema"
            assert "data" in entry
            assert entry["data"]["number"] == 42
            assert entry["data"]["list"] == [1, 2, 3]
            # Cleanup
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_redaction_of_secret_like_keys():
    """Keys containing 'key', 'token', 'secret', 'password' are removed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": True})
            audit_log("test_redaction", {
                "api_key": "sk-12345",
                "auth_token": "xyz",
                "secret_password": "hidden",
                "safe_field": "visible",
                "some_keyword": "should be removed",  # contains 'key'
            })
            log_file = config_dir / "logs" / "neurocad-audit.log"
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            entry = json.loads(lines[0])
            data = entry["data"]
            assert "api_key" not in data
            assert "auth_token" not in data
            assert "secret_password" not in data
            assert "some_keyword" not in data
            assert data["safe_field"] == "visible"
            # Cleanup
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_preview_and_object_name_caps_applied():
    """Preview and new_object_names fields are automatically capped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": True})
            long_preview = "x" * (AUDIT_LOG_MAX_PREVIEW_CHARS + 20)
            many_names = [f"obj{i}" for i in range(AUDIT_LOG_MAX_OBJECT_NAMES + 7)]
            audit_log("test_caps", {
                "preview": long_preview,
                "new_object_names": many_names,
                "other_field": "unchanged",
            })
            log_file = config_dir / "logs" / "neurocad-audit.log"
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            entry = json.loads(lines[0])
            data = entry["data"]
            # Preview capped
            assert len(data["preview"]) == AUDIT_LOG_MAX_PREVIEW_CHARS + 3
            assert data["preview"].endswith("...")
            # Object names capped
            assert len(data["new_object_names"]) == AUDIT_LOG_MAX_OBJECT_NAMES + 1
            assert data["new_object_names"][-1] == f"... and 7 more"
            assert data["other_field"] == "unchanged"
            # Cleanup
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_correlation_id_consistent_within_session():
    """All entries in the same session share the same correlation ID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": True})
            cid = get_correlation_id()
            assert cid is not None
            audit_log("event1", {"step": 1})
            audit_log("event2", {"step": 2})
            log_file = config_dir / "logs" / "neurocad-audit.log"
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            for line in lines:
                entry = json.loads(line)
                assert entry["correlation_id"] == cid
            # Cleanup
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_correlation_id_override():
    """Explicit correlation_id parameter overrides the session‑wide one."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / "config"
        config_dir.mkdir()
        with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
            init_audit_log({"audit_log_enabled": True})
            session_cid = get_correlation_id()
            custom_cid = "custom-123"
            audit_log("test_override", {"foo": "bar"}, correlation_id=custom_cid)
            log_file = config_dir / "logs" / "neurocad-audit.log"
            lines = log_file.read_text(encoding="utf-8").strip().splitlines()
            entry = json.loads(lines[0])
            assert entry["correlation_id"] == custom_cid
            assert entry["correlation_id"] != session_cid
            # Cleanup
            import neurocad.core.audit
            neurocad.core.audit._AUDIT_LOGGER = None
            neurocad.core.audit._AUDIT_ENABLED = False


def test_rotation_mocked():
    """RotatingFileHandler is configured with expected parameters."""
    mock_handler = MagicMock()
    with patch("logging.handlers.RotatingFileHandler", mock_handler):
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            log_file = config_dir / "logs" / "neurocad-audit.log"
            with patch("neurocad.core.audit._get_config_dir", return_value=config_dir):
                init_audit_log({"audit_log_enabled": True})
                # Verify RotatingFileHandler was instantiated with correct args
                mock_handler.assert_called_once()
                args, kwargs = mock_handler.call_args
                # filename is a keyword argument
                assert kwargs.get("filename") == log_file
                assert kwargs.get("maxBytes") == 5 * 1024 * 1024  # 5 MiB
                assert kwargs.get("backupCount") == 5
                assert kwargs.get("encoding") == "utf-8"
                # Cleanup
                import neurocad.core.audit
                neurocad.core.audit._AUDIT_LOGGER = None
                neurocad.core.audit._AUDIT_ENABLED = False


def test_adapter_init_failure_audited(monkeypatch, qapp):
    """When adapter initialization fails, an audit entry is recorded."""
    # Mock audit_log to capture calls
    mock_audit = MagicMock()
    monkeypatch.setattr("neurocad.core.audit.audit_log", mock_audit)
    # Simulate audit enabled
    monkeypatch.setattr("neurocad.core.audit._AUDIT_ENABLED", True)
    monkeypatch.setattr("neurocad.core.audit._AUDIT_LOGGER", MagicMock())

    # Import panel after monkeypatching
    from neurocad.ui.panel import CopilotPanel
    # Mock load_config to return a config with audit enabled
    mock_config = {"audit_log_enabled": True, "provider": "openai"}
    monkeypatch.setattr("neurocad.ui.panel.load_config", lambda: mock_config)
    # Mock load_adapter to raise an exception
    monkeypatch.setattr(
        "neurocad.ui.panel.load_adapter",
        MagicMock(side_effect=ValueError("No API key found")),
    )
    # Mock init_audit_log to not interfere
    monkeypatch.setattr("neurocad.ui.panel.init_audit_log", lambda cfg: None)
    # Mock log_warn to avoid side effects
    monkeypatch.setattr("neurocad.ui.panel.log_warn", MagicMock())
    # Mock UI-building methods to avoid Qt widget creation
    monkeypatch.setattr(CopilotPanel, "_build_ui", lambda self: None)
    monkeypatch.setattr(CopilotPanel, "_connect_signals", lambda self: None)
    # Mock _update_status_for_adapter to avoid accessing missing UI widgets
    monkeypatch.setattr(CopilotPanel, "_update_status_for_adapter", lambda self: None)

    # Create panel (will call _init_adapter)
    panel = CopilotPanel(None)  # parent=None for test, qapp exists
    # Verify audit_log was called with expected event_type
    mock_audit.assert_called_once()
    call_args = mock_audit.call_args
    assert call_args[0][0] == "adapter_init_failure"
    data = call_args[0][1]
    assert "error" in data
    assert "No API key found" in data["error"]
    # Ensure no secrets are logged
    assert "api_key" not in data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])