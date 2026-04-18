#!/usr/bin/env python3
"""Sprint 5.7 — dog-food log analyzer.

Parses the NeuroCad audit log (llm-audit.jsonl) and classifies recent user
requests against the R1–R4 success criteria, so the developer doesn't have
to read raw JSON entries by eye.

Usage:
    python scripts/dogfood_check.py                 # last 1 hour
    python scripts/dogfood_check.py --last-minutes 15
    python scripts/dogfood_check.py --since "2026-04-18 19:00"
    python scripts/dogfood_check.py --log /path/to/llm-audit.jsonl

Scenarios (matched by keywords in user_prompt_preview):
    R1 — болт M24 / M-bolt with thread   (prompt ~ "болт" + ("M24" | "резьб"))
    R2 — болт M30 + шайба                (prompt ~ "болт" + "M30" + "шайб")
    R3 — колесо                          (prompt ~ "колесо")
    R4 — простой регресс                 (prompt ~ "куб" + dimension)

For each correlation_id matching a scenario, the script collects the final
outcome (agent_success / agent_error) plus the attempt details, then prints
a punch-list report with pass/fail verdicts.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
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


@dataclass
class Run:
    correlation_id: str
    prompt: str = ""
    attempts: list[dict] = field(default_factory=list)
    final_event: str | None = None
    final_error: str | None = None
    final_error_type: str | None = None
    final_objects: list[str] = field(default_factory=list)
    start_ts: datetime | None = None


@dataclass
class Scenario:
    code: str
    title: str
    prompt_matcher: "re.Pattern[str]"
    success_check: Callable[["Run"], tuple[bool, str]]


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _to_utc_naive(dt: datetime | None) -> datetime | None:
    """Normalize datetime to naive UTC for comparison."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Treat naive input as UTC (that's what log timestamps are).
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def load_runs(log_path: Path, since: datetime | None) -> dict[str, Run]:
    """Chunk audit entries into per-prompt runs.

    Each `agent_start` event opens a new run. All subsequent events with the
    same correlation_id (until the next `agent_start`) belong to that run.
    This handles the common case where a whole NeuroCad session shares a
    single correlation_id across dozens of prompts (no automatic rotation).

    Run keys are `f"{correlation_id}#{start_ts_iso}"` so they stay unique
    within a session.
    """
    if not log_path.exists():
        print(f"ERROR: audit log not found at {log_path}", file=sys.stderr)
        sys.exit(2)

    since_utc = _to_utc_naive(since)
    runs: dict[str, Run] = {}
    # Track the latest open run per correlation_id.
    current_key_by_cid: dict[str, str] = {}

    with log_path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso(entry.get("timestamp", ""))
            if since_utc and ts:
                ts_utc = _to_utc_naive(ts)
                if ts_utc and ts_utc < since_utc:
                    continue

            cid = entry.get("correlation_id", "")
            if not cid:
                continue
            ev = entry.get("event_type", "")
            data = entry.get("data", {}) or {}

            if ev == "agent_start":
                # Open a fresh run keyed by cid + this start timestamp.
                key = f"{cid}#{ts.isoformat() if ts else 'unknown'}"
                runs[key] = Run(correlation_id=cid)
                runs[key].prompt = data.get("user_prompt_preview", "")
                runs[key].start_ts = ts
                current_key_by_cid[cid] = key
                continue

            key = current_key_by_cid.get(cid)
            if key is None or key not in runs:
                # Orphan event — no preceding agent_start in window. Skip.
                continue
            run = runs[key]

            if ev == "agent_attempt":
                run.attempts.append(data)
            elif ev == "agent_success":
                run.final_event = "success"
                run.final_objects = list(data.get("new_object_names", []) or [])
            elif ev == "agent_error":
                run.final_event = "error"
                run.final_error = str(data.get("error", "")) or None
                run.final_error_type = data.get("error_type") or None

    # Filter: keep only runs with either a prompt or at least one attempt.
    cleaned = {k: r for k, r in runs.items() if r.prompt or r.attempts}
    return cleaned


# --- Scenario matchers ------------------------------------------------------

_RE_R1 = re.compile(r"болт.*(?:m24|резьб)", re.IGNORECASE)
_RE_R2 = re.compile(r"болт.*m30.*(?:шайб|washer)|шайб.*болт.*m30", re.IGNORECASE)
_RE_R3 = re.compile(r"колесо", re.IGNORECASE)
_RE_R4 = re.compile(r"куб.*\d|шестер[её]нк", re.IGNORECASE)


def _objs_contain(objects: list[str], needles: tuple[str, ...]) -> bool:
    lower = [o.lower() for o in objects]
    return any(any(n.lower() in obj for n in needles) for obj in lower)


def check_r1(run: Run) -> tuple[bool, str]:
    if run.final_event != "success":
        return False, f"final: {run.final_event} ({run.final_error_type or run.final_error})"
    # Expect at least one bolt/thread object
    if _objs_contain(run.final_objects, ("Thread", "Bolt")):
        return True, f"success ({len(run.final_objects)} objects)"
    return False, f"success but no Thread/Bolt object: {run.final_objects[:4]}"


