#!/usr/bin/env python3
"""One-shot migration: load existing JSONL audit log into SQLite (Sprint 6.2+).

Usage:
    .venv/bin/python scripts/audit_migrate.py
    .venv/bin/python scripts/audit_migrate.py --jsonl <path> --db <path>

By default migrates the production log at
    ~/Library/Application Support/FreeCAD/v1-1/neurocad/logs/llm-audit.jsonl
into
    ~/Library/Application Support/FreeCAD/v1-1/neurocad/logs/audit-events.db

Idempotent — re-running it skips already-imported rows (matched by
timestamp + event_type pair).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


DEFAULT_JSONL = (
    Path.home() / "Library" / "Application Support" / "FreeCAD"
    / "v1-1" / "neurocad" / "logs" / "llm-audit.jsonl"
)
DEFAULT_DB = DEFAULT_JSONL.parent / "audit-events.db"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--jsonl", type=Path, default=DEFAULT_JSONL)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    args = p.parse_args()
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from neurocad.core.audit_db import migrate_jsonl_to_sqlite, counts_by_state
    if not args.jsonl.exists():
        print(f"jsonl not found: {args.jsonl}", file=sys.stderr)
        return 2
    print(f"Migrating {args.jsonl} → {args.db}")
    inserted, skipped = migrate_jsonl_to_sqlite(args.jsonl, args.db)
    print(f"  inserted: {inserted}")
    print(f"  skipped (already present): {skipped}")
    print()
    print("State distribution in DB:")
    states = counts_by_state()
    for state, n in sorted(states.items()):
        print(f"  {state:30s} : {n}")
    print(f"  total                          : {sum(states.values())}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
