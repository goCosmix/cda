#!/usr/bin/env python3
"""
cda/watcher.py

Live sync daemon. Watches all VSCode storage locations and streams
updates into cda.db as they happen during a session.

What it watches:
  - chatSessions/*.jsonl          — append-only, new lines → chat_messages + fts
  - transcripts/*.jsonl           — append-only, new lines → transcript_events
  - chat-session-resources/       — new tool output files → vfs
  - chatEditingSessions/*/state.json — rewrites → vfs update
  - memory-tool/memories/**       — new/changed files → memory_files
  - state.vscdb                   — mtime change → state_items refresh

After any transcript change for a session, re-reconstructs exchanges
and refreshes fts_exchanges for that session only.

Runs as a foreground daemon. Write PID to watcher.pid.
"""

import os
import sys
import json
import gzip
import hashlib
import sqlite3
import time
import threading
import signal
import logging
from pathlib import Path
from typing import Optional

try:
    from watchfiles import watch
except ImportError:
    print("ERROR: watchfiles not installed. Run: pip install watchfiles")
    sys.exit(1)

from cda.kernel.paths import DB_PATH, PID_FILE, QUEUE_DIR, LOG_DIR, ensure_dirs
# Allow override via env var for portability
VSCODE_DATA_DIR = Path(os.environ.get("VSCODE_DATA_DIR", Path.home() / "Library/Application Support/Code/User"))
VS_ROOT   = VSCODE_DATA_DIR / "workspaceStorage"
GLOBAL_MEM = VSCODE_DATA_DIR / "globalStorage/github.copilot-chat/memory-tool/memories"

ensure_dirs()
log_file = LOG_DIR / "watcher.log"
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
    filename=str(log_file),
    filemode='a',
)
log = logging.getLogger("ark-watcher")


# ─────────────────────────────────────────────
# DB helpers
# ─────────────────────────────────────────────

def get_conn():
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.row_factory = sqlite3.Row
    return conn


def compress(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=6)


def sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def now_ms() -> int:
    return int(time.time() * 1000)


# ─────────────────────────────────────────────
# Offset tracking — so we only parse new bytes
# ─────────────────────────────────────────────

OFFSETS_SCHEMA = """
CREATE TABLE IF NOT EXISTS file_offsets (
    path         TEXT PRIMARY KEY,
    byte_offset  INTEGER DEFAULT 0,
    updated_at   INTEGER
);
"""


def get_offset(conn, path: str) -> int:
    row = conn.execute("SELECT byte_offset FROM file_offsets WHERE path=?", (path,)).fetchone()
    return row[0] if row else 0


def set_offset(conn, path: str, offset: int):
    conn.execute(
        "INSERT OR REPLACE INTO file_offsets(path, byte_offset, updated_at) VALUES(?,?,?)",
        (path, offset, now_ms())
    )


# ─────────────────────────────────────────────
# Extract workspace_id + session_id from a path
# ─────────────────────────────────────────────

def parse_path(path: Path):
    """
    Returns (workspace_id, session_id, file_type) or None.
    file_type: 'transcript' | 'chat_session' | 'tool_output' |
               'edit_state' | 'memory_workspace' | 'memory_global' | 'state_vscdb'
    """
    try:
        rel = path.relative_to(VS_ROOT)
        parts = rel.parts
        ws_id = parts[0]

        # chatSessions/<session_id>.jsonl
        if len(parts) == 3 and parts[1] == "chatSessions" and path.suffix == ".jsonl":
            return ws_id, parts[2].replace(".jsonl", ""), "chat_session"

        # GitHub.copilot-chat/transcripts/<session_id>.jsonl
        if len(parts) == 4 and parts[1] == "GitHub.copilot-chat" and parts[2] == "transcripts" and path.suffix == ".jsonl":
            return ws_id, parts[3].replace(".jsonl", ""), "transcript"

        # GitHub.copilot-chat/chat-session-resources/<session_id>/<tool_dir>/content.txt
        if len(parts) == 6 and parts[1] == "GitHub.copilot-chat" and parts[2] == "chat-session-resources" and parts[5] == "content.txt":
            return ws_id, parts[3], "tool_output"

        # chatEditingSessions/<session_id>/state.json
        if len(parts) == 4 and parts[1] == "chatEditingSessions" and parts[3] == "state.json":
            return ws_id, parts[2], "edit_state"

        # chatEditingSessions/<session_id>/contents/<blob_file>
        if len(parts) == 5 and parts[1] == "chatEditingSessions" and parts[3] == "contents":
            return ws_id, parts[2], "edit_content"

        # GitHub.copilot-chat/memory-tool/memories/**
        if len(parts) >= 5 and parts[1] == "GitHub.copilot-chat" and parts[2] == "memory-tool" and parts[3] == "memories":
            return ws_id, None, "memory_workspace"

        # state.vscdb
        if len(parts) == 2 and parts[1] == "state.vscdb":
            return ws_id, None, "state_vscdb"

    except ValueError:
        pass

    # Global memory
    try:
        path.relative_to(GLOBAL_MEM)
        return None, None, "memory_global"
    except ValueError:
        pass

    return None


