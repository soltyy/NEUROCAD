#!/usr/bin/env python3
"""Sprint 5.21 — audit log processing-state migration / mark / stats CLI.

Lifecycle (see neurocad.core.audit module docstring):
    new                    — just written, not reviewed
    analyzed_needs_action  — reviewed, needs follow-up fix
    analyzed_done          — reviewed, no action needed
    processed              — fix shipped, closed

Sub-commands:
    migrate   — add `processing_state` to entries that lack it; auto-classify
                using the sprint-mapped rule table below. Safe to re-run
                (idempotent). Respects entries that already have a non-default
                state — never downgrades.
    stats     — counts by processing_state and event_type.
    mark      — set state on entries matching `--ts`, `--cid`, or `--event`.

Usage:
    python scripts/audit_state.py migrate
    python scripts/audit_state.py stats
    python scripts/audit_state.py mark --ts 2026-04-18T22:43:14.123456Z --state processed
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from pathlib import Path

DEFAULT_LOG = (
    Path.home()
    / "Library"
    / "Application Support"
    / "FreeCAD"
    / "v1-1"
    / "neurocad"
    / "logs"
    / "llm-audit.jsonl"
)

STATE_NEW = "new"
STATE_ANALYZED_NEEDS_ACTION = "analyzed_needs_action"
STATE_ANALYZED_DONE = "analyzed_done"
STATE_PROCESSED = "processed"
VALID_STATES = (STATE_NEW, STATE_ANALYZED_NEEDS_ACTION, STATE_ANALYZED_DONE, STATE_PROCESSED)


# ---------------------------------------------------------------------------
# Classification rules — what's been addressed and in which sprint.
#
# Match is by substring of `data.error` (lower-cased) OR `data.error_type` OR
# `data.error_category`. The rules are ordered: first match wins. A rule maps
# to a (state, sprint_tag) pair; the sprint tag is recorded as a side comment
# in the dry-run output.
# ---------------------------------------------------------------------------

# error string substring → (state, sprint annotation)
_ERROR_PATTERN_RULES: tuple[tuple[str, str, str], ...] = (
    # === Errors addressed by a shipped fix → processed ===
    ("touched", STATE_PROCESSED, "5.6/5.8 — validation feedback + thread-specific branch"),
    ("invalid", STATE_PROCESSED, "5.6/5.16 — Shape is invalid feedback / Revolution branch"),
    ("shape is null", STATE_PROCESSED, "5.6 — validation feedback"),
    ("shape is invalid", STATE_PROCESSED, "5.6/5.16 — validation + revolution feedback"),
    ("list index out of range", STATE_PROCESSED, "5.6 — circular-edge IndexError feedback"),
    ("execution handoff timeout", STATE_PROCESSED, "5.6/5.18 — handoff timeout config + truncation"),
    ("is not a document object type", STATE_PROCESSED, "5.7/5.8 — LinearPattern/InvoluteGear removal"),
    ("is not defined", STATE_PROCESSED, "5.13/5.20 — naming contract + forgot-to-fetch heuristic"),
    ("must be bool, not int", STATE_PROCESSED, "5.6 — Quantity-style bool/int feedback"),
    ("argument 2 must be bool", STATE_PROCESSED, "5.6 — bool/int feedback"),
    ("quantity::operator", STATE_PROCESSED, "5.4/5.18 — Quantity vs float anti-pattern"),
    ("unit mismatch", STATE_PROCESSED, "5.4/5.18 — Quantity feedback"),
    ("'sketcher.sketchobject' object has no attribute 'support'",
        STATE_PROCESSED, "5.8 — AttachmentSupport rename feedback"),
    ("'partdesign.feature' object has no attribute", STATE_PROCESSED,
        "5.8 — PartDesign::Feature feedback"),
    ("'partgui.viewproviderpartext' object has no attribute", STATE_PROCESSED,
        "5.20 — ViewObject feedback"),
    ("has no attribute 'fontsize'", STATE_PROCESSED, "5.20 — ViewObject FontSize feedback"),
    ("module 'part' has no attribute 'make", STATE_PROCESSED, "5.4 — unsupported FreeCAD API"),
    ("module 'freecad' has no attribute", STATE_PROCESSED, "5.5 — math namespace + categorize"),
    ("module 'app' has no attribute", STATE_PROCESSED, "5.5 — math namespace + categorize"),
    ("rotation constructor", STATE_PROCESSED, "5.4 — Rotation constructor feedback"),
    # Sprint 5.22 — newly-covered patterns (feedback added in agent._make_feedback)
    ("range() arg 3 must not be zero", STATE_PROCESSED,
        "5.22 — defensive step pattern feedback"),
    ("cannot create polygon", STATE_PROCESSED,
        "5.22 — polygon-vertex guard feedback"),
    ("failed to create face from wire", STATE_PROCESSED,
        "5.22 — wire-validation checklist feedback"),
    ("unsupported format string passed to base.quantity", STATE_PROCESSED,
        "5.22 — Quantity.__format__ → .Value feedback"),
    ("quantity.__format__", STATE_PROCESSED,
        "5.22 — Quantity.__format__ → .Value feedback"),
    ("either three floats", STATE_PROCESSED,
        "5.14/5.22 — Vector 3D guard + feedback hint"),
    ("has no attribute 'makepipeshell'", STATE_PROCESSED,
        "5.11 — Face.makePipeShell → Wire.makePipeShell feedback"),
    ("has no attribute 'transform'", STATE_PROCESSED,
        "5.16 — Shape.transform → transformShape feedback"),
    # LLM-side timeouts: cannot be fixed by the agent, only by config or model;
    # the timeout-category feedback already nudges the user toward splitting.
    ("llm request timed out", STATE_PROCESSED,
        "5.6/5.18 — by-design, timeout feedback + handoff config"),
    ("blocked token", STATE_PROCESSED, "5.4/5.6/5.13 — sandbox feedback + REFUSAL_KEYWORDS narrow"),
    ("syntax error", STATE_PROCESSED, "5.18 — truncation detection covers root cause"),
    ("tokenization error", STATE_PROCESSED, "5.18 — truncation detection"),
    ("eof in multi-line", STATE_PROCESSED, "5.18 — truncation detection"),
    ("created too many objects", STATE_PROCESSED, "5.4 — max_created_objects safety, working as designed"),
    ("execution timed out", STATE_PROCESSED, "5.6 — timeout feedback / handoff config"),
    ("no result", STATE_PROCESSED, "5.6 — worker handoff / cancel paths"),
    # No-code / cancellation: by-design UX, considered closed
    ("no code generated", STATE_PROCESSED, "5.16 — no-code retry + stronger feedback"),
    ("cancelled by user", STATE_PROCESSED, "5.6 — fast-exit cancellation"),
    ("cancelled while waiting", STATE_PROCESSED, "5.6 — cancellation path"),
    ("cancelled before exec", STATE_PROCESSED, "5.6 — cancellation path"),
    ("cancelled", STATE_PROCESSED, "5.6 — user-initiated cancel"),
    # LLM transport
    ("llm error", STATE_ANALYZED_NEEDS_ACTION, "open — network-side, no agent fix possible"),
    ("adapter call failed", STATE_ANALYZED_NEEDS_ACTION, "open — adapter / network"),
)

_ERROR_TYPE_RULES: dict[str, tuple[str, str]] = {
    "cancelled_by_user":       (STATE_PROCESSED, "5.6 — by-design"),
    "handoff_timeout":         (STATE_PROCESSED, "5.6 — by-design"),
    "no_code_generated":       (STATE_PROCESSED, "5.16 — by-design"),
    "truncated":               (STATE_PROCESSED, "5.18 — by-design"),
    "max_retries_exhausted":   (STATE_ANALYZED_NEEDS_ACTION,
                                "varies — see last_error; rule-list will refine"),
    "early_refusal":           (STATE_PROCESSED, "5.13 — REFUSAL_KEYWORDS narrowed"),
    "llm_call_failed":         (STATE_ANALYZED_NEEDS_ACTION, "open — network"),
    # 5.22 — adapter init w/out a saved key is a user-config issue, not an
    # agent bug. The Settings dialog covers it; nothing more to do code-side.
    "adapter_init_failure":    (STATE_PROCESSED, "5.15/5.17 — by-design, Settings dialog"),
}

# Event categories that do NOT need any action (informational / positive)
_POSITIVE_EVENT_TYPES = frozenset({"agent_start", "agent_success"})


def classify(entry: dict) -> tuple[str, str]:
    """Return (state, reason) for an entry. Never returns STATE_NEW —
    the migration's job is to move new → analyzed.
    """
    ev = entry.get("event_type", "")
    data = entry.get("data", {}) or {}

    if ev in _POSITIVE_EVENT_TYPES:
        return STATE_ANALYZED_DONE, f"{ev} — informational / success, no action needed"

    if ev == "agent_attempt":
        if data.get("ok") is True:
            return STATE_ANALYZED_DONE, "agent_attempt ok=True — success, no action needed"
        # Failed attempt → look up by error category / message
        err = (str(data.get("error", "")) or "").lower()
        cat = (str(data.get("error_category", "")) or "").lower()
        for needle, state, sprint in _ERROR_PATTERN_RULES:
            if needle in err or needle in cat:
                return state, f"error matches {needle!r} → {sprint}"
        return STATE_ANALYZED_NEEDS_ACTION, f"unmatched error pattern: {err[:120]!r}"

    if ev == "agent_error":
        et = data.get("error_type", "")
        if et in _ERROR_TYPE_RULES:
            state, sprint = _ERROR_TYPE_RULES[et]
            # max_retries_exhausted: refine by last_error if it matches a known pattern
            if state == STATE_ANALYZED_NEEDS_ACTION:
                err = (str(data.get("last_error") or data.get("error") or "") or "").lower()
                for needle, st, sp in _ERROR_PATTERN_RULES:
                    if needle in err:
                        return st, f"max_retries_exhausted → last_error matches {needle!r} → {sp}"
            return state, f"error_type {et!r} → {sprint}"
        err = (str(data.get("error", "")) or "").lower()
        for needle, state, sprint in _ERROR_PATTERN_RULES:
            if needle in err:
                return state, f"error matches {needle!r} → {sprint}"
        return STATE_ANALYZED_NEEDS_ACTION, f"unmatched agent_error type {et!r}"

    # adapter_init_failure / other named event types — route via _ERROR_TYPE_RULES
    if ev in _ERROR_TYPE_RULES:
        state, sprint = _ERROR_TYPE_RULES[ev]
        return state, f"event_type {ev!r} → {sprint}"

    # Unknown event types — leave for human review
    return STATE_ANALYZED_NEEDS_ACTION, f"unknown event_type {ev!r}"


# ---------------------------------------------------------------------------
# CLI sub-commands
# ---------------------------------------------------------------------------

def cmd_migrate(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: audit log not found at {log_path}", file=sys.stderr)
        return 2

    # State ordering for the no-degradation rule. A reclassification may
    # only PROMOTE (move right): new < analyzed_needs_action < analyzed_done < processed.
    state_rank = {
        STATE_NEW: 0,
        STATE_ANALYZED_NEEDS_ACTION: 1,
        STATE_ANALYZED_DONE: 2,
        STATE_PROCESSED: 3,
    }

    counts: Counter[str] = Counter()
    transitions: Counter[str] = Counter()
    tmp = log_path.with_suffix(log_path.suffix + ".tmp")

    with open(log_path, encoding="utf-8") as fin, open(tmp, "w", encoding="utf-8") as fout:
        for raw in fin:
            line = raw.rstrip("\n")
            if not line.strip():
                fout.write(raw)
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                fout.write(raw)
                counts["malformed"] += 1
                continue

            existing = entry.get("processing_state")
            if existing in VALID_STATES and existing != STATE_NEW and not args.reclassify:
                # Already classified — do not downgrade (no-degradation rule).
                counts[existing] += 1
                fout.write(raw)
                continue

            new_state, reason = classify(entry)
            # Even with --reclassify, never downgrade: promotion-only.
            if existing in state_rank and state_rank[new_state] < state_rank[existing]:
                counts[existing] += 1
                fout.write(raw)
                continue

            entry["processing_state"] = new_state
            counts[new_state] += 1
            if existing != new_state:
                transitions[f"{existing or 'absent'} → {new_state}"] += 1
            fout.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")

    if args.dry_run:
        os.unlink(tmp)
        print("DRY RUN — log not modified.")
    else:
        os.replace(tmp, log_path)
        print(f"Wrote {log_path}")
    print("\nFinal processing_state distribution:")
    for state in (STATE_NEW, STATE_ANALYZED_NEEDS_ACTION, STATE_ANALYZED_DONE, STATE_PROCESSED):
        print(f"  {state:30s} : {counts[state]}")
    if counts.get("malformed"):
        print(f"  malformed (preserved as-is)   : {counts['malformed']}")
    print("\nTransitions:")
    for k, v in sorted(transitions.items(), key=lambda kv: -kv[1]):
        print(f"  {k:50s} : {v}")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: audit log not found at {log_path}", file=sys.stderr)
        return 2

    by_state: Counter[str] = Counter()
    by_state_and_event: Counter[tuple[str, str]] = Counter()
    needs_action_samples: list[tuple[str, str, str]] = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            state = entry.get("processing_state", "absent")
            ev = entry.get("event_type", "?")
            by_state[state] += 1
            by_state_and_event[(state, ev)] += 1
            if state == STATE_ANALYZED_NEEDS_ACTION:
                d = entry.get("data", {}) or {}
                err = str(d.get("error") or d.get("last_error") or "")[:120]
                needs_action_samples.append((entry.get("timestamp","")[:19], ev, err))

    total = sum(by_state.values())
    print(f"Total entries: {total}\n")
    print("By processing_state:")
    for state in ("new", *VALID_STATES[1:], "absent"):
        n = by_state.get(state, 0)
        pct = (100 * n / total) if total else 0.0
        print(f"  {state:28s} : {n:5d}  ({pct:5.1f} %)")
    print("\nBy (state, event_type):")
    for (state, ev), n in sorted(by_state_and_event.items()):
        print(f"  {state:28s} {ev:18s} : {n}")
    if needs_action_samples:
        print(f"\nFirst 10 entries marked '{STATE_ANALYZED_NEEDS_ACTION}':")
        for ts, ev, err in needs_action_samples[:10]:
            print(f"  [{ts}] {ev:18s} {err!r}")
    return 0


def cmd_mark(args: argparse.Namespace) -> int:
    log_path = Path(args.log)
    if not log_path.exists():
        print(f"ERROR: audit log not found at {log_path}", file=sys.stderr)
        return 2

    if args.state not in VALID_STATES:
        print(f"ERROR: state must be one of {VALID_STATES}", file=sys.stderr)
        return 2

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from neurocad.core.audit import update_processing_state

    updated = update_processing_state(
        log_path,
        args.state,
        timestamp=args.ts,
        correlation_id=args.cid,
        event_type=args.event,
    )
    print(f"Updated {updated} entries → processing_state={args.state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="audit log path")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mig = sub.add_parser("migrate", help="add processing_state to legacy entries")
    p_mig.add_argument("--dry-run", action="store_true", help="report without writing")
    p_mig.add_argument(
        "--reclassify",
        action="store_true",
        help=(
            "re-evaluate entries that already have a processing_state. "
            "Promotion-only: an entry is upgraded if the current classifier "
            "rules now map it to a higher state. Never downgrades."
        ),
    )
    p_mig.set_defaults(func=cmd_migrate)

    p_stats = sub.add_parser("stats", help="show processing_state distribution")
    p_stats.set_defaults(func=cmd_stats)

    p_mark = sub.add_parser("mark", help="set state on matching entries")
    p_mark.add_argument("--state", required=True, choices=VALID_STATES)
    p_mark.add_argument("--ts", help="exact timestamp filter")
    p_mark.add_argument("--cid", help="correlation_id filter")
    p_mark.add_argument("--event", help="event_type filter")
    p_mark.set_defaults(func=cmd_mark)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
