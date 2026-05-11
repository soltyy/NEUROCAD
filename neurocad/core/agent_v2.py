"""Plan-driven multi-pass agent v2 (Sprint 6.0+).

Lifecycle (per user prompt):

    PHASE 1 — CLARIFY      single LLM call. If response contains a
                           <question>, pause on `on_question` callback and
                           re-send the prompt with the answer in history.
                           Loop until response has no blocking question.

    PHASE 2 — PLAN         the same LLM response must contain a <plan>
                           tag with a JSON DesignIntent. The intent is
                           stored and re-used for the rest of the run AND
                           persisted to history for follow-up requests.

    PHASE 3 — EXECUTE_STEP for each Part in the plan, in order:
                             a. find the matching <code step="N"> block
                                in the current response (or request a
                                fresh one if missing — recovery path)
                             b. execute through `on_exec_needed`
                             c. inspect (via the executor's new_objects)
                             d. run contract_verifier on ONLY this part's
                                features and dimensions
                             e. on fail: build diff feedback, re-prompt
                                the LLM for THIS STEP ONLY, max 3 retries
                             f. on success: continue to next step

    PHASE 4 — VERIFY_WHOLE   global joint checks across all parts (parts
                             with `mode=touch` must have distToShape ≤ tol,
                             coaxial parts must share an axis, etc.).
                             On fail: send the full plan + the global
                             diff back to the LLM for re-planning (PHASE 2
                             again), capped at 1 re-plan per request.

    PHASE 5 — DELIVER       return AgentV2Result with intent + per-step
                             attempt counts + final geometry status.

Differences from agent.run v1:
    * No bespoke recipes in the prompt.
    * No per-object validator anti-patterns.
    * Code does not arrive in one batch — agent re-prompts per step.
    * User can be asked clarifying questions mid-flow.
    * Plan persists across requests (the next prompt can reference the
      previous plan via History).
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .audit import audit_log, get_correlation_id
from .debug import log_error, log_info, log_warn
from .history import History, Role
from .intent import DesignIntent
from .message import Message, MessageKind
from .response_parser import code_messages, extract_plan, has_blocking_question, parse


def find_recent_plan(history: History) -> DesignIntent | None:
    """Scan history's prior assistant messages for the most-recent <plan>.

    Used by Sprint 6.0+ follow-up requests: when the user says «добавь
    шайбу к болту», the agent should see the previous PLAN so the LLM can
    reason about deltas rather than rebuild from scratch.

    Returns None if no recoverable plan is found.
    """
    items = getattr(history, "items", None) or []
    for item in reversed(items):
        if item.get("role") != Role.ASSISTANT:
            continue
        text = item.get("content") or ""
        try:
            msgs = parse(text)
        except Exception:
            continue
        plan = extract_plan(msgs)
        if plan is not None:
            return plan
    return None


# ---------------------------------------------------------------------------
# Callbacks + result types
# ---------------------------------------------------------------------------

@dataclass
class AgentV2Callbacks:
    """All v2 callbacks. UI is dispatched as typed Messages.

    `on_verify_step` lets the harness/worker run contract_verifier in the
    FreeCAD process rather than on the driver (where doc is a stub).
    If None, agent_v2 calls contract_verifier.verify(doc, intent) locally.
    """
    on_message:     Callable[[Message], None] = lambda _m: None
    on_status:      Callable[[str], None] = lambda _s: None
    on_attempt:     Callable[[int, int], None] = lambda _n, _m: None
    on_exec_needed: Callable[[str, int], dict] = (
        lambda _c, _s: {"ok": False, "new_objects": [], "error": "no executor"}
    )
    on_question:    Callable[[Message], str | None] = lambda _q: None
    on_verify_step: Callable[[dict, int], dict] | None = None
    on_verify_whole: Callable[[dict], dict] | None = None
    on_fea:         Callable[[dict], dict] | None = None    # Sprint 6.1 FEA bridge
    # Sprint 6.3: between step-retries, ask the host to delete the objects
    # the failed attempt left behind. Without this, leftover objects from
    # attempt N are still in doc.Objects when attempt N+1 runs, and
    # `_find_part_object` substring match can return the stale solid box
    # instead of the fresh hollow geometry — verify keeps failing forever.
    on_rollback:    Callable[[list[str]], None] = lambda _names: None


@dataclass
class StepResult:
    step_idx: int
    part_name: str
    ok: bool
    attempts: int
    new_objects: list[str] = field(default_factory=list)
    error: str | None = None
    verify_report: dict = field(default_factory=dict)


@dataclass
class AgentV2Result:
    ok: bool
    intent: DesignIntent | None = None
    steps: list[StepResult] = field(default_factory=list)
    error: str | None = None
    messages: list[Message] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

# Sprint 6.3 — progress-aware retry budget.
#
# A fixed 3-attempt cap was too tight: a step where the LLM was visibly
# converging (8 → 4 → 2 verify failures) would be killed before reaching
# success. A fixed «large» cap is wasteful in the opposite case — when
# the model is stuck repeating the same mistake, every extra attempt
# burns tokens for nothing.
#
# New policy:
#   - Continue while `len(report.failures)` strictly *decreases* between
#     attempts (= the LLM is learning from the verifier diff).
#   - Stop after `_PROGRESS_PATIENCE` consecutive non-improving attempts
#     (= stuck; further retries unlikely to help).
#   - Hard safety cap `_MAX_PER_STEP_RETRIES_HARD` so a catastrophically
#     misspecified step doesn't burn the entire token budget.
#   - Exec failures are treated as «infinitely many» verify failures —
#     going from exec-fail to verify-fail(5) counts as progress.
_MAX_PER_STEP_RETRIES_HARD = 12         # absolute ceiling, even if progressing
_PROGRESS_PATIENCE = 2                   # consecutive stalls → give up
_EXEC_FAIL_SENTINEL = 10**6              # exec-fail counts as "lots of failures"

_MAX_CLARIFY_ROUNDS = 3
_MAX_REPLAN_ROUNDS = 1


def _update_stall_counter(
    history: list[int],
    new_count: int,
    consecutive_stalls: int,
) -> tuple[int, str | None]:
    """Append `new_count` to `history`; return (stalls, reason).

    Progress is defined as a STRICTLY decreasing failure count between
    consecutive attempts. Equal counts or an increase counts as a stall.
    Reason is one of: "first_attempt", "progress", "stall", or
    "regression" (failures went up).
    """
    history.append(new_count)
    if len(history) < 2:
        return 0, "first_attempt"
    prev = history[-2]
    cur = history[-1]
    if cur < prev:
        return 0, "progress"
    if cur > prev:
        return consecutive_stalls + 1, "regression"
    return consecutive_stalls + 1, "stall"


def _llm_call(adapter, history: History, system: str, *, purpose: str = "") -> str:
    """Single LLM completion. Records an `agent_v2_llm_call` audit event
    with token counts + latency so v1↔v2 cost comparisons are possible
    from the audit DB."""
    import time as _time
    messages = history.to_llm_messages()
    log_info("agent_v2.llm",
             "calling adapter.complete",
             message_count=len(messages),
             system_chars=len(system),
             purpose=purpose)
    t0 = _time.monotonic()
    response = adapter.complete(messages, system=system)
    dt = _time.monotonic() - t0
    audit_log(
        "agent_v2_llm_call",
        {
            "purpose": purpose,
            "message_count": len(messages),
            "system_chars": len(system),
            "input_tokens": getattr(response, "input_tokens", None),
            "output_tokens": getattr(response, "output_tokens", None),
            "stop_reason": getattr(response, "stop_reason", None),
            "latency_s": round(dt, 3),
            "content_preview": (response.content or "")[:300],
        },
        correlation_id=get_correlation_id(),
    )
    return response.content


def _dispatch_messages(
    msgs: list[Message],
    callbacks: AgentV2Callbacks,
    sink: list[Message],
) -> None:
    """Send each typed message to the UI sink + record it."""
    for m in msgs:
        sink.append(m)
        try:
            callbacks.on_message(m)
        except Exception as exc:  # noqa: BLE001
            log_warn("agent_v2.dispatch", "callback raised", error=str(exc))


def _verify_part(doc, intent: DesignIntent, step_idx: int,
                  on_verify_step: Callable | None = None):
    """Run contract_verifier on ONLY one part of the plan.

    If `on_verify_step` callback is provided, delegate to it (used by the
    headless harness to run verification inside the FreeCAD worker
    subprocess, where the real doc lives). Otherwise call
    contract_verifier.verify(doc, intent) directly.

    Returns a VerifyReport-shaped object (either the real one or a
    lightweight dict-backed adapter from the callback's response).
    """
    from .contract_verifier import VerifyReport, verify
    if step_idx < 1 or step_idx > len(intent.parts):
        return VerifyReport(ok=True)
    sub_intent = DesignIntent(
        prompt=intent.prompt,
        parts=[intent.parts[step_idx - 1]],
        joints=[],
        loads=[],
        notes=intent.notes,
    )
    if on_verify_step is not None:
        # Callback returns a dict {ok, failures: [{part, feature, reason, measured}], detail: [...]}
        raw = on_verify_step(sub_intent.model_dump(), step_idx)
        return _adapt_remote_report(raw)
    return verify(doc, sub_intent)


def _adapt_remote_report(raw: dict):
    """Build a VerifyReport-shaped object from a remote callback's dict."""
    from .contract_verifier import CheckRecord, VerifyReport
    from .features import DetectionResult
    failures = []
    detail = []
    for f in raw.get("failures", []):
        rec = CheckRecord(
            f.get("part", "?"), f.get("feature", "?"),
            DetectionResult(
                ok=False, reason=f.get("reason"),
                measured=f.get("measured") or {},
            ),
        )
        failures.append(rec); detail.append(rec)
    for d in raw.get("detail", []):
        if d in failures:
            continue
        detail.append(CheckRecord(
            d.get("part", "?"), d.get("feature", "?"),
            DetectionResult(
                ok=d.get("ok", True), reason=d.get("reason"),
                measured=d.get("measured") or {},
            ),
        ))
    return VerifyReport(ok=bool(raw.get("ok")), failures=failures, detail=detail)


# ---------------------------------------------------------------------------
# PHASE 1 — CLARIFY
# ---------------------------------------------------------------------------

def _clarify_loop(
    text: str,
    doc,
    adapter,
    history: History,
    system: str,
    callbacks: AgentV2Callbacks,
    sink: list[Message],
) -> tuple[list[Message], bool]:
    """Loop until the LLM stops asking questions. Returns the final batch
    of messages (which should contain <plan> + <code> blocks) AND a flag
    indicating whether the user cancelled."""
    history.add(Role.USER, text)
    for round_idx in range(_MAX_CLARIFY_ROUNDS):
        is_final_round = (round_idx == _MAX_CLARIFY_ROUNDS - 1)
        callbacks.on_status(
            f"clarify round {round_idx + 1}/{_MAX_CLARIFY_ROUNDS}"
        )
        # On the last allowed round, force the LLM to commit:
        if is_final_round:
            history.add(
                Role.FEEDBACK,
                "STOP asking questions. You have enough information. "
                "Use reasonable defaults for any remaining gaps (typical ISO "
                "standards, common materials) and emit <plan> + <code step=\"1\"> "
                "NOW. Do NOT emit another <question>.",
            )
        raw = _llm_call(adapter, history, system,
                        purpose=f"clarify_round_{round_idx + 1}")
        msgs = parse(raw)
        _dispatch_messages(msgs, callbacks, sink)
        history.add(Role.ASSISTANT, raw)
        q = has_blocking_question(msgs)
        if q is None:
            return msgs, False
        if is_final_round:
            log_warn("agent_v2.clarify",
                     "LLM still asking after final-round nudge — giving up")
            break
        try:
            answer = callbacks.on_question(q)
        except Exception as exc:  # noqa: BLE001
            log_error("agent_v2.clarify", "on_question raised", error=str(exc))
            return msgs, True
        if answer is None:
            log_warn("agent_v2.clarify", "user cancelled question — aborting")
            return msgs, True
        # After each user answer, NUDGE the LLM toward committing:
        history.add(Role.USER, answer)
        history.add(
            Role.FEEDBACK,
            "You now have the user's answer. Emit <plan> + <code step=\"1\"> "
            "for the very next response. Avoid asking another question unless "
            "the new info is absolutely missing and critical.",
        )
        answer_msg = Message(kind=MessageKind.ANSWER, text=answer)
        sink.append(answer_msg)
        callbacks.on_message(answer_msg)
    log_warn("agent_v2.clarify",
             "exceeded max clarify rounds, proceeding without plan")
    return msgs, False


# ---------------------------------------------------------------------------
# PHASE 3 — EXECUTE_STEP (single-step retry loop)
# ---------------------------------------------------------------------------

def _execute_single_step(
    step_idx: int,
    part_name: str,
    initial_code_msg: Message | None,
    doc,
    adapter,
    history: History,
    system: str,
    intent: DesignIntent,
    callbacks: AgentV2Callbacks,
    sink: list[Message],
) -> StepResult:
    """Run one plan step with a progress-aware retry budget.

    Stops when ANY of:
      - verifier returns ok=True (success),
      - `_PROGRESS_PATIENCE` consecutive attempts failed to reduce the
        verify-failure count (stuck),
      - `_MAX_PER_STEP_RETRIES_HARD` attempts have been used (safety cap),
      - the user cancelled (via callbacks.on_exec_needed → 'Cancelled').

    Each retry sends the verifier diff back to the LLM and asks for a
    fresh <code step="N"> block.
    """
    code_msg = initial_code_msg
    attempts = 0
    last_error: str | None = None
    last_new_objects: list[str] = []
    last_verify_report: dict = {}
    # Progress tracking — see _MAX_PER_STEP_RETRIES_HARD doc block.
    failures_history: list[int] = []
    consecutive_stalls = 0
    stall_reason: str | None = None
    audit_log(
        "agent_v2_step_start",
        {"step_idx": step_idx, "part_name": part_name,
         "part_type": intent.parts[step_idx - 1].type if step_idx - 1 < len(intent.parts) else None},
        correlation_id=get_correlation_id(),
    )

    for attempt in range(_MAX_PER_STEP_RETRIES_HARD):
        attempts = attempt + 1
        # `on_attempt(n, max)` — `max` shown in the UI is the SAFETY cap;
        # most steps will stop earlier due to progress/success/stall.
        callbacks.on_attempt(attempts, _MAX_PER_STEP_RETRIES_HARD)
        callbacks.on_status(
            f"executing step {step_idx} ({part_name}) attempt {attempts}"
        )
        if code_msg is None:
            # Re-prompt the LLM for this step's code only.
            history.add(
                Role.FEEDBACK,
                f"Emit ONLY <code step=\"{step_idx}\"> for "
                f"part {part_name!r}.",
            )
            raw = _llm_call(adapter, history, system,
                            purpose=f"step_{step_idx}_retry_{attempt + 1}")
            msgs = parse(raw)
            _dispatch_messages(msgs, callbacks, sink)
            history.add(Role.ASSISTANT, raw)
            for m in code_messages(msgs):
                if m.step_idx == step_idx or m.step_idx is None:
                    code_msg = m
                    break
            if code_msg is None:
                last_error = "LLM did not emit code for this step"
                continue
        # Execute
        exec_result = callbacks.on_exec_needed(code_msg.text, step_idx)
        ok = bool(exec_result.get("ok"))
        new_objects = list(exec_result.get("new_objects") or [])
        error = exec_result.get("error")
        snap_msg = Message(
            kind=MessageKind.SNAPSHOT,
            text=f"step {step_idx}: {len(new_objects)} new objects",
            data={"new_objects": new_objects, "ok": ok, "error": error},
            step_idx=step_idx,
        )
        sink.append(snap_msg)
        callbacks.on_message(snap_msg)
        last_new_objects = new_objects
        if not ok:
            last_error = error or "exec failed"
            # Progress tracking: exec failure → sentinel "lots of failures".
            # Going exec-fail → verify-fail(5) counts as progress next loop.
            consecutive_stalls, stall_reason = _update_stall_counter(
                failures_history, _EXEC_FAIL_SENTINEL, consecutive_stalls,
            )
            # Roll back whatever survived the failed attempt. Even when the
            # FreeCAD transaction was aborted, the executor's `new_objects`
            # may contain pre-commit additions on hosts that don't expose
            # transactions (headless harness). Best-effort — host ignores
            # unknown names. Reverse so consumers go before producers.
            if new_objects:
                try:
                    callbacks.on_rollback(list(reversed(new_objects)))
                    audit_log(
                        "agent_v2_step_rollback",
                        {"step_idx": step_idx, "part_name": part_name,
                         "reason": "exec_failed",
                         "deleted": new_objects[:50]},
                        correlation_id=get_correlation_id(),
                    )
                except Exception as exc:  # noqa: BLE001
                    log_warn("agent_v2.rollback", "callback raised",
                             error=str(exc))
            if consecutive_stalls >= _PROGRESS_PATIENCE:
                break
            history.add(
                Role.FEEDBACK,
                f"Step {step_idx} ({part_name}) exec error: {last_error}. "
                f"Re-emit <code step=\"{step_idx}\"> with a fix.",
            )
            code_msg = None
            continue
        # Verify this part against its plan claims
        report = _verify_part(doc, intent, step_idx, callbacks.on_verify_step)
        verify_msg = Message(
            kind=MessageKind.VERIFY,
            text=report.short_summary(),
            data={
                "ok": report.ok,
                "failures": [
                    {"part": f.part, "feature": f.feature_kind,
                     "reason": f.result.reason,
                     "measured": f.result.measured}
                    for f in report.failures
                ],
            },
            step_idx=step_idx,
        )
        sink.append(verify_msg)
        callbacks.on_message(verify_msg)
        last_verify_report = verify_msg.data
        if report.ok:
            audit_log(
                "agent_v2_step_done",
                {"step_idx": step_idx, "part_name": part_name,
                 "ok": True, "attempts": attempts,
                 "new_objects": new_objects[:50]},
                correlation_id=get_correlation_id(),
            )
            return StepResult(
                step_idx=step_idx,
                part_name=part_name,
                ok=True,
                attempts=attempts,
                new_objects=new_objects,
                verify_report=last_verify_report,
            )
        # Verify failed → track progress, roll back, then re-prompt
        # (unless we've stalled for `_PROGRESS_PATIENCE` attempts).
        n_failures = len(report.failures)
        consecutive_stalls, stall_reason = _update_stall_counter(
            failures_history, n_failures, consecutive_stalls,
        )
        # Without rollback, attempt N+1's verifier still sees attempt N's
        # solid-box leftover and reports density=0.95 even after the LLM
        # correctly emits a hollow caged structure.
        if new_objects:
            try:
                callbacks.on_rollback(list(reversed(new_objects)))
                audit_log(
                    "agent_v2_step_rollback",
                    {"step_idx": step_idx, "part_name": part_name,
                     "reason": "verify_failed",
                     "deleted": new_objects[:50],
                     "first_failure": (
                         f"{report.failures[0].part}.{report.failures[0].feature_kind}"
                         if report.failures else ""
                     )},
                    correlation_id=get_correlation_id(),
                )
            except Exception as exc:  # noqa: BLE001
                log_warn("agent_v2.rollback", "callback raised",
                         error=str(exc))
        last_error = f"verify failed: {report.short_summary()}"
        if consecutive_stalls >= _PROGRESS_PATIENCE:
            break
        feedback = report.to_feedback()
        history.add(Role.FEEDBACK, feedback)
        code_msg = None
    audit_log(
        "agent_v2_step_done",
        {"step_idx": step_idx, "part_name": part_name,
         "ok": False, "attempts": attempts,
         "new_objects": last_new_objects[:50],
         "error": (last_error or "")[:240],
         "failures_history": failures_history[:30],
         "stall_reason": stall_reason or (
             "safety_cap_hit" if attempts >= _MAX_PER_STEP_RETRIES_HARD else None
         )},
        correlation_id=get_correlation_id(),
    )
    return StepResult(
        step_idx=step_idx,
        part_name=part_name,
        ok=False,
        attempts=attempts,
        new_objects=last_new_objects,
        error=last_error,
        verify_report=last_verify_report,
    )


# ---------------------------------------------------------------------------
# PHASE 4 — VERIFY_WHOLE (joints + global)
# ---------------------------------------------------------------------------

def _verify_whole(doc, intent: DesignIntent):
    """Check global joints + (future) FEA. Currently only joints."""
    if not intent.joints:
        from .contract_verifier import VerifyReport
        return VerifyReport(ok=True)
    from .contract_verifier import CheckRecord, VerifyReport
    from .features import DetectionResult
    failures = []
    detail = []
    for j in intent.joints:
        try:
            obj_a = doc.getObject(j.a) if hasattr(doc, "getObject") else None
            obj_b = doc.getObject(j.b) if hasattr(doc, "getObject") else None
        except Exception:
            obj_a = obj_b = None
        if obj_a is None or obj_b is None:
            rec = CheckRecord(
                f"{j.a}↔{j.b}", f"joint:{j.mode}",
                DetectionResult(ok=False, reason="part not found"),
            )
            detail.append(rec); failures.append(rec)
            continue
        sa, sb = getattr(obj_a, "Shape", None), getattr(obj_b, "Shape", None)
        if sa is None or sb is None:
            rec = CheckRecord(
                f"{j.a}↔{j.b}", f"joint:{j.mode}",
                DetectionResult(ok=False, reason="missing shape"),
            )
            detail.append(rec); failures.append(rec)
            continue
        try:
            d = float(sa.distToShape(sb)[0])
        except Exception as exc:
            rec = CheckRecord(
                f"{j.a}↔{j.b}", f"joint:{j.mode}",
                DetectionResult(ok=False, reason=f"distToShape raised: {exc}"),
            )
            detail.append(rec); failures.append(rec)
            continue
        ok = d <= j.tol_mm
        rec = CheckRecord(
            f"{j.a}↔{j.b}", f"joint:{j.mode}",
            DetectionResult(
                ok=ok,
                measured={"distance_mm": d, "tol_mm": j.tol_mm},
                reason=None if ok else
                       f"distance {d:.2f} mm > tol {j.tol_mm:.2f}",
            ),
        )
        detail.append(rec)
        if not ok:
            failures.append(rec)
    return VerifyReport(ok=not failures, failures=failures, detail=detail)


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def run(
    text: str,
    doc,
    adapter,
    history: History,
    callbacks: AgentV2Callbacks | None = None,
) -> AgentV2Result:
    """Run the v2 plan-driven loop."""
    if callbacks is None:
        callbacks = AgentV2Callbacks()
    from .context import capture
    from .prompt_v2 import build_system_v2
    snap = capture(doc)
    prior_plan = find_recent_plan(history)
    system = build_system_v2(snap, prior_plan=prior_plan)

    sink: list[Message] = []
    user_msg = Message(kind=MessageKind.USER, text=text)
    sink.append(user_msg)
    callbacks.on_message(user_msg)
    callbacks.on_status("phase 1: clarify")
    log_info("agent_v2.run", "starting v2 loop", prompt=text)

    audit_log(
        "agent_v2_start",
        {
            "user_prompt_preview": text,
            "provider": getattr(adapter, "provider", type(adapter).__name__),
            "model": getattr(adapter, "model", "unknown"),
            "document_name": getattr(doc, "Name", None),
        },
        correlation_id=get_correlation_id(),
    )

    # PHASE 1: CLARIFY → final response with plan + code blocks
    msgs, cancelled = _clarify_loop(
        text, doc, adapter, history, system, callbacks, sink
    )
    if cancelled:
        return AgentV2Result(
            ok=False, error="cancelled by user during clarification",
            messages=sink,
        )

    # PHASE 2: PLAN — extract DesignIntent
    intent = extract_plan(msgs)
    if intent is None:
        # Diagnostic audit: log what the final clarify response actually
        # contained so future "no plan" hangs can be triaged from logs alone.
        audit_log(
            "agent_v2_plan_missing",
            {
                "user_prompt_preview": text,
                "n_messages": len(msgs),
                "message_kinds": [str(m.kind) for m in msgs],
                "first_comment_preview": next(
                    (m.text[:300] for m in msgs if m.kind == MessageKind.COMMENT),
                    "",
                ),
                "first_error_preview": next(
                    (m.text[:300] for m in msgs if m.kind == MessageKind.ERROR),
                    "",
                ),
                "code_blocks": sum(1 for m in msgs if m.kind == MessageKind.CODE),
            },
            correlation_id=get_correlation_id(),
        )
        # No structured plan — fall back to executing any legacy code blocks
        # (single-pass behaviour). This keeps the door open for simple
        # «куб 20×20×20» prompts where a plan is overkill.
        legacy_codes = code_messages(msgs)
        kinds_in_response = [str(m.kind) for m in msgs]
        log_warn("agent_v2.plan",
                 "no <plan> found; running in legacy mode",
                 n_messages=len(msgs),
                 kinds=kinds_in_response,
                 n_legacy_codes=len(legacy_codes))
        callbacks.on_status("no plan emitted; executing legacy code blocks")
        intent = None
        if not legacy_codes:
            # Conversational fallback: a prompt like «Привет» or a clarifying
            # question that didn't need a plan. The LLM emitted comment(s)
            # only — treat as a successful chat reply, not a failure.
            comment_count = sum(
                1 for m in msgs if m.kind == MessageKind.COMMENT
            )
            if comment_count > 0:
                final = Message(
                    kind=MessageKind.SUCCESS,
                    text=f"conversational reply ({comment_count} comment(s))",
                    data={"ok": True, "conversational": True},
                )
                sink.append(final)
                callbacks.on_message(final)
                audit_log(
                    "agent_v2_done",
                    {"ok": True, "conversational": True, "prompt": text},
                    correlation_id=get_correlation_id(),
                )
                return AgentV2Result(
                    ok=True, intent=None, steps=[], error=None, messages=sink,
                )
            audit_log(
                "agent_v2_error",
                {"error_type": "no_plan_no_code", "prompt": text},
                correlation_id=get_correlation_id(),
            )
            return AgentV2Result(
                ok=False, intent=None, error="no plan and no code emitted",
                messages=sink,
            )
        # Execute each legacy code block as a single anonymous step
        step_results: list[StepResult] = []
        for i, c in enumerate(legacy_codes, start=1):
            r = callbacks.on_exec_needed(c.text, i)
            ok = bool(r.get("ok"))
            step_results.append(StepResult(
                step_idx=i, part_name=f"legacy_{i}", ok=ok,
                attempts=1,
                new_objects=list(r.get("new_objects") or []),
                error=r.get("error"),
            ))
            if not ok:
                break
        ok_all = all(s.ok for s in step_results)
        return AgentV2Result(
            ok=ok_all, intent=None, steps=step_results,
            error=None if ok_all else "legacy step failed",
            messages=sink,
        )

    # PHASE 3: per-step execute + verify + retry
    callbacks.on_status(f"phase 3: executing {len(intent.parts)} step(s)")
    step_results = []
    parts_by_idx = {i: p for i, p in enumerate(intent.parts, start=1)}
    initial_codes = {c.step_idx: c for c in code_messages(msgs) if c.step_idx}

    overall_ok = True
    for step_idx, part in parts_by_idx.items():
        initial = initial_codes.get(step_idx)
        result = _execute_single_step(
            step_idx, part.name, initial,
            doc, adapter, history, system, intent,
            callbacks, sink,
        )
        step_results.append(result)
        if not result.ok:
            overall_ok = False
            log_warn("agent_v2.run",
                     "step failed, aborting remaining steps",
                     step_idx=step_idx, name=part.name, error=result.error)
            break

    # PHASE 4: VERIFY_WHOLE (joints + optional FEA)
    if overall_ok:
        callbacks.on_status("phase 4: verifying assembly")
        whole = _verify_whole(doc, intent)
        # Optional FEA: if intent.loads is non-empty AND a callback exists,
        # run a structural check (σ_max < material yield × safety_factor).
        if intent.loads and callbacks.on_fea is not None:
            try:
                fea_payload = {
                    "loads": [load.model_dump() for load in intent.loads],
                    "parts": [p.name for p in intent.parts],
                }
                fea_result = callbacks.on_fea(fea_payload)
                fea_msg = Message(
                    kind=MessageKind.VERIFY,
                    text=(
                        f"FEA: σ_max={fea_result.get('sigma_max_mpa'):.1f} MPa, "
                        f"displacement={fea_result.get('displacement_mm'):.3f} mm, "
                        f"FoS={fea_result.get('factor_of_safety'):.2f}"
                        if fea_result.get("ok")
                        else f"FEA failed: {fea_result.get('error', 'unknown')}"
                    ),
                    data={"scope": "fea", **fea_result},
                )
                sink.append(fea_msg)
                callbacks.on_message(fea_msg)
                if not fea_result.get("ok"):
                    overall_ok = False
            except Exception as exc:  # noqa: BLE001
                log_warn("agent_v2.fea", "fea callback raised", error=str(exc))
        whole_msg = Message(
            kind=MessageKind.VERIFY,
            text=whole.short_summary(),
            data={
                "ok": whole.ok,
                "failures": [
                    {"part": f.part, "feature": f.feature_kind,
                     "reason": f.result.reason}
                    for f in whole.failures
                ],
                "scope": "whole",
            },
        )
        sink.append(whole_msg)
        callbacks.on_message(whole_msg)
        if not whole.ok:
            overall_ok = False
            log_warn("agent_v2.run", "global verify failed",
                     n_failures=len(whole.failures))

    final = Message(
        kind=MessageKind.SUCCESS if overall_ok else MessageKind.ERROR,
        text=(
            f"plan completed: {len(step_results)} step(s)"
            if overall_ok else
            f"plan aborted at step {step_results[-1].step_idx} "
            f"({step_results[-1].part_name})"
        ),
        data={
            "ok": overall_ok,
            "n_steps": len(step_results),
            "attempts_per_step": {
                str(s.step_idx): s.attempts for s in step_results
            },
        },
    )
    sink.append(final)
    callbacks.on_message(final)

    audit_log(
        "agent_v2_done",
        {
            "ok": overall_ok,
            "n_parts_planned": len(intent.parts),
            "n_steps_executed": len(step_results),
            "attempts_per_step": {
                str(s.step_idx): s.attempts for s in step_results
            },
            "intent_summary": [p.name + "/" + p.type for p in intent.parts],
        },
        correlation_id=get_correlation_id(),
    )

    return AgentV2Result(
        ok=overall_ok, intent=intent, steps=step_results,
        error=None if overall_ok else step_results[-1].error,
        messages=sink,
    )
