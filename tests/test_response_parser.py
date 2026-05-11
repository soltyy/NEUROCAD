"""Tests for the multi-channel response parser (Sprint 6.0)."""

import json

import pytest

from neurocad.core.message import MessageKind
from neurocad.core.response_parser import (
    code_messages,
    extract_plan,
    has_blocking_question,
    parse,
)


# --- Pure prose -------------------------------------------------------------

def test_parse_pure_prose_becomes_comment():
    msgs = parse("This is just narration.")
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.COMMENT
    assert "narration" in msgs[0].text


def test_parse_empty_returns_empty():
    assert parse("") == []
    assert parse("   \n  ") == []


# --- Legacy fenced ```python``` --------------------------------------------

def test_parse_legacy_fenced_python_block():
    text = "Here is the code:\n```python\nbox = doc.addObject('Part::Box', 'B')\n```"
    msgs = parse(text)
    assert any(m.kind == MessageKind.CODE for m in msgs)
    code = code_messages(msgs)[0]
    assert "addObject" in code.text
    assert code.step_idx is None  # legacy → no step


def test_parse_two_fenced_python_blocks():
    text = "```python\nimport math\n```\n\nNarration.\n\n```python\nx=1\n```"
    msgs = parse(text)
    codes = code_messages(msgs)
    assert len(codes) == 2


# --- <comment> tag ---------------------------------------------------------

def test_parse_comment_tag():
    msgs = parse("<comment>Using coarse pitch P=3.</comment>")
    assert len(msgs) == 1
    assert msgs[0].kind == MessageKind.COMMENT
    assert "coarse pitch" in msgs[0].text


def test_parse_comment_with_prose_around():
    text = "Pre. <comment>middle</comment> Post."
    msgs = parse(text)
    kinds = [m.kind for m in msgs]
    assert kinds.count(MessageKind.COMMENT) == 3


# --- <question> tag --------------------------------------------------------

def test_parse_question_with_options():
    text = '<question type="choice" options="ISO 4014|ISO 4017">Какой стандарт?</question>'
    msgs = parse(text)
    assert len(msgs) == 1
    q = msgs[0]
    assert q.kind == MessageKind.QUESTION
    assert q.data["type"] == "choice"
    assert q.data["options"] == ["ISO 4014", "ISO 4017"]
    assert "стандарт" in q.text


def test_parse_question_free_type():
    text = '<question>Какие размеры?</question>'
    msgs = parse(text)
    assert msgs[0].kind == MessageKind.QUESTION
    assert msgs[0].data["options"] is None


def test_has_blocking_question_returns_first():
    text = "<comment>preamble</comment><question>x?</question><question>y?</question>"
    msgs = parse(text)
    q = has_blocking_question(msgs)
    assert q is not None and "x" in q.text


# --- <code step="N"> -------------------------------------------------------

def test_parse_code_with_step():
    text = '<code step="2">x = doc.addObject("Part::Box","B")</code>'
    msgs = parse(text)
    assert len(msgs) == 1
    c = msgs[0]
    assert c.kind == MessageKind.CODE
    assert c.step_idx == 2
    assert c.data["step"] == 2
    assert "addObject" in c.text


def test_parse_multiple_code_blocks_with_steps():
    text = (
        '<code step="1">a=1</code>'
        '<comment>between</comment>'
        '<code step="2">b=2</code>'
    )
    msgs = parse(text)
    codes = code_messages(msgs)
    assert [c.step_idx for c in codes] == [1, 2]


# --- <plan> tag ------------------------------------------------------------

_SAMPLE_PLAN = {
    "prompt": "Болт M24",
    "parts": [
        {
            "name": "Bolt",
            "type": "bolt",
            "dimensions": {
                "length": {"value": 60.0, "unit": "mm", "tol": 0.5},
            },
            "features": [
                {"kind": "hex_head", "params": {"across_flats_mm": 36.0}},
                {"kind": "thread", "params": {"axis": "Z", "pitch_mm": 3.0,
                                               "length_mm": 30.0, "major_d_mm": 24.0}},
            ],
        }
    ],
}


