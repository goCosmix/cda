#!/usr/bin/env python3
"""
vscode-ark/reconstruct.py

Walks transcript_events for every session and builds fully-structured
request/response exchanges, joining tool outputs from the VFS.

Output table: exchanges
  - One row per user→assistant cycle (request/response pair)
  - exchange_json contains the full structured object

Schema added: exchanges
"""

import sqlite3
import json
import gzip
import time
from typing import Optional
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOCAL_DIR = ROOT_DIR / "local"
DB_PATH = LOCAL_DIR / "data" / "vscode-ark.db"
NOW_MS  = int(time.time() * 1000)

EXCHANGES_SCHEMA = """
CREATE TABLE IF NOT EXISTS exchanges (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT,
    workspace_id    TEXT,
    exchange_index  INTEGER,   -- 0-based turn index within session
    request_id      TEXT,      -- event id of the user.message
    user_ts         TEXT,      -- ISO timestamp of user message
    assistant_ts    TEXT,      -- ISO timestamp of first assistant.turn_start
    user_message    TEXT,      -- plain text of user prompt
    attachments     TEXT,      -- JSON array of attachments
    reasoning_text  TEXT,      -- concatenated reasoningText from all assistant.message events
    response_text   TEXT,      -- concatenated content from all assistant.message events
    tool_calls      TEXT,      -- JSON array of {toolCallId, name, arguments, output, success}
    tool_call_count INTEGER,
    has_tool_output INTEGER,   -- 1 if any tool call has a VFS payload
    session_meta    TEXT,      -- from session.start event (versions, producer)
    ingested_at     INTEGER,
    UNIQUE(session_id, exchange_index)
);
CREATE INDEX IF NOT EXISTS ex_session   ON exchanges(session_id);
CREATE INDEX IF NOT EXISTS ex_workspace ON exchanges(workspace_id);
CREATE INDEX IF NOT EXISTS ex_ts        ON exchanges(user_ts);
"""


def decompress_vfs(blob: bytes) -> bytes:
    # Safety check: don't decompress blobs larger than 100MB
    MAX_DECOMPRESS_SIZE = 100 * 1024 * 1024  # 100MB
    if len(blob) > MAX_DECOMPRESS_SIZE:
        print(f"Warning: Skipping decompression of large blob ({len(blob)} bytes)")
        return blob

    try:
        return gzip.decompress(blob)
    except Exception:
        return blob


def build_tool_output_index(conn, session_id: str) -> dict:
    """
    Returns {toolCallId: content_text} by reading VFS tool_output rows
    where source_path contains the toolCallId directory segment.
    """
    rows = conn.execute(
        "SELECT source_path, content FROM vfs WHERE session_id=? AND source_type='tool_output'",
        (session_id,)
    ).fetchall()
    index = {}
    for row in rows:
        # path: .../chat-session-resources/<session_id>/<toolCallId>__vscode-.../content.txt
        parts = Path(row[0]).parts
        # Find the directory directly under the session_id dir
        try:
            for i, p in enumerate(parts):
                if p == session_id and i + 1 < len(parts):
                    tool_call_dir = parts[i + 1]
                    # toolCallId is the prefix before '__vscode-'
                    tool_call_id = tool_call_dir.split('__vscode-')[0]
                    content = decompress_vfs(row[1]).decode('utf-8', errors='replace')
                    index[tool_call_id] = content
                    break
        except Exception:
            pass
    return index


