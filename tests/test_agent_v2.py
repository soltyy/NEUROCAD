"""Tests for the plan-driven agent v2 (Sprint 6.0)."""

import json
from unittest.mock import MagicMock

import pytest

from neurocad.core.agent_v2 import AgentV2Callbacks, run
from neurocad.core.history import History
from neurocad.core.message import MessageKind


def _make_adapter(responses: list[str]):
    """Build an adapter mock that returns successive scripted responses."""
    adapter = MagicMock()
    adapter.provider = "mock"
    adapter.model = "mock-v2"
    iterator = iter(responses)

    def _complete(messages, system=""):
        text = next(iterator)
        resp = MagicMock()
        resp.content = text
        resp.input_tokens = 100
        resp.output_tokens = 100
        resp.stop_reason = "stop"
        return resp

    adapter.complete = MagicMock(side_effect=_complete)
    return adapter


def _make_doc():
    """A doc-stub with empty Objects and a getObject stub."""
    doc = MagicMock()
    doc.Name = "TestDoc"
    doc.Objects = []
    doc.getObject = MagicMock(return_value=None)
    return doc


def _sample_plan_dict(part_name="Cube", part_type="box"):
    return {
        "prompt": "test",
        "parts": [
            {
                "name": part_name,
                "type": part_type,
                "dimensions": {},
                "features": [
                    # Use bbox_length so the verifier has something cheap to check
                    {"kind": "bbox_length",
                     "params": {"axis": "x", "value_mm": 20.0, "tol_mm": 0.5}}
                ],
            }
        ],
    }


def test_simple_plan_executes_one_step():
    """End-to-end: <plan> + <code step=1> → executor called → success."""
    plan = json.dumps(_sample_plan_dict())
    response = (
        f"<plan>{plan}</plan>\n"
        '<code step="1">box = doc.addObject("Part::Box","Cube")</code>\n'
    )
    adapter = _make_adapter([response])

    # Stub doc.getObject to return an object whose Shape's bbox satisfies bbox_length
    box = MagicMock()
    bb = MagicMock()
    bb.XLength = 20.0; bb.YLength = 20.0; bb.ZLength = 20.0
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.Label = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)

    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"], "error": None}
    )
    result = run("куб 20×20×20", doc, adapter, History(), cb)
    assert result.ok is True
    assert result.intent is not None
    assert result.intent.parts[0].name == "Cube"
    assert len(result.steps) == 1
    assert result.steps[0].ok is True


