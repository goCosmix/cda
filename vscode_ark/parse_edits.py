#!/usr/bin/env python3
"""
parse_edits.py — Edit session analysis.

Parses edit_state VFS blobs and populates:
  - edit_sessions  : per-session file edit summary
  - edited_files   : per-file-per-session record

edit_state schema (VSCode internal, version 2):
  {
    version: 2,
    initialFileContents: [[fileUri, contentHash], ...],
    timeline: {
      checkpoints: [{checkpointId, requestId, epoch, label}, ...],
      currentEpoch: N,
      fileBaselines: ...
    },
    recentSnapshot: {
      entries: [{resource, languageId, originalHash, currentHash, state}, ...]
    }
  }

State values (from VSCode source):
  0 = Unmodified
  1 = Modified (pending)
  2 = Accepted
  3 = Rejected

Modified files: originalHash != currentHash in snapshot entries
Edit rounds: len(checkpoints) - 1  (first is always "Initial State")
"""

import sqlite3, gzip, json, re
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "vscode-ark.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS edit_sessions (
    session_id         TEXT PRIMARY KEY,
    workspace_id       TEXT,
    total_files        INTEGER DEFAULT 0,   -- files in snapshot
    modified_files     INTEGER DEFAULT 0,   -- files where hash changed
    edit_rounds        INTEGER DEFAULT 0,   -- checkpoints minus initial
    file_paths         TEXT,                -- JSON array of modified file paths
    all_file_paths     TEXT,                -- JSON array of all file paths in session
    ingested_at        TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS edited_files (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL,
    workspace_id    TEXT,
    file_uri        TEXT NOT NULL,
    file_path       TEXT,                   -- path without file:// scheme
    language_id     TEXT,
    original_hash   TEXT,
    current_hash    TEXT,
    was_modified    INTEGER DEFAULT 0,      -- 1 if original_hash != current_hash
    final_state     INTEGER,                -- 0=unmodified,1=modified,2=accepted,3=rejected
    ingested_at     TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_edit_sessions_workspace ON edit_sessions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_edited_files_session ON edited_files(session_id);
CREATE INDEX IF NOT EXISTS idx_edited_files_path ON edited_files(file_path);
CREATE INDEX IF NOT EXISTS idx_edited_files_modified ON edited_files(was_modified);
"""


def strip_scheme(uri):
    """Convert file:///path/to/file → /path/to/file"""
    if uri.startswith('file://'):
        return uri[7:]
    return uri


def parse_edit_state(conn, session_id, workspace_id, content):
    """Parse one edit_state blob and upsert rows."""
    raw = gzip.decompress(content).decode('utf-8', errors='replace')
    try:
        obj = json.loads(raw)
    except Exception:
        return 0

    if obj.get('version') != 2:
        return 0

    snapshot = obj.get('recentSnapshot', {})
    entries = snapshot.get('entries', [])

    timeline = obj.get('timeline', {})
    checkpoints = timeline.get('checkpoints', [])
    edit_rounds = max(0, len(checkpoints) - 1)  # subtract initial state

    total_files = len(entries)
    modified_files = 0
    file_paths_modified = []
    all_file_paths = []

    file_rows = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        uri = entry.get('resource', '')
        file_path = strip_scheme(uri)
        lang = entry.get('languageId', '')
        orig = entry.get('originalHash', '')
        curr = entry.get('currentHash', '')
        state = entry.get('state', 0)
        was_mod = 1 if (orig and curr and orig != curr) else 0

        if was_mod:
            modified_files += 1
            file_paths_modified.append(file_path)
        if file_path:
            all_file_paths.append(file_path)

        file_rows.append((
            session_id, workspace_id,
            uri, file_path, lang,
            orig, curr, was_mod, state,
        ))

    # Upsert edit_sessions row
    conn.execute("""
        INSERT INTO edit_sessions
        (session_id, workspace_id, total_files, modified_files,
         edit_rounds, file_paths, all_file_paths)
        VALUES (?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
          workspace_id=excluded.workspace_id,
          total_files=excluded.total_files,
          modified_files=excluded.modified_files,
          edit_rounds=excluded.edit_rounds,
          file_paths=excluded.file_paths,
          all_file_paths=excluded.all_file_paths,
          ingested_at=datetime('now')
    """, (
        session_id, workspace_id,
        total_files, modified_files,
        edit_rounds,
        json.dumps(file_paths_modified),
        json.dumps(all_file_paths),
    ))

    # Delete existing file rows for this session (re-run safe)
    conn.execute("DELETE FROM edited_files WHERE session_id=?", (session_id,))

    # Insert file rows
    conn.executemany("""
        INSERT INTO edited_files
        (session_id, workspace_id, file_uri, file_path, language_id,
         original_hash, current_hash, was_modified, final_state)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, file_rows)

    return len(file_rows)


def run():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.executescript(SCHEMA)
    conn.commit()

    blobs = conn.execute(
        """SELECT v.session_id, s.workspace_id, v.content
           FROM vfs v
           LEFT JOIN sessions s ON s.session_id = v.session_id
           WHERE v.source_type = 'edit_state'
           ORDER BY v.size_bytes DESC"""
    ).fetchall()

    print(f"Parsing {len(blobs)} edit_state blobs...")
    total_files = 0
    total_modified = 0
    errors = 0

    # Deduplicate by session_id — use largest blob per session
    seen = set()
    deduped = []
    for sid, wid, content in blobs:
        if sid not in seen:
            seen.add(sid)
            deduped.append((sid, wid, content))

    print(f"  Unique sessions: {len(deduped)}")

    for sid, wid, content in deduped:
        try:
            n = parse_edit_state(conn, sid, wid, content)
            row = conn.execute(
                "SELECT total_files, modified_files, edit_rounds FROM edit_sessions WHERE session_id=?",
                (sid,)
            ).fetchone()
            if row:
                total_files += row[0]
                total_modified += row[1]
                if row[1] > 0:
                    print(f"  {sid[:16]}  files={row[0]}  modified={row[1]}  rounds={row[2]}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR {sid[:16]}: {e}")

    conn.commit()

    # Summary stats
    n_sessions = conn.execute("SELECT COUNT(*) FROM edit_sessions").fetchone()[0]
    n_mod_sessions = conn.execute("SELECT COUNT(*) FROM edit_sessions WHERE modified_files > 0").fetchone()[0]
    n_file_rows = conn.execute("SELECT COUNT(*) FROM edited_files").fetchone()[0]
    n_mod_files = conn.execute("SELECT COUNT(*) FROM edited_files WHERE was_modified=1").fetchone()[0]

    print()
    print("=== EDIT PARSE COMPLETE ===")
    print(f"  edit_sessions rows:    {n_sessions}")
    print(f"  sessions with changes: {n_mod_sessions}")
    print(f"  edited_files rows:     {n_file_rows}")
    print(f"  modified files:        {n_mod_files}")
    print(f"  errors:                {errors}")

    # Top modified files across all sessions
    print()
    print("=== TOP MODIFIED FILES ===")
    rows = conn.execute("""
        SELECT file_path, COUNT(DISTINCT session_id) sessions,
               SUM(was_modified) times_modified
        FROM edited_files
        WHERE was_modified=1 AND file_path != ''
        GROUP BY file_path
        ORDER BY times_modified DESC
        LIMIT 15
    """).fetchall()
    for r in rows:
        print(f"  {r[2]:>3}×  {r[0][-70:]}")

    conn.close()


if __name__ == "__main__":
    run()
