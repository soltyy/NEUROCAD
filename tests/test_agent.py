"""Tests for agent.py."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.core.agent import (
    AgentCallbacks,
    _execute_with_rollback,
    run,
)
from neurocad.core.executor import ExecResult
from neurocad.core.history import History


def test_execute_with_rollback_success():
    """_execute_with_rollback commits transaction on success."""
    mock_doc = MagicMock()
    mock_doc.getObject.return_value = MagicMock()
    with patch("neurocad.core.agent.execute") as mock_execute:
        mock_execute.return_value = ExecResult(
            ok=True,
            new_objects=["Box"],
        )
        with patch("neurocad.core.agent.validate") as mock_validate:
            mock_validate.return_value.ok = True
            result = _execute_with_rollback("code", mock_doc)
            assert result.ok is True
            mock_doc.openTransaction.assert_called_once_with("NeuroCad")
            mock_doc.commitTransaction.assert_called_once()
            mock_doc.abortTransaction.assert_not_called()


def test_execute_with_rollback_exec_failure():
    """_execute_with_rollback aborts on execution failure."""
    mock_doc = MagicMock()
    with patch("neurocad.core.agent.execute") as mock_execute:
        mock_execute.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="Execution failed",
        )
        result = _execute_with_rollback("code", mock_doc)
        assert result.ok is False
        mock_doc.abortTransaction.assert_called_once()


def test_execute_with_rollback_validation_failure():
    """_execute_with_rollback aborts when validation fails."""
    mock_doc = MagicMock()
    mock_obj = MagicMock()
    mock_doc.getObject.return_value = mock_obj
    with patch("neurocad.core.agent.execute") as mock_execute:
        mock_execute.return_value = ExecResult(
            ok=True,
            new_objects=["Box"],
        )
        with patch("neurocad.core.agent.validate") as mock_validate:
            mock_validate.return_value.ok = False
            mock_validate.return_value.error = "Shape invalid"
            result = _execute_with_rollback("code", mock_doc)
            assert result.ok is False
            mock_doc.abortTransaction.assert_called_once()


def test_agent_callbacks_default():
    """Default callbacks do nothing."""
    cb = AgentCallbacks()
    cb.on_chunk("test")
    cb.on_attempt(1, 3)
    result = cb.on_exec_needed("code", 1)
    assert result["ok"] is False


@patch("neurocad.core.context.capture")
@patch("neurocad.core.agent.build_system")
@patch("neurocad.core.agent.extract_code")
def test_run_success_without_callbacks(
    mock_extract, mock_build_system, mock_capture
):
    """run succeeds when LLM returns valid code and execution passes."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nPart.makeBox(10,10,10)\n```"
    mock_extract.return_value = "Part.makeBox(10,10,10)"
    mock_build_system.return_value = "system"
    mock_capture.return_value = MagicMock()

    history = History()

    with patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_exec.return_value = ExecResult(ok=True, new_objects=["Box"])
        result = run("make a box", mock_doc, mock_adapter, history, callbacks=None)

        assert result.ok is True
        assert result.attempts == 1
        assert "Box" in result.new_objects
        mock_adapter.complete.assert_called_once()
        mock_exec.assert_called_once()


@patch("neurocad.core.context.capture")
@patch("neurocad.core.agent.build_system")
def test_run_retry_on_failure(mock_build_system, mock_capture):
    """run retries up to MAX_RETRIES."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "code"
    mock_build_system.return_value = "system"
    mock_capture.return_value = MagicMock()

    history = History()

    with patch("neurocad.core.agent.extract_code", return_value="code"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
            mock_exec.return_value = ExecResult(
                ok=False,
                new_objects=[],
                error="Execution failed",
            )
            result = run("make a box", mock_doc, mock_adapter, history, callbacks=None)

            assert result.ok is False
            assert result.attempts == 3
            assert "Max retries" in result.error
            assert mock_exec.call_count == 3


def test_run_no_code_generated():
    """run returns error when extracted code is empty."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "No code here"
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code", return_value=""):
            result = run("prompt", mock_doc, mock_adapter, history)
            assert result.ok is False
            assert "No code generated" in result.error