def reconstruct_session(conn, session_id: str, workspace_id: str) -> int:
    """
    Reconstructs all exchanges for a session from transcript_events.
    Returns number of exchanges written.
    """
    # Load all events ordered by timestamp
    rows = conn.execute(
        """SELECT event_type, data_json, id, ts
           FROM transcript_events
           WHERE session_id=?
           ORDER BY ts ASC, rowid ASC""",
        (session_id,)
    ).fetchall()

    if not rows:
        return 0

    # Build event list
    events = []
    for row in rows:
        try:
            d = json.loads(row[1])
        except Exception:
            d = {}
        events.append({
            "type":      row[0],
            "data":      d.get("data", {}),
            "event_id":  d.get("id"),
            "timestamp": d.get("timestamp"),
            "ts_ms":     row[2],
        })

    # Extract session.start metadata
    session_meta = {}
    for e in events:
        if e["type"] == "session.start":
            session_meta = e["data"]
            break

    # Build tool output index: toolCallId → output text
    tool_output_index = build_tool_output_index(conn, session_id)

    # Walk events and group into exchanges
    # An exchange = one user.message + everything until the next user.message
    exchanges = []
    current: Optional[dict] = None
    current_turn: Optional[dict] = None   # tracks the active assistant turn

    def flush_turn():
        nonlocal current_turn
        if current_turn and current:
            current["turns"].append(current_turn)
        current_turn = None

    def new_turn():
        nonlocal current_turn
        flush_turn()
        current_turn = {"messages": [], "tool_calls": []}

    for e in events:
        etype = e["type"]
        data  = e["data"]

        if etype == "user.message":
            # Flush previous exchange
            if current is not None:
                flush_turn()
                exchanges.append(current)
            current = {
                "request_id":    e["event_id"],
                "user_ts":       e["timestamp"],
                "user_message":  data.get("content", ""),
                "attachments":   data.get("attachments", []),
                "assistant_ts":  None,
                "turns":         [],
            }
            current_turn = None

        elif etype == "assistant.turn_start":
            if current is None:
                # Turn before any user message — session-level assistant intro
                current = {
                    "request_id":   None,
                    "user_ts":      None,
                    "user_message": "",
                    "attachments":  [],
                    "assistant_ts": e["timestamp"],
                    "turns":        [],
                }
            if current["assistant_ts"] is None:
                current["assistant_ts"] = e["timestamp"]
            new_turn()

        elif etype == "assistant.message":
            if current_turn is None:
                new_turn()
            current_turn["messages"].append({
                "message_id":   data.get("messageId"),
                "content":      data.get("content", ""),
                "reasoning":    data.get("reasoningText", ""),
                "tool_requests": data.get("toolRequests", []),
                "timestamp":    e["timestamp"],
            })

        elif etype == "tool.execution_start":
            if current_turn is None:
                new_turn()
            tool_call_id = data.get("toolCallId", "")
            current_turn["tool_calls"].append({
                "toolCallId": tool_call_id,
                "name":       data.get("toolName", ""),
                "arguments":  data.get("arguments", {}),
                "output":     tool_output_index.get(tool_call_id),
                "success":    None,
                "timestamp":  e["timestamp"],
            })

        elif etype == "tool.execution_complete":
            # Patch success onto the matching tool call in current turn
            tool_call_id = data.get("toolCallId", "")
            if current_turn:
                for tc in current_turn["tool_calls"]:
                    if tc["toolCallId"] == tool_call_id:
                        tc["success"] = data.get("success")
                        break

        elif etype == "assistant.turn_end":
            flush_turn()

    # Flush final exchange
    if current is not None:
        flush_turn()
        exchanges.append(current)

    # Write to DB
    written = 0
    for idx, ex in enumerate(exchanges):
        # Flatten turns into top-level fields
        reasoning_parts = []
        response_parts  = []
        all_tool_calls  = []

        for turn in ex.get("turns", []):
            for msg in turn.get("messages", []):
                if msg.get("reasoning"):
                    reasoning_parts.append(msg["reasoning"])
                if msg.get("content"):
                    response_parts.append(msg["content"])
            all_tool_calls.extend(turn.get("tool_calls", []))

        has_output = any(tc.get("output") is not None for tc in all_tool_calls)

        conn.execute(
            """INSERT OR IGNORE INTO exchanges(
                session_id, workspace_id, exchange_index, request_id,
                user_ts, assistant_ts,
                user_message, attachments,
                reasoning_text, response_text,
                tool_calls, tool_call_count, has_tool_output,
                session_meta, ingested_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, workspace_id, idx,
                ex.get("request_id"),
                ex.get("user_ts"),
                ex.get("assistant_ts"),
                ex.get("user_message", ""),
                json.dumps(ex.get("attachments", [])),
                "\n\n".join(reasoning_parts),
                "\n\n".join(response_parts),
                json.dumps(all_tool_calls),
                len(all_tool_calls),
                1 if has_output else 0,
                json.dumps(session_meta),
                NOW_MS,
            )
        )
        written += 1

    return written


def _parse_chat_request(req, turn_index):
    """Parse a raw chat-session request dict into a normalized exchange record."""
    msg = req.get('message', {})
    text = msg.get('text', '') if isinstance(msg, dict) else ''

    model_id = req.get('modelId', '')
    if not model_id and isinstance(req.get('modelState'), dict):
        model_id = req['modelState'].get('modelId', '')

    # Response content — array of parts in kind=0 snapshot
    response = req.get('response') or []
    response_parts = []
    if isinstance(response, list):
        for part in response:
            if isinstance(part, dict):
                v = part.get('value', '') or part.get('content', '') or ''
                if isinstance(v, str) and v and 'conversation-summary' not in v.lower():
                    response_parts.append(v)

    # Tool requests
    tool_requests = []
    for tr in (req.get('toolRequests') or req.get('toolResults') or []):
        if isinstance(tr, dict):
            tool_requests.append({
                'toolCallId': tr.get('toolCallId', ''),
                'name': tr.get('toolName', '') or tr.get('name', ''),
                'arguments': tr.get('arguments', {}),
                'success': tr.get('success'),
            })

    return {
        'request_id': req.get('requestId', ''),
        'ts': req.get('timestamp', 0),
        'turn_index': turn_index,
        'message_text': text,
        'model_id': model_id,
        'response_text': '\n\n'.join(response_parts),
        'tool_requests': tool_requests,
    }


def reconstruct_from_chat_blob(conn, session_id, workspace_id, content):
    """
    Reconstruct exchanges from a chat_session VFS blob.
    Used for sessions that have no transcript_events (chat-only sessions).
    Returns number of exchanges written.
    """
    raw = gzip.decompress(content).decode('utf-8', errors='replace')
    lines = [ln for ln in raw.splitlines() if ln.strip()]

    requests_map = {}   # request_id -> parsed dict (ordered by insertion)
    turn_index = 0

    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue

        kind = obj.get('kind')

        # kind=0: initial snapshot
        if kind == 0:
            for req in (obj.get('v', {}).get('requests') or []):
                rid = req.get('requestId', '')
                if rid and rid not in requests_map:
                    requests_map[rid] = _parse_chat_request(req, turn_index)
                    turn_index += 1

        # kind=2: delta patches — new requests appended
        elif kind == 2:
            k = obj.get('k', [])
            v = obj.get('v')
            if k == ['requests'] and isinstance(v, list):
                for req in v:
                    rid = req.get('requestId', '')
                    if rid and rid not in requests_map:
                        requests_map[rid] = _parse_chat_request(req, turn_index)
                        turn_index += 1

        # kind=1: result patches — response content, model, usage
        elif kind == 1:
            k = obj.get('k', [])
            v = obj.get('v', {})
            if len(k) >= 3 and k[0] == 'requests' and k[2] == 'result' and isinstance(v, dict):
                idx = k[1]
                items = list(requests_map.values())
                if 0 <= idx < len(items):
                    req = items[idx]
                    meta = (v.get('metadata') or {})
                    # Fill model if missing
                    if not req['model_id']:
                        resolved = meta.get('resolvedModel', '')
                        if resolved:
                            req['model_id'] = resolved if isinstance(resolved, str) else str(resolved)
                    # Backfill response text from result if not already present
                    if not req['response_text']:
                        # result.value or result.output
                        for key in ('value', 'output', 'content', 'text'):
                            rv = v.get(key)
                            if isinstance(rv, str) and rv:
                                req['response_text'] = rv[:5000]
                                break

    if not requests_map:
        return 0

    tool_output_index = build_tool_output_index(conn, session_id)

    written = 0
    for idx, req in enumerate(requests_map.values()):
        # Skip requests with no user message text (system/empty entries)
        if not req['message_text']:
            continue

        tool_calls = []
        for tr in req.get('tool_requests', []):
            tc_id = tr.get('toolCallId', '')
            tool_calls.append({
                'toolCallId': tc_id,
                'name': tr.get('name', ''),
                'arguments': tr.get('arguments', {}),
                'output': tool_output_index.get(tc_id),
                'success': tr.get('success'),
            })

        has_output = any(tc.get('output') is not None for tc in tool_calls)

        conn.execute(
            """INSERT OR IGNORE INTO exchanges(
                session_id, workspace_id, exchange_index, request_id,
                user_ts, assistant_ts,
                user_message, attachments,
                reasoning_text, response_text,
                tool_calls, tool_call_count, has_tool_output,
                session_meta, ingested_at
               ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_id, workspace_id, written,
                req.get('request_id'),
                req.get('ts'),
                None,
                req.get('message_text', ''),
                json.dumps([]),
                '',
                req.get('response_text', ''),
                json.dumps(tool_calls),
                len(tool_calls),
                1 if has_output else 0,
                json.dumps({}),
                NOW_MS,
            )
        )
        written += 1

    return written


