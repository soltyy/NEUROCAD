"""Sprint 5.7 — tests for the dog-food log analyzer (scripts/dogfood_check.py).

Feeds the script a synthetic audit log and verifies that the R1–R4
classifier and success checks return the expected verdicts, so we know
the report is trustworthy before using it on real dog-food data.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

# Dynamically load scripts/dogfood_check.py as a module (not a package member).
# Register in sys.modules *before* exec so @dataclass resolves module globals.
_SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "dogfood_check.py"
_spec = importlib.util.spec_from_file_location("dogfood_check", _SCRIPT_PATH)
assert _spec and _spec.loader
dogfood = importlib.util.module_from_spec(_spec)
sys.modules["dogfood_check"] = dogfood
_spec.loader.exec_module(dogfood)


def _entry(ts: datetime, cid: str, event: str, **data):
    return {
        "timestamp": ts.isoformat() + "Z",
        "correlation_id": cid,
        "event_type": event,
        "data": data,
    }


def _write_log(path: Path, entries: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _run_by_cid(runs: dict, cid: str):
    """Return the (first) run that has this correlation_id. Tests use this
    instead of `runs[cid]` because keys are now f'{cid}#{start_ts}'.
    """
    for r in runs.values():
        if r.correlation_id == cid:
            return r
    return None


def _has_cid(runs: dict, cid: str) -> bool:
    return _run_by_cid(runs, cid) is not None


def test_classify_r1_bolt_m24(tmp_path: Path):
    log = tmp_path / "llm-audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c1", "agent_start", user_prompt_preview="Сделай болт M24 по ISO с резьбой"),
        _entry(now, "c1", "agent_attempt", attempt=1, ok=True, new_object_names=["BoltBody", "ThreadedBolt"]),
        _entry(now, "c1", "agent_success", attempts=1, new_object_names=["BoltBody", "ThreadedBolt"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c1")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc is not None
    assert sc.code == "R1"
    ok, detail = sc.success_check(run)
    assert ok, detail


def test_classify_r2_bolt_m30_with_washer(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c2", "agent_start", user_prompt_preview="Сделай сложный болт M30 с резьбой и шайбой"),
        _entry(now, "c2", "agent_attempt", attempt=1, ok=True,
               new_object_names=["BoltBody", "ThreadedBolt", "Washer"]),
        _entry(now, "c2", "agent_success", attempts=1,
               new_object_names=["BoltBody", "ThreadedBolt", "Washer"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c2")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc is not None
    assert sc.code == "R2", f"expected R2, got {sc.code}"
    ok, detail = sc.success_check(run)
    assert ok, detail


def test_r2_fails_when_no_washer(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c3", "agent_start",
               user_prompt_preview="Сделай сложный болт M30 с резьбой и шайбой"),
        _entry(now, "c3", "agent_success", attempts=1,
               new_object_names=["BoltBody", "ThreadedBolt"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c3")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R2"
    ok, detail = sc.success_check(run)
    assert not ok
    assert "washer" in detail.lower()


def test_classify_r3_wheel(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c4", "agent_start", user_prompt_preview="Сделай колесо велосипеда со спицами"),
        _entry(now, "c4", "agent_success", attempts=2,
               new_object_names=["Hub", "Rim", "Spokes", "WheelAssembly"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c4")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R3"
    ok, detail = sc.success_check(run)
    assert ok, detail


def test_classify_r4_cube_regression(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c5", "agent_start", user_prompt_preview="Сделай куб 50x50x50"),
        _entry(now, "c5", "agent_attempt", attempt=1, ok=True, new_object_names=["Box"]),
        _entry(now, "c5", "agent_success", attempts=1, new_object_names=["Box"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c5")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R4"
    ok, detail = sc.success_check(run)
    assert ok, detail


def test_r4_fails_when_too_many_attempts(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c6", "agent_start", user_prompt_preview="Сделай куб 20x20x20"),
        _entry(now, "c6", "agent_attempt", attempt=1, ok=False),
        _entry(now, "c6", "agent_attempt", attempt=2, ok=False),
        _entry(now, "c6", "agent_attempt", attempt=3, ok=True, new_object_names=["Box"]),
        _entry(now, "c6", "agent_success", attempts=3, new_object_names=["Box"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c6")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R4"
    ok, detail = sc.success_check(run)
    assert not ok
    assert "≤ 2" in detail or "3 attempts" in detail


def test_agent_error_is_reported_as_fail(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c7", "agent_start", user_prompt_preview="Сделай болт M24 по ISO"),
        _entry(now, "c7", "agent_error", error_type="max_retries_exhausted",
               error="Max retries exceeded: Shape is null"),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c7")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R1"
    ok, detail = sc.success_check(run)
    assert not ok
    assert "max_retries_exhausted" in detail or "error" in detail.lower()


def test_cancelled_is_reported_as_fail(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c8", "agent_start", user_prompt_preview="Сделай колесо велосипеда"),
        _entry(now, "c8", "agent_error", error_type="cancelled_by_user",
               error="Cancelled by user"),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c8")
    assert run is not None
    sc = dogfood.classify(run)
    assert sc.code == "R3"
    ok, detail = sc.success_check(run)
    assert not ok
    assert "cancelled_by_user" in detail or "cancelled" in detail.lower()


def test_since_cutoff_excludes_old_entries(tmp_path: Path):
    """Entries before `since` must be filtered out."""
    log = tmp_path / "audit.jsonl"
    old = datetime.utcnow() - timedelta(hours=2)
    new = datetime.utcnow()
    _write_log(log, [
        _entry(old, "old", "agent_start", user_prompt_preview="Сделай куб 10x10x10"),
        _entry(old, "old", "agent_success", attempts=1, new_object_names=["Box"]),
        _entry(new, "fresh", "agent_start", user_prompt_preview="Сделай куб 50x50x50"),
        _entry(new, "fresh", "agent_success", attempts=1, new_object_names=["Box"]),
    ])
    runs = dogfood.load_runs(log, since=datetime.utcnow() - timedelta(minutes=30))
    assert _has_cid(runs, "fresh")
    assert not _has_cid(runs, "old")


def test_tz_aware_since_normalizes_to_utc(tmp_path: Path):
    """Sprint 5.7: timezone-aware `since` must be converted to UTC for
    comparison. Log timestamps are written as UTC (trailing Z); if the caller
    passes a tz-aware `since` in e.g. UTC+3, naive stripping without conversion
    would wrongly exclude entries from the last hour.
    """
    from datetime import timezone
    log = tmp_path / "audit.jsonl"
    # Write an entry 30 minutes ago UTC.
    entry_utc = datetime.utcnow() - timedelta(minutes=30)
    _write_log(log, [
        _entry(entry_utc, "c1", "agent_start", user_prompt_preview="Сделай куб 10x10x10"),
        _entry(entry_utc, "c1", "agent_success", attempts=1, new_object_names=["Box"]),
    ])
    # Caller provides a tz-aware `since` expressed in UTC+3 but representing
    # the same moment as "1 hour ago UTC". The entry is 30 min old UTC, so
    # it must be INCLUDED (newer than the cutoff).
    since_plus3 = (datetime.utcnow() - timedelta(hours=1)).replace(
        tzinfo=timezone.utc
    ).astimezone(timezone(timedelta(hours=3)))
    runs = dogfood.load_runs(log, since=since_plus3)
    assert _has_cid(runs, "c1"), "tz-aware since should be normalized to UTC"


def test_unrelated_prompt_is_unclassified(tmp_path: Path):
    log = tmp_path / "audit.jsonl"
    now = datetime.utcnow()
    _write_log(log, [
        _entry(now, "c9", "agent_start", user_prompt_preview="Сделай чашку"),
        _entry(now, "c9", "agent_success", attempts=1, new_object_names=["Cup"]),
    ])
    runs = dogfood.load_runs(log, since=now - timedelta(minutes=5))
    run = _run_by_cid(runs, "c9")
    assert run is not None
    assert dogfood.classify(run) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
