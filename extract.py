#!/usr/bin/env python3
"""
extract.py — Signal and token extraction pass.

Processes all chat sessions in vscode-ark.db and populates:
  - token_usage        : per-request token accounting
  - compactions        : context window compaction events
  - exchange_signals   : behavioral signals (corrections, affirmations, etc.)
  - session_analysis   : per-session rollup

Signal taxonomy:
  correction    — user said stop / pause / wrong / jumping ahead / etc.
  redirect      — user pivoting direction mid-session
  affirmation   — user approved / confirmed / "yes" / "lets do it" / "perfect"
  question      — user asking conceptual question (zoom out / meta / think)
  approval      — explicit build approval ("build it", "go", "lets do that")
"""

import sqlite3
import gzip
import json
import re
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple, Optional, DefaultDict
from collections import defaultdict

DB_PATH = Path(__file__).parent / "vscode-ark.db"

# ─────────────────────────────────────────────────────────
# Signal patterns
# ─────────────────────────────────────────────────────────

SIGNAL_PATTERNS = [
    # (signal_type, [keywords], description)
    ("correction", [
        "stop,", "stop.", "stop ", "pause", "wrong", "jumping ahead",
        "not listening", "thats not", "that's not", "nope,", "nope.",
        "incorrect", "you're off", "youre off", "missed the point",
        "not what i", "didn't ask", "didnt ask", "too much", "slow down",
        "hold on", "wait,", "wait.", "no,", "no.", "actually, no",
        "you missed", "thats wrong", "that's wrong", "bad habit",
        "you are jumping", "don't do that", "dont do that",
        "i said", "do what was asked", "stay focused",
    ], "Model correction — user redirecting agent behavior"),

    ("redirect", [
        "actually", "pivot", "change direction", "lets change",
        "let's change", "forget that", "scratch that", "instead,",
        "different approach", "new direction", "zoom out",
        "step back", "big picture", "meta moment", "meta perspective",
    ], "Session redirect — user changing scope or direction"),

    ("affirmation", [
        "perfect", "exactly", "yes,", "yes.", "correct", "thats right",
        "that's right", "great", "nice", "good", "love it", "love that",
        "well done", "solid", "clean", "nailed it", "exactly right",
        "thats it", "that's it", "yes!", "boom", "beautiful", "brilliant",
    ], "Affirmation — user confirming agent is on track"),

    ("approval", [
        "lets do it", "let's do it", "lets build", "let's build",
        "go ahead", "build it", "start implementation", "do it",
        "proceed", "run it", "execute", "ship it", "make it",
        "yes lets", "yes let's", "go!", "go.", "implement",
    ], "Build approval — user authorizing execution"),

    ("question", [
        "what do you think", "your thoughts", "zoom out", "meta",
        "think about", "can you think", "what is", "how does",
        "why does", "explain", "show me", "tell me", "what are",
        "understand", "curious", "wonder if",
    ], "Conceptual question — user probing for analysis"),

    # ── Frustration: explicit irritation, swearing, all-caps ──
    ("frustration", [
        "pissing me off", "pisses me off", "pissed off", "piss off",
        "are you kidding", "are you serious", "you're kidding",
        "wtf", "wth", "what the hell", "what the fuck", "what the f",
        "are you stupid", "this is stupid", "this is ridiculous",
        "omg", "oh my god", "jesus", "jesus christ", "ffs",
        "for fuck's sake", "for fucks sake", "goddamn", "god damn",
        "seriously?", "seriously!", "come on!", "come on,",
        "give me a break", "unbelievable", "unreal",
        "you broke it", "you broke", "its broken", "it's broken",
        "i'm done", "im done", "i give up", "forget it",
        "this is a mess", "what a mess", "disaster",
    ], "Frustration — explicit irritation signal"),

    # ── Pre-correction: rising tone, about to redirect ──
    ("pre_correction", [
        "listen,", "listen.", "ok no", "ok wait", "ok stop",
        "alright stop", "alright no", "alright wait",
        "hey,", "look,", "look.", "no no", "nono",
        "read the", "re-read", "read it again",
        "i just said", "i just told you", "i literally",
        "why did you", "why are you", "why would you",
        "you just", "you literally just",
        "thats not what i", "that's not what i",
        "not again", "again?", "again.", "every time",
        "you keep", "you always", "you never",
        "i've told you", "ive told you", "told you",
        "this is the", "how many times",
    ], "Pre-correction — rising tone before a correction"),
]