def test_question_pauses_until_user_answers():
    """LLM emits <question> first → user answers → second response with plan."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        '<question type="choice" options="20|30">Какой размер куба?</question>',
        f"<plan>{plan}</plan>\n<code step=\"1\">x=1</code>",
    ]
    adapter = _make_adapter(responses)
    answers = iter(["20"])
    doc = _make_doc()
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=20; bb.YLength=20; bb.ZLength=20
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.InList = []
    doc.getObject = MagicMock(return_value=box)
    cb = AgentV2Callbacks(
        on_question=lambda q: next(answers),
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
    )
    result = run("куб", doc, adapter, History(), cb)
    assert adapter.complete.call_count == 2
    assert result.ok is True


def test_user_cancels_question_aborts_run():
    """on_question returning None → cancellation."""
    adapter = _make_adapter(["<question>Какой размер?</question>"])
    cb = AgentV2Callbacks(on_question=lambda q: None)
    result = run("куб", _make_doc(), adapter, History(), cb)
    assert result.ok is False
    assert "cancelled" in (result.error or "").lower()


def test_legacy_fenced_code_without_plan_still_executes():
    """Backward compatibility: LLM emits ```python``` only — no plan."""
    response = "```python\nbox = doc.addObject('Part::Box','B')\n```"
    adapter = _make_adapter([response])
    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["B"]},
    )
    result = run("куб", _make_doc(), adapter, History(), cb)
    assert result.ok is True
    assert result.intent is None  # no plan emitted
    assert len(result.steps) == 1
    assert result.steps[0].part_name.startswith("legacy")


def test_verify_failure_triggers_retry():
    """Verifier fails first time → LLM emits corrected code → success."""
    plan = json.dumps(_sample_plan_dict())
    # First response: bad code (will be exec'd, but the verifier will reject)
    # Second response: corrected code (after retry feedback)
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">first=1</code>",
        '<code step="1">corrected=1</code>',
    ]
    adapter = _make_adapter(responses)

    # First exec returns a 100mm box (verifier rejects since bbox != 20mm)
    # Second exec returns a 20mm box (verifier accepts)
    call_count = {"n": 0}
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=100; bb.YLength=100; bb.ZLength=100  # initial: 100mm
    bb.XMin=0; bb.XMax=100; bb.YMin=0; bb.YMax=100; bb.ZMin=0; bb.ZMax=100
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 1e6
    box.Name = "Cube"; box.InList = []

    def _exec_side_effect(code, step):
        call_count["n"] += 1
        if call_count["n"] == 2:
            # Second call: corrected box, bbox now 20mm
            bb.XLength = 20.0; bb.YLength = 20.0; bb.ZLength = 20.0
            box.Shape.Volume = 8000
        return {"ok": True, "new_objects": ["Cube"]}

    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)
    cb = AgentV2Callbacks(on_exec_needed=_exec_side_effect)
    result = run("куб 20x20x20", doc, adapter, History(), cb)
    assert result.ok is True
    assert result.steps[0].attempts == 2  # one retry


def test_step_rollback_called_between_attempts():
    """Sprint 6.3 regression: when verify fails, the agent must ask the
    host to delete that attempt's objects before the next attempt runs.

    Symptom in production (audit 2026-05-11): step «Veranda» retried 3×;
    each attempt created `Veranda`, `Veranda001`, `Veranda002` (FreeCAD
    auto-rename), but only the latest had the correct hollow caged shape.
    Verifier's substring lookup returned the stale solid `Veranda001`
    first → contract failed forever. Rollback wipes them between tries."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">first=1</code>",
        '<code step="1">corrected=1</code>',
    ]
    adapter = _make_adapter(responses)
    # First attempt fails verify; second succeeds.
    call_count = {"n": 0}
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=100; bb.YLength=100; bb.ZLength=100  # initial: wrong
    bb.XMin=0; bb.XMax=100; bb.YMin=0; bb.YMax=100; bb.ZMin=0; bb.ZMax=100
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 1e6
    box.Name = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)

    def _exec(code, step):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"ok": True, "new_objects": ["Cube", "Cube_Helper"]}
        # Second attempt: corrected bbox, verify passes
        bb.XLength = 20.0; bb.YLength = 20.0; bb.ZLength = 20.0
        box.Shape.Volume = 8000
        return {"ok": True, "new_objects": ["Cube"]}

    rollback_calls: list[list[str]] = []
    cb = AgentV2Callbacks(
        on_exec_needed=_exec,
        on_rollback=lambda names: rollback_calls.append(list(names)),
    )
    result = run("куб 20x20x20", doc, adapter, History(), cb)
    assert result.ok is True
    assert result.steps[0].attempts == 2
    # Rollback fired exactly once — between attempt 1 and attempt 2.
    assert len(rollback_calls) == 1, (
        f"expected one rollback call, got {len(rollback_calls)}: {rollback_calls}"
    )
    # Names match attempt 1's new_objects, reversed (consumers first).
    assert rollback_calls[0] == ["Cube_Helper", "Cube"]


