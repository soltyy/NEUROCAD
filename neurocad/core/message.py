"""Typed messages for the multi-channel agent (Sprint 6.0+).

The legacy `History` (neurocad.core.history) stores everything as a Role
string + plain text. The plan-driven agent v2 needs richer typing because
a single LLM completion can contain a plan, several comments, a question,
and several code blocks — each with different routing:
    * PLAN → DesignIntent persisted across requests
    * COMMENT → info-style chat bubble (NOT executed)
    * QUESTION → blocks agent until user answers
    * CODE → executor + per-step verifier
    * SNAPSHOT / VERIFY → auto-emitted by agent runtime, recorded for audit

A new `MessageKind` enum + `Message` dataclass replaces the string-typed
records. The history adapter (`history_v2.py`, follows in this sprint)
keeps the legacy LLM-message conversion working so the existing
adapter/prompt code does not break.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class MessageKind(str, Enum):
    USER      = "user"        # user prompt or user answer to a QUESTION
    PLAN      = "plan"        # structured DesignIntent (from <plan> tag)
    COMMENT   = "comment"     # LLM's narration / rationale (info bubble)
    QUESTION  = "question"    # blocking question to user
    ANSWER    = "answer"      # user's response to a QUESTION (semantic, same content as USER)
    CODE      = "code"        # python block emitted by LLM for a step
    SNAPSHOT  = "snapshot"    # agent: inspect of doc after a step
    VERIFY    = "verify"      # agent: contract_verifier report
    ERROR     = "error"       # agent: exec or verify failure
    SUCCESS   = "success"     # agent: whole-plan completion
    SYSTEM    = "system"      # system-level note (e.g. clarifier decision)


@dataclass
class Message:
    """A single typed record in the conversation.

    Fields:
        kind       — message kind (see MessageKind)
        text       — primary human-readable text (always present)
        data       — structured payload, kind-specific:
                      PLAN     → dict (DesignIntent.model_dump())
                      QUESTION → {"options": list[str] | None,
                                  "type": "choice" | "free"}
                      CODE     → {"step": int, "block_index": int}
                      SNAPSHOT → {"objects": [...]}
                      VERIFY   → {"ok": bool, "failures": [...]}
        step_idx   — when applicable (CODE / SNAPSHOT / VERIFY / ERROR),
                     which plan-step this message belongs to. None for
                     global messages (USER, PLAN, COMMENT, …).
        timestamp  — unix epoch float, set at creation time.
    """
    kind: MessageKind
    text: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    step_idx: int | None = None
    timestamp: float = field(default_factory=time.time)

    # -------- conversion to legacy LLM chat-message format -----------------

    def to_llm_role(self) -> str | None:
        """Map MessageKind → chat-completion role for adapter consumption.

        Returns None for messages that should NOT be replayed to the LLM
        (internal SNAPSHOT/VERIFY/SYSTEM live in the audit trail only).
        """
        if self.kind in (MessageKind.USER, MessageKind.ANSWER):
            return "user"
        if self.kind in (
            MessageKind.PLAN, MessageKind.COMMENT, MessageKind.QUESTION,
            MessageKind.CODE, MessageKind.SUCCESS,
        ):
            return "assistant"
        if self.kind == MessageKind.ERROR:
            return "user"           # feedback delivered as user-side hint
        return None                  # SNAPSHOT / VERIFY / SYSTEM — internal

    def to_llm_text(self) -> str:
        """Render the LLM-visible text for this message.

        We DO include the <plan>/<comment>/<question>/<code> tags so that
        in retry-attempts the LLM sees the same structured format it
        emitted earlier — keeps the conversation self-consistent.
        """
        if self.kind == MessageKind.PLAN:
            import json
            return f"<plan>\n{json.dumps(self.data, ensure_ascii=False, indent=2)}\n</plan>"
        if self.kind == MessageKind.COMMENT:
            return f"<comment>{self.text}</comment>"
        if self.kind == MessageKind.QUESTION:
            opts = self.data.get("options")
            attrs = f' type="{self.data.get("type", "free")}"'
            if opts:
                attrs += f' options="{"|".join(opts)}"'
            return f"<question{attrs}>{self.text}</question>"
        if self.kind == MessageKind.CODE:
            step = self.step_idx if self.step_idx is not None else 1
            return f"<code step=\"{step}\">\n{self.text}\n</code>"
        if self.kind == MessageKind.ERROR:
            return f"<error>{self.text}</error>"
        return self.text
