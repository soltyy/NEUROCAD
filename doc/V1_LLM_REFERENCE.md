# NeuroCAD v1 LLM Reference Archive

**Purpose.** This document preserves the v1 (cookbook-recipe) agent's full
LLM-facing configuration so that — if v1 is later removed in favor of v2 —
we can still reason about what the model was being asked, what it was
allowed to do, and how its mistakes were corrected. Without this archive,
deleting v1 would erase ~1750 lines of accumulated prompt-engineering
that took multiple sprints to develop.

**Provenance.**

| Field | Value |
|---|---|
| Repository | `NEUROCAD` |
| Git HEAD at archive | `dcbd25ba58cdf753f0eef6c119693ad8bfb27bec` |
| Archived | 2026-05-11 |
| v1 status at archive | active behind `use_agent_v2=false` config flag (default) |
| v2 status at archive | opt-in behind `use_agent_v2=true`, Sprint 6.0+ |

---

## 1. System prompt

The full v1 system prompt is preserved verbatim in
[V1_SYSTEM_PROMPT.txt](V1_SYSTEM_PROMPT.txt) (1748 lines, ~84 KB).

Source of truth in the codebase: `neurocad/config/defaults.py:25-1772`,
constant name `DEFAULT_SYSTEM_PROMPT`. Builder in
`neurocad/core/prompt.py:9-14`:

```python
def build_system(snap: DocSnapshot) -> str:
    snapshot_desc = describe_snapshot(snap)
    return f"{snapshot_desc}\n\n{DEFAULT_SYSTEM_PROMPT}"
```

Structural sections inside the prompt (search the dump for the headers):

- `## Output format` — required ` ```python ` fenced block contract.
- `## Available APIs` — Part, PartDesign, Sketcher, Draft, Mesh whitelist.
- `## Sandbox restrictions` — blocked tokens (`os`, `sys`, `eval`, ...).
- `### PART V — recipes` — concrete cookbook snippets for bolt threads,
  involute gears, wheelsets, hex prisms, helices, etc.
- `### PART VIII — anti-patterns` — failure modes the LLM is told to avoid
  (mixing PartDesign body features with Part WB booleans outside the body,
  filleting threaded objects, recomputing without `recompute()`, ...).
- `## Naming conventions` — canonical variable names (`major_d`,
  `shank_h`, `pitch`, ...) so multi-block responses don't drift.

---

## 2. Anti-patterns (post-execution validator)

Source: `neurocad/core/validator.py`. The validator runs per-object after
each fenced block executes, gated by the new `legacy_anti_patterns`
config flag (default `True` for backward compatibility; v2 ignores it).

| Class | Token list (substring, case-insensitive) | Check |
|---|---|---|
| wheel  | `wheel`, `колес`, `велосип` | must have radial spokes (axial inside-runs detector) |
| axle   | `axle`, `ось_`, `ось `, `axleru`, `wheelset` | must have stepped Z-profile (volume ≠ plain cylinder, ratio < 0.95) |
| gear   | `gear`, `шестер`, `шестрен`, `зубч` | must have ≥ N teeth (radial inside-runs detector) |
| house  | `house`, `дом_`, `дом `, `building`, `здани`, `коттедж` | must contain bounding box of declared floors / footprint |

Plus `_is_intermediate(obj)`: skip the check if any other object in the
doc has this one in its `InList` (i.e. it's a Cut/Fuse operand, not the
final result).

---

## 3. Retry policy

Source: `neurocad/core/agent.py:683-1132`.

| Knob | Value | Where |
|---|---|---|
| `MAX_RETRIES` | `3` | agent.py:683 |
| handoff timeout | `exec_handoff_timeout_s` from config, default `60.0 s` | worker.py |
| cancellation fast-exit | yes — single `cancelled_by_user` audit event, no further LLM calls | agent.py:_make_feedback runtime branch |
| handoff timeout fast-exit | yes — `handoff_timeout` audit event, no retry | agent.py timeout-category branch |
| early refusal exit | yes — `early_refusal` if model emits ”I cannot…” pattern | agent.py |

Per-attempt history:
- Append `Role.USER` (current text) once before the loop.
- For each attempt: `adapter.complete(messages, system)` → execute → validate.
- If exec/validate fail: `_make_feedback(error, category)` → `Role.FEEDBACK`.
- After 3 attempts: emit `max_retries_exhausted` audit event, return failure.

---

## 4. Feedback-message catalog (`_make_feedback`)

