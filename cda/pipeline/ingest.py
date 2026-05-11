#!/usr/bin/env python3
"""
cda/ingest.py

Extracts all VSCode/Copilot session data into a local SQLite database.

Storage locations ingested per workspace/session:
  1. transcripts/*.jsonl         — Copilot transcript event stream
  2. chatSessions/*.jsonl        — VS Code chat UI state (kind 0/1/2)
  3. chatEditingSessions/*/state.json    — file edit checkpoints
  4. chatEditingSessions/*/contents/*   — versioned file content blobs
  5. chat-session-resources/*/*/content.txt — tool output payloads
  6. debug-logs/*/models.json    — model catalog at session start
  7. debug-logs/*/main.jsonl     — minimal debug events
  8. state.vscdb ItemTable       — VS Code workspace state (parsed, not blobbed)
  9. memory-tool/ (workspace)    — workspace-scoped memory files
 10. globalStorage/.../memories/ — global memory files (once, not per-workspace)
"""

import os
import json
import sqlite3
import gzip
import hashlib
import time
import logging
from pathlib import Path

from cda.kernel.paths import DB_PATH, ensure_dirs

# Ensure local dirs are present before writing
ensure_dirs()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("ark-ingest")

HOME        = Path.home()
# Allow override via env var for portability
VSCODE_DATA_DIR = Path(os.environ.get("VSCODE_DATA_DIR", HOME / "Library/Application Support/Code/User"))
VS_STORAGE  = VSCODE_DATA_DIR / "workspaceStorage"
GLOBAL_MEM  = VSCODE_DATA_DIR / "globalStorage/github.copilot-chat/memory-tool/memories"

# Large index DBs — too big to blob, record path only
SKIP_BLOB_PATTERNS = ["workspace-chunks.db", "local-index"]

NOW_MS = int(time.time() * 1000)


# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def sha256_short(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


def compress(data: bytes) -> bytes:
    return gzip.compress(data, compresslevel=6)


def read_bytes(path):
    try:
        return Path(path).read_bytes()
    except Exception as e:
        log.warning(f"Failed to read bytes from {path}: {e}")
        return None


def read_json(path):
    try:
        return json.loads(Path(path).read_text())
    except Exception as e:
        log.warning(f"Failed to read JSON from {path}: {e}")
        return None


def log_ingest(conn, workspace_id, session_id, source_type, status, message=""):
    conn.execute(
        "INSERT INTO ingest_log(workspace_id, session_id, source_type, status, message, at) VALUES(?,?,?,?,?,?)",
        (workspace_id, session_id, source_type, status, message, NOW_MS)
    )


# ─────────────────────────────────────────────
# SCHEMA
# ─────────────────────────────────────────────