def test_progress_continues_beyond_three_attempts():
    """Sprint 6.3 progress-aware retry: when verify-failure count keeps
    DECREASING across attempts, the agent must keep retrying past the
    old fixed cap of 3. This is the «3 попытки не предел» case —
    a converging step should run until success or stall.

    Scenario: a verifier returns 5 → 3 → 1 → 0 failures across attempts.
    Under the old 3-attempt cap, attempt 4 would never happen and the
    step would die one step away from success.
    """
    plan = json.dumps(_sample_plan_dict())
    # Five LLM responses — initial + 4 retries. Only the first carries plan.
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">attempt1=1</code>",
        '<code step="1">attempt2=1</code>',
        '<code step="1">attempt3=1</code>',
        '<code step="1">attempt4=1</code>',
    ]
    adapter = _make_adapter(responses)
    doc = _make_doc()

    # Verifier returns decreasing failure counts then success.
    verify_calls = {"n": 0}
    failure_schedule = [5, 3, 1, 0]   # n_failures per attempt

    def _on_verify_step(intent_dict, step_idx):
        n = failure_schedule[verify_calls["n"]]
        verify_calls["n"] += 1
        if n == 0:
            return {"ok": True, "failures": [], "detail": []}
        return {
            "ok": False,
            "failures": [{"part": "Cube", "feature": "bbox_length",
                          "reason": f"failure {i}", "measured": {}}
                          for i in range(n)],
            "detail": [],
        }

    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
        on_verify_step=_on_verify_step,
        on_rollback=lambda _names: None,
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is True, f"expected success, got: {result.error}"
    # Four attempts (5→3→1→0) — would have been killed at 3 under the
    # old cap.
    assert result.steps[0].attempts == 4
    assert verify_calls["n"] == 4


def test_no_progress_stalls_after_two_consecutive_stalls():
    """Sprint 6.3: when failure count stays the same (or grows) for two
    consecutive attempts after the first, the step is declared stuck.
    Without this, a fundamentally misspecified part would burn the full
    safety cap (12 attempts) emitting the same bad verifier diff."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">a=1</code>",
        '<code step="1">b=1</code>',
        '<code step="1">c=1</code>',
        '<code step="1">d=1</code>',
        '<code step="1">e=1</code>',
    ]
    adapter = _make_adapter(responses)
    doc = _make_doc()

    # Verifier returns the SAME failure count forever — no progress.
    def _on_verify_step(intent_dict, step_idx):
        return {
            "ok": False,
            "failures": [{"part": "Cube", "feature": "bbox_length",
                          "reason": "stuck", "measured": {}}],
            "detail": [],
        }

    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
        on_verify_step=_on_verify_step,
        on_rollback=lambda _names: None,
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is False
    # attempt 1: first_attempt (stalls=0)
    # attempt 2: stall (stalls=1)
    # attempt 3: stall (stalls=2 ≥ _PROGRESS_PATIENCE) → break
    assert result.steps[0].attempts == 3, (
        f"expected 3 attempts before stall-out, got {result.steps[0].attempts}"
    )
    assert "verify failed" in (result.steps[0].error or "").lower()


def test_regression_in_failures_also_counts_as_stall():
    """If the LLM makes things WORSE (failure count grows), that's still
    a stall — we don't reward regressions with more retries."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">a=1</code>",
        '<code step="1">b=1</code>',
        '<code step="1">c=1</code>',
        '<code step="1">d=1</code>',
    ]
    adapter = _make_adapter(responses)
    doc = _make_doc()

    failure_schedule = [2, 3, 4, 5]
    idx = {"n": 0}

    def _on_verify_step(intent_dict, step_idx):
        n = failure_schedule[idx["n"]]
        idx["n"] += 1
        return {
            "ok": False,
            "failures": [{"part": "Cube", "feature": "bbox_length",
                          "reason": f"#{i}", "measured": {}}
                          for i in range(n)],
            "detail": [],
        }

    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
        on_verify_step=_on_verify_step,
        on_rollback=lambda _names: None,
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is False
    assert result.steps[0].attempts == 3   # two regressions → stop


