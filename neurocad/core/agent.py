"""Agent orchestrates LLM, execution, validation, and rollback."""

import threading
from collections.abc import Callable
from dataclasses import dataclass

from .code_extractor import extract_code
from .debug import log_error, log_info, log_warn
from .executor import ExecResult, execute
from .history import History, Role
from .prompt import build_system
from .validator import validate


@dataclass
class AgentCallbacks:
    """Callbacks for agent events."""
    on_chunk: Callable[[str], None] = lambda _: None
    on_attempt: Callable[[int, int], None] = lambda _, __: None
    on_status: Callable[[str], None] = lambda _: None
    on_exec_needed: Callable[[str, int], dict] = lambda _, __: {"ok": False, "new_objects": []}


@dataclass
class AgentResult:
    """Result of an agent run."""
    ok: bool
    attempts: int
    error: str | None = None
    new_objects: list[str] | None = None
    rollback_count: int = 0

    def __post_init__(self):
        if self.new_objects is None:
            self.new_objects = []


def _categorize_error(error: str) -> str:
    """Return normalized error category."""
    if error is None:
        return "runtime"
    error_lower = error.lower()
    if "blocked token" in error_lower:
        return "blocked_token"
    if "module 'part' has no attribute" in error_lower or "has no attribute 'make" in error_lower:
        return "unsupported_api"
    if "validation failed" in error_lower:
        return "validation"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "llm error" in error_lower or "adapter call failed" in error_lower:
        return "llm_transport"
    return "runtime"


def _make_feedback(error: str, category: str) -> str:
    """Return a concise user-facing feedback message."""
    if category == "blocked_token":
        return "The code contains forbidden tokens (e.g., import, FreeCADGui). Remove them."
    if category == "unsupported_api":
        return (
            "Unsupported FreeCAD API used. Use only supported primitives: "
            "makeBox, makeCylinder, makeSphere, makeCone."
        )
    if category == "validation":
        return f"Validation failed: {error}"
    if category == "timeout":
        return "Execution timed out."
    if category == "llm_transport":
        return f"LLM error: {error}"
    # default
    return f"Execution failed: {error}"


def _complete_with_timeout(adapter, messages, system: str, timeout_s: float = 12.0):
    """Run adapter.complete() with a hard timeout guard."""
    payload: dict[str, object] = {"response": None, "error": None}

    def _target():
        try:
            payload["response"] = adapter.complete(messages, system=system)
        except Exception as exc:  # pragma: no cover - exercised through caller
            payload["error"] = exc

    thread = threading.Thread(target=_target, daemon=True, name="NeuroCad-LLMCall")
    thread.start()
    thread.join(timeout=timeout_s)
    if thread.is_alive():
        raise TimeoutError(f"LLM request timed out after {timeout_s:.0f}s")
    if payload["error"] is not None:
        raise payload["error"]  # type: ignore[misc]
    return payload["response"]


def _execute_with_rollback(code: str, doc) -> ExecResult:
    """Execute code inside a FreeCAD transaction named 'NeuroCad'.

    Rolls back the transaction if execution fails or geometry is invalid.
    """
    log_info("agent.exec", "opening FreeCAD transaction", document=getattr(doc, "Name", None))
    doc.openTransaction("NeuroCad")  # type: ignore
    try:
        result = execute(code, doc)
        if not result.ok:
            log_warn("agent.exec", "execution failed, aborting transaction", error=result.error)
            doc.abortTransaction()  # type: ignore
            # Increment rollback count because transaction was aborted
            return ExecResult(
                ok=False,
                new_objects=result.new_objects,
                error=result.error,
                rollback_count=result.rollback_count + 1
            )

        # Validate each new object
        for obj_name in result.new_objects:
            obj = doc.getObject(obj_name)
            if obj is None:
                continue
            validation = validate(obj)
            if not validation.ok:
                log_warn(
                    "agent.exec",
                    "validation failed, aborting transaction",
                    object_name=obj_name,
                    error=validation.error,
                )
                doc.abortTransaction()  # type: ignore
                return ExecResult(
                    ok=False,
                    new_objects=[],
                    error=f"Validation failed for {obj_name}: {validation.error}",
                    rollback_count=1
                )

        # Everything OK – commit
        log_info(
            "agent.exec",
            "execution and validation succeeded, committing transaction",
            new_objects=result.new_objects,
        )
        doc.commitTransaction()  # type: ignore
        return result
    except Exception as e:
        log_error(
            "agent.exec",
            "unexpected exception during execution, aborting transaction",
            error=e,
        )
        doc.abortTransaction()  # type: ignore
        return ExecResult(ok=False, new_objects=[], error=f"Unexpected error: {e}")


