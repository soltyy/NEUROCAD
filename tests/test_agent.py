"""Tests for agent.py."""

from unittest.mock import MagicMock, patch

import pytest

from neurocad.core.agent import (
    AgentCallbacks,
    _complete_with_timeout,
    _contains_refusal_intent,
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
            mock_doc.openTransaction.assert_called_once_with("NeuroCAD")
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
@patch("neurocad.core.agent.extract_code_blocks")
def test_run_success_without_callbacks(
    mock_extract, mock_build_system, mock_capture
):
    """run succeeds when LLM returns valid code and execution passes."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nPart.makeBox(10,10,10)\n```"
    mock_extract.return_value = ["Part.makeBox(10,10,10)"]
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

    with patch("neurocad.core.agent.extract_code_blocks", return_value=["code"]), \
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
         patch("neurocad.core.agent.extract_code_blocks", return_value=[]):
            result = run("prompt", mock_doc, mock_adapter, history)
            assert result.ok is False
            assert "No code generated" in result.error


def test_run_multi_block_sequential():
    """Multiple code blocks are executed sequentially."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = """```python
Part.makeBox(10,10,10)
```
```python
Part.makeCylinder(5,20)
```"""
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        # First call succeeds, second call succeeds
        mock_exec.side_effect = [
            ExecResult(ok=True, new_objects=["Box"]),
            ExecResult(ok=True, new_objects=["Cylinder"]),
        ]
        result = run("make shapes", mock_doc, mock_adapter, history)
        assert result.ok is True
        assert result.attempts == 1
        assert result.new_objects == ["Box", "Cylinder"]
        assert mock_exec.call_count == 2
        # Verify call order
        call_args = [call[0][0] for call in mock_exec.call_args_list]
        assert "Part.makeBox" in call_args[0]
        assert "Part.makeCylinder" in call_args[1]


def test_run_multi_block_stop_on_failure():
    """Within one attempt execution stops at first failing block; agent retries up to MAX_RETRIES."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = """```python
Part.makeBox(10,10,10)
```
```python
Part.makeCylinder(5,20)
```"""
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        # Block 1 fails each attempt — block 2 should never be executed within an attempt
        mock_exec.side_effect = [
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeBox'"),
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeBox'"),
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeBox'"),
        ]
        result = run("make shapes", mock_doc, mock_adapter, history)
        assert result.ok is False
        assert result.attempts == 3  # retries exhaust MAX_RETRIES
        assert mock_exec.call_count == 3  # one exec per attempt, stops at block 1 each time


def test_multi_step_failure_stop_semantics():
    """When a middle block fails, later blocks in that attempt are not executed; agent retries."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = """```python
Part.makeBox(10,10,10)
```
```python
Part.makeCylinder(5,20)
```
```python
Part.makeSphere(15)
```"""
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        # Each attempt: block 1 succeeds, block 2 fails → block 3 never executed
        # 3 attempts × 2 execs = 6 total calls
        mock_exec.side_effect = [
            ExecResult(ok=True, new_objects=["Box"]),
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeCylinder'"),
            ExecResult(ok=True, new_objects=["Box"]),
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeCylinder'"),
            ExecResult(ok=True, new_objects=["Box"]),
            ExecResult(ok=False, new_objects=[], error="module 'Part' has no attribute 'makeCylinder'"),
        ]
        result = run("make shapes", mock_doc, mock_adapter, history)
        assert result.ok is False
        assert result.attempts == 3
        assert mock_exec.call_count == 6  # 2 blocks per attempt × 3 attempts


def test_run_sandbox_policy_safe_imports_pass_through():
    """stdlib imports pass through; redundant FreeCAD module imports are stripped by extractor."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = """```python
import math
import Part
import FreeCAD
box = Part.makeBox(10, 10, 10)
```"""
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_exec.return_value = ExecResult(ok=True, new_objects=["Box"])
        result = run("make box", mock_doc, mock_adapter, history)
        assert result.ok is True
        executed_code = mock_exec.call_args[0][0]
        # stdlib imports pass through (math is not stripped)
        assert "import math" in executed_code
        # Pre-loaded FreeCAD module imports are stripped as redundant (already in namespace)
        assert "import Part" not in executed_code
        assert "import FreeCAD" not in executed_code
        # The actual code is preserved
        assert "Part.makeBox" in executed_code


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


def test_complete_with_timeout_uses_adapter_timeout():
    """_complete_with_timeout should default to adapter.timeout when not overridden."""
    mock_adapter = MagicMock()
    mock_adapter.timeout = 180.0
    mock_adapter.complete.return_value = MagicMock(content="ok")

    response = _complete_with_timeout(mock_adapter, [], system="")

    assert response.content == "ok"
    mock_adapter.complete.assert_called_once_with([], system="")


@patch("neurocad.core.context.capture")
@patch("neurocad.core.agent.build_system")
@patch("neurocad.core.agent.extract_code_blocks")
def test_run_with_callbacks_uses_complete_not_stream(
    mock_extract, mock_build_system, mock_capture
):
    """Sprint 2 path should use complete() even when callbacks are provided."""
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nprint('ok')\n```"
    mock_extract.return_value = ["print('ok')"]
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
        mock_to_prompt.assert_called_once_with(mock_snap, max_chars=1500)
        assert "Snapshot description" in result
        assert "Blocked" in result or "blocked" in result  # blocked modules listed


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
    assert "not allowed" in _make_feedback("", "blocked_token") or "forbidden" in _make_feedback("", "blocked_token")
    assert "Unsupported FreeCAD API" in _make_feedback("", "unsupported_api")
    assert "Validation failed" in _make_feedback("error", "validation")
    assert "Execution timed out" in _make_feedback("", "timeout")
    assert "LLM error" in _make_feedback("error", "llm_transport")
    assert "Execution failed" in _make_feedback("error", "runtime")


def test_run_retriable_errors_exhaust_retries():
    """blocked_token and unsupported_api are retriable — agent exhausts MAX_RETRIES."""
    from unittest.mock import MagicMock, patch

    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "code"
    history = History()

    with patch("neurocad.core.context.capture"), patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code_blocks", return_value=["code"]), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        # blocked_token: LLM keeps failing → exhausts 3 retries
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="Blocked token 'FreeCADGui' found at line 1",
        )
        result = run("make a box", mock_doc, mock_adapter, history)
        assert result.ok is False
        assert result.attempts == 3
        assert mock_exec.call_count == 3

        # unsupported_api: same — exhausts 3 retries
        mock_exec.reset_mock()
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="module 'Part' has no attribute 'makeGear'",
        )
        history.clear()
        result2 = run("make a gear", mock_doc, mock_adapter, history)
        assert result2.ok is False
        assert result2.attempts == 3
        assert mock_exec.call_count == 3


def test_run_early_refusal():
    """Sprint 5.13: early-refusal only for genuine fetch-from-network intents.
    "import a STEP file" no longer refuses — the executor sandbox catches real
    file-system / network calls if the LLM generates them.
    """
    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    history = History()

    # Explicit network-fetch request — refused at triage stage.
    result = run("download from http://example.com", mock_doc, mock_adapter, history)
    assert result.ok is False
    assert result.attempts == 0
    assert "Unsupported operation" in result.error
    assert not mock_adapter.complete.called
    # Adapter should not be called
    assert not mock_adapter.complete.called


def test_contains_refusal_intent():
    """Sprint 5.13: _contains_refusal_intent only fires on real fetch-from-network
    intents. Legitimate requests like 'импорт STEP' / 'export to file' / 'load fcstd'
    must pass through — the real sandbox is in executor._BLOCKED_NAME_TOKENS.
    """
    # Positive cases (genuine fetch-from-network intents)
    assert _contains_refusal_intent("download from http://example.com") is True
    assert _contains_refusal_intent("fetch url") is True
    assert _contains_refusal_intent("wget some.zip") is True
    assert _contains_refusal_intent("run curl") is True
    # Previously blocked, now correctly allowed (triage shouldn't block them)
    assert _contains_refusal_intent("import a file") is False   # LLM may generate valid open-file code
    assert _contains_refusal_intent("load a file") is False
    assert _contains_refusal_intent("https request") is False
    # False-positive guards
    assert _contains_refusal_intent("external diameter") is False
    assert _contains_refusal_intent("resource management") is False
    assert _contains_refusal_intent("filet") is False
    assert _contains_refusal_intent("important") is False
    # Case-insensitive
    assert _contains_refusal_intent("DOWNLOAD the file") is True
    assert _contains_refusal_intent("") is False


def test_blocked_dangerous_module_triggers_corrective_regeneration():
    """Blocked dangerous module (os, sys, etc.) adds corrective feedback and retries."""
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nimport os\nos.system('ls')\n```"
    history = History()

    with patch("neurocad.core.context.capture") as mock_capture, \
         patch("neurocad.core.agent.build_system") as mock_build_system, \
         patch("neurocad.core.agent.extract_code_blocks") as mock_extract, \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_capture.return_value = MagicMock()
        mock_build_system.return_value = "system"
        mock_extract.return_value = ["import os\nos.system('ls')"]
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="Blocked token 'os' found at line 1",
        )
        result = run("list files", mock_doc, mock_adapter, history)

        assert result.ok is False
        assert result.attempts == 3          # retries exhaust MAX_RETRIES
        assert "os" in result.error.lower()
        assert mock_adapter.complete.call_count == 3
        assert mock_exec.call_count == 3


def test_multi_step_execution_edge_cases():
    """Regression test for edge cases: blocks separated by text, empty blocks."""
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    # Simulate LLM response with three blocks separated by text, one empty block
    raw_response = '''First some text.
```python
Part.makeBox(1,1,1)
```
More text.
```python
Part.makeCylinder(5,10)
```
Empty block:
```python

```
Final block:
```python
Part.makeSphere(3)
```'''
    mock_adapter.complete.return_value.content = raw_response
    history = History()

    with patch("neurocad.core.context.capture") as mock_capture, \
         patch("neurocad.core.agent.build_system") as mock_build_system, \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_capture.return_value = MagicMock()
        mock_build_system.return_value = "system"
        # Expect three non-empty blocks (empty block filtered out)
        mock_exec.side_effect = [
            ExecResult(ok=True, new_objects=["Box"]),
            ExecResult(ok=True, new_objects=["Cylinder"]),
            ExecResult(ok=True, new_objects=["Sphere"]),
        ]
        result = run("create shapes", mock_doc, mock_adapter, history, callbacks=None)

        assert result.ok is True
        assert result.attempts == 1
        assert len(result.new_objects) == 3
        assert "Box" in result.new_objects
        assert "Cylinder" in result.new_objects
        assert "Sphere" in result.new_objects
        # Verify each block executed exactly once
        assert mock_exec.call_count == 3
        # Verify that empty block was not passed to executor
        # (implied by call count)


def test_supported_case_no_forbidden_import():
    """Regression: prompt calls out blocked modules and lists available primitives.

    Sprint 5.7: 'no import statements' phrasing was removed (it contradicted the
    later section that explicitly allows math/FreeCAD imports). The contract is
    now: imports are permitted but dangerous modules are explicitly blocked.
    """
    from neurocad.core.context import DocSnapshot
    from neurocad.core.prompt import build_system

    snap = DocSnapshot(filename="test.FCStd", objects=[])
    system = build_system(snap)

    # Dangerous imports are explicitly blocked and named
    assert "Blocked:" in system
    assert "os" in system and "subprocess" in system
    # PartDesign is in scope
    assert "PartDesign" in system
    # Core primitives still documented
    assert "Part::Cylinder" in system


def test_error_categorization_freecad_math():
    """_categorize_error classifies missing math functions as unsupported_api."""
    from neurocad.core.agent import _categorize_error
    # FreeCAD missing attribute
    err = "module 'FreeCAD' has no attribute 'cos'"
    assert _categorize_error(err) == "unsupported_api"
    # App missing attribute
    err = "module 'App' has no attribute 'sin'"
    assert _categorize_error(err) == "unsupported_api"
    # Part missing attribute (already covered)
    err = "module 'Part' has no attribute 'tan'"
    assert _categorize_error(err) == "unsupported_api"
    # Mesh, Draft, Sketcher, PartDesign
    for mod in ["Mesh", "Draft", "Sketcher", "PartDesign"]:
        err = f"module '{mod}' has no attribute 'sqrt'"
        assert _categorize_error(err) == "unsupported_api"

    # Random missing attribute (should also be unsupported_api)
    err = "module 'FreeCAD' has no attribute 'random'"
    assert _categorize_error(err) == "unsupported_api"


def test_make_feedback_math_hint():
    """_make_feedback includes hint about math module for missing math functions."""
    from neurocad.core.agent import _make_feedback
    # error containing cos
    feedback = _make_feedback("module 'FreeCAD' has no attribute 'cos'", "unsupported_api")
    assert "FreeCAD modules have no math functions" in feedback
    assert "math.cos()" in feedback
    assert "math.sin()" in feedback
    # error containing sin
    feedback = _make_feedback("module 'Part' has no attribute 'sin'", "unsupported_api")
    assert "FreeCAD modules have no math functions" in feedback
    # error not containing math keyword -> generic unsupported API message
    feedback = _make_feedback("module 'Part' has no attribute 'makeGear'", "unsupported_api")
    assert "Unsupported FreeCAD API used" in feedback
    assert "math.cos()" not in feedback
    
    
def test_unsupported_api_math_retries():
    """Error 'module FreeCAD has no attribute cos' is unsupported_api — retries with math hint."""
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "```python\nFreeCAD.cos(0)\n```"
    history = History()

    with patch("neurocad.core.context.capture") as mock_capture, \
         patch("neurocad.core.agent.build_system") as mock_build_system, \
         patch("neurocad.core.agent.extract_code_blocks") as mock_extract, \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec:
        mock_capture.return_value = MagicMock()
        mock_build_system.return_value = "system"
        mock_extract.return_value = ["FreeCAD.cos(0)"]
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="module 'FreeCAD' has no attribute 'cos'",
        )
        result = run("calculate cosine", mock_doc, mock_adapter, history)

        assert result.ok is False
        assert result.attempts == 3          # retries exhaust MAX_RETRIES
        # result.error carries the raw last error; math hint is in history as feedback
        assert "freecad" in result.error.lower() or "cos" in result.error.lower()
        assert mock_adapter.complete.call_count == 3
        assert mock_exec.call_count == 3


def test_make_feedback_bool_not_int():
    """_make_feedback gives actionable hint for 'must be bool, not int' TypeError."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("argument 2 must be bool, not int", "runtime")
    assert "True/False" in feedback
    assert "makePipeShell" in feedback
    feedback2 = _make_feedback("TypeError: must be bool, not int", "runtime")
    assert "True/False" in feedback2


def test_make_feedback_cancelled():
    """Sprint 5.6: 'Cancelled' runtime error → 'Cancelled by user.'"""
    from neurocad.core.agent import _make_feedback
    assert _make_feedback("Cancelled", "runtime") == "Cancelled by user."
    assert _make_feedback("cancelled", "runtime") == "Cancelled by user."
    assert _make_feedback("Cancelled while waiting", "runtime") == "Cancelled by user."


def test_make_feedback_handoff_timeout():
    """Sprint 5.6: handoff timeout gives a 'split the script' hint."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("Execution handoff timeout", "timeout")
    assert "Split the script" in feedback
    assert "handoff" in feedback.lower()
    # Generic timeout (non-handoff) keeps the old short message.
    assert _make_feedback("request timed out", "timeout") == "Execution timed out."


def test_make_feedback_list_index_out_of_range():
    """Sprint 5.6: list index out of range → circular-edge / Vertexes hint."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("IndexError: list index out of range", "runtime")
    assert "circular" in feedback.lower()
    assert "Vertexes" in feedback
    assert "len(" in feedback


def test_make_feedback_shape_invalid():
    """Sprint 5.6: 'Shape is invalid' validation gives a shape.fix() / isValid() hint."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback(
        "Validation failed for Fusion: Shape is invalid", "validation"
    )
    assert "shape.fix()" in feedback
    assert "self-intersection" in feedback
    assert "isValid()" in feedback


def test_make_feedback_polygon_too_few_vertices():
    """Sprint 5.22: 'Cannot create polygon because less than two vertices...'
    → polygon-vertex guard hint."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback(
        "Cannot create polygon because less than two vertices are given", "runtime"
    )
    assert "polygon" in feedback.lower()
    assert "len(points)" in feedback
    assert "Draft.make_polygon" in feedback