# ─────────────────────────────────────────────
# Persistent Queue for Resilience
# ─────────────────────────────────────────────

def init_queue():
    """Initialize the queue directory."""
    QUEUE_DIR.mkdir(exist_ok=True)


def queue_operation(op_type: str, data: dict):
    """Write an operation to the persistent queue before executing."""
    timestamp = now_ms()
    queue_file = QUEUE_DIR / f"{timestamp}_{op_type}.json"
    try:
        queue_file.write_text(json.dumps({
            "timestamp": timestamp,
            "type": op_type,
            "data": data,
            "status": "pending"
        }))
        log.debug(f"Queued operation: {op_type}")
    except Exception as e:
        log.error(f"Failed to queue operation {op_type}: {e}")


def dequeue_operation(queue_file: Path):
    """Mark a queued operation as completed."""
    try:
        data = json.loads(queue_file.read_text())
        data["status"] = "completed"
        queue_file.write_text(json.dumps(data))
        # Rename to .completed extension
        completed_file = queue_file.with_suffix(".completed")
        queue_file.rename(completed_file)
        log.debug(f"Dequeued operation: {queue_file.name}")
    except Exception as e:
        log.error(f"Failed to dequeue {queue_file}: {e}")


def replay_queue(conn):
    """Replay any pending operations from the queue on startup."""
    if not QUEUE_DIR.exists():
        return

    pending_files = list(QUEUE_DIR.glob("*.json"))
    if not pending_files:
        return

    log.info(f"Replaying {len(pending_files)} queued operations...")

    for queue_file in sorted(pending_files):
        try:
            data = json.loads(queue_file.read_text())
            if data.get("status") == "pending":
                op_type = data["type"]
                op_data = data["data"]

                if op_type == "vfs_insert":
                    _insert_vfs(conn, op_data["path"], op_data["ws_id"], op_data["session_id"],
                              op_data["source_type"], None, op_data["filename"])
                elif op_type == "transcript_event":
                    _insert_transcript_events(conn, op_data["ws_id"], op_data["session_id"],
                                            op_data["events"])
                elif op_type in ("chat_message", "exchange_rebuild"):
                    log.warning(f"Skipping unsupported queue op type on replay: {op_type}")

                dequeue_operation(queue_file)
        except Exception as e:
            log.error(f"Failed to replay {queue_file}: {e}")


def cleanup_old_queue_files():
    """Clean up completed queue files older than 7 days."""
    if not QUEUE_DIR.exists():
        return

    cutoff = now_ms() - (7 * 24 * 60 * 60 * 1000)  # 7 days ago

    for completed_file in QUEUE_DIR.glob("*.completed"):
        try:
            data = json.loads(completed_file.read_text())
            if data.get("timestamp", 0) < cutoff:
                completed_file.unlink()
        except Exception:
            completed_file.unlink()  # Remove corrupted files


def _insert_vfs(conn, path: str, ws_id: str, session_id: str, source_type: str, content: "Optional[bytes]", filename: str):
    """Insert VFS blob - used by queue replay."""
    if content is None:
        try:
            content = Path(path).read_bytes()
        except Exception as e:
            raise RuntimeError(f"Failed to read queued VFS content from {path}: {e}") from e

    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (ws_id, session_id, source_type, path, filename,
         "jsonl", compress(content), len(content), sha256_short(content), now_ms())
    )