Source: `neurocad/core/agent.py:83-540` (≈ 460 lines of branch logic).

Categories:

- `blocked_token` → per-token messages for `os/sys/subprocess`, `freecadgui`,
  `eval/exec/__import__`, generic fallback.
- `unsupported_api` → math keywords, `makePipeShell`, `.transform`,
  generic fallback.
- `validation` → `shape is invalid` (with revolution-vs-generic split),
  `shape is null`, `['Touched', 'Invalid']` (with thread-vs-fillet split).
- `timeout` → `handoff` (split-the-script message) vs generic.
- `llm_transport` → opaque.
- Runtime catch-all branches (in order of specificity):
  - `Cancelled` → "Cancelled by user."
  - `is not a document object type` → recipe for missing pattern/gear types.
  - `is not defined` → cross-block naming drift OR forgot-to-fetch OR
    generic scoping.
  - `unit mismatch / Quantity::operator` → "use float(box.Height)".
  - `'partdesign.feature' object has no attribute` → PartDesign vs Part WB.
  - `list index out of range` → `edge.Vertexes[1]` on circular edges.
  - `must be bool, not int`, `sketchobject…support`, `cannot import name`, ...
    (~ 25 more specialized branches).

Full text of every branch lives at `agent.py:83-540`. The branches were
collected over Sprints 5.1-5.6 by analyzing real audit logs of failed
runs; each one closed a specific recurring failure mode.

---

## 5. Sandbox / execution

Source:
- `neurocad/core/sandbox.py` — token-blocking whitelist.
- `neurocad/core/executor.py` — exec wrapper, new-object diff.
- `neurocad/core/agent.py:545-602` — `_execute_with_rollback` opens a
  named FreeCAD transaction, calls executor, then validates each new
  object. On any failure: `doc.abortTransaction()` and bump
  `rollback_count`.

Whitelisted modules (defaults.py:7-19): `FreeCAD`, `App`, `Base`, `Part`,
`PartDesign`, `Sketcher`, `Draft`, `Mesh`, `math`, `json`, `random`.

---

## 6. Audit-event vocabulary v1 wrote

Recorded in `audit-events.db` (SQLite, Sprint 6.2) and
`llm-audit.jsonl` (archive copy):

| event_type | meaning |
|---|---|
| `agent_start` | request received |
| `agent_attempt` | LLM call dispatched (attempt 1/N..3/N) |
| `agent_success` | code executed + validated cleanly |
| `agent_error` | terminal failure |

`error_type` values inside `agent_error`:

- `cancelled_by_user`
- `early_refusal`
- `handoff_timeout`
- `llm_call_failed`
- `max_retries_exhausted`
- `no_code_generated`
- `truncated`

Each entry carries `correlation_id` (session UUID), per-attempt
`new_object_names`, `rollback_count`, sanitized `user_prompt_preview` and
`llm_response_preview` (capped at `AUDIT_LOG_MAX_PREVIEW_CHARS = 500`).

---

## 7. Differences vs v2 (for orientation)

| Aspect | v1 | v2 (Sprint 6.0+) |
|---|---|---|
| Output format | `\`\`\`python ... \`\`\`` blocks only | XML-like `<plan>` + `<comment>` + `<question>` + `<code step=N>` |
| Verification | Per-object anti-patterns (token-matched) | Declarative `DesignIntent` + generic feature detectors |
| Multi-step | One LLM call, multiple fenced blocks within | Plan → execute step → verify step → next step |
| Asking the user | No — must guess defaults | `<question>` can pause for user input mid-flow |
| Rollback | FreeCAD transaction (abortTransaction) | Same + Sprint 6.3: between step-retries, delete previous attempt's new_objects |
| Retry budget | 3 / request | 3 / step (each step retries independently) |
| State | Single shot | History persisted across requests — prior plan injected into the next system prompt |

---

## 8. How to reproduce a v1 run later

If v1 is removed from the codebase, recreate its behavior with:

1. The verbatim system prompt from `V1_SYSTEM_PROMPT.txt`.
2. The retry loop from this doc's section 3, calling
   `adapter.complete(history, system)` with `Role.USER` and `Role.FEEDBACK`
   roles in the conversation.
3. The validator anti-patterns from section 2 applied post-exec.
4. The feedback-message catalog from section 4 mapped from
   error → category → message.

The mechanical glue (executor, sandbox, audit logger) is shared with v2
and isn't part of "what v1 is" — it's part of the host.
