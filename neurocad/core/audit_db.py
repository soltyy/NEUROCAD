"""SQLite-backed audit log (Sprint 6.2+).

Replaces the JSONL `llm-audit.jsonl` as the source of truth. Why SQLite:

  * Indexed queries by timestamp / correlation_id / event_type — orders of
    magnitude faster than re-parsing JSONL on each `dogfood_check.py` run.
  * `processing_state` updates are an UPDATE, not a tmp-file rewrite.
  * ACID transactions: an interrupted write leaves the DB consistent.
  * Concurrent readers (CLI tools + UI) while the worker is writing.
  * stdlib — no new dependency.

Backward compatibility:
  * `audit.audit_log(...)` continues to write to JSONL as a redundancy /
    archive (so existing dogfood_check.py and other readers keep working
    during the transition).
  * `migrate_jsonl_to_sqlite(jsonl_path, db_path)` is a one-shot CLI helper
    that loads an existing JSONL into the SQLite DB.

Schema:
    CREATE TABLE audit_events (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,                   -- ISO-8601 UTC microseconds
        correlation_id TEXT,
        event_type TEXT NOT NULL,
        processing_state TEXT NOT NULL DEFAULT 'new',
        data_json TEXT NOT NULL                    -- sanitized payload as JSON
    )
    + indexes on (timestamp), (correlation_id), (event_type), (processing_state)
"""

from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any


SCHEMA = """
CREATE TABLE IF NOT EXISTS audit_events (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp        TEXT NOT NULL,
    correlation_id   TEXT,
    event_type       TEXT NOT NULL,
    processing_state TEXT NOT NULL DEFAULT 'new',
    data_json        TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_audit_ts    ON audit_events(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_cid   ON audit_events(correlation_id);
CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_state ON audit_events(processing_state);
"""


# Module-level state — one DB connection per process; SQLite handles
# threading via `check_same_thread=False`, all writes serialised through
# `_DB_LOCK`.
_DB_CONN: sqlite3.Connection | None = None
_DB_PATH: Path | None = None
_DB_LOCK = threading.Lock()


def init(db_path: Path) -> None:
    """Open or create the audit-events SQLite database at `db_path`.

    Idempotent — safe to call multiple times.
    """
    global _DB_CONN, _DB_PATH
    db_path = Path(db_path)
    if _DB_CONN is not None and _DB_PATH == db_path:
        return
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(
        str(db_path),
        check_same_thread=False,    # writes/reads from Qt worker + main thread
        isolation_level=None,        # autocommit; we wrap explicit transactions
    )
    conn.row_factory = sqlite3.Row
    with _DB_LOCK:
        conn.executescript(SCHEMA)
    _DB_CONN = conn
    _DB_PATH = db_path


def close() -> None:
    global _DB_CONN, _DB_PATH
    with _DB_LOCK:
        if _DB_CONN is not None:
            try:
                _DB_CONN.close()
            except Exception:
                pass
        _DB_CONN = None
        _DB_PATH = None


def is_enabled() -> bool:
    return _DB_CONN is not None


def insert_event(
    *,
    timestamp: str,
    event_type: str,
    correlation_id: str | None,
    processing_state: str,
    data: dict[str, Any],
) -> None:
    if _DB_CONN is None:
        return
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    with _DB_LOCK:
        _DB_CONN.execute(
            "INSERT INTO audit_events "
            "(timestamp, correlation_id, event_type, processing_state, data_json) "
            "VALUES (?, ?, ?, ?, ?)",
            (timestamp, correlation_id, event_type, processing_state, payload),
        )


def update_processing_state(
    new_state: str,
    *,
    timestamp: str | None = None,
    correlation_id: str | None = None,
    event_type: str | None = None,
) -> int:
    """UPDATE audit_events SET processing_state = ? WHERE (filters…).
    Returns affected row count."""
    if _DB_CONN is None:
        return 0
    clauses: list[str] = []
    params: list[Any] = [new_state]
    if timestamp is not None:
        clauses.append("timestamp = ?")
        params.append(timestamp)
    if correlation_id is not None:
        clauses.append("correlation_id = ?")
        params.append(correlation_id)
    if event_type is not None:
        clauses.append("event_type = ?")
        params.append(event_type)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    with _DB_LOCK:
        cur = _DB_CONN.execute(
            f"UPDATE audit_events SET processing_state = ?{where}",
            params,
        )
        return int(cur.rowcount or 0)