# Swear words as standalone detection (for any message, not keyword-anchored)
PROFANITY_PATTERNS = re.compile(
    r'\b(fuck|shit|ass|bitch|damn|crap|hell|bastard|bullshit|motherfuck|dumbass|idiot|moron)\b',
    re.IGNORECASE
)

# ALL CAPS detection: ≥3 consecutive uppercase words = signal
ALL_CAPS_PATTERN = re.compile(r'(?:[A-Z]{2,}\s+){2,}[A-Z]{2,}|[A-Z]{4,}')


def classify_message(text):
    """Return list of (signal_type, matched_keyword) for a user message."""
    tl = text.lower().strip()
    signals = []
    seen_types = set()
    for sig_type, keywords, _ in SIGNAL_PATTERNS:
        if sig_type in seen_types:
            continue
        for kw in keywords:
            if kw in tl:
                signals.append((sig_type, kw))
                seen_types.add(sig_type)
                break

    # Profanity detection (adds frustration signal if not already caught)
    if 'frustration' not in seen_types:
        m = PROFANITY_PATTERNS.search(text)
        if m:
            signals.append(('frustration', m.group(0).lower()))
            seen_types.add('frustration')

    # All-caps detection (≥4 uppercase chars or 3+ uppercase words)
    if 'frustration' not in seen_types:
        # Strip URLs, code blocks, and known tool output artifacts before checking
        clean = re.sub(r'https?://\S+|`[^`]*`', '', text)
        # Skip if it looks like tool output (contains PREVIOUS OUTPUT TRUN or similar)
        skip_phrases = ['PREVIOUS OUTPUT', 'TRUNCATED', 'EXIT CODE', 'CWD:', 'TERMINAL:']
        if not any(p in clean for p in skip_phrases):
            if ALL_CAPS_PATTERN.search(clean):
                # Make sure it's not just an acronym (less than 8 caps chars total)
                caps_count = sum(1 for c in clean if c.isupper())
                if caps_count >= 8:
                    m2 = ALL_CAPS_PATTERN.search(clean)
                    signals.append(('frustration', 'ALL_CAPS:' + m2.group(0)[:20]))
                    seen_types.add('frustration')

    return signals


def extract_requests_from_chat(lines):
    """
    Walk JSONL lines from a chat session blob.
    Returns:
      requests   — list of {request_id, ts, message_text, model_id, turn_index}
      token_rows — list of {request_id, ts, turn_index, prompt, completion, cached, total, output, model_id}
      compaction_rows — list of {request_id, ts, turn_index, summary_text, trigger_text}
    """
    # Build a snapshot from kind=0 + patches from kind=1/2
    # kind=0: initial snapshot (has requests[])
    # kind=2: patches with new request arrays
    # kind=1: result patches (timings, metadata, usage)

    requests_map = {}  # request_id -> dict
    turn_index = 0

    for line in lines:
        try:
            obj = json.loads(line)
        except Exception:
            continue

        kind = obj.get('kind')

        # kind=0: initial snapshot
        if kind == 0:
            v = obj.get('v', {})
            for req in (v.get('requests') or []):
                rid = req.get('requestId', '')
                if rid:
                    requests_map[rid] = _parse_request(req, turn_index)
                    turn_index += 1

        # kind=2: delta patches — new requests appended
        elif kind == 2:
            k = obj.get('k', [])
            v = obj.get('v')
            # ['requests'] with a list value = new batch of requests
            if k == ['requests'] and isinstance(v, list):
                for req in v:
                    rid = req.get('requestId', '')
                    if rid and rid not in requests_map:
                        requests_map[rid] = _parse_request(req, turn_index)
                        turn_index += 1
            # ['requests', N, field] = patch to existing request
            elif len(k) >= 3 and k[0] == 'requests' and isinstance(k[1], int):
                pass  # handled below in result patches

        # kind=1: result patches — contains usage, timings, metadata
        elif kind == 1:
            k = obj.get('k', [])
            v = obj.get('v', {})
            # ['requests', N, 'result'] — usage is here
            if len(k) >= 3 and k[0] == 'requests' and k[2] == 'result' and isinstance(v, dict):
                idx = k[1]
                # Find the request at that index
                req_at_idx = _find_request_by_index(requests_map, idx)
                if req_at_idx:
                    _apply_result_patch(req_at_idx, v)

    return requests_map