def _insert_transcript_events(conn, ws_id: str, session_id: str, events: list):
    """Insert transcript events - used by queue replay."""
    for event_data in events:
        conn.execute(
            """INSERT INTO transcript_events(session_id, workspace_id, event_type, request_id, turn_index, ts, data_json)
               VALUES(?,?,?,?,?,?,?)""",
            event_data
        )


# ─────────────────────────────────────────────
# Incremental JSONL parse
# ─────────────────────────────────────────────

def read_new_lines(path: Path, from_offset: int):
    """Returns (new_lines, new_offset)."""
    try:
        raw = path.read_bytes()
    except Exception:
        return [], from_offset
    new_bytes = raw[from_offset:]
    if not new_bytes:
        return [], from_offset
    text = new_bytes.decode("utf-8", errors="replace")
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    return lines, len(raw)


# ─────────────────────────────────────────────
# Handlers
# ─────────────────────────────────────────────

def handle_transcript(conn, ws_id, session_id, path: Path):
    path_str = str(path)
    offset = get_offset(conn, path_str)
    lines, new_offset = read_new_lines(path, offset)
    if not lines:
        return 0

    count = 0
    turn_index = conn.execute(
        "SELECT COALESCE(MAX(turn_index),0) FROM transcript_events WHERE session_id=?",
        (session_id,)
    ).fetchone()[0]

    events_data = []
    for line in lines:
        try:
            evt = json.loads(line)
        except Exception:
            continue
        event_type = evt.get("type", "unknown")
        request_id = evt.get("requestId") or evt.get("request_id")
        ts = evt.get("timestamp") or evt.get("ts")
        if event_type in ("assistant.turn_start", "user.message"):
            turn_index += 1
        events_data.append((session_id, ws_id, event_type, request_id, turn_index, ts, line))
        count += 1

    # Queue the transcript events operation
    queue_operation("transcript_event", {
        "ws_id": ws_id,
        "session_id": session_id,
        "events": events_data
    })

    # Execute the operations
    for event_data in events_data:
        conn.execute(
            """INSERT INTO transcript_events(session_id, workspace_id, event_type, request_id, turn_index, ts, data_json)
               VALUES(?,?,?,?,?,?,?)""",
            event_data
        )

    set_offset(conn, path_str, new_offset)

    # Queue VFS update
    queue_operation("vfs_insert", {
        "path": path_str,
        "ws_id": ws_id,
        "session_id": session_id,
        "source_type": "transcript",
        "filename": path.name
    })

    # Update VFS blob
    conn.execute(
        "DELETE FROM vfs WHERE session_id=? AND source_type='transcript'", (session_id,)
    )
    _insert_vfs(conn, path_str, ws_id, session_id, "transcript", path.read_bytes(), path.name)

    log.info(f"transcript  +{count} events  {session_id[:16]}  (total offset {new_offset})")
    return count


def handle_chat_session(conn, ws_id, session_id, path: Path):
    path_str = str(path)
    offset = get_offset(conn, path_str)
    lines, new_offset = read_new_lines(path, offset)
    if not lines:
        return 0

    count = 0
    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue
        kind = obj.get("kind")
        v = obj.get("v")
        if kind == 1 and isinstance(v, str):
            conn.execute(
                "INSERT INTO chat_messages(session_id, workspace_id, role, content, kind) VALUES(?,?,?,?,?)",
                (session_id, ws_id, "user", v, 1)
            )
            count += 1
        elif kind == 2 and isinstance(v, list):
            for req in v:
                if not isinstance(req, dict):
                    continue
                request_id = req.get("requestId")
                ts = req.get("timestamp")
                agent_id = (req.get("agent") or {}).get("id")
                conn.execute(
                    """INSERT INTO chat_messages(session_id, workspace_id, request_id, ts, role, content, agent_id, kind)
                       VALUES(?,?,?,?,?,?,?,?)""",
                    (session_id, ws_id, request_id, ts, "request_meta",
                     json.dumps(req), agent_id, 2)
                )
                count += 1

    # Update VFS blob
    raw = path.read_bytes()
    conn.execute("DELETE FROM vfs WHERE session_id=? AND source_type='chat_session'", (session_id,))
    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (ws_id, session_id, "chat_session", str(path), path.name,
         "jsonl", compress(raw), len(raw), sha256_short(raw), now_ms())
    )

    set_offset(conn, path_str, new_offset)
    log.info(f"chat_session +{count} msgs   {session_id[:16]}")
    return count