def query(
    *,
    event_type: str | None = None,
    correlation_id: str | None = None,
    since_ts: str | None = None,
    processing_state: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Read-only query. Returns list of dicts with keys:
        timestamp, correlation_id, event_type, processing_state, data."""
    if _DB_CONN is None:
        return []
    clauses: list[str] = []
    params: list[Any] = []
    if event_type is not None:
        clauses.append("event_type = ?")
        params.append(event_type)
    if correlation_id is not None:
        clauses.append("correlation_id = ?")
        params.append(correlation_id)
    if since_ts is not None:
        clauses.append("timestamp >= ?")
        params.append(since_ts)
    if processing_state is not None:
        clauses.append("processing_state = ?")
        params.append(processing_state)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    limit_sql = f" LIMIT {int(limit)}" if limit else ""
    with _DB_LOCK:
        rows = _DB_CONN.execute(
            f"SELECT timestamp, correlation_id, event_type, processing_state, "
            f"data_json FROM audit_events{where} ORDER BY id ASC{limit_sql}",
            params,
        ).fetchall()
    result = []
    for r in rows:
        try:
            data = json.loads(r["data_json"]) if r["data_json"] else {}
        except Exception:
            data = {}
        result.append({
            "timestamp": r["timestamp"],
            "correlation_id": r["correlation_id"],
            "event_type": r["event_type"],
            "processing_state": r["processing_state"],
            "data": data,
        })
    return result


def counts_by_state() -> dict[str, int]:
    if _DB_CONN is None:
        return {}
    with _DB_LOCK:
        rows = _DB_CONN.execute(
            "SELECT processing_state, COUNT(*) as n FROM audit_events "
            "GROUP BY processing_state"
        ).fetchall()
    return {r["processing_state"]: int(r["n"]) for r in rows}


def migrate_jsonl_to_sqlite(jsonl_path: Path, db_path: Path,
                             *, skip_existing: bool = True) -> tuple[int, int]:
    """One-shot helper: read each line of `jsonl_path`, insert into the
    SQLite DB at `db_path`. Returns (inserted, skipped).

    With `skip_existing=True`, rows that already exist (matched by
    timestamp + event_type) are not duplicated — re-running the migration
    is idempotent.
    """
    jsonl_path = Path(jsonl_path)
    db_path = Path(db_path)
    if not jsonl_path.exists():
        return (0, 0)
    init(db_path)
    inserted = 0
    skipped = 0
    seen: set[tuple[str, str]] = set()
    if skip_existing:
        with _DB_LOCK:
            rows = _DB_CONN.execute(
                "SELECT timestamp, event_type FROM audit_events"
            ).fetchall()
        for r in rows:
            seen.add((r["timestamp"], r["event_type"]))
    with _DB_LOCK:
        _DB_CONN.execute("BEGIN")
    try:
        with jsonl_path.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue
                ts = entry.get("timestamp", "")
                ev = entry.get("event_type", "")
                if not ts or not ev:
                    continue
                key = (ts, ev)
                if skip_existing and key in seen:
                    skipped += 1
                    continue
                cid = entry.get("correlation_id")
                state = entry.get("processing_state", "new")
                data = entry.get("data", {}) or {}
                payload = json.dumps(data, ensure_ascii=False,
                                     separators=(",", ":"))
                with _DB_LOCK:
                    _DB_CONN.execute(
                        "INSERT INTO audit_events "
                        "(timestamp, correlation_id, event_type, "
                        "processing_state, data_json) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (ts, cid, ev, state, payload),
                    )
                seen.add(key)
                inserted += 1
        with _DB_LOCK:
            _DB_CONN.execute("COMMIT")
    except Exception:
        with _DB_LOCK:
            _DB_CONN.execute("ROLLBACK")
        raise
    return (inserted, skipped)


def default_db_path() -> Path:
    """Resolve the canonical audit-events.db location: same directory as
    the legacy llm-audit.jsonl."""
    from ..config.config import _get_config_dir
    return _get_config_dir() / "logs" / "audit-events.db"
