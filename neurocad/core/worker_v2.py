"""LLM worker thread for the plan-driven agent v2 (Sprint 6.0+).

Parallel to `worker.LLMWorker` but routes typed `Message` objects through
the UI dispatcher AND adds a blocking `on_question` handoff so the LLM
can pause for user input mid-flow.

All UI callbacks are scheduled on the Qt main thread via the same
`_MainThreadDispatcher` pattern as v1. The question dispatch is the only
new wrinkle: worker thread parks on `threading.Event`, UI thread shows
the question, user answers via `receive_answer(text)`, event is set.
"""

from __future__ import annotations

import threading
from collections.abc import Callable

from ..ui.compat import QtCore, Signal, Slot
from .agent_v2 import AgentV2Callbacks
from .agent_v2 import run as agent_v2_run
from .debug import log_error, log_info, log_warn
from .history import History
from .message import Message, MessageKind


class _MainThreadDispatcher(QtCore.QObject):
    invoke = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.invoke.connect(self._invoke, QtCore.Qt.QueuedConnection)

    @Slot(object, object)
    def _invoke(self, callback, args):
        callback(*args)


class LLMWorkerV2:
    """Plan-driven worker. UI must implement:
        on_message(Message)     — typed-message dispatch (PLAN/COMMENT/.../VERIFY)
        on_status(str)          — phase / status line
        on_attempt(int, int)    — current attempt / max
        on_exec_needed(code, step) → dict[ok, new_objects, error]
        on_question_request(msg) — UI presents the question; UI calls
                                    receive_answer(text) when user answers
                                    OR receive_answer(None) on cancel.
        on_done(AgentV2Result)
        on_error(str)
    """

    def __init__(
        self,
        on_message: Callable[[Message], None],
        on_status: Callable[[str], None],
        on_attempt: Callable[[int, int], None],
        on_exec_needed: Callable[[str, int], dict],
        on_question_request: Callable[[Message], None],
        on_verify_request: Callable[[dict, int], None],
        on_done: Callable[[object], None],
        on_error: Callable[[str], None],
    ):
        self._on_message = on_message
        self._on_status = on_status
        self._on_attempt = on_attempt
        self._on_exec_needed = on_exec_needed
        self._on_question_request = on_question_request
        self._on_verify_request = on_verify_request
        self._on_done = on_done
        self._on_error = on_error

        self._thread: threading.Thread | None = None
        self._cancelled = threading.Event()
        # exec handoff
        self._exec_event = threading.Event()
        self._exec_result: dict | None = None
        # question handoff
        self._answer_event = threading.Event()
        self._answer_text: str | None = None
        # verify handoff (Sprint 6.0+ hotfix: FreeCAD APIs are NOT thread-safe,
        # contract_verifier must run on the main thread).
        self._verify_event = threading.Event()
        self._verify_result: dict | None = None
        self._running = False
        self._dispatcher = _MainThreadDispatcher()

    def start(self, text: str, doc, adapter, history: History):
        if self._running:
            log_warn("worker_v2.start", "ignored: already running")
            return
        self._cancelled.clear()
        self._exec_event.clear()
        self._answer_event.clear()
        self._exec_result = None
        self._answer_text = None
        self._running = True
        log_info("worker_v2.start", "spawning v2 worker",
                 document=getattr(doc, "Name", None),
                 adapter_type=type(adapter).__name__)
        self._thread = threading.Thread(
            target=self._run, args=(text, doc, adapter, history),
            daemon=True, name="NeuroCad-LLMWorkerV2",
        )
        self._thread.start()

    def cancel(self):
        log_warn("worker_v2.cancel", "cancellation requested")
        self._cancelled.set()
        self._exec_event.set()
        self._answer_event.set()           # unblock any pending question
        self._verify_event.set()           # unblock any pending verifier
        self._running = False

    def is_running(self) -> bool:
        return self._running and self._thread is not None and self._thread.is_alive()

    # ------- exec handoff (same as v1) -------------------------------------

    def receive_exec_result(self, result: dict):
        log_info("worker_v2.exec_result", "received",
                 ok=result.get("ok"), error=result.get("error"))
        self._exec_result = result
        self._exec_event.set()

    def _schedule_main(self, callback, *args):
        self._dispatcher.invoke.emit(callback, args)

    def _request_exec(self, code: str, step_idx: int) -> dict:
        if self._cancelled.is_set():
            return {"ok": False, "new_objects": [], "error": "Cancelled"}
        self._exec_event.clear()
        self._schedule_main(self._on_exec_needed, code, step_idx)
        if not self._exec_event.wait(timeout=180.0):
            return {"ok": False, "new_objects": [],
                    "error": "Execution handoff timeout"}
        if self._cancelled.is_set():
            return {"ok": False, "new_objects": [], "error": "Cancelled"}
        return self._exec_result or {"ok": False, "new_objects": [],
                                      "error": "No result"}

    # ------- question handoff (new in v2) ----------------------------------

    def receive_answer(self, text: str | None):
        """UI calls this when the user has answered (or cancelled with None)."""
        log_info("worker_v2.answer",
                 "received user answer",
                 has_text=text is not None,
                 preview=(text or "")[:80])
        self._answer_text = text
        self._answer_event.set()

    # ------- verify handoff (Sprint 6.0+ thread-safety hotfix) -------------

    def receive_verify_result(self, result: dict):
        """UI calls this with the contract_verifier report (main thread)."""
        log_info("worker_v2.verify_result", "received",
                 ok=result.get("ok"),
                 n_failures=len(result.get("failures") or []))
        self._verify_result = result
        self._verify_event.set()

    def _request_verify_step(self, intent_dict: dict, step_idx: int) -> dict:
        """Run contract_verifier ON THE MAIN THREAD (FreeCAD APIs are not
        thread-safe). Worker parks on `_verify_event` while the UI thread
        does the geometry queries."""
        if self._cancelled.is_set():
            return {"ok": False, "failures": [{"part": "<cancel>",
                                                 "feature": "<cancel>",
                                                 "reason": "cancelled"}]}
        self._verify_event.clear()
        self._verify_result = None
        self._schedule_main(self._on_verify_request, intent_dict, step_idx)
        if not self._verify_event.wait(timeout=120.0):
            log_error("worker_v2.verify",
                      "timed out waiting for main-thread verify result")
            return {"ok": False,
                    "failures": [{"part": "<verify>", "feature": "<timeout>",
                                   "reason": "verify handoff timeout"}]}
        if self._cancelled.is_set():
            return {"ok": False,
                    "failures": [{"part": "<cancel>", "feature": "<cancel>",
                                   "reason": "cancelled"}]}
        return self._verify_result or {
            "ok": False,
            "failures": [{"part": "<verify>", "feature": "<no result>",
                           "reason": "verify returned no result"}],
        }

    def _request_question(self, q_msg: Message) -> str | None:
        if self._cancelled.is_set():
            return None
        self._answer_event.clear()
        self._answer_text = None
        self._schedule_main(self._on_question_request, q_msg)
        # 10-minute safety timeout so a forgotten dialog never hangs the
        # worker forever. The Stop button (which sets _cancelled +
        # _answer_event) still pre-empts this.
        if not self._answer_event.wait(timeout=600.0):
            log_warn("worker_v2.question", "timed out waiting for user answer")
            return None
        if self._cancelled.is_set():
            return None
        return self._answer_text

    # ------- main loop ------------------------------------------------------

    def _run(self, text: str, doc, adapter, history: History):
        try:
            log_info("worker_v2.run", "loop started", text=text)
            callbacks = AgentV2Callbacks(
                on_message=lambda m: self._schedule_main(self._on_message, m),
                on_status=lambda s: self._schedule_main(self._on_status, s),
                on_attempt=lambda n, mx: self._schedule_main(self._on_attempt, n, mx),
                on_exec_needed=self._request_exec,
                on_question=self._request_question,
                on_verify_step=self._request_verify_step,
            )
            result = agent_v2_run(text, doc, adapter, history, callbacks)
            if self._cancelled.is_set():
                log_warn("worker_v2.run", "cancelled before completion")
                return
            log_info("worker_v2.run", "agent_v2 returned",
                     ok=result.ok, n_steps=len(result.steps))
            self._schedule_main(self._on_done, result)
        except Exception as exc:  # noqa: BLE001
            if not self._cancelled.is_set():
                log_error("worker_v2.run", "unhandled exception", error=str(exc))
                self._schedule_main(self._on_error, str(exc))
        finally:
            log_info("worker_v2.run", "loop ended")
            self._running = False
