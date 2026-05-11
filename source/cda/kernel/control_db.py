"""
cda control_db — write-side interface for control/data/control.db.

Used by:
  - selfcheck (cda check)  → writes to health table
  - sync pipeline          → writes to runs table
  - cli events             → writes to events table

The control DB lives outside the source tree at:
  <repo_root>/control/data/control.db

If the DB or its parent directory doesn't exist, all writes are silently
skipped — the control plane is optional and must not block normal operation.
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import List

PACKAGE_DIR  = Path(__file__).resolve().parent
PROJECT_DIR  = PACKAGE_DIR.parent.parent.parent
CONTROL_DB   = PROJECT_DIR / "control" / "data" / "control.db"


def _connect():
    """Open a connection to control.db, or return None if unavailable."""
    if not CONTROL_DB.exists():
        return None
    try:
        conn = sqlite3.connect(CONTROL_DB, timeout=3)
        conn.execute("PRAGMA journal_mode=WAL")
        return conn
    except Exception:
        return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── health ────────────────────────────────────────────────────────────────────

def write_health(results: List[dict], run_at: str = None):
    """
    Write a list of selfcheck result dicts to the health table.
    Each dict must have: name, passed, message.
    """
    conn = _connect()
    if conn is None:
        return
    ts = run_at or _now()
    try:
        with conn:
            conn.executemany(
                "INSERT INTO health (run_at, check_name, passed, message) VALUES (?, ?, ?, ?)",
                [(ts, r["name"], 1 if r["passed"] else 0, r.get("message", "")) for r in results],
            )
    except Exception:
        pass
    finally:
        conn.close()


# ── runs ─────────────────────────────────────────────────────────────────────

def start_run(trigger: str = "manual") -> int:
    """
    Record the start of a sync pipeline run.
    Returns the run id (for passing to finish_run), or -1 on failure.
    """
    conn = _connect()
    if conn is None:
        return -1
    try:
        with conn:
            cur = conn.execute(
                "INSERT INTO runs (started_at, trigger) VALUES (?, ?)",
                (_now(), trigger),
            )
            return cur.lastrowid
    except Exception:
        return -1
    finally:
        conn.close()


def finish_run(run_id: int, stages: list[str], counts: dict, errors: int = 0,
               exit_code: int = 0, notes: str = None):
    """
    Update a run record on completion.
    counts dict: sessions, exchanges, tool_calls, vfs_files
    """
    if run_id < 0:
        return
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            conn.execute(
                """UPDATE runs SET
                    finished_at = ?,
                    stages      = ?,
                    sessions    = ?,
                    exchanges   = ?,
                    tool_calls  = ?,
                    vfs_files   = ?,
                    errors      = ?,
                    exit_code   = ?,
                    notes       = ?
                WHERE id = ?""",
                (
                    _now(),
                    ",".join(stages),
                    counts.get("sessions"),
                    counts.get("exchanges"),
                    counts.get("tool_calls"),
                    counts.get("vfs_files"),
                    errors,
                    exit_code,
                    notes,
                    run_id,
                ),
            )
    except Exception:
        pass
    finally:
        conn.close()


# ── events ────────────────────────────────────────────────────────────────────

def log_event(kind: str, subject: str = None, detail: str = None, actor: str = "cda"):
    """
    Append a single event to the events table.
    kind examples: watcher.start, watcher.stop, sync.complete, version.bump
    """
    conn = _connect()
    if conn is None:
        return
    try:
        with conn:
            conn.execute(
                "INSERT INTO events (occurred_at, kind, actor, subject, detail) VALUES (?, ?, ?, ?, ?)",
                (_now(), kind, actor, subject, detail),
            )
    except Exception:
        pass
    finally:
        conn.close()
