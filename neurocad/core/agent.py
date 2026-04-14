"""Agent orchestrates LLM, execution, validation, and rollback."""

import re
import threading
import traceback
from collections.abc import Callable
from dataclasses import dataclass

from neurocad.config.defaults import REFUSAL_KEYWORDS

from .audit import audit_log, get_correlation_id
from .code_extractor import extract_code_blocks
from .debug import log_error, log_info, log_notify, log_warn
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
    unsupported_modules = ["part", "freecad", "app", "mesh", "draft", "sketcher", "partdesign"]
    if any(f"module '{mod}' has no attribute" in error_lower for mod in unsupported_modules) or "has no attribute 'make" in error_lower:
        return "unsupported_api"
    if "validation failed" in error_lower:
        return "validation"
    if "timeout" in error_lower or "timed out" in error_lower:
        return "timeout"
    if "llm error" in error_lower or "adapter call failed" in error_lower:
        return "llm_transport"
    return "runtime"


def _is_blocked_import(error: str) -> bool:
    """Return True if the blocked token is 'import' or 'from'."""
    if error is None:
        return False
    error_lower = error.lower()
    if "blocked token" in error_lower:
        # Check for 'import' or 'from' token
        # Example: "Blocked token 'import' found at line 1"
        import_pos = error_lower.find("'import'")
        from_pos = error_lower.find("'from'")
        return import_pos != -1 or from_pos != -1
    return False


def _make_feedback(error: str, category: str) -> str:
    """Return a concise user-facing feedback message."""
    if category == "blocked_token":
        if "'import'" in error.lower():
            return "The code contains an import statement. The math and random modules are already pre‑loaded; use math.cos(), math.sin(), math.pi, random.random() etc. directly without importing."
        return "The code contains forbidden tokens (e.g., import, FreeCADGui). Remove them."
    if category == "unsupported_api":
        error_lower = error.lower()
        math_keywords = ["cos", "sin", "tan", "sqrt", "pi", "atan"]
        if any(kw in error_lower for kw in math_keywords):
            return (
                "FreeCAD modules have no math functions. Use `math.cos()`, `math.sin()` etc. — "
                "`math` is pre‑loaded in the namespace."
            )
        if "makepipeshell" in error_lower:
            return (
                "makePipeShell must be called on a Wire (the path), not on a Face. "
                "Correct pattern: helix = Part.makeHelix(pitch, height, radius); "
                "profile = Part.Wire([Part.makeCircle(r, center, normal)]); "
                "shape = helix.makePipeShell([profile], makeSolid=True, isFrenet=True); "
                "feat = doc.addObject('Part::Feature', 'Name'); feat.Shape = shape; doc.recompute()"
            )
        if "has no attribute 'transform'" in error_lower:
            return (
                "Part.Shape has no .transform() method. "
                "Use shape.transformShape(matrix) to modify in-place, or "
                "new_shape = shape.transformed(matrix) to get a copy. "
                "Build a rotation matrix with: m = FreeCAD.Matrix(); m.rotateZ(angle_rad). "
                "Alternatively compute rotated coordinates directly with math.cos/sin."
            )
        return (
            "Unsupported FreeCAD API used. Available: Part primitives (makeBox, makeCylinder, "
            "makeSphere, makeCone, makeHelix, makePolygon, makeCircle), "
            "wire.makePipeShell(), Part::Feature for raw shapes, "
            "PartDesign::InvoluteGear for gears."
        )
    if category == "validation":
        return f"Validation failed: {error}"
    if category == "timeout":
        return "Execution timed out."
    if category == "llm_transport":
        return f"LLM error: {error}"
    # default
    return f"Execution failed: {error}"


def _contains_refusal_intent(text: str) -> bool:
    """Return True if the user prompt contains unsupported file/import/resource keywords."""
    lower = text.lower()
    return any(re.search(rf'\b{re.escape(kw)}\b', lower) for kw in REFUSAL_KEYWORDS)


def _log_status(msg: str, notifications: list[str], callbacks: AgentCallbacks) -> None:
    """Emit status to Report View, collect it for per-attempt audit, and call UI callback."""
    log_notify(msg)
    notifications.append(msg)
    callbacks.on_status(msg)