def test_make_feedback_range_step_zero():
    """Sprint 5.22: range() arg 3 must not be zero → defensive step pattern."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("range() arg 3 must not be zero", "runtime")
    assert "step" in feedback.lower()
    assert "max(1" in feedback
    assert "rounding" in feedback.lower() or "int(" in feedback


def test_make_feedback_face_from_wire():
    """Sprint 5.22: 'Failed to create face from wire' → wire-validation checklist."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("Failed to create face from wire", "runtime")
    assert "isClosed()" in feedback
    assert "isValid()" in feedback
    assert "planar" in feedback.lower() or "plane" in feedback.lower()


def test_make_feedback_quantity_format_string():
    """Sprint 5.22: 'unsupported format string passed to Base.Quantity.__format__'
    → use `.Value` before f-string format spec."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback(
        "unsupported format string passed to Base.Quantity.__format__", "runtime"
    )
    assert ".Value" in feedback
    assert "f'{obj.Length.Value:.2f}'" in feedback or "f'{obj.Length.Value" in feedback


def test_make_feedback_vector_three_floats_expected():
    """Sprint 5.22: 'Either three floats, tuple or Vector expected' → nD → 3D
    projection hint (recipe PART VI)."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback(
        "Either three floats, tuple or Vector expected", "runtime"
    )
    assert "3" in feedback
    assert "coord[:3]" in feedback or "[:3]" in feedback
    assert "PART VI" in feedback