def test_run_llm_error_fails_fast():
    """LLM transport errors should fail fast instead of consuming all retries."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.side_effect = RuntimeError("network timeout")
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"):
        result = run("prompt", mock_doc, mock_adapter, history)

    assert result.ok is False
    assert result.attempts == 1
    assert "LLM error" in result.error


def test_run_llm_timeout_fails_fast():
    """A hung adapter.complete() call should fail fast with a timeout error."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    history = History()

    def _hang(*args, **kwargs):
        import time

        time.sleep(0.2)
        return MagicMock(content="late")

    mock_adapter.complete.side_effect = _hang

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"), \
         patch(
             "neurocad.core.agent._complete_with_timeout",
             side_effect=TimeoutError("LLM request timed out after 12s"),
         ):
        result = run("prompt", mock_doc, mock_adapter, history)

    assert result.ok is False
    assert result.attempts == 1
    assert "timed out" in result.error


@patch("neurocad.core.context.capture")
@patch("neurocad.core.agent.build_system")
@patch("neurocad.core.agent.extract_code")
def test_run_with_callbacks_uses_complete_not_stream(
    mock_extract, mock_build_system, mock_capture
):
    """Sprint 2 path should use complete() even when callbacks are provided."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nprint('ok')\n```"
    mock_extract.return_value = "print('ok')"
    mock_build_system.return_value = "system"
    mock_capture.return_value = MagicMock()
    history = History()
    callbacks = AgentCallbacks(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_exec_needed=MagicMock(return_value={"ok": True, "new_objects": ["Box"], "error": None}),
    )

    result = run("make a box", mock_doc, mock_adapter, history, callbacks=callbacks)

    assert result.ok is True
    mock_adapter.complete.assert_called_once()
    mock_adapter.stream.assert_not_called()
    callbacks.on_chunk.assert_called_once()


def test_build_system_includes_snapshot():
    """build_system should incorporate document snapshot."""
    from unittest.mock import patch

    from neurocad.core.context import DocSnapshot
    from neurocad.core.prompt import build_system
    mock_snap = DocSnapshot(filename="test", objects=[])
    with patch("neurocad.core.prompt.to_prompt_str") as mock_to_prompt:
        mock_to_prompt.return_value = "Snapshot description"
        result = build_system(mock_snap)
        mock_to_prompt.assert_called_once_with(mock_snap, max_chars=1000)
        assert "Snapshot description" in result
        assert "Supported Part primitives" in result


def test_error_categorization():
    """_categorize_error should classify unsupported API errors."""
    from neurocad.core.agent import _categorize_error
    # blocked token
    assert _categorize_error("Blocked token 'import' found at line 1") == "blocked_token"
    # unsupported API
    err = "module 'Part' has no attribute 'makeGear'"
    assert _categorize_error(err) == "unsupported_api"
    err2 = "AttributeError: module 'Part' has no attribute 'makeInvoluteGear'"
    assert _categorize_error(err2) == "unsupported_api"
    # validation
    assert _categorize_error("Validation failed for Box: Shape invalid") == "validation"
    # timeout
    assert _categorize_error("Execution timed out") == "timeout"
    # llm transport (should be caught earlier)
    assert _categorize_error("LLM error: network") == "llm_transport"
    # runtime default
    assert _categorize_error("Some random error") == "runtime"


def test_make_feedback():
    """_make_feedback returns user-friendly messages."""
    from neurocad.core.agent import _make_feedback
    assert "forbidden tokens" in _make_feedback("", "blocked_token")
    assert "Unsupported FreeCAD API" in _make_feedback("", "unsupported_api")
    assert "Validation failed" in _make_feedback("error", "validation")
    assert "Execution timed out" in _make_feedback("", "timeout")
    assert "LLM error" in _make_feedback("error", "llm_transport")
    assert "Execution failed" in _make_feedback("error", "runtime")


def test_run_non_retriable_errors():
    """blocked_token and unsupported_api errors stop after first attempt."""
    from unittest.mock import MagicMock, patch

    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "code"
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code", return_value="code"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
                # Test blocked token error
                mock_exec.return_value = ExecResult(
                    ok=False,
                    new_objects=[],
                    error="Blocked token 'import' found at line 1",
                )
                result = run("make a box", mock_doc, mock_adapter, history)
                assert result.ok is False
                assert result.attempts == 1
                assert "forbidden tokens" in result.error
                assert mock_exec.call_count == 1
                # Reset for unsupported API error
                mock_exec.reset_mock()
                mock_exec.return_value = ExecResult(
                    ok=False,
                    new_objects=[],
                    error="module 'Part' has no attribute 'makeGear'",
                )
                history.clear()
                result2 = run("make a gear", mock_doc, mock_adapter, history)
                assert result2.ok is False
                assert result2.attempts == 1
                assert "Unsupported FreeCAD API" in result2.error
                assert mock_exec.call_count == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