def _complete_with_timeout(adapter, messages, system: str, timeout_s: float | None = None):
    """Run adapter.complete() with a hard timeout guard."""
    if timeout_s is None:
        timeout_s = float(getattr(adapter, "timeout", 120.0))
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
    """Execute code inside a FreeCAD transaction named 'NeuroCAD'.

    Rolls back the transaction if execution fails or geometry is invalid.
    """
    log_info("agent.exec", "opening FreeCAD transaction", document=getattr(doc, "Name", None))
    doc.openTransaction("NeuroCAD")  # type: ignore
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
            traceback=traceback.format_exc(),
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
    log_notify("history updated")
    callbacks.on_status("history updated")
    # Audit log
    audit_log(
        "agent_start",
        {
            "user_prompt_preview": text[:500],
            "provider": getattr(adapter, "provider", type(adapter).__name__),
            "model": getattr(adapter, "model", "unknown"),
            "document_name": getattr(doc, "Name", None),
        },
        correlation_id=get_correlation_id(),
    )

    # Early refusal for file/import/external-resource intents
    if _contains_refusal_intent(text):
        log_info("agent.run", "early refusal for file/import/external-resource intent", text=text)
        log_notify("unsupported file/import/external-resource operation")
        callbacks.on_status("unsupported file/import/external-resource operation")
        # Audit log
        audit_log(
            "agent_error",
            {
                "error_type": "early_refusal",
                "user_prompt_preview": text[:500],
                "provider": getattr(adapter, "provider", type(adapter).__name__),
                "model": getattr(adapter, "model", "unknown"),
                "document_name": getattr(doc, "Name", None),
                "attempts": 0,
                "error": (
                    "Unsupported operation: file/import/external-resource "
                    "operations are not supported."
                ),
            },
            correlation_id=get_correlation_id(),
        )
        return AgentResult(
            ok=False,
            attempts=0,
            error=(
                "Unsupported operation: file/import/external-resource operations are not supported."
            ),
            new_objects=[],
            rollback_count=0,
        )

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
    log_notify("system prompt ready", objects=len(snap.objects))
    callbacks.on_status(f"system prompt ready, objects={len(snap.objects)}")

    MAX_RETRIES = 3
    attempts = 0
    last_error = None
    total_rollback_count = 0

    while attempts < MAX_RETRIES:
        attempts += 1
        attempt_notifications: list[str] = []
        log_info("agent.run", "starting attempt", attempt=attempts, max_retries=MAX_RETRIES)
        callbacks.on_attempt(attempts, MAX_RETRIES)
        _log_status(f"attempt {attempts}/{MAX_RETRIES}", attempt_notifications, callbacks)

        # Get LLM response
        try:
            messages = history.to_llm_messages()
            log_info(
                "agent.run",
                "sending request to adapter.complete",
                message_count=len(messages),
                provider=type(adapter).__name__,
            )
            _log_status("sending request to LLM", attempt_notifications, callbacks)
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
            _log_status(f"LLM response received, chars={len(llm_text)}", attempt_notifications, callbacks)
            if use_callbacks:
                callbacks.on_chunk(llm_text)
        except Exception as e:
            log_error("agent.run", "adapter call failed", error=e)
            _log_status(f"LLM call failed: {e}", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "ok": False,
                    "error": str(e),
                    "error_category": "llm_transport",
                    "new_object_names": [],
                    "block_count": 0,
                    "rollback_count": 0,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Final error audit log
            audit_log(
                "agent_error",
                {
                    "error_type": "llm_call_failed",
                    "user_prompt_preview": text[:500],
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "error": str(e),
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=False,
                attempts=attempts,
                error=f"LLM error: {e}",
                new_objects=[],
                rollback_count=0,
            )

        # Extract code blocks
        blocks = extract_code_blocks(llm_text)
        log_info("agent.run", "code blocks extracted", block_count=len(blocks))
        _log_status(f"code extracted, blocks={len(blocks)}", attempt_notifications, callbacks)
        if not blocks:
            # No code → treat as feedback
            history.add(Role.FEEDBACK, "No code generated.")
            log_warn("agent.run", "LLM returned no executable code")
            _log_status("LLM returned no executable code", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text[:500],
                    "ok": False,
                    "error": "No code generated",
                    "error_category": "no_code",
                    "new_object_names": [],
                    "block_count": 0,
                    "rollback_count": 0,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Final error audit log
            audit_log(
                "agent_error",
                {
                    "error_type": "no_code_generated",
                    "user_prompt_preview": text[:500],
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "block_count": 0,
                    "error": "No code generated",
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=False,
                attempts=attempts,
                error="No code generated",
                new_objects=[],
                rollback_count=0,
            )

        # Execute each block sequentially
        all_new_objects: list[str] = []
        block_rollback_count = 0
        overall_ok = True
        block_error = None
        block_category = None
        block_feedback = None

        for idx, block in enumerate(blocks, start=1):
            log_info(
                "agent.run",
                "executing block",
                block_idx=idx,
                total_blocks=len(blocks),
                preview=block[:200],
            )
            _log_status(f"executing block {idx}/{len(blocks)}", attempt_notifications, callbacks)

            if use_callbacks:
                # Delegate execution to UI thread
                log_info("agent.run", "delegating block execution to UI thread", attempt=attempts)
                exec_result_dict = callbacks.on_exec_needed(block, attempts)
                exec_result = ExecResult(
                    ok=exec_result_dict.get("ok", False),
                    new_objects=exec_result_dict.get("new_objects", []),
                    error=exec_result_dict.get("error"),
                    rollback_count=exec_result_dict.get("rollback_count", 0),
                )
            else:
                # Direct execution
                exec_result = _execute_with_rollback(block, doc)

            block_rollback_count += exec_result.rollback_count

            if exec_result.ok:
                # Block succeeded – accumulate new objects
                all_new_objects.extend(exec_result.new_objects)
                continue
            else:
                # Block failed – stop execution of subsequent blocks
                overall_ok = False
                block_error = exec_result.error
                if block_error is None:
                    block_error = "Unknown error"
                block_category = _categorize_error(block_error)
                block_feedback = _make_feedback(block_error, block_category)
                log_warn(
                    "agent.run",
                    "block execution failed",
                    block_idx=idx,
                    error=block_error,
                    category=block_category,
                )
                _log_status(f"block {idx} failed: {block_feedback}", attempt_notifications, callbacks)
                break

        total_rollback_count += block_rollback_count

        if overall_ok:
            # All blocks succeeded – add assistant response to history
            history.add(Role.ASSISTANT, llm_text)
            log_info(
                "agent.run",
                "attempt succeeded",
                attempt=attempts,
                new_objects=all_new_objects,
                block_count=len(blocks),
            )
            _log_status("execution succeeded", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text[:500],
                    "code_preview": (blocks[0] if blocks else "")[:500],
                    "ok": True,
                    "error": None,
                    "error_category": None,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "rollback_count": block_rollback_count,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Final success audit log
            audit_log(
                "agent_success",
                {
                    "user_prompt_preview": text[:500],
                    "llm_response_preview": llm_text[:500],
                    "code_preview": (blocks[0] if blocks else "")[:500],
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                    "attempts": attempts,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "rollback_count": total_rollback_count,
                },
                correlation_id=get_correlation_id(),
            )
            return AgentResult(
                ok=True,
                attempts=attempts,
                new_objects=all_new_objects,
                rollback_count=total_rollback_count,
            )
        else:
            # At least one block failed
            last_error = block_error
            category = block_category
            feedback = block_feedback
            assert feedback is not None
            assert last_error is not None
            assert category is not None
            history.add(Role.FEEDBACK, feedback)
            log_warn(
                "agent.run",
                "attempt failed",
                attempt=attempts,
                error=last_error,
                category=category,
            )
            _log_status(f"execution failed: {feedback}", attempt_notifications, callbacks)
            # Per-attempt audit log
            audit_log(
                "agent_attempt",
                {
                    "attempt": attempts,
                    "max_retries": MAX_RETRIES,
                    "llm_response_preview": llm_text[:500],
                    "code_preview": (blocks[0] if blocks else "")[:500],
                    "ok": False,
                    "error": last_error,
                    "error_category": category,
                    "new_object_names": all_new_objects,
                    "block_count": len(blocks),
                    "rollback_count": block_rollback_count,
                    "notifications": attempt_notifications,
                    "provider": getattr(adapter, "provider", type(adapter).__name__),
                    "model": getattr(adapter, "model", "unknown"),
                    "document_name": getattr(doc, "Name", None),
                },
                correlation_id=get_correlation_id(),
            )
            # Retry loop continues — blocked_token and unsupported_api are
            # self-correctable: feedback is already in history, LLM can fix on next attempt.

    # All retries exhausted
    error_msg = f"Max retries exceeded: {last_error}" if last_error else "Max retries exceeded"
    # Audit log
    audit_log(
        "agent_error",
        {
            "error_type": "max_retries_exhausted",
            "user_prompt_preview": text[:500],
            "llm_response_preview": llm_text[:500] if 'llm_text' in locals() else "",
            "code_preview": (blocks[0] if blocks else "")[:500] if 'blocks' in locals() else "",
            "provider": getattr(adapter, "provider", type(adapter).__name__),
            "model": getattr(adapter, "model", "unknown"),
            "document_name": getattr(doc, "Name", None),
            "attempts": attempts,
            "error": error_msg,
            "last_error": last_error,
            "rollback_count": total_rollback_count,
        },
        correlation_id=get_correlation_id(),
    )
    return AgentResult(
        ok=False,
        attempts=attempts,
        error=error_msg,
        new_objects=[],
        rollback_count=total_rollback_count,
    )