def handle_tool_output(conn, ws_id, session_id, path: Path):
    try:
        raw = path.read_bytes()
    except Exception:
        return
    # Check if already in VFS by path
    exists = conn.execute(
        "SELECT id FROM vfs WHERE source_path=? AND source_type='tool_output'", (str(path),)
    ).fetchone()
    if exists:
        return
    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (ws_id, session_id, "tool_output", str(path), path.name,
         "text", compress(raw), len(raw), sha256_short(raw), now_ms())
    )
    log.info(f"tool_output  +1         {session_id[:16]}  ({len(raw)} bytes)")


def handle_edit_state(conn, ws_id, session_id, path: Path):
    try:
        raw = path.read_bytes()
    except Exception:
        return
    conn.execute(
        "DELETE FROM vfs WHERE session_id=? AND source_type='edit_state'", (session_id,)
    )
    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (ws_id, session_id, "edit_state", str(path), path.name,
         "json", compress(raw), len(raw), sha256_short(raw), now_ms())
    )
    log.info(f"edit_state   updated    {session_id[:16]}")


def handle_edit_content(conn, ws_id, session_id, path: Path):
    try:
        raw = path.read_bytes()
    except Exception:
        conn.execute(
            "DELETE FROM vfs WHERE source_path=? AND source_type='edit_content'", (str(path),)
        )
        log.info(f"edit_content removed    {session_id[:16]} {path.name}")
        return
    conn.execute(
        "DELETE FROM vfs WHERE source_path=? AND source_type='edit_content'", (str(path),)
    )
    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (ws_id, session_id, "edit_content", str(path), path.name,
         "binary", compress(raw), len(raw), sha256_short(raw), now_ms())
    )
    log.info(f"edit_content updated    {session_id[:16]} {path.name}")


def handle_memory(conn, scope, ws_id, path: Path):
    try:
        content = path.read_text(errors="replace")
    except Exception:
        return
    conn.execute(
        """INSERT OR REPLACE INTO memory_files(scope, workspace_id, filename, content, size_bytes, ingested_at)
           VALUES(?,?,?,?,?,?)""",
        (scope, ws_id, path.name, content, path.stat().st_size, now_ms())
    )
    log.info(f"memory       updated    [{scope}] {path.name}")


def handle_state_vscdb(conn, ws_id, path: Path):
    try:
        src = sqlite3.connect(str(path), timeout=3)
        rows = src.execute("SELECT key, value FROM ItemTable").fetchall()
        src.close()
    except Exception as e:
        log.warning(f"state_vscdb  read error  {ws_id[:16]}: {e}")
        return
    for key, value in rows:
        conn.execute(
            "INSERT OR REPLACE INTO state_items(workspace_id, key, value) VALUES(?,?,?)",
            (ws_id, key, value)
        )
    log.info(f"state_vscdb  refreshed  {ws_id[:16]}  ({len(rows)} rows)")


# ─────────────────────────────────────────────
# Exchange reconstruction (incremental)
# ─────────────────────────────────────────────

from cda.pipeline.reconstruct import EXCHANGES_SCHEMA, reconstruct_session as _reconstruct_session


def rebuild_exchanges(conn, session_id: str, ws_id: str):
    """Delete and rebuild exchanges + FTS for one session."""
    conn.executescript(EXCHANGES_SCHEMA)
    conn.execute("DELETE FROM exchanges WHERE session_id=?", (session_id,))
    # Remove from FTS (content= tables auto-handle via triggers if configured,
    # but since we used content= without triggers, rebuild manually)
    n = _reconstruct_session(conn, session_id, ws_id or "unknown")

    # Refresh FTS for this session
    # FTS5 content= tables need explicit sync after content table changes
    # Use transaction for atomicity
    with conn:
        conn.execute(
            "INSERT INTO fts_exchanges(fts_exchanges, rowid, session_id, workspace_id, exchange_index, user_ts, user_message, reasoning_text, response_text, tool_calls) SELECT 'delete', id, session_id, workspace_id, exchange_index, user_ts, user_message, reasoning_text, response_text, tool_calls FROM exchanges WHERE session_id=?",  # noqa: E501
            (session_id,)
        )
        # Re-insert
        conn.execute(
            "INSERT INTO fts_exchanges(rowid, session_id, workspace_id, exchange_index, user_ts, user_message, reasoning_text, response_text, tool_calls) SELECT id, session_id, workspace_id, exchange_index, user_ts, user_message, reasoning_text, response_text, tool_calls FROM exchanges WHERE session_id=?",  # noqa: E501
            (session_id,)
        )

    log.info(f"exchanges    rebuilt    {session_id[:16]}  ({n} exchanges)")
    return n


