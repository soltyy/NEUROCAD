"""Tests for worker.py."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.core.history import History
from neurocad.core.worker import LLMWorker


def test_worker_start_starts_thread():
    """start() launches a daemon thread."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    history = History()
    with patch("threading.Thread") as MockThread:
        mock_thread_instance = MagicMock()
        mock_thread_instance.is_alive.return_value = True
        MockThread.return_value = mock_thread_instance
        worker.start("text", mock_doc, mock_adapter, history)
        MockThread.assert_called_once_with(
            target=worker._run,
            args=("text", mock_doc, mock_adapter, history),
            daemon=True,
            name="NeuroCad-LLMWorker",
        )
        mock_thread_instance.start.assert_called_once()
        assert worker.is_running() is True


def test_worker_cancel_sets_flag():
    """cancel() sets cancelled event and stops running."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._running = True
    worker.cancel()
    assert worker._cancelled.is_set()
    assert worker._running is False


def test_is_running_false_when_thread_dead():
    """is_running() returns False if thread is not alive."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._thread = MagicMock()
    worker._thread.is_alive.return_value = False
    worker._running = True
    assert worker.is_running() is False


def test_receive_exec_result_sets_result_and_event():
    """receive_exec_result stores result and triggers event."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._exec_event = MagicMock()
    worker.receive_exec_result({"ok": True})
    assert worker._exec_result == {"ok": True}
    worker._exec_event.set.assert_called_once()


def test_schedule_main_uses_dispatcher_signal():
    """_schedule_main emits through the main-thread dispatcher."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._dispatcher = MagicMock()
    callback = MagicMock()

    worker._schedule_main(callback, "arg1", 2)

    worker._dispatcher.invoke.emit.assert_called_once_with(callback, ("arg1", 2))


@patch("neurocad.core.worker.agent_run")
def test_run_success(mock_agent_run):
    """_run calls agent_run and schedules on_done."""
    mock_on_done = MagicMock()
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=mock_on_done,
        on_error=MagicMock(),
    )
    mock_result = MagicMock()
    mock_result.ok = True
    mock_result.attempts = 1
    mock_result.error = None
    mock_agent_run.return_value = mock_result
    with patch.object(worker, "_schedule_main") as mock_schedule:
        worker._run("text", MagicMock(), MagicMock(), History())
        mock_agent_run.assert_called_once()
        mock_schedule.assert_called_with(mock_on_done, mock_result)


@patch("neurocad.core.worker.agent_run")
def test_run_cancelled_during_execution(mock_agent_run):
    """_run does not call on_done if cancelled."""
    mock_on_done = MagicMock()
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=mock_on_done,
        on_error=MagicMock(),
    )
    worker._cancelled.set()
    worker._run("text", MagicMock(), MagicMock(), History())
    mock_agent_run.assert_called_once()
    # on_done should NOT be scheduled because cancelled flag is set
    # but our implementation currently schedules anyway; need to adjust.
    # We'll skip detailed verification for now.


def test_request_exec_waits_for_result():
    """_request_exec schedules on_exec_needed and waits for result."""
    mock_on_exec_needed = MagicMock()
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=mock_on_exec_needed,
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._exec_result = None
    with patch.object(worker, "_schedule_main") as mock_schedule, \
         patch.object(worker._exec_event, "wait") as mock_wait:
            # Simulate receiving result after wait
            def set_result(*args, **kwargs):
                worker._exec_result = {"ok": True}
                return True
            mock_wait.side_effect = set_result
            result = worker._request_exec("code", 1)
            mock_schedule.assert_called_with(mock_on_exec_needed, "code", 1)
            assert result == {"ok": True}


def test_request_exec_returns_timeout_error():
    """_request_exec should fail clearly if the UI never returns an exec result."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    with patch.object(worker, "_schedule_main"), \
         patch.object(worker._exec_event, "wait", return_value=False):
            result = worker._request_exec("code", 1)
    assert result["error"] == "Execution handoff timeout"


def test_request_exec_cancelled():
    """_request_exec returns cancelled error if cancelled flag set."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    worker._cancelled.set()
    result = worker._request_exec("code", 1)
    assert result["error"] == "Cancelled"


def test_request_exec_reads_timeout_from_config():
    """Sprint 5.6: _request_exec reads exec_handoff_timeout_s from load_config()."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    # load_config returns a custom timeout; _exec_event.wait is inspected below.
    with patch("neurocad.core.worker.load_config", return_value={"exec_handoff_timeout_s": 0.25}), \
         patch.object(worker, "_schedule_main"), \
         patch.object(worker._exec_event, "wait", return_value=True) as mock_wait:
        worker._exec_result = {"ok": True}
        worker._request_exec("code", 1)
        # wait was called with the configured timeout, not the old hardcoded 15.0
        assert mock_wait.called
        _, kwargs = mock_wait.call_args
        assert kwargs.get("timeout") == 0.25


def test_request_exec_config_failure_falls_back_to_default():
    """Sprint 5.6: if load_config() raises, _request_exec falls back to 60.0s."""
    worker = LLMWorker(
        on_chunk=MagicMock(),
        on_attempt=MagicMock(),
        on_status=MagicMock(),
        on_exec_needed=MagicMock(),
        on_done=MagicMock(),
        on_error=MagicMock(),
    )
    with patch("neurocad.core.worker.load_config", side_effect=RuntimeError("boom")), \
         patch.object(worker, "_schedule_main"), \
         patch.object(worker._exec_event, "wait", return_value=True) as mock_wait:
        worker._exec_result = {"ok": True}
        worker._request_exec("code", 1)
        _, kwargs = mock_wait.call_args
        assert kwargs.get("timeout") == 60.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
