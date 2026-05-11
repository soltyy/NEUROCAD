#!/usr/bin/env python3
"""Audit-log analytics: compare v1 (legacy) vs v2 (plan-driven) agent stats.

Used during the post-Sprint-6.0 observation period to decide when to flip
the default of `use_agent_v2` from False → True. Criteria (proposed):

    1. v2 success rate ≥ v1 success rate, OR not statistically worse
       (Wilson 95 % CI overlap acceptable)
    2. v2 mean prompt tokens per success ≤ 0.5 × v1 mean
    3. v2 has ≥ 30 sessions (statistically meaningful)
    4. No new error categories unique to v2 in the last 7 days

Usage:
    python scripts/v2_observability.py
    python scripts/v2_observability.py --since 2026-05-01
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path


DEFAULT_LOG = (
    Path.home()
    / "Library" / "Application Support" / "FreeCAD"
    / "v1-1" / "neurocad" / "logs" / "llm-audit.jsonl"
)


def _parse_iso(ts: str) -> datetime | None:
    if not ts:
        return None
    if ts.endswith("Z"):
        ts = ts[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(ts)
    except ValueError:
        return None


def _to_naive_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def collect(log_path: Path, since: datetime | None):
    """Group entries into runs keyed by correlation_id + agent variant.

    Returns dict {variant: {"runs": int, "success": int, "fail": int,
                            "tokens_per_success": list[int]}}
    """
    runs: dict[tuple[str, str], dict] = {}     # (variant, cid) → run dict
    since_utc = _to_naive_utc(since)
    if not log_path.exists():
        print(f"audit log not found: {log_path}", file=sys.stderr)
        return {}
    with log_path.open(encoding="utf-8") as f:
        for line in f:
            try:
                e = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = _parse_iso(e.get("timestamp", ""))
            ts_utc = _to_naive_utc(ts)
            if since_utc and ts_utc and ts_utc < since_utc:
                continue
            ev = e.get("event_type", "")
            cid = e.get("correlation_id", "")
            data = e.get("data", {}) or {}
            if ev in ("agent_start", "agent_v2_start"):
                variant = "v2" if "v2" in ev else "v1"
                key = (variant, f"{cid}#{ts_utc.isoformat() if ts_utc else 'no_ts'}")
                runs[key] = {
                    "variant": variant,
                    "start_ts": ts_utc,
                    "prompt": data.get("user_prompt_preview", ""),
                    "outcome": None,
                    "tokens": None,
                    "n_attempts": 0,
                }
            elif ev in ("agent_attempt",):
                # Find most-recent run with this cid
                for key in reversed(list(runs.keys())):
                    if key[1].startswith(cid):
                        runs[key]["n_attempts"] = max(runs[key]["n_attempts"], 1) + (
                            1 if data.get("ok") else 1
                        )
                        if data.get("ok"):
                            runs[key]["tokens"] = data.get("prompt_tokens")
                        break
            elif ev in ("agent_success",):
                for key in reversed(list(runs.keys())):
                    if key[1].startswith(cid) and runs[key]["outcome"] is None:
                        runs[key]["outcome"] = "success"
                        if data.get("prompt_tokens"):
                            runs[key]["tokens"] = data["prompt_tokens"]
                        break
            elif ev in ("agent_error",):
                for key in reversed(list(runs.keys())):
                    if key[1].startswith(cid) and runs[key]["outcome"] is None:
                        runs[key]["outcome"] = "fail"
                        runs[key]["error"] = data.get("error", "")[:160]
                        break
            elif ev == "agent_v2_done":
                for key in reversed(list(runs.keys())):
                    if key[1].startswith(cid) and key[0] == "v2" and runs[key]["outcome"] is None:
                        runs[key]["outcome"] = "success" if data.get("ok") else "fail"
                        runs[key]["n_attempts"] = sum(
                            int(v) for v in (data.get("attempts_per_step") or {}).values()
                        ) or 1
                        break
    return runs


def summarize(runs: dict):
    by_variant: dict[str, dict] = defaultdict(
        lambda: {"runs": 0, "success": 0, "fail": 0, "incomplete": 0,
                  "tokens_total": 0, "n_with_tokens": 0,
                  "attempts": Counter()}
    )
    for run in runs.values():
        v = run["variant"]
        s = by_variant[v]
        s["runs"] += 1
        out = run["outcome"] or "incomplete"
        s[out] += 1
        if run["tokens"]:
            s["tokens_total"] += int(run["tokens"])
            s["n_with_tokens"] += 1
        s["attempts"][run["n_attempts"]] += 1
    return by_variant


def _wilson_ci(success: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return 0.0, 1.0
    p = success / total
    denom = 1 + z**2 / total
    centre = (p + z**2 / (2 * total)) / denom
    halfwidth = z * math.sqrt(p * (1 - p) / total + z**2 / (4 * total**2)) / denom
    return max(0.0, centre - halfwidth), min(1.0, centre + halfwidth)


def report(by_variant: dict):
    if not by_variant:
        print("no runs in window")
        return 0
    for v in ("v1", "v2"):
        s = by_variant.get(v)
        if not s:
            print(f"{v}: 0 runs in window")
            continue
        succ_rate = s["success"] / s["runs"] if s["runs"] else 0.0
        lo, hi = _wilson_ci(s["success"], s["runs"])
        avg_tokens = (
            s["tokens_total"] / s["n_with_tokens"]
            if s["n_with_tokens"] > 0 else 0.0
        )
        print(f"{v}: runs={s['runs']:4d}  success={s['success']:4d} ({succ_rate*100:5.1f}%) "
              f"CI=[{lo*100:5.1f}%,{hi*100:5.1f}%]  fail={s['fail']:3d}  "
              f"incomplete={s['incomplete']:3d}  avg_prompt_tokens={avg_tokens:7.0f}")
    v1 = by_variant.get("v1") or {"success": 0, "runs": 0,
                                  "tokens_total": 0, "n_with_tokens": 0}
    v2 = by_variant.get("v2") or {"success": 0, "runs": 0,
                                  "tokens_total": 0, "n_with_tokens": 0}
    print()
    if v2["runs"] >= 30:
        v1_rate = v1["success"] / v1["runs"] if v1["runs"] else 0.0
        v2_rate = v2["success"] / v2["runs"] if v2["runs"] else 0.0
        v1_avg = (v1["tokens_total"] / v1["n_with_tokens"]
                   if v1["n_with_tokens"] else 0.0)
        v2_avg = (v2["tokens_total"] / v2["n_with_tokens"]
                   if v2["n_with_tokens"] else 0.0)
        criteria = [
            ("v2 success rate ≥ v1", v2_rate >= v1_rate * 0.95,
             f"{v2_rate*100:.1f}% vs {v1_rate*100:.1f}%"),
            ("v2 avg tokens ≤ 0.5×v1",
             v1_avg > 0 and v2_avg <= 0.5 * v1_avg,
             f"v2={v2_avg:.0f}, v1={v1_avg:.0f}"),
            ("v2 has ≥ 30 sessions", v2["runs"] >= 30, str(v2["runs"])),
        ]
        print("Default-flip criteria:")
        for label, ok, note in criteria:
            mark = "✓" if ok else "✗"
            print(f"  [{mark}] {label}  ({note})")
        all_ok = all(ok for _, ok, _ in criteria)
        print()
        if all_ok:
            print("VERDICT: ready to flip `use_agent_v2` default to True.")
            return 0
        print("VERDICT: keep `use_agent_v2` default False until criteria met.")
    else:
        print(f"v2 has only {v2['runs']} runs — need ≥30 for statistical confidence.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--log", type=Path, default=DEFAULT_LOG)
    p.add_argument("--since", type=str, default=None,
                   help='ISO date, e.g. 2026-05-01')
    p.add_argument("--last-days", type=int, default=None)
    args = p.parse_args()
    since: datetime | None = None
    if args.since:
        since = _parse_iso(args.since.replace(" ", "T"))
    elif args.last_days:
        since = datetime.utcnow() - timedelta(days=args.last_days)
    runs = collect(args.log, since)
    return report(summarize(runs))


if __name__ == "__main__":
    sys.exit(main())
