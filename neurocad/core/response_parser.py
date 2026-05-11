"""Multi-channel LLM response parser (Sprint 6.0+).

A single LLM completion in the v2 architecture can contain several typed
blocks — `<plan>`, `<comment>`, `<question>`, `<code step="N">` — together
with arbitrary plain prose between them. The parser splits the response
into an ordered list of `Message` records that the agent v2 dispatches to
its per-kind handlers (planning store, chat UI, blocking-question UI,
executor + verifier).

The parser is INTENTIONALLY tolerant:
    * Unknown tags fall through as COMMENT (we never lose LLM text).
    * Triple-backtick ```python``` blocks at the top level (legacy format)
      ARE recognised and converted to CODE with `step=None` so the v1
      single-pass agent path keeps working.
    * `step="N"` attribute parses to int; absent → step_idx = None.
    * `options="A|B|C"` for questions parses to list[str].

Adding a new tag — extend `_TAG_HANDLERS` only, no other changes.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable

from pydantic import ValidationError

from .intent import DesignIntent
from .message import Message, MessageKind


# Tag-block pattern: <tag attrs...>content</tag>. DOTALL so content can
# span lines. Non-greedy to handle multiple tags in one response.
_TAG_RE = re.compile(
    r"<(plan|comment|question|code)"             # tag name (group 1)
    r"((?:\s+[a-z]+\s*=\s*\"[^\"]*\")*)"          # attributes (group 2)
    r"\s*>"
    r"(.*?)"                                       # content (group 3)
    r"</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Fallback: legacy ```python ... ``` fenced code (v1 format).
_FENCED_RE = re.compile(r"```python\s*\n(.*?)```", re.DOTALL)

# Attribute parser: key="value" pairs inside a tag.
_ATTR_RE = re.compile(r"([a-z]+)\s*=\s*\"([^\"]*)\"", re.IGNORECASE)


def _parse_attrs(raw: str) -> dict[str, str]:
    return {m.group(1).lower(): m.group(2) for m in _ATTR_RE.finditer(raw)}


def _build_plan_message(content: str) -> Message:
    """Parse plan body (JSON) into a DesignIntent + return PLAN message."""
    text = content.strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return Message(
            kind=MessageKind.ERROR,
            text=f"plan JSON parse failed: {exc}; raw={text[:200]!r}",
        )
    try:
        intent = DesignIntent.model_validate(data)
    except ValidationError as exc:
        return Message(
            kind=MessageKind.ERROR,
            text=f"plan schema validation failed: {exc}; raw={text[:200]!r}",
        )
    return Message(
        kind=MessageKind.PLAN,
        text=intent.notes or f"{len(intent.parts)} parts planned",
        data=intent.model_dump(),
    )


def _build_question_message(attrs: dict[str, str], content: str) -> Message:
    """Build a QUESTION message with options + type from tag attrs."""
    qtype = attrs.get("type", "free").lower()
    raw_opts = attrs.get("options", "")
    options = [o.strip() for o in raw_opts.split("|") if o.strip()] if raw_opts else None
    return Message(
        kind=MessageKind.QUESTION,
        text=content.strip(),
        data={"type": qtype, "options": options},
    )


def _build_comment_message(content: str) -> Message:
    return Message(kind=MessageKind.COMMENT, text=content.strip())


def _build_code_message(attrs: dict[str, str], content: str) -> Message:
    step_raw = attrs.get("step")
    step_idx: int | None
    try:
        step_idx = int(step_raw) if step_raw else None
    except ValueError:
        step_idx = None
    return Message(
        kind=MessageKind.CODE,
        text=content.strip("\n"),
        data={"step": step_idx},
        step_idx=step_idx,
    )


_TAG_HANDLERS = {
    "plan":     lambda _attrs, content: _build_plan_message(content),
    "comment":  lambda _attrs, content: _build_comment_message(content),
    "question": _build_question_message,
    "code":     _build_code_message,
}


def parse(raw_response: str) -> list[Message]:
    """Split a multi-channel LLM response into typed `Message`s.

    Ordering preserved: messages appear in the same order as their tags
    in the raw text. Trailing/leading prose (outside any tag) is emitted
    as a single COMMENT at its position.

    Behaviour with no tags at all:
        — if the response has ```python``` fenced blocks, each becomes a
          CODE message with step_idx=None (legacy single-pass mode);
        — otherwise the whole response becomes one COMMENT.
    """
    messages: list[Message] = []
    cursor = 0
    saw_structured_tag = False
    for match in _TAG_RE.finditer(raw_response):
        saw_structured_tag = True
        before = raw_response[cursor: match.start()].strip()
        if before:
            messages.append(_build_comment_message(before))
        tag = match.group(1).lower()
        attrs = _parse_attrs(match.group(2))
        content = match.group(3)
        handler = _TAG_HANDLERS[tag]
        messages.append(handler(attrs, content))
        cursor = match.end()

    # If no structured tags at all, scan the WHOLE text for legacy fenced
    # ```python``` blocks. Otherwise scan only the tail (what's left after
    # the last </tag>) to avoid double-counting blocks inside <code> tags.
    region = raw_response if not saw_structured_tag else raw_response[cursor:]
    fenced = list(_FENCED_RE.finditer(region))
    if fenced:
        prose_cursor = 0
        for code_match in fenced:
            prose_before = region[prose_cursor: code_match.start()].strip()
            if prose_before:
                messages.append(_build_comment_message(prose_before))
            messages.append(Message(
                kind=MessageKind.CODE,
                text=code_match.group(1).strip("\n"),
                data={"step": None},
                step_idx=None,
            ))
            prose_cursor = code_match.end()
        trailing = region[prose_cursor:].strip()
        if trailing:
            messages.append(_build_comment_message(trailing))
    else:
        trailing = region.strip()
        if trailing and not saw_structured_tag:
            # Pure prose, no tags, no fences → one COMMENT.
            messages.append(_build_comment_message(trailing))
        elif trailing:
            messages.append(_build_comment_message(trailing))

    return messages


def extract_plan(messages: Iterable[Message]) -> DesignIntent | None:
    """Convenience: return the first PLAN message's intent, if any."""
    for m in messages:
        if m.kind == MessageKind.PLAN and m.data:
            try:
                return DesignIntent.model_validate(m.data)
            except ValidationError:
                continue
    return None


def has_blocking_question(messages: Iterable[Message]) -> Message | None:
    """Return the first QUESTION message (the agent pauses on this)."""
    for m in messages:
        if m.kind == MessageKind.QUESTION:
            return m
    return None


def code_messages(messages: Iterable[Message]) -> list[Message]:
    """All CODE messages, ordered."""
    return [m for m in messages if m.kind == MessageKind.CODE]