def _parse_request(req, turn_index):
    """Parse a raw request dict into our normalized form."""
    msg = req.get('message', {})
    text = msg.get('text', '') if isinstance(msg, dict) else ''
    # Model
    model_id = req.get('modelId', '')
    if not model_id and isinstance(req.get('modelState'), dict):
        model_id = req['modelState'].get('modelId', '')
    # Response — check for compaction summary in response parts
    response = req.get('response') or []
    compaction_summary = ''
    if isinstance(response, list):
        for part in response:
            if isinstance(part, dict):
                ptext = part.get('value', '') or part.get('content', '')
                if isinstance(ptext, str) and 'conversation-summary' in ptext.lower():
                    m = re.search(r'<conversation-summary>(.*?)</conversation-summary>', ptext, re.DOTALL | re.IGNORECASE)
                    if m:
                        compaction_summary = m.group(1).strip()
    return {
        'request_id': req.get('requestId', ''),
        'ts': req.get('timestamp', 0),
        'turn_index': turn_index,
        'message_text': text,
        'model_id': model_id,
        'compaction_summary': compaction_summary,
        # filled by result patch:
        'prompt_tokens': 0,
        'completion_tokens': 0,
        'cached_tokens': 0,
        'total_tokens': 0,
        'output_tokens': 0,
        'rendered_context': '',
        'compaction_meta': {},
    }


def _find_request_by_index(requests_map, idx):
    """Find request at position idx (by insertion order)."""
    items = list(requests_map.values())
    if 0 <= idx < len(items):
        return items[idx]
    return None


def _apply_result_patch(req, result):
    """Apply a result patch (timings, metadata, usage) to a request record."""
    meta = result.get('metadata', {}) or {}

    # Token usage — directly in metadata (promptTokens / outputTokens)
    pt = meta.get('promptTokens')
    ot = meta.get('outputTokens')
    if pt is not None:
        req['prompt_tokens'] = pt
    if ot is not None:
        req['output_tokens'] = ot
        req['completion_tokens'] = ot  # outputTokens IS completion tokens here

    # Model
    resolved = meta.get('resolvedModel', '')
    if resolved and not req['model_id']:
        req['model_id'] = resolved if isinstance(resolved, str) else str(resolved)

    # Compaction summaries — in metadata.summaries list
    summaries = meta.get('summaries', []) or []
    if isinstance(summaries, list) and summaries:
        # Take the first (most recent) summary entry
        s = summaries[0]
        if isinstance(s, dict) and s.get('text') and not req['compaction_summary']:
            req['compaction_summary'] = s['text']
            # Store rich compaction metadata on the request for use in build step
            req['compaction_meta'] = {
                'tool_call_round_id': s.get('toolCallRoundId', ''),
                'model': s.get('model', ''),
                'summarization_mode': s.get('summarizationMode', ''),
                'num_rounds': s.get('numRounds', 0),
                'context_length_before': s.get('contextLengthBefore', 0),
                'duration_ms': s.get('durationMs', 0),
                'outcome': s.get('outcome', ''),
                'usage': s.get('usage', {}),
            }


# ─────────────────────────────────────────────────────────
# Main processing
# ─────────────────────────────────────────────────────────