def main():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")

    # Add schema
    conn.executescript(EXCHANGES_SCHEMA)
    conn.commit()

    # Wipe existing exchanges to allow re-run
    conn.execute("DELETE FROM exchanges")
    conn.commit()

    # Get all sessions that have transcript events
    sessions = conn.execute(
        """SELECT DISTINCT te.session_id, s.workspace_id
           FROM transcript_events te
           LEFT JOIN sessions s USING(session_id)"""
    ).fetchall()

    print(f"Reconstructing {len(sessions)} sessions with transcript data...")

    total_exchanges = 0
    for session_id, workspace_id in sessions:
        n = reconstruct_session(conn, session_id, workspace_id or "unknown")
        total_exchanges += n
        print(f"  [transcript] {session_id[:16]}  {n} exchanges")
        conn.commit()

    # ── Chat-only sessions: reconstruct from chat_session blob ──────────────
    # Sessions that have a chat_session blob but no transcript events
    chat_only = conn.execute(
        """SELECT v.session_id, s.workspace_id, v.content
           FROM vfs v
           LEFT JOIN sessions s ON s.session_id = v.session_id
           WHERE v.source_type = 'chat_session'
             AND v.session_id NOT IN (
                 SELECT DISTINCT session_id FROM transcript_events
             )
           ORDER BY v.session_id"""
    ).fetchall()

    print(f"\nReconstructing {len(chat_only)} chat-only sessions (no transcript)...")
    chat_total = 0
    for session_id, workspace_id, content in chat_only:
        try:
            n = reconstruct_from_chat_blob(conn, session_id, workspace_id or "unknown", content)
            chat_total += n
            if n > 0:
                print(f"  [chat-blob]  {session_id[:16]}  {n} exchanges")
            conn.commit()
        except Exception as e:
            print(f"  [chat-blob]  {session_id[:16]}  ERROR: {e}")

    total_exchanges += chat_total

    print()
    print("=== RECONSTRUCTION COMPLETE ===")
    print(f"  From transcripts: {total_exchanges - chat_total}")
    print(f"  From chat blobs:  {chat_total}")
    print(f"  Total exchanges:  {total_exchanges}")

    # Spot-check this session
    this_session = 'f274fb87-77f8-477a-993e-ed6e73d930ff'
    print()
    print(f"=== Spot-check: {this_session[:16]}... ===")
    rows = conn.execute(
        """SELECT exchange_index, user_ts, user_message, tool_call_count, has_tool_output,
                  LENGTH(reasoning_text) reasoning_len, LENGTH(response_text) response_len
           FROM exchanges WHERE session_id=? ORDER BY exchange_index""",
        (this_session,)
    ).fetchall()
    for r in rows:
        user_preview = (r[2] or "")[:60].replace('\n', ' ')
        print(f"  [{r[0]:>2}] {r[1] or '':>25}  tools={r[3]}  has_output={r[4]}  "
              f"reasoning={r[5]}b  response={r[6]}b  user='{user_preview}'")

    # Show one full exchange as sample
    print()
    print("=== Sample exchange [1] full structure ===")
    row = conn.execute(
        "SELECT * FROM exchanges WHERE session_id=? AND exchange_index=1",
        (this_session,)
    ).fetchone()
    if row:
        cols = [d[0] for d in conn.execute("SELECT * FROM exchanges LIMIT 0").description]
        d = dict(zip(cols, row))
        # Truncate large fields for display
        for field in ['tool_calls', 'session_meta', 'reasoning_text', 'response_text']:
            if d.get(field):
                d[field] = d[field][:300] + ('...' if len(str(d[field])) > 300 else '')
        print(json.dumps(d, indent=2)[:2000])

    conn.close()


if __name__ == "__main__":
    main()