def run(
    text: str,
    doc,
    adapter,
    history: History,
    callbacks: AgentCallbacks | None = None,
) -> AgentResult:
    """Run the agent loop: LLM → code extraction → execution → validation.

    If callbacks is None, the agent runs synchronously (no streaming).
    Otherwise, callbacks are invoked as appropriate.
    """
    use_callbacks = callbacks is not None
    if callbacks is None:
        callbacks = AgentCallbacks()

    # Add user message to history
    history.add(Role.USER, text)
    log_info("agent.run", "history updated with user prompt", text=text)
    callbacks.on_status("history updated")

    # Build system prompt from document snapshot
    from .context import capture
    snap = capture(doc)
    system = build_system(snap)
    log_info(
        "agent.run",
        "system prompt built",
        system_chars=len(system),
        object_count=len(snap.objects),
    )
    callbacks.on_status(f"system prompt ready, objects={len(snap.objects)}")

    MAX_RETRIES = 3
    attempts = 0
    last_error = None
    total_rollback_count = 0

    while attempts < MAX_RETRIES:
        attempts += 1
        log_info("agent.run", "starting attempt", attempt=attempts, max_retries=MAX_RETRIES)
        callbacks.on_attempt(attempts, MAX_RETRIES)
        callbacks.on_status(f"attempt {attempts}/{MAX_RETRIES}")

        # Get LLM response
        try:
            messages = history.to_llm_messages()
            log_info(
                "agent.run",
                "sending request to adapter.complete",
                message_count=len(messages),
                provider=type(adapter).__name__,
            )
            callbacks.on_status("sending request to LLM")
            # Sprint 2 uses a single complete() call. Streaming is deferred.
            response = _complete_with_timeout(adapter, messages, system=system)
            llm_text = response.content
            log_info(
                "agent.run",
                "received LLM response",
                chars=len(llm_text),
                stop_reason=response.stop_reason,
                output_tokens=response.output_tokens,
            )
            callbacks.on_status(f"LLM response received, chars={len(llm_text)}")
            if use_callbacks:
                callbacks.on_chunk(llm_text)
        except Exception as e:
            log_error("agent.run", "adapter call failed", error=e)
            callbacks.on_status(f"LLM call failed: {e}")
            return AgentResult(
                ok=False,
                attempts=attempts,
                error=f"LLM error: {e}",
                new_objects=[],
                rollback_count=0,
            )

        # Extract code
        code = extract_code(llm_text)
        log_info("agent.run", "code extracted", chars=len(code), preview=code[:200])
        callbacks.on_status(f"code extracted, chars={len(code)}")
        if not code.strip():
            # No code → treat as feedback
            history.add(Role.FEEDBACK, "No code generated.")
            log_warn("agent.run", "LLM returned no executable code")
            callbacks.on_status("LLM returned no executable code")
            return AgentResult(
                ok=False,
                attempts=attempts,
                error="No code generated",
                new_objects=[],
                rollback_count=0,
            )

        # Execute (with rollback) via callback or directly
        if use_callbacks:
            # Delegate execution to UI thread
            log_info("agent.run", "delegating execution to UI thread", attempt=attempts)
            callbacks.on_status("dispatching code to FreeCAD main thread")
            exec_result_dict = callbacks.on_exec_needed(code, attempts)
            exec_result = ExecResult(
                ok=exec_result_dict.get("ok", False),
                new_objects=exec_result_dict.get("new_objects", []),
                error=exec_result_dict.get("error"),
                rollback_count=exec_result_dict.get("rollback_count", 0),
            )
        else:
            # Direct execution
            log_info(
                "agent.run",
                "executing directly in current thread",
                attempt=attempts,
            )
            exec_result = _execute_with_rollback(code, doc)

        total_rollback_count += exec_result.rollback_count

        if exec_result.ok:
            # Success – add assistant response to history
            history.add(Role.ASSISTANT, llm_text)
            log_info(
                "agent.run",
                "attempt succeeded",
                attempt=attempts,
                new_objects=exec_result.new_objects,
            )
            callbacks.on_status("execution succeeded")
            return AgentResult(
                ok=True,
                attempts=attempts,
                new_objects=exec_result.new_objects,
                rollback_count=total_rollback_count,
            )
        else:
            last_error = exec_result.error
            if last_error is None:
                last_error = "Unknown error"
            category = _categorize_error(last_error)
            feedback = _make_feedback(last_error, category)
            history.add(Role.FEEDBACK, feedback)
            log_warn(
                "agent.run",
                "attempt failed",
                attempt=attempts,
                error=last_error,
                category=category,
            )
            callbacks.on_status(f"execution failed: {feedback}")
            # Retry loop continues unless error is non-retriable
            if category in ("blocked_token", "unsupported_api"):
                return AgentResult(
                    ok=False,
                    attempts=attempts,
                    error=feedback,
                    new_objects=[],
                    rollback_count=total_rollback_count,
                )
            # otherwise loop continues

    # All retries exhausted
    error_msg = f"Max retries exceeded: {last_error}" if last_error else "Max retries exceeded"
    return AgentResult(
        ok=False,
        attempts=attempts,
        error=error_msg,
        new_objects=[],
        rollback_count=total_rollback_count,
    )