def process_session(conn, session_id, blob):
    """Process one chat session blob and write rows to all tables."""
    raw = gzip.decompress(blob).decode('utf-8', errors='replace')
    lines = [l for l in raw.splitlines() if l.strip()]

    requests_map = extract_requests_from_chat(lines)
    if not requests_map:
        return 0, 0, 0

    token_rows = []
    signal_rows = []
    compaction_rows = []

    for req in requests_map.values():
        rid = req['request_id']
        ts = req['ts']
        ti = req['turn_index']
        mid = req['model_id']

        # Token usage row (only if we have real data)
        if req['prompt_tokens'] or req['output_tokens']:
            token_rows.append((
                session_id, rid, ti, ts,
                req['prompt_tokens'], req['completion_tokens'],
                req['cached_tokens'], req['total_tokens'],
                req['output_tokens'], mid
            ))

        # Compaction row
        if req['compaction_summary']:
            trigger = req['message_text'][:200] if req['message_text'] else ''
            cmeta = req.get('compaction_meta', {})
            compaction_rows.append((
                session_id, rid, ti, ts,
                req['compaction_summary'],
                len(req['compaction_summary']),
                trigger,
                cmeta.get('context_length_before', 0),
                cmeta.get('num_rounds', 0),
                cmeta.get('model', ''),
                cmeta.get('duration_ms', 0),
            ))

        # Signal rows
        if req['message_text']:
            signals = classify_message(req['message_text'])
            for sig_type, matched_kw in signals:
                signal_rows.append((
                    session_id, None, rid, ts,
                    sig_type, req['message_text'][:500],
                    matched_kw, req['message_text'][:200]
                ))

    # Insert
    conn.executemany(
        """INSERT OR IGNORE INTO token_usage
           (session_id, request_id, turn_index, ts,
            prompt_tokens, completion_tokens, cached_tokens,
            total_tokens, output_tokens, model_id)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        token_rows
    )
    conn.executemany(
        """INSERT OR IGNORE INTO compactions
           (session_id, request_id, turn_index, ts,
            summary_text, summary_length, trigger_text,
            context_length_before, num_rounds, summary_model, duration_ms)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        compaction_rows
    )
    conn.executemany(
        """INSERT OR IGNORE INTO exchange_signals
           (session_id, exchange_index, request_id, ts,
            signal_type, signal_text, matched_keyword, user_message)
           VALUES (?,?,?,?,?,?,?,?)""",
        signal_rows
    )

    return len(token_rows), len(signal_rows), len(compaction_rows)