def test_update_stall_counter_helper():
    """Direct unit test of the helper — easy to reason about."""
    from neurocad.core.agent_v2 import _update_stall_counter
    hist: list[int] = []
    s, r = _update_stall_counter(hist, 5, 0)
    assert hist == [5] and s == 0 and r == "first_attempt"
    s, r = _update_stall_counter(hist, 3, s)
    assert hist == [5, 3] and s == 0 and r == "progress"
    s, r = _update_stall_counter(hist, 3, s)
    assert hist == [5, 3, 3] and s == 1 and r == "stall"
    s, r = _update_stall_counter(hist, 4, s)
    assert hist == [5, 3, 3, 4] and s == 2 and r == "regression"


def test_exec_error_triggers_rollback():
    """Sprint 6.3: even an exec-failed attempt can leave half-created
    objects (when the host doesn't expose FreeCAD transactions, e.g. the
    headless harness). Roll them back too."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">broken</code>",
        '<code step="1">fixed=1</code>',
    ]
    adapter = _make_adapter(responses)
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=20; bb.YLength=20; bb.ZLength=20
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)
    call_count = {"n": 0}

    def _exec(code, step):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"ok": False, "new_objects": ["HalfCube"], "error": "boom"}
        return {"ok": True, "new_objects": ["Cube"]}

    rollback_calls: list[list[str]] = []
    cb = AgentV2Callbacks(
        on_exec_needed=_exec,
        on_rollback=lambda names: rollback_calls.append(list(names)),
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is True
    assert result.steps[0].attempts == 2
    assert rollback_calls == [["HalfCube"]]


def test_exec_error_triggers_retry():
    """Executor returns error → LLM re-prompted → retry."""
    plan = json.dumps(_sample_plan_dict())
    responses = [
        f"<plan>{plan}</plan>\n<code step=\"1\">broken</code>",
        '<code step="1">fixed=1</code>',
    ]
    adapter = _make_adapter(responses)
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=20; bb.YLength=20; bb.ZLength=20
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)
    call_count = {"n": 0}
    def _exec(code, step):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return {"ok": False, "new_objects": [], "error": "syntax error"}
        return {"ok": True, "new_objects": ["Cube"]}
    cb = AgentV2Callbacks(on_exec_needed=_exec)
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is True
    assert result.steps[0].attempts == 2


def test_dispatched_message_kinds_include_plan_code_snapshot_verify():
    """Every kind of typed message must reach the UI callback."""
    plan = json.dumps(_sample_plan_dict())
    response = (
        "<comment>Building cube.</comment>"
        f"<plan>{plan}</plan>"
        '<code step="1">x=1</code>'
    )
    adapter = _make_adapter([response])
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=20; bb.YLength=20; bb.ZLength=20
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)
    captured: list = []
    cb = AgentV2Callbacks(
        on_message=lambda m: captured.append(m.kind),
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is True
    assert MessageKind.USER in captured
    assert MessageKind.COMMENT in captured
    assert MessageKind.PLAN in captured
    assert MessageKind.CODE in captured
    assert MessageKind.SNAPSHOT in captured
    assert MessageKind.VERIFY in captured
    assert MessageKind.SUCCESS in captured


def test_no_plan_no_code_with_comment_is_conversational_ok():
    """LLM responds to «Привет» with only a <comment> — that's a valid
    conversational reply, NOT a failure (Sprint 6.0+ hotfix)."""
    adapter = _make_adapter(["<comment>Hi! How can I help?</comment>"])
    cb = AgentV2Callbacks()
    result = run("Привет", _make_doc(), adapter, History(), cb)
    assert result.ok is True
    assert result.intent is None
    # Conversational SUCCESS message present in the sink
    from neurocad.core.message import MessageKind
    assert any(m.kind == MessageKind.SUCCESS and m.data.get("conversational")
               for m in result.messages)


def test_no_plan_no_code_no_comment_returns_error():
    """LLM emits empty / unparseable response — that IS a failure."""
    adapter = _make_adapter([""])
    cb = AgentV2Callbacks()
    result = run("???", _make_doc(), adapter, History(), cb)
    assert result.ok is False
    assert "no plan and no code" in (result.error or "").lower()


def test_find_recent_plan_extracts_from_assistant_message():
    """Plan persistence: follow-up requests must see the previous plan."""
    from neurocad.core.agent_v2 import find_recent_plan
    from neurocad.core.history import Role
    plan = json.dumps(_sample_plan_dict())
    history = History()
    history.add(Role.USER, "Сделай куб 20×20×20 мм")
    history.add(Role.ASSISTANT,
                f"<comment>OK</comment>\n<plan>{plan}</plan>\n<code step=\"1\">x=1</code>")
    history.add(Role.USER, "теперь добавь шайбу к нему")
    found = find_recent_plan(history)
    assert found is not None
    assert found.parts[0].name == "Cube"


def test_find_recent_plan_returns_none_when_no_plan():
    """No prior plan → returns None, agent_v2 starts fresh."""
    from neurocad.core.agent_v2 import find_recent_plan
    from neurocad.core.history import Role
    history = History()
    history.add(Role.USER, "Сделай куб")
    history.add(Role.ASSISTANT, "<comment>Building a cube.</comment>")
    assert find_recent_plan(history) is None


def test_build_system_v2_includes_prior_plan_when_provided():
    """prompt_v2 must surface the prior plan to the LLM as delta context."""
    from neurocad.core.intent import DesignIntent
    from neurocad.core.prompt_v2 import build_system_v2
    prior = DesignIntent.model_validate(_sample_plan_dict())
    text = build_system_v2(prior_plan=prior)
    assert "Previous plan" in text
    assert "Cube" in text     # part name leaks through


def test_build_system_v2_no_prior_plan_omits_section():
    from neurocad.core.prompt_v2 import build_system_v2
    text = build_system_v2()
    assert "Previous plan" not in text


def test_fea_callback_invoked_when_intent_has_loads():
    """If intent.loads non-empty and on_fea provided → FEA result becomes
    a VERIFY message in the sink."""
    plan_data = _sample_plan_dict()
    plan_data["loads"] = [{
        "on_part": "Cube",
        "kind": "force",
        "magnitude": 1000.0,
        "direction": [0.0, 0.0, -1.0],
    }]
    plan_data["parts"][0]["features"] = []      # let cube pass bbox check
    plan_data["parts"][0]["dimensions"] = {
        "length": {"value": 20.0, "unit": "mm", "tol": 0.5},
    }
    response = (
        f"<plan>{json.dumps(plan_data)}</plan>"
        '<code step="1">x=1</code>'
    )
    adapter = _make_adapter([response])
    box = MagicMock()
    bb = MagicMock()
    bb.XLength=20; bb.YLength=20; bb.ZLength=20
    bb.XMin=0; bb.XMax=20; bb.YMin=0; bb.YMax=20; bb.ZMin=0; bb.ZMax=20
    box.Shape = MagicMock()
    box.Shape.BoundBox = bb
    box.Shape.Volume = 8000
    box.Name = "Cube"; box.InList = []
    doc = _make_doc()
    doc.getObject = MagicMock(return_value=box)
    fea_calls = []
    def _fea(payload):
        fea_calls.append(payload)
        return {"ok": True, "sigma_max_mpa": 50.0, "displacement_mm": 0.01,
                "factor_of_safety": 5.5}
    cb = AgentV2Callbacks(
        on_exec_needed=lambda c, s: {"ok": True, "new_objects": ["Cube"]},
        on_fea=_fea,
    )
    result = run("куб", doc, adapter, History(), cb)
    assert result.ok is True
    assert len(fea_calls) == 1
    assert fea_calls[0]["loads"][0]["magnitude"] == 1000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