SCHEMA = """
CREATE TABLE IF NOT EXISTS workspaces (
    workspace_id  TEXT PRIMARY KEY,
    uri           TEXT,
    name          TEXT,
    type          TEXT,       -- 'workspace' | 'folder' | 'unknown'
    session_count INTEGER DEFAULT 0,
    ingested_at   INTEGER
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id       TEXT PRIMARY KEY,
    workspace_id     TEXT,
    title            TEXT,
    created_at       INTEGER,
    last_message_at  INTEGER,
    request_count    INTEGER DEFAULT 0,
    response_state   INTEGER,
    initial_location TEXT,
    ingested_at      INTEGER,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(workspace_id)
);

-- Which of the 14 locations exist for each session + sizes
CREATE TABLE IF NOT EXISTS session_storage (
    session_id               TEXT PRIMARY KEY,
    workspace_id             TEXT,
    has_transcript           INTEGER DEFAULT 0,
    transcript_size          INTEGER DEFAULT 0,
    has_chat_session         INTEGER DEFAULT 0,
    chat_session_size        INTEGER DEFAULT 0,
    has_edit_session         INTEGER DEFAULT 0,
    edit_state_size          INTEGER DEFAULT 0,
    edit_content_count       INTEGER DEFAULT 0,
    has_tool_outputs         INTEGER DEFAULT 0,
    tool_output_count        INTEGER DEFAULT 0,
    has_debug_log            INTEGER DEFAULT 0,
    debug_models_size        INTEGER DEFAULT 0,
    in_state_vscdb           INTEGER DEFAULT 0,
    has_workspace_memory     INTEGER DEFAULT 0,
    workspace_memory_count   INTEGER DEFAULT 0,
    semantic_index_path      TEXT,
    fulltext_index_path      TEXT
);

-- Blob VFS — raw file content, gzip-compressed
CREATE TABLE IF NOT EXISTS vfs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  TEXT,
    session_id    TEXT,
    source_type   TEXT,    -- transcript | chat_session | edit_state | edit_content |
                           -- tool_output | debug_models | debug_main | memory_global | memory_workspace
    source_path   TEXT,    -- original path on disk
    filename      TEXT,    -- basename
    content_type  TEXT,    -- jsonl | json | text | binary
    content       BLOB,    -- gzip-compressed raw bytes
    size_bytes    INTEGER, -- original uncompressed size
    sha256        TEXT,
    ingested_at   INTEGER
);
CREATE INDEX IF NOT EXISTS vfs_session    ON vfs(session_id);
CREATE INDEX IF NOT EXISTS vfs_type       ON vfs(source_type);
CREATE INDEX IF NOT EXISTS vfs_workspace  ON vfs(workspace_id);

-- Parsed transcript events (from transcripts/*.jsonl)
CREATE TABLE IF NOT EXISTS transcript_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id  TEXT,
    workspace_id TEXT,
    event_type  TEXT,
    request_id  TEXT,
    turn_index  INTEGER,
    ts          INTEGER,
    data_json   TEXT
);
CREATE INDEX IF NOT EXISTS te_session ON transcript_events(session_id);
CREATE INDEX IF NOT EXISTS te_type    ON transcript_events(event_type);
CREATE INDEX IF NOT EXISTS te_request ON transcript_events(request_id);

-- Parsed chat messages (from chatSessions kind=1 user text + kind=2 request entries)
CREATE TABLE IF NOT EXISTS chat_messages (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id   TEXT,
    workspace_id TEXT,
    request_id   TEXT,
    ts           INTEGER,
    role         TEXT,     -- 'user' | 'assistant' | 'request_meta'
    content      TEXT,
    agent_id     TEXT,
    kind         INTEGER   -- original chatSessions kind
);
CREATE INDEX IF NOT EXISTS cm_session ON chat_messages(session_id);
CREATE INDEX IF NOT EXISTS cm_request ON chat_messages(request_id);

-- state.vscdb ItemTable rows per workspace
CREATE TABLE IF NOT EXISTS state_items (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  TEXT,
    key           TEXT,
    value         TEXT,
    UNIQUE(workspace_id, key)
);
CREATE INDEX IF NOT EXISTS si_workspace ON state_items(workspace_id);
CREATE INDEX IF NOT EXISTS si_key       ON state_items(key);

-- Memory files (global + workspace-scoped)
CREATE TABLE IF NOT EXISTS memory_files (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    scope         TEXT,    -- 'global' | 'workspace' | 'session' | 'repo'
    workspace_id  TEXT,
    session_id    TEXT,
    filename      TEXT,
    content       TEXT,
    size_bytes    INTEGER,
    ingested_at   INTEGER
);

-- Ingest audit trail
CREATE TABLE IF NOT EXISTS ingest_log (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id  TEXT,
    session_id    TEXT,
    source_type   TEXT,
    status        TEXT,    -- 'ok' | 'skip' | 'error'
    message       TEXT,
    at            INTEGER
);
"""


# ─────────────────────────────────────────────
# VFS INSERT
# ─────────────────────────────────────────────