def build_session_analysis(conn, session_id):
    """Compute and upsert session_analysis row."""
    tok = conn.execute(
        """SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(cached_tokens)
           FROM token_usage WHERE session_id=?""", (session_id,)
    ).fetchone()

    sigs = conn.execute(
        """SELECT signal_type, COUNT(*) FROM exchange_signals
           WHERE session_id=? GROUP BY signal_type""", (session_id,)
    ).fetchall()
    sig_map = {r[0]: r[1] for r in sigs}

    comp = conn.execute(
        "SELECT COUNT(*) FROM compactions WHERE session_id=?", (session_id,)
    ).fetchone()[0]

    exc = conn.execute(
        """SELECT SUM(tool_call_count), MIN(user_ts), MAX(user_ts)
           FROM exchanges WHERE session_id=?""", (session_id,)
    ).fetchone()

    models = conn.execute(
        """SELECT DISTINCT model_id FROM token_usage
           WHERE session_id=? AND model_id != ''""", (session_id,)
    ).fetchall()
    model_ids = ','.join(r[0] for r in models)

    first_ts = exc[1]
    last_ts = exc[2]
    duration = None
    if first_ts and last_ts:
        try:
            from datetime import datetime
            f = datetime.fromisoformat(str(first_ts).replace('Z', '+00:00'))
            l = datetime.fromisoformat(str(last_ts).replace('Z', '+00:00'))
            duration = (l - f).total_seconds() / 60
        except Exception:
            pass

    total_corrections = sig_map.get('correction', 0)
    total_frustrations = sig_map.get('frustration', 0)
    total_pre_corrections = sig_map.get('pre_correction', 0)
    # Clean run = no corrections and at least 3 exchanges
    exc_count = conn.execute(
        "SELECT COUNT(*) FROM exchanges WHERE session_id=?", (session_id,)
    ).fetchone()[0]
    clean_run = 1 if total_corrections == 0 and exc_count >= 3 else 0

    # Heat score: weighted sum of negative signals
    # corrections=3pts, pre_correction=2pts, frustration=5pts, redirects=1pt
    # Normalized to 0–100 range (cap at 100)
    HEAT_WEIGHT = {
        'correction': 3,
        'pre_correction': 2,
        'frustration': 5,
        'redirect': 1,
    }
    raw_heat = (
        total_corrections * 3 +
        total_pre_corrections * 2 +
        total_frustrations * 5 +
        sig_map.get('redirect', 0) * 1
    )
    heat_score = min(100, raw_heat)

    # ── Per-turn heat timeline ─────────────────────────────────────
    # Group signals by ts, compute heat contribution per turn,
    # find: peak_heat, final_heat (last 5 turns), turning_point
    from collections import defaultdict
    signals_ordered = conn.execute(
        """SELECT ts, signal_type, user_message FROM exchange_signals
           WHERE session_id=? ORDER BY ts NULLS LAST""",
        (session_id,)
    ).fetchall()

    heat_by_ts: DefaultDict[int, int] = defaultdict(int)   # ts -> heat contribution
    types_by_ts: DefaultDict[int, List[str]] = defaultdict(list) # ts -> [signal_types]
    msg_by_ts: Dict[int, str] = {}                  # ts -> first message at that ts
    for s in signals_ordered:
        ts_val = s[0] or 0
        st = s[1]
        heat_by_ts[ts_val] += HEAT_WEIGHT.get(st, 0)
        types_by_ts[ts_val].append(st)
        if ts_val not in msg_by_ts and s[2]:
            msg_by_ts[ts_val] = s[2]

    sorted_ts = sorted(heat_by_ts.keys())

    # Cumulative heat timeline → peak_heat = heat_score (total is the peak)
    peak_heat = heat_score  # heat only accumulates, so peak == total

    # final_heat: heat contributed by last 5 turns
    last_5_ts = sorted_ts[-5:] if len(sorted_ts) >= 5 else sorted_ts
    final_heat = sum(heat_by_ts[ts] for ts in last_5_ts)

    # Turning point: ts of the LAST heat-generating signal (the "Antidote")
    # This is the correction/frustration that preceded recovery
    turning_point_ts = None
    turning_point_text = None
    for ts_val in reversed(sorted_ts):
        if heat_by_ts[ts_val] > 0:
            turning_point_ts = ts_val
            turning_point_text = (msg_by_ts.get(ts_val) or '')[:500]
            break

    # Saved session: had significant heat AND recovered
    # Recovery = final_heat == 0 (no heat in last 5 turns) AND ended with affirmations
    total_affirmations = sig_map.get('affirmation', 0) + sig_map.get('approval', 0)
    post_peak_affirmations = 0
    if turning_point_ts is not None:
        post_peak_affirmations = conn.execute(
            """SELECT COUNT(*) FROM exchange_signals
               WHERE session_id=? AND ts > ? AND signal_type IN ('affirmation','approval')""",
            (session_id, turning_point_ts)
        ).fetchone()[0]
    saved_session = 1 if (peak_heat >= 25 and final_heat <= peak_heat * 0.4 and post_peak_affirmations >= 1) else 0

    conn.execute("""
        INSERT INTO session_analysis
        (session_id, total_corrections, total_redirects, total_affirmations,
         total_tool_calls, total_tokens_prompt, total_tokens_completion,
         total_tokens_cached, compaction_count, session_duration_min,
         first_ts, last_ts, model_ids, clean_run,
         total_frustrations, total_pre_corrections, heat_score,
         peak_heat, final_heat, saved_session,
         turning_point_ts, turning_point_text)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ON CONFLICT(session_id) DO UPDATE SET
          total_corrections=excluded.total_corrections,
          total_redirects=excluded.total_redirects,
          total_affirmations=excluded.total_affirmations,
          total_tool_calls=excluded.total_tool_calls,
          total_tokens_prompt=excluded.total_tokens_prompt,
          total_tokens_completion=excluded.total_tokens_completion,
          total_tokens_cached=excluded.total_tokens_cached,
          compaction_count=excluded.compaction_count,
          session_duration_min=excluded.session_duration_min,
          first_ts=excluded.first_ts,
          last_ts=excluded.last_ts,
          model_ids=excluded.model_ids,
          clean_run=excluded.clean_run,
          total_frustrations=excluded.total_frustrations,
          total_pre_corrections=excluded.total_pre_corrections,
          heat_score=excluded.heat_score,
          peak_heat=excluded.peak_heat,
          final_heat=excluded.final_heat,
          saved_session=excluded.saved_session,
          turning_point_ts=excluded.turning_point_ts,
          turning_point_text=excluded.turning_point_text,
          analyzed_at=datetime('now')
    """, (
        session_id,
        sig_map.get('correction', 0),
        sig_map.get('redirect', 0),
        sig_map.get('affirmation', 0),
        exc[0] or 0,
        tok[0] or 0, tok[1] or 0, tok[2] or 0,
        comp,
        duration,
        first_ts, last_ts,
        model_ids,
        clean_run,
        total_frustrations,
        total_pre_corrections,
        heat_score,
        peak_heat,
        final_heat,
        saved_session,
        turning_point_ts,
        turning_point_text,
    ))