def check_r2(run: Run) -> tuple[bool, str]:
    if run.final_event != "success":
        return False, f"final: {run.final_event} ({run.final_error_type or run.final_error})"
    has_bolt = _objs_contain(run.final_objects, ("Thread", "Bolt"))
    has_washer = _objs_contain(run.final_objects, ("Washer", "Flange", "Ring"))
    if has_bolt and has_washer:
        return True, f"bolt+washer ({len(run.final_objects)} objects)"
    missing = []
    if not has_bolt:
        missing.append("bolt")
    if not has_washer:
        missing.append("washer")
    return False, f"success but missing {'/'.join(missing)}: {run.final_objects[:6]}"


def check_r3(run: Run) -> tuple[bool, str]:
    if run.final_event != "success":
        return False, f"final: {run.final_event} ({run.final_error_type or run.final_error})"
    if len(run.final_objects) >= 3:
        return True, f"{len(run.final_objects)} objects (wheel + spokes)"
    return False, f"only {len(run.final_objects)} objects: {run.final_objects}"


def check_r4(run: Run) -> tuple[bool, str]:
    if run.final_event != "success":
        return False, f"final: {run.final_event} ({run.final_error_type or run.final_error})"
    attempts = len(run.attempts)
    if attempts <= 2 and run.final_objects:
        return True, f"{attempts} attempt(s), {len(run.final_objects)} object(s)"
    return False, f"{attempts} attempts or no objects — expected ≤ 2"


SCENARIOS: list[Scenario] = [
    Scenario("R1", "Болт M24 / резьба", _RE_R1, check_r1),
    Scenario("R2", "Болт M30 + шайба", _RE_R2, check_r2),
    Scenario("R3", "Колесо со спицами", _RE_R3, check_r3),
    Scenario("R4", "Регрессия (куб / шестерёнка)", _RE_R4, check_r4),
]


def classify(run: Run) -> Scenario | None:
    # R2 takes priority over R1 because it also matches "болт".
    for sc in [s for s in SCENARIOS if s.code == "R2"] + \
              [s for s in SCENARIOS if s.code != "R2"]:
        if sc.prompt_matcher.search(run.prompt or ""):
            return sc
    return None


# --- Report formatting ------------------------------------------------------

def format_run(run: Run, sc: Scenario, ok: bool, detail: str) -> str:
    verdict = "PASS" if ok else "FAIL"
    ts = run.start_ts.strftime("%H:%M:%S") if run.start_ts else "??:??:??"
    cid = run.correlation_id[:8]
    return f"  [{ts}] [{cid}] {verdict}  — {detail}  (prompt: {run.prompt[:80]!r})"


def report(runs: dict[str, Run]) -> int:
    # Group by scenario
    by_scenario: dict[str, list[tuple[Run, bool, str]]] = {s.code: [] for s in SCENARIOS}
    unclassified: list[Run] = []

    for run in sorted(runs.values(), key=lambda r: r.start_ts or datetime.min):
        sc = classify(run)
        if sc is None:
            unclassified.append(run)
            continue
        ok, detail = sc.success_check(run)
        by_scenario[sc.code].append((run, ok, detail))

    # Print per-scenario summary
    total_ok = 0
    total_runs = 0
    for sc in SCENARIOS:
        items = by_scenario[sc.code]
        n = len(items)
        ok_count = sum(1 for _, ok, _ in items if ok)
        total_ok += ok_count
        total_runs += n
        header = f"{sc.code} — {sc.title}"
        if n == 0:
            print(f"{header}: нет прогонов в выборке")
        else:
            pct = int(100 * ok_count / n) if n else 0
            print(f"{header}: {ok_count}/{n} ok ({pct}%)")
            for run, ok, detail in items:
                print(format_run(run, sc, ok, detail))
        print()

    # Overall
    print("=" * 70)
    if total_runs == 0:
        print("ОБЩИЙ ИТОГ: нет релевантных прогонов")
    else:
        pct = int(100 * total_ok / total_runs)
        print(f"ОБЩИЙ ИТОГ: {total_ok}/{total_runs} ({pct}%)  "
              f"— цель Sprint 5.7: ≥ 60% на R1–R3")

    if unclassified:
        print()
        print("Не классифицировано (не R1–R4):")
        for run in unclassified[-10:]:
            ts = run.start_ts.strftime("%H:%M:%S") if run.start_ts else "??:??:??"
            print(f"  [{ts}] [{run.correlation_id[:8]}] {run.prompt[:80]!r} "
                  f"→ {run.final_event or 'no-final'}")

    return 0 if total_runs == 0 or total_ok >= total_runs * 0.6 else 1


# --- CLI --------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG,
                        help=f"audit log path (default: {DEFAULT_LOG})")
    parser.add_argument("--since", type=str, default=None,
                        help='cutoff ISO timestamp (e.g. "2026-04-18 19:00")')
    parser.add_argument("--last-minutes", type=int, default=None,
                        help="include entries from the last N minutes")
    parser.add_argument("--last-hour", action="store_true",
                        help="shortcut for --last-minutes 60 (default if nothing specified)")
    args = parser.parse_args()

    # Compute `since` — log timestamps are UTC, so work in UTC here.
    since: datetime | None = None
    if args.since:
        since = _parse_iso(args.since.replace(" ", "T"))
    elif args.last_minutes is not None:
        since = datetime.utcnow() - timedelta(minutes=args.last_minutes)
    else:
        # default: last hour (UTC)
        since = datetime.utcnow() - timedelta(minutes=60)

    if since:
        print(f"Analyzing audit log since {since.isoformat(timespec='seconds')}")
    print(f"Log: {args.log}\n")

    runs = load_runs(args.log, since=since)
    return report(runs)


if __name__ == "__main__":
    sys.exit(main())