def vfs_insert(conn, workspace_id, session_id, source_type, source_path, content_type, raw: bytes):
    compressed = compress(raw)
    h = sha256_short(raw)
    filename = Path(source_path).name
    conn.execute(
        """INSERT INTO vfs(workspace_id, session_id, source_type, source_path, filename,
                           content_type, content, size_bytes, sha256, ingested_at)
           VALUES(?,?,?,?,?,?,?,?,?,?)""",
        (workspace_id, session_id, source_type, str(source_path), filename,
         content_type, compressed, len(raw), h, NOW_MS)
    )


# ─────────────────────────────────────────────
# INGEST: TRANSCRIPT
# ─────────────────────────────────────────────

def ingest_transcript(conn, workspace_id, session_id, path: Path):
    raw = read_bytes(path)
    if raw is None:
        return 0
    vfs_insert(conn, workspace_id, session_id, "transcript", path, "jsonl", raw)
    count = 0
    turn_index = 0
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            evt = json.loads(line)
        except Exception:
            continue
        event_type = evt.get("type", "unknown")
        request_id = evt.get("requestId") or evt.get("request_id")
        ts = evt.get("timestamp") or evt.get("ts")
        if event_type in ("assistant.turn_start", "user.message"):
            turn_index += 1
        conn.execute(
            """INSERT INTO transcript_events(session_id, workspace_id, event_type, request_id, turn_index, ts, data_json)
               VALUES(?,?,?,?,?,?,?)""",
            (session_id, workspace_id, event_type, request_id, turn_index, ts, line)
        )
        count += 1
    return count


# ─────────────────────────────────────────────
# INGEST: CHAT SESSIONS
# ─────────────────────────────────────────────

