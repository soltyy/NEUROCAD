"""LLM worker thread (runs LLM I/O outside the main thread)."""

import threading
from collections.abc import Callable

from ..ui.compat import QtCore, Signal, Slot
from .agent import AgentCallbacks
from .agent import run as agent_run
from .debug import log_error, log_info, log_warn
from .history import History


class _MainThreadDispatcher(QtCore.QObject):
    """Dispatch arbitrary callbacks onto the Qt main thread."""

    invoke = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._invoke, QtCore.Qt.QueuedConnection)

    @Slot(object, object)
    def _invoke(self, callback, args):
        callback(*args)


class LLMWorker:
    """Worker that runs LLM inference in a background thread.

    All UI callbacks are scheduled via a queued-signal dispatcher
    (_MainThreadDispatcher) to run in the main thread.
    Execution results are handed off via threading.Event.
    """

    def __init__(
        self,
        on_chunk: Callable[[str], None],
        on_attempt: Callable[[int, int], None],
        on_status: Callable[[str], None],
        on_exec_needed: Callable[[str, int], dict],
        on_done: Callable[[object], None],
        on_error: Callable[[str], None],
    ):
        self._on_chunk = on_chunk
        self._on_attempt = on_attempt
        self._on_status = on_status
        self._on_exec_needed = on_exec_needed
        self._on_done = on_done
        self._on_error = on_error

        self._thread: threading.Thread | None = None
        self._cancelled = threading.Event()
        self._exec_event = threading.Event()
        self._exec_result: dict | None = None
        self._running = False
        self._dispatcher = _MainThreadDispatcher()

    def start(self, text: str, doc, adapter, history: History):
        """Start the worker thread."""
        if self._running:
            log_warn("worker.start", "ignored: worker already running")
            return
        self._cancelled.clear()
        self._exec_event.clear()
        self._exec_result = None
        self._running = True
        log_info(
            "worker.start",
            "spawning background worker",
            document=getattr(doc, "Name", None),
            adapter_type=type(adapter).__name__,
        )
        self._thread = threading.Thread(
            target=self._run,
            args=(text, doc, adapter, history),
            daemon=True,
            name="NeuroCad-LLMWorker",
        )
        self._thread.start()

    def cancel(self):
        """Cancel the ongoing work."""
        log_warn("worker.cancel", "cancellation requested")
        self._cancelled.set()
        self._exec_event.set()  # unblock any waiting execution
        self._running = False

    def is_running(self) -> bool:
        """Return True if the worker thread is alive."""
        return self._running and self._thread is not None and self._thread.is_alive()

    def receive_exec_result(self, result: dict):
        """Provide execution result from the main thread."""
        log_info(
            "worker.exec_result",
            "received execution result",
            ok=result.get("ok"),
            error=result.get("error"),
            new_objects=result.get("new_objects"),
        )
        self._exec_result = result
        self._exec_event.set()

    def _schedule_main(self, callback, *args):
        """Schedule a callback to run in the main thread."""
        self._dispatcher.invoke.emit(callback, args)

    def _run(self, text: str, doc, adapter, history: History):
        """Main worker loop."""
        try:
            log_info("worker.run", "worker loop started", text=text)
            callbacks = AgentCallbacks(
                on_chunk=lambda chunk: self._schedule_main(self._on_chunk, chunk),
                on_attempt=lambda n, mx: self._schedule_main(self._on_attempt, n, mx),
                on_status=lambda msg: self._schedule_main(self._on_status, msg),
                on_exec_needed=self._request_exec,
            )
            result = agent_run(text, doc, adapter, history, callbacks)
            if self._cancelled.is_set():
                log_warn("worker.run", "worker cancelled before completion")
                return
            log_info(
                "worker.run",
                "agent returned",
                ok=result.ok,
                attempts=result.attempts,
                error=result.error,
            )
            self._schedule_main(self._on_done, result)
        except Exception as e:
            if not self._cancelled.is_set():
                log_error("worker.run", "unhandled worker exception", error=e)
                self._schedule_main(self._on_error, str(e))
        finally:
            log_info("worker.run", "worker loop ended")
            self._running = False

    def _request_exec(self, code: str, attempt: int) -> dict:
        """Request execution in the main thread and wait for the result."""
        if self._cancelled.is_set():
            log_warn("worker.exec", "cancelled before exec request")
            return {"ok": False, "new_objects": [], "error": "Cancelled"}
        self._exec_event.clear()
        log_info(
            "worker.exec",
            "dispatching exec to main thread",
            attempt=attempt,
            code_preview=code[:200],
        )
        self._schedule_main(self._on_exec_needed, code, attempt)
        if not self._exec_event.wait(timeout=15.0):
            log_error("worker.exec", "timed out waiting for main-thread exec result")
            return {"ok": False, "new_objects": [], "error": "Execution handoff timeout"}
        if self._cancelled.is_set():
            log_warn("worker.exec", "cancelled while waiting for exec result")
            return {"ok": False, "new_objects": [], "error": "Cancelled"}
        log_info("worker.exec", "returning exec result to agent")
        return self._exec_result or {"ok": False, "new_objects": [], "error": "No result"}