def run():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.execute("PRAGMA journal_mode=WAL")

    # Ensure analysis tables exist
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            request_id TEXT,
            turn_index INTEGER,
            ts INTEGER,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            cached_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            model_id TEXT,
            ingested_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_token_usage_session ON token_usage(session_id);

        CREATE TABLE IF NOT EXISTS compactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            request_id TEXT,
            turn_index INTEGER,
            ts INTEGER,
            summary_text TEXT,
            summary_length INTEGER,
            trigger_text TEXT,
            ingested_at TEXT DEFAULT (datetime('now')),
            context_length_before INTEGER DEFAULT 0,
            num_rounds INTEGER DEFAULT 0,
            summary_model TEXT,
            duration_ms INTEGER DEFAULT 0
        );
        CREATE INDEX IF NOT EXISTS idx_compactions_session ON compactions(session_id);

        CREATE TABLE IF NOT EXISTS exchange_signals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            exchange_index INTEGER,
            request_id TEXT,
            ts INTEGER,
            signal_type TEXT NOT NULL,
            signal_text TEXT,
            matched_keyword TEXT,
            user_message TEXT,
            ingested_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_signals_session ON exchange_signals(session_id);
        CREATE INDEX IF NOT EXISTS idx_signals_type ON exchange_signals(signal_type);

        CREATE TABLE IF NOT EXISTS session_analysis (
            session_id TEXT PRIMARY KEY,
            total_corrections INTEGER DEFAULT 0,
            total_redirects INTEGER DEFAULT 0,
            total_affirmations INTEGER DEFAULT 0,
            total_tool_calls INTEGER DEFAULT 0,
            total_tokens_prompt INTEGER DEFAULT 0,
            total_tokens_completion INTEGER DEFAULT 0,
            total_tokens_cached INTEGER DEFAULT 0,
            compaction_count INTEGER DEFAULT 0,
            session_duration_min REAL,
            first_ts INTEGER,
            last_ts INTEGER,
            model_ids TEXT,
            analyzed_at TEXT DEFAULT (datetime('now')),
            total_frustrations INTEGER DEFAULT 0,
            total_pre_corrections INTEGER DEFAULT 0,
            heat_score INTEGER DEFAULT 0,
            peak_heat INTEGER DEFAULT 0,
            final_heat INTEGER DEFAULT 0,
            saved_session INTEGER DEFAULT 0,
            turning_point_ts INTEGER,
            turning_point_text TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS fts_exchanges USING fts5(
            session_id      UNINDEXED,
            workspace_id    UNINDEXED,
            exchange_index  UNINDEXED,
            user_ts         UNINDEXED,
            user_message,
            reasoning_text,
            response_text,
            tool_calls,
            content=exchanges,
            content_rowid=id
        );

        CREATE TABLE IF NOT EXISTS symbols (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id TEXT,
            file_path TEXT,
            symbol_name TEXT,
            symbol_type TEXT,  -- function, class, method, variable, etc.
            line_number INTEGER,
            context TEXT,      -- surrounding code context
            indexed_at INTEGER
        );
        CREATE INDEX IF NOT EXISTS idx_symbols_workspace ON symbols(workspace_id);
        CREATE INDEX IF NOT EXISTS idx_symbols_type ON symbols(symbol_type);
        CREATE INDEX IF NOT EXISTS idx_symbols_name ON symbols(symbol_name);
    """)

    # Ensure tool_calls table exists
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id      TEXT NOT NULL,
            exchange_index  INTEGER,
            request_id      TEXT,
            tool_call_id    TEXT,
            tool_name       TEXT NOT NULL,
            file_path       TEXT,
            arguments_json  TEXT,
            has_output      INTEGER DEFAULT 0,
            ingested_at     TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_tool_calls_session  ON tool_calls(session_id);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_name     ON tool_calls(tool_name);
        CREATE INDEX IF NOT EXISTS idx_tool_calls_file     ON tool_calls(file_path);
    """)
    conn.commit()

    # Clear existing extracted data for a clean re-run
    conn.execute("DELETE FROM token_usage")
    conn.execute("DELETE FROM compactions")
    conn.execute("DELETE FROM exchange_signals")
    conn.execute("DELETE FROM session_analysis")
    conn.commit()

    # Get all sessions that have a chat_session blob
    blobs = conn.execute(
        """SELECT v.session_id, v.content
           FROM vfs v
           WHERE v.source_type = 'chat_session'
           ORDER BY v.session_id"""
    ).fetchall()

    print(f"Processing {len(blobs)} chat sessions...")
    total_tok = total_sig = total_comp = 0
    errors = 0

    for i, (sid, content) in enumerate(blobs):
        try:
            t, s, c = process_session(conn, sid, content)
            total_tok += t
            total_sig += s
            total_comp += c
            build_session_analysis(conn, sid)
            if i % 20 == 0:
                conn.commit()
                print(f"  [{i+1}/{len(blobs)}] tokens={total_tok} signals={total_sig} compactions={total_comp}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"  ERROR {sid[:16]}: {e}")

    conn.commit()

    # ── Populate tool_calls from exchanges ──────────────────────────────────
    print("\nBuilding tool_calls index from exchanges...")
    conn.execute("DELETE FROM tool_calls")
    tc_rows = []
    exch_rows = conn.execute(
        "SELECT session_id, exchange_index, request_id, tool_calls FROM exchanges WHERE tool_call_count > 0"
    ).fetchall()
    for sid, ex_idx, req_id, tc_json in exch_rows:
        try:
            tool_calls_list = json.loads(tc_json or '[]')
        except Exception:
            continue
        for tc in tool_calls_list:
            if not isinstance(tc, dict):
                continue
            name = tc.get('name', '') or ''
            tc_id = tc.get('toolCallId', '') or ''
            args = tc.get('arguments', {}) or {}
            has_out = 1 if tc.get('output') else 0
            # Extract file path from common argument patterns
            file_path = ''
            if isinstance(args, dict):
                file_path = (
                    args.get('filePath') or args.get('file_path') or
                    args.get('path') or args.get('uri') or ''
                )
                if not file_path:
                    # For read_file / grep_search / replace_string_in_file
                    for k in ('filePath', 'file_path', 'path', 'uri', 'includePattern', 'query'):
                        v = args.get(k)
                        if isinstance(v, str) and ('/' in v or '\\' in v):
                            file_path = v
                            break
            tc_rows.append((
                sid, ex_idx, req_id, tc_id, name,
                str(file_path)[:500] if file_path else '',
                json.dumps(args)[:1000], has_out,
            ))

    conn.executemany("""
        INSERT INTO tool_calls
        (session_id, exchange_index, request_id, tool_call_id,
         tool_name, file_path, arguments_json, has_output)
        VALUES (?,?,?,?,?,?,?,?)
    """, tc_rows)
    conn.commit()
    n_tc = conn.execute("SELECT COUNT(*) FROM tool_calls").fetchone()[0]
    print(f"  tool_calls rows: {n_tc}")

    conn.close()

    print(f"\nDone.")
    print(f"  token_usage rows:     {total_tok}")
    print(f"  exchange_signals rows:{total_sig}")
    print(f"  compaction rows:      {total_comp}")
    print(f"  errors:               {errors}")


if __name__ == "__main__":
    run()