def test_parse_plan_with_valid_json():
    text = f"<plan>\n{json.dumps(_SAMPLE_PLAN)}\n</plan>"
    msgs = parse(text)
    assert len(msgs) == 1
    p = msgs[0]
    assert p.kind == MessageKind.PLAN
    intent = extract_plan(msgs)
    assert intent is not None
    assert intent.parts[0].name == "Bolt"
    assert intent.parts[0].features[1].kind == "thread"


def test_parse_plan_with_bad_json_becomes_error():
    text = "<plan>not valid json{</plan>"
    msgs = parse(text)
    assert msgs[0].kind == MessageKind.ERROR
    assert "parse failed" in msgs[0].text


def test_parse_plan_with_bad_schema_becomes_error():
    text = '<plan>{"prompt": "x"}</plan>'  # missing parts
    msgs = parse(text)
    # Either ERROR (validation fails) or PLAN with empty parts depending on
    # pydantic strictness; either way it should not silently succeed.
    if msgs[0].kind == MessageKind.PLAN:
        intent = extract_plan(msgs)
        assert intent is None or intent.parts == []
    else:
        assert msgs[0].kind == MessageKind.ERROR


# --- Composite responses ---------------------------------------------------

def test_parse_full_multi_channel_response():
    text = (
        "<comment>Reading the request…</comment>\n"
        f"<plan>{json.dumps(_SAMPLE_PLAN)}</plan>\n"
        "<comment>Building step 1.</comment>\n"
        "<code step=\"1\">a = 1</code>\n"
    )
    msgs = parse(text)
    kinds = [m.kind for m in msgs]
    assert MessageKind.PLAN in kinds
    assert MessageKind.COMMENT in kinds
    assert MessageKind.CODE in kinds
    plan = extract_plan(msgs)
    assert plan is not None and plan.parts[0].name == "Bolt"


def test_parse_plan_plus_legacy_fence():
    """An LLM might emit <plan> and then a single bare ```python``` block."""
    text = (
        f"<plan>{json.dumps(_SAMPLE_PLAN)}</plan>\n"
        "```python\nx = 1\n```\n"
    )
    msgs = parse(text)
    plan = extract_plan(msgs)
    codes = code_messages(msgs)
    assert plan is not None
    assert len(codes) == 1
    assert codes[0].step_idx is None  # legacy fenced → no step


# --- Message → LLM text round-trip ----------------------------------------

def test_message_to_llm_text_preserves_tag():
    text = "<comment>note</comment>"
    msgs = parse(text)
    assert msgs[0].to_llm_text() == "<comment>note</comment>"


def test_message_to_llm_text_code_includes_step():
    text = '<code step="3">x=1</code>'
    msgs = parse(text)
    rendered = msgs[0].to_llm_text()
    assert 'step="3"' in rendered
    assert "x=1" in rendered


# --- Quantity coercion (Sprint 6.0+ LLM-friendly shorthand) ---------------

def test_quantity_accepts_plain_number():
    from neurocad.core.intent import Quantity
    q = Quantity.model_validate(12000)
    assert q.value == 12000.0
    assert q.unit == "mm"


def test_quantity_accepts_string_with_unit():
    from neurocad.core.intent import Quantity
    q = Quantity.model_validate("25 mm")
    assert q.value == 25.0 and q.unit == "mm"
    q2 = Quantity.model_validate("90 deg")
    assert q2.value == 90.0 and q2.unit == "deg"


def test_quantity_accepts_dict_form_unchanged():
    from neurocad.core.intent import Quantity
    q = Quantity.model_validate({"value": 60, "unit": "mm", "tol": 0.5})
    assert q.value == 60.0 and q.tol == 0.5


def test_design_intent_with_int_dimensions_loads():
    """LLM emits plain numbers — Pydantic must auto-coerce."""
    from neurocad.core.intent import DesignIntent
    intent = DesignIntent.model_validate({
        "prompt": "house",
        "parts": [{
            "name": "Foundation",
            "type": "slab",
            "dimensions": {"length": 12000, "width": 10000, "height": 300},
        }],
    })
    p = intent.parts[0]
    assert p.dimensions["length"].value == 12000.0
    assert p.dimensions["height"].unit == "mm"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