def ingest_chat_session(conn, workspace_id, session_id, path: Path):
    raw = read_bytes(path)
    if raw is None:
        return 0
    vfs_insert(conn, workspace_id, session_id, "chat_session", path, "jsonl", raw)
    count = 0
    for line in raw.decode("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except Exception:
            continue
        kind = obj.get("kind")
        v = obj.get("v")

        if kind == 1 and isinstance(v, str):
            # Raw user message text
            conn.execute(
                "INSERT INTO chat_messages(session_id, workspace_id, request_id, ts, role, content, kind) VALUES(?,?,?,?,?,?,?)",
                (session_id, workspace_id, None, None, "user", v, 1)
            )
            count += 1

        elif kind == 2 and isinstance(v, list):
            # Incremental request entries
            for req in v:
                if not isinstance(req, dict):
                    continue
                request_id = req.get("requestId")
                ts = req.get("timestamp")
                agent_id = None
                if isinstance(req.get("agent"), dict):
                    agent_id = req["agent"].get("id")
                conn.execute(
                    "INSERT INTO chat_messages(session_id, workspace_id, request_id, ts, role, content, agent_id, kind) VALUES(?,?,?,?,?,?,?,?)",
                    (session_id, workspace_id, request_id, ts, "request_meta",
                     json.dumps(req), agent_id, 2)
                )
                count += 1
    return count


# ─────────────────────────────────────────────
# INGEST: CHAT EDITING SESSIONS
# ─────────────────────────────────────────────

def ingest_edit_session(conn, workspace_id, session_id, session_dir: Path):
    state_path = session_dir / "state.json"
    raw = read_bytes(state_path)
    if raw:
        vfs_insert(conn, workspace_id, session_id, "edit_state", state_path, "json", raw)

    contents_dir = session_dir / "contents"
    content_count = 0
    if contents_dir.is_dir():
        for blob_file in contents_dir.iterdir():
            if blob_file.is_file():
                raw_blob = read_bytes(blob_file)
                if raw_blob:
                    vfs_insert(conn, workspace_id, session_id, "edit_content", blob_file, "binary", raw_blob)
                    content_count += 1

    return content_count


# ─────────────────────────────────────────────
# INGEST: TOOL OUTPUTS
# ─────────────────────────────────────────────

def ingest_tool_outputs(conn, workspace_id, session_id, session_dir: Path):
    count = 0
    if not session_dir.is_dir():
        return 0
    for tool_dir in session_dir.iterdir():
        if not tool_dir.is_dir():
            continue
        content_file = tool_dir / "content.txt"
        raw = read_bytes(content_file)
        if raw:
            vfs_insert(conn, workspace_id, session_id, "tool_output", content_file, "text", raw)
            count += 1
    return count


# ─────────────────────────────────────────────
# INGEST: DEBUG LOGS
# ─────────────────────────────────────────────

def ingest_debug_log(conn, workspace_id, session_id, session_dir: Path):
    models_size = 0
    for name, ctype in [("models.json", "json"), ("main.jsonl", "jsonl")]:
        path = session_dir / name
        raw = read_bytes(path)
        if raw:
            vfs_insert(conn, workspace_id, session_id, "debug_models" if name == "models.json" else "debug_main",
                       path, ctype, raw)
            if name == "models.json":
                models_size = len(raw)
    return models_size


# ─────────────────────────────────────────────
# INGEST: STATE.VSCDB
# ─────────────────────────────────────────────

def ingest_state_vscdb(conn, workspace_id, ws_path: Path):
    db_path = ws_path / "state.vscdb"
    if not db_path.exists():
        return 0
    try:
        src = sqlite3.connect(str(db_path))
        src.row_factory = sqlite3.Row
        rows = src.execute("SELECT key, value FROM ItemTable").fetchall()
        src.close()
    except Exception as e:
        log_ingest(conn, workspace_id, None, "state_vscdb", "error", str(e))
        return 0
    count = 0
    for row in rows:
        try:
            conn.execute(
                "INSERT OR REPLACE INTO state_items(workspace_id, key, value) VALUES(?,?,?)",
                (workspace_id, row["key"], row["value"])
            )
            count += 1
        except Exception:
            pass
    return count


# ─────────────────────────────────────────────
# INGEST: MEMORY FILES
# ─────────────────────────────────────────────

def ingest_memory_dir(conn, scope, workspace_id, session_id, mem_dir: Path):
    count = 0
    if not mem_dir.is_dir():
        return 0
    for f in mem_dir.rglob("*"):
        if not f.is_file():
            continue
        try:
            content = f.read_text(errors="replace")
            conn.execute(
                """INSERT INTO memory_files(scope, workspace_id, session_id, filename, content, size_bytes, ingested_at)
                   VALUES(?,?,?,?,?,?,?)""",
                (scope, workspace_id, session_id, f.name, content, f.stat().st_size, NOW_MS)
            )
            count += 1
        except Exception:
            pass
    return count


# ─────────────────────────────────────────────
# INGEST: ONE WORKSPACE
# ─────────────────────────────────────────────

def ingest_workspace(conn, ws_id: str):
    ws_path = VS_STORAGE / ws_id

    # Resolve workspace URI
    ws_json_path = ws_path / "workspace.json"
    ws_data = read_json(ws_json_path) or {}
    uri = ws_data.get("workspace") or ws_data.get("folder") or ws_data.get("folderUri") or "unknown"
    ws_type = "workspace" if "workspace" in ws_data else ("folder" if "folder" in ws_data else "unknown")

    # Derive name
    name = Path(str(uri).rstrip("/").replace("file://", "")).name or ws_id[:12]

    # Collect session IDs from transcripts dir (most reliable)
    sessions_found: dict[str, dict] = {}
    copilot_dir = ws_path / "GitHub.copilot-chat"

    transcripts_dir = copilot_dir / "transcripts"
    if transcripts_dir.is_dir():
        for f in transcripts_dir.glob("*.jsonl"):
            sid = f.stem
            sessions_found.setdefault(sid, {})["transcript"] = f

    chat_sessions_dir = ws_path / "chatSessions"
    if chat_sessions_dir.is_dir():
        for f in chat_sessions_dir.glob("*.jsonl"):
            sid = f.stem
            sessions_found.setdefault(sid, {})["chat_session"] = f

    # Get session metadata from state.vscdb
    session_meta: dict[str, dict] = {}
    state_db_path = ws_path / "state.vscdb"
    if state_db_path.exists():
        try:
            src = sqlite3.connect(str(state_db_path))
            row = src.execute("SELECT value FROM ItemTable WHERE key='chat.ChatSessionStore.index'").fetchone()
            if row:
                idx = json.loads(row[0])
                for sid, entry in (idx.get("entries") or {}).items():
                    session_meta[sid] = entry
            src.close()
        except Exception:
            pass

    # Merge sessions from all sources
    for sid, entry in session_meta.items():
        sessions_found.setdefault(sid, {})["meta"] = entry

    edit_sessions_dir = ws_path / "chatEditingSessions"
    if edit_sessions_dir.is_dir():
        for d in edit_sessions_dir.iterdir():
            if d.is_dir():
                sessions_found.setdefault(d.name, {})["edit_session_dir"] = d

    tool_resources_dir = copilot_dir / "chat-session-resources"
    if tool_resources_dir.is_dir():
        for d in tool_resources_dir.iterdir():
            if d.is_dir():
                sessions_found.setdefault(d.name, {})["tool_outputs_dir"] = d

    debug_logs_dir = copilot_dir / "debug-logs"
    if debug_logs_dir.is_dir():
        for d in debug_logs_dir.iterdir():
            if d.is_dir():
                sessions_found.setdefault(d.name, {})["debug_log_dir"] = d

    # Register workspace
    conn.execute(
        "INSERT OR REPLACE INTO workspaces(workspace_id, uri, name, type, session_count, ingested_at) VALUES(?,?,?,?,?,?)",
        (ws_id, str(uri), name, ws_type, len(sessions_found), NOW_MS)
    )

    # Ingest state.vscdb
    ingest_state_vscdb(conn, ws_id, ws_path)

    # Ingest workspace memory files
    ws_mem_dir = copilot_dir / "memory-tool" / "memories"
    ingest_memory_dir(conn, "workspace", ws_id, None, ws_mem_dir)

    # Process each session
    for sid, sources in sessions_found.items():
        meta = sources.get("meta", {})
        title = meta.get("title") or meta.get("customTitle") or "untitled"
        created_at = (meta.get("timing") or {}).get("created") or meta.get("creationDate")
        last_msg = (meta.get("timing") or {}).get("lastRequestStarted") or meta.get("lastMessageDate")
        response_state = meta.get("lastResponseState")
        initial_location = meta.get("initialLocation")

        conn.execute(
            """INSERT OR REPLACE INTO sessions(session_id, workspace_id, title, created_at,
               last_message_at, response_state, initial_location, ingested_at)
               VALUES(?,?,?,?,?,?,?,?)""",
            (sid, ws_id, title, created_at, last_msg, response_state, initial_location, NOW_MS)
        )

        storage_row = {
            "session_id": sid, "workspace_id": ws_id,
            "has_transcript": 0, "transcript_size": 0,
            "has_chat_session": 0, "chat_session_size": 0,
            "has_edit_session": 0, "edit_state_size": 0, "edit_content_count": 0,
            "has_tool_outputs": 0, "tool_output_count": 0,
            "has_debug_log": 0, "debug_models_size": 0,
            "in_state_vscdb": 1 if sid in session_meta else 0,
            "has_workspace_memory": 0, "workspace_memory_count": 0,
        }

        # 1. Transcript
        if "transcript" in sources:
            p = sources["transcript"]
            evt_count = ingest_transcript(conn, ws_id, sid, p)
            storage_row.update(has_transcript=1, transcript_size=p.stat().st_size)
            conn.execute("UPDATE sessions SET request_count=? WHERE session_id=?",
                         (evt_count, sid))

        # 2. Chat session
        if "chat_session" in sources:
            p = sources["chat_session"]
            ingest_chat_session(conn, ws_id, sid, p)
            storage_row.update(has_chat_session=1, chat_session_size=p.stat().st_size)

        # 3. Edit session
        if "edit_session_dir" in sources:
            d = sources["edit_session_dir"]
            content_count = ingest_edit_session(conn, ws_id, sid, d)
            state_size = 0
            sp = d / "state.json"
            if sp.exists():
                state_size = sp.stat().st_size
            storage_row.update(has_edit_session=1, edit_state_size=state_size,
                               edit_content_count=content_count)

        # 4. Tool outputs
        if "tool_outputs_dir" in sources:
            d = sources["tool_outputs_dir"]
            count = ingest_tool_outputs(conn, ws_id, sid, d)
            storage_row.update(has_tool_outputs=1 if count > 0 else 0, tool_output_count=count)

        # 5. Debug logs
        if "debug_log_dir" in sources:
            d = sources["debug_log_dir"]
            models_size = ingest_debug_log(conn, ws_id, sid, d)
            storage_row.update(has_debug_log=1, debug_models_size=models_size)

        # 6. Large index DBs — path only
        semantic = ws_path / "GitHub.copilot-chat" / "workspace-chunks.db"
        fulltext_candidates = list(ws_path.glob("local-index*"))
        storage_row["semantic_index_path"] = str(semantic) if semantic.exists() else None
        storage_row["fulltext_index_path"] = str(fulltext_candidates[0]) if fulltext_candidates else None

        conn.execute(
            """INSERT OR REPLACE INTO session_storage(
               session_id, workspace_id,
               has_transcript, transcript_size,
               has_chat_session, chat_session_size,
               has_edit_session, edit_state_size, edit_content_count,
               has_tool_outputs, tool_output_count,
               has_debug_log, debug_models_size,
               in_state_vscdb,
               has_workspace_memory, workspace_memory_count,
               semantic_index_path, fulltext_index_path
            ) VALUES(
               :session_id, :workspace_id,
               :has_transcript, :transcript_size,
               :has_chat_session, :chat_session_size,
               :has_edit_session, :edit_state_size, :edit_content_count,
               :has_tool_outputs, :tool_output_count,
               :has_debug_log, :debug_models_size,
               :in_state_vscdb,
               :has_workspace_memory, :workspace_memory_count,
               :semantic_index_path, :fulltext_index_path
            )""",
            storage_row
        )

    return len(sessions_found)


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    print(f"cda ingest → {DB_PATH}")

    if DB_PATH.exists():
        DB_PATH.unlink()
        print("  dropped existing DB")

    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA)
    conn.commit()
    print("  schema initialized")

    # Global memory files
    global_mem_count = ingest_memory_dir(conn, "global", None, None, GLOBAL_MEM)
    print(f"  global memory: {global_mem_count} files")
    conn.commit()

    # Walk all workspaces
    workspace_dirs = [d for d in VS_STORAGE.iterdir() if d.is_dir()]
    print(f"  found {len(workspace_dirs)} workspace dirs")

    total_sessions = 0
    for i, ws_dir in enumerate(sorted(workspace_dirs), 1):
        ws_id = ws_dir.name
        try:
            n = ingest_workspace(conn, ws_id)
            total_sessions += n
            if n > 0:
                print(f"  [{i:3}] {ws_id[:16]}...  {n} session(s)")
        except Exception as e:
            print(f"  [{i:3}] {ws_id[:16]}... ERROR: {e}")
            log_ingest(conn, ws_id, None, "workspace", "error", str(e))
        if i % 10 == 0:
            conn.commit()

    conn.commit()

    # Summary
    print()
    print("=== INGEST COMPLETE ===")
    for table in ["workspaces", "sessions", "session_storage", "vfs", "transcript_events",
                  "chat_messages", "state_items", "memory_files", "ingest_log"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table:<25} {count:>8} rows")

    db_size = DB_PATH.stat().st_size
    print(f"\n  DB size: {db_size / 1024 / 1024:.1f} MB")
    print(f"  workspaces: {len(workspace_dirs)}")
    print(f"  sessions:   {total_sessions}")
    conn.close()


if __name__ == "__main__":
    main()