# ─────────────────────────────────────────────
# Debounce: batch changes per session
# ─────────────────────────────────────────────

class Debouncer:
    """Collect dirty sessions and flush after DELAY seconds of quiet."""
    DELAY = 2.0

    def __init__(self, flush_fn):
        self._dirty: dict[str, tuple] = {}  # session_id → (ws_id, deadline)
        self._lock = threading.Lock()
        self._flush_fn = flush_fn
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def mark(self, session_id: str, ws_id: str):
        with self._lock:
            self._dirty[session_id] = (ws_id, time.time() + self.DELAY)

    def _loop(self):
        while True:
            time.sleep(0.5)
            now = time.time()
            with self._lock:
                ready = [(sid, ws) for sid, (ws, deadline) in self._dirty.items() if now >= deadline]
                for sid, _ in ready:
                    del self._dirty[sid]
            for sid, ws in ready:
                try:
                    self._flush_fn(sid, ws)
                except Exception as e:
                    log.error(f"flush error {sid[:16]}: {e}")


# ─────────────────────────────────────────────
# Main loop
# ─────────────────────────────────────────────

def main():
    print("STARTING WATCHER", os.environ.get('PYTHONPATH'), file=sys.stderr)
    # Initialize persistent queue
    init_queue()
    cleanup_old_queue_files()

    PID_FILE.write_text(str(os.getpid()))
    log.info(f"cda watcher started  pid={os.getpid()}")
    log.info(f"DB: {DB_PATH}")
    log.info(f"Queue: {QUEUE_DIR}")
    log.info(f"Watching: {VS_ROOT}")

    conn = get_conn()
    conn.executescript(OFFSETS_SCHEMA)
    conn.executescript(EXCHANGES_SCHEMA)
    conn.commit()

    # Ensure watcher-required schema exists before replaying operations.
    try:
        import importlib
        extract = importlib.import_module('cda.extract')
        importlib.reload(extract)
        extract.ensure_schema(conn)
    except Exception as ex:
        log.warning(f"Failed to ensure extract schema: {ex}")

    # Replay any pending operations from queue
    replay_queue(conn)

    # Initialize offsets for all existing JSONL files so we don't re-ingest
    log.info("Initializing offsets for existing files...")
    for ws_dir in VS_ROOT.iterdir():
        if not ws_dir.is_dir():
            continue
        ws_id = ws_dir.name

        # chatSessions
        cs_dir = ws_dir / "chatSessions"
        if cs_dir.is_dir():
            for f in cs_dir.glob("*.jsonl"):
                if get_offset(conn, str(f)) == 0:
                    try:
                        set_offset(conn, str(f), f.stat().st_size)
                    except Exception:
                        pass

        # transcripts
        tr_dir = ws_dir / "GitHub.copilot-chat" / "transcripts"
        if tr_dir.is_dir():
            for f in tr_dir.glob("*.jsonl"):
                if get_offset(conn, str(f)) == 0:
                    try:
                        set_offset(conn, str(f), f.stat().st_size)
                    except Exception:
                        pass

    conn.commit()
    log.info("Offsets initialized — watching for new data only")

    # Debouncer: when transcript changes, rebuild exchanges after quiet period
    def flush_exchanges(session_id, ws_id):
        c = get_conn()
        try:
            rebuild_exchanges(c, session_id, ws_id)
            c.commit()
        finally:
            c.close()
        # Incremental extraction: run behavioral signals + session analysis
        try:
            import importlib
            extract = importlib.import_module('cda.extract')
            importlib.reload(extract)
            c2 = get_conn()
            try:
                blob_row = c2.execute(
                    "SELECT content FROM vfs WHERE session_id=? AND source_type='chat_session'",
                    (session_id,)
                ).fetchone()
                if blob_row:
                    c2.execute("DELETE FROM token_usage WHERE session_id=?", (session_id,))
                    c2.execute("DELETE FROM compactions WHERE session_id=?", (session_id,))
                    c2.execute("DELETE FROM exchange_signals WHERE session_id=?", (session_id,))
                    extract.process_session(c2, session_id, blob_row[0])
                    extract.build_session_analysis(c2, session_id)
                    c2.commit()
                    try:
                        embed = importlib.import_module('cda.embed')
                        importlib.reload(embed)
                        embed.build_session_intelligence(c2, session_id)
                        c2.commit()
                    except Exception as ex2:
                        log.warning(f"embed pass failed for {session_id[:8]}: {ex2}")
            finally:
                c2.close()
        except Exception as ex:
            log.warning(f"extract pass failed for {session_id[:8]}: {ex}")

    debouncer = Debouncer(flush_exchanges)

    # Track session→workspace for debouncer
    session_ws_map: dict[str, str] = {}

    def handle_shutdown(sig, frame):
        log.info("Shutting down...")
        try:
            PID_FILE.unlink()
        except Exception:
            pass
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    watch_paths = [str(VS_ROOT), str(GLOBAL_MEM)]
    log.info(f"Watch paths: {watch_paths}")

    # Build session→workspace map from DB
    c = get_conn()
    for row in c.execute("SELECT session_id, workspace_id FROM sessions"):
        session_ws_map[row[0]] = row[1]
    c.close()

    needs_exchange_rebuild = set()  # noqa: F841 — reserved for future use
    symbol_index_dirty = False

    for changes in watch(VS_ROOT, GLOBAL_MEM, watch_filter=lambda change, path: True, yield_on_timeout=True, rust_timeout=500):
        c = get_conn()
        try:
            for change_type, path_str in changes:
                path = Path(path_str)

                # Skip SQLite WAL/SHM side files and our own DB
                if path.suffix in ('.wal', '.shm') or path == DB_PATH:
                    continue
                if 'cda.db' in path_str:
                    continue

                result = parse_path(path)
                if result is None:
                    continue

                ws_id, session_id, file_type = result

                if file_type == "transcript":
                    session_ws_map[session_id] = ws_id
                    n = handle_transcript(c, ws_id, session_id, path)
                    if n > 0:
                        debouncer.mark(session_id, ws_id)

                elif file_type == "chat_session":
                    session_ws_map[session_id] = ws_id
                    n = handle_chat_session(c, ws_id, session_id, path)
                    if n > 0:
                        debouncer.mark(session_id, ws_id)

                elif file_type == "tool_output":
                    handle_tool_output(c, ws_id, session_id, path)
                    if session_id:
                        debouncer.mark(session_id, ws_id or session_ws_map.get(session_id, "unknown"))

                elif file_type == "edit_state":
                    handle_edit_state(c, ws_id, session_id, path)
                    symbol_index_dirty = True

                elif file_type == "edit_content":
                    handle_edit_content(c, ws_id, session_id, path)
                    symbol_index_dirty = True

                elif file_type == "memory_workspace":
                    if path.is_file():
                        handle_memory(c, "workspace", ws_id, path)

                elif file_type == "memory_global":
                    if path.is_file():
                        handle_memory(c, "global", None, path)

                elif file_type == "state_vscdb":
                    handle_state_vscdb(c, ws_id, path)

            c.commit()
            if symbol_index_dirty:
                try:
                    import importlib
                    extract = importlib.import_module('cda.extract')
                    importlib.reload(extract)
                    c2 = get_conn()
                    try:
                        extract.build_symbol_index(c2)
                        c2.commit()
                    finally:
                        c2.close()
                except Exception as ex:
                    log.warning(f"symbol index rebuild failed: {ex}")
                symbol_index_dirty = False
        except Exception as e:
            log.error(f"handler error: {e}", exc_info=True)
        finally:
            c.close()


if __name__ == "__main__":
    main()