def test_make_feedback_assertion_error_hint():
    """Sprint 5.23: an AssertionError raised by a self-asserting recipe
    (e.g. wheel density assert, axle radii-level assert) routes to a hint
    that tells the LLM to fix the underlying invariant — and NOT to delete
    the assertion."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback(
        "AssertionError: Wheel is too solid: density=1.02 (max 0.30)", "runtime"
    )
    assert "AssertionError" in feedback or "assert" in feedback.lower()
    assert "invariant" in feedback.lower() or "contract" in feedback.lower()
    assert "Part::Cut" in feedback


def test_make_feedback_assertion_starts_with_assert():
    """Some Python exception strings start directly with 'assert ...'
    without the AssertionError prefix."""
    from neurocad.core.agent import _make_feedback
    feedback = _make_feedback("assert len(edges_nd) == N * 2**(N-1)", "runtime")
    assert "assert" in feedback.lower()
    assert "contract" in feedback.lower() or "invariant" in feedback.lower()


def test_run_truncated_response_detected_and_retries(qapp):
    """Sprint 5.18: stop_reason='length' → truncation feedback + retry, not a
    bogus SyntaxError-on-truncated-code silent loop.
    """
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.history import History, Role

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    # Response pretends to be truncated mid-statement.
    mock_response = MagicMock()
    mock_response.content = "```python\nx = doc.addObject(\"Part::Box\""
    mock_response.stop_reason = "length"
    mock_adapter.complete.return_value = mock_response
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"):
        result = run("heavy kitchen prompt", mock_doc, mock_adapter, history)

    assert mock_adapter.complete.call_count == 3   # retried
    assert result.ok is False
    assert "truncated" in (result.error or "").lower()
    # Feedback added to history mentions split-into-blocks
    feedback = [i["content"] for i in history.items if i["role"] == Role.FEEDBACK]
    assert feedback
    assert any("TRUNCATED" in f or "max_tokens" in f for f in feedback)
    assert any("split" in f.lower() or "fenced" in f.lower() for f in feedback)


def test_run_truncated_max_tokens_variant_also_detected(qapp):
    """Providers sometimes report 'max_tokens' instead of 'length' — same branch."""
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_response = MagicMock()
    mock_response.content = "```python\npartial"
    mock_response.stop_reason = "max_tokens"
    mock_adapter.complete.return_value = mock_response
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"):
        result = run("heavy", mock_doc, mock_adapter, history)

    assert result.ok is False
    assert "truncated" in (result.error or "").lower()


def test_openai_adapter_default_max_tokens_raised_to_8192():
    """Sprint 5.18: default max_tokens bumped 4096 → 8192 so complex assemblies fit."""
    from neurocad.llm.openai import OpenAIAdapter
    adapter = OpenAIAdapter(api_key="x")
    assert adapter.max_tokens == 8192


def test_anthropic_adapter_default_max_tokens_raised_to_8192():
    """Sprint 5.18: default max_tokens bumped 4096 → 8192 for Claude too."""
    from neurocad.llm.anthropic import AnthropicAdapter
    adapter = AnthropicAdapter(api_key="x")
    assert adapter.max_tokens == 8192


def test_make_feedback_nameerror_forgot_to_fetch_single_block():
    """Sprint 5.20: single-block NameError for an object-like name should
    point at `doc.getObject(...)` rather than the generic scoping message.
    """
    from neurocad.core.agent import _make_feedback
    # Russian Cyrillic object name — definitely looks like a document object
    fb_ru = _make_feedback(
        "name 'прозрачная_сфера' is not defined", "runtime",
        block_idx=1, total_blocks=1,
    )
    assert "doc.getObject" in fb_ru
    assert "never fetched" in fb_ru.lower() or "document object" in fb_ru.lower()

    # Capitalized English name — "ПрозрачнаяСфера" normalized pattern
    fb_cap = _make_feedback(
        "name 'BoltBody' is not defined", "runtime",
        block_idx=1, total_blocks=1,
    )
    assert "doc.getObject" in fb_cap

    # Lowercase pure-scoping typo — stays on generic branch
    fb_generic = _make_feedback(
        "name 'pitch' is not defined", "runtime",
        block_idx=1, total_blocks=1,
    )
    assert "never fetched" not in fb_generic.lower()
    assert "typo" in fb_generic.lower()


def test_make_feedback_viewobject_fontsize():
    """Sprint 5.20: FontSize on a Part ViewProvider → redirect to PART VII recipe."""
    from neurocad.core.agent import _make_feedback
    fb = _make_feedback(
        "'PartGui.ViewProviderPartExt' object has no attribute 'FontSize'",
        "runtime",
    )
    assert "FontSize" in fb
    assert "Draft.make_shapestring" in fb
    assert "neurocad_default_font" in fb
    assert "Extrusion" in fb


def test_make_feedback_viewobject_generic_attribute_error():
    """Non-text ViewObject attribute errors get a generic diagnostic listing valid properties."""
    from neurocad.core.agent import _make_feedback
    fb = _make_feedback(
        "'PartGui.ViewProviderPartExt' object has no attribute 'InvisibleMagic'",
        "runtime",
    )
    assert "ShapeColor" in fb
    assert "Transparency" in fb
    # Does NOT mention the text-specific recipe for unrelated attributes
    assert "Draft.make_shapestring" not in fb


def test_executor_namespace_exposes_platform_name_and_file_exists():
    """Sprint 5.20: executor injects `platform_name` and `file_exists` so the
    PART VII font-resolver recipe works without `import os` / `import sys`."""
    from unittest.mock import MagicMock
    from neurocad.core.executor import _build_namespace
    ns = _build_namespace(MagicMock())
    assert "platform_name" in ns
    assert isinstance(ns["platform_name"], str)
    assert "file_exists" in ns
    assert callable(ns["file_exists"])
    # file_exists returns False for a clearly non-existent path
    assert ns["file_exists"]("/definitely/not/a/real/path/xyz123") is False


def test_make_feedback_shape_invalid_revolution_specific():
    """Sprint 5.16: 'Shape is invalid' on a Revolution-related object name gives
    revolution-specific hints (closed wire, one side of axis, fillet-arc bugs)
    instead of the generic boolean/sweep diagnosis.
    """
    from neurocad.core.agent import _make_feedback
    fb = _make_feedback(
        "Validation failed for WheelAxisRevolution: Shape is invalid",
        "validation",
    )
    assert "Part::Revolution" in fb or "revolved" in fb.lower()
    assert "isValid" in fb
    assert "CCW" in fb or "closed" in fb.lower()
    assert "fillet_arc_points" in fb or "linear bevel" in fb.lower()
    # Non-revolution object falls back to the general boolean/sweep message.
    fb_boolean = _make_feedback(
        "Validation failed for FusedCube: Shape is invalid",
        "validation",
    )
    assert "boolean Fuse/Cut" in fb_boolean


def test_run_no_code_generated_retries(qapp):
    """Sprint 5.16: a first attempt that produces no code now retries instead
    of failing immediately. Only after MAX_RETRIES exhausted does it return
    no_code_generated.
    """
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "just prose, no fenced block"
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code_blocks", return_value=[]):
        result = run("make a box", mock_doc, mock_adapter, history)

    # LLM called MAX_RETRIES times (previously: only 1)
    assert mock_adapter.complete.call_count == 3
    assert result.attempts == 3
    assert result.ok is False
    assert "No code generated" in (result.error or "")


def test_run_no_code_generated_feedback_is_stronger(qapp):
    """Sprint 5.16: the FEEDBACK added to history after no-code now demands
    a fenced code block explicitly, not the old soft 'No code generated.'
    """
    from unittest.mock import MagicMock, patch
    from neurocad.core.agent import run
    from neurocad.core.history import History, Role

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "prose"
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code_blocks", return_value=[]):
        run("make a box", mock_doc, mock_adapter, history)

    # Feedback messages added to history (History.items is a property → list of dicts)
    feedback_msgs = [
        item for item in history.items if item["role"] == Role.FEEDBACK
    ]
    assert feedback_msgs, "expected at least one feedback message"
    last = feedback_msgs[-1]["content"]
    assert "fenced" in last.lower() or "```python" in last
    assert "apologize" in last.lower() or "describe" in last.lower()


def test_make_feedback_touched_invalid_thread_specific():
    """Sprint 5.8: thread-related Touched/Invalid gets thread-specific guidance."""
    from neurocad.core.agent import _make_feedback
    # Thread-related object name → thread-specific hints
    fb = _make_feedback(
        "Validation failed for ThreadedBolt: Object state indicates error: ['Touched', 'Invalid']",
        "validation",
    )
    assert "sweep.Shape.isValid()" in fb
    assert "10 turns" in fb or "10 * pitch" in fb
    assert "Frenet" in fb
    # Non-thread Touched/Invalid → existing fillet diagnosis
    fb_fillet = _make_feedback(
        "Validation failed for FilletedBox: Object state indicates error: ['Touched', 'Invalid']",
        "validation",
    )
    assert "Fillet" in fb_fillet


def test_make_feedback_nameerror_block_scoping_diagnosis():
    """Sprint 5.13: NameError in block >= 2 gets cross-block naming drift diagnosis.

    This is the #1 failure mode in dog-food (14+ cases on 2026-04-18) — the
    LLM uses `major_d` in Block 1 and then `major_diameter` in Block 2.
    """
    from neurocad.core.agent import _make_feedback
    err = "name 'major_diameter' is not defined"

    # Block 2/3 of a 3-block response → specialized drift-diagnosis
    fb = _make_feedback(err, "runtime", block_idx=2, total_blocks=3)
    assert "Block 2/3" in fb
    assert "FRESH namespace" in fb
    assert "major_d" in fb  # concrete canonical name suggestion
    assert "shank_h" in fb
    assert "doc.getObject" in fb

    # Single-block response → fall-back diagnosis (no mention of fresh namespace)
    fb_single = _make_feedback(err, "runtime", block_idx=1, total_blocks=1)
    assert "Block" not in fb_single  # no block-number prefix
    assert "typo" in fb_single.lower() or "previous" in fb_single.lower()


def test_make_feedback_involute_gear_not_a_type():
    """Sprint 5.8: PartDesign::InvoluteGear gets manual-involute guidance."""
    from neurocad.core.agent import _make_feedback
    fb = _make_feedback(
        "Document::addObject: 'PartDesign::InvoluteGear' is not a document object type",
        "runtime",
    )
    assert "Gears Workbench" in fb or "Gears WB" in fb
    assert "Part.makeCompound" in fb
    assert "teeth_n" in fb or "teeth" in fb.lower()


def test_run_cancellation_fast_exit():
    """Sprint 5.6: 'Cancelled' exec result must NOT trigger retry — single attempt only."""
    from unittest.mock import MagicMock, patch

    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "code"
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code_blocks", return_value=["code"]), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec, \
         patch("neurocad.core.agent.audit_log") as mock_audit:
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="Cancelled",
        )
        result = run("make a box", mock_doc, mock_adapter, history)
        assert result.ok is False
        assert result.attempts == 1
        assert mock_exec.call_count == 1
        assert result.error == "Cancelled by user"
        # One of the audit_log calls must be agent_error with cancelled_by_user
        error_events = [
            c for c in mock_audit.call_args_list
            if c.args and c.args[0] == "agent_error"
        ]
        assert any(
            c.args[1].get("error_type") == "cancelled_by_user" for c in error_events
        )


def test_run_handoff_timeout_fast_exit():
    """Sprint 5.6: 'Execution handoff timeout' must NOT retry — single attempt only."""
    from unittest.mock import MagicMock, patch

    from neurocad.core.agent import run
    from neurocad.core.executor import ExecResult
    from neurocad.core.history import History

    mock_doc = MagicMock()
    mock_adapter = MagicMock()
    mock_adapter.complete.return_value.content = "code"
    history = History()

    with patch("neurocad.core.context.capture"), \
         patch("neurocad.core.agent.build_system"), \
         patch("neurocad.core.agent.extract_code_blocks", return_value=["code"]), \
         patch("neurocad.core.agent._execute_with_rollback") as mock_exec, \
         patch("neurocad.core.agent.audit_log") as mock_audit:
        mock_exec.return_value = ExecResult(
            ok=False,
            new_objects=[],
            error="Execution handoff timeout",
        )
        result = run("heavy code", mock_doc, mock_adapter, history)
        assert result.ok is False
        assert result.attempts == 1
        assert mock_exec.call_count == 1
        assert "Split the script" in (result.error or "")
        error_events = [
            c for c in mock_audit.call_args_list
            if c.args and c.args[0] == "agent_error"
        ]
        assert any(
            c.args[1].get("error_type") == "handoff_timeout" for c in error_events
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
