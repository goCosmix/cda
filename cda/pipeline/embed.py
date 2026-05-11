#!/usr/bin/env python3
"""embed.py — Semantic intelligence for vscode-ark.

This stage builds semantic embeddings and mini-intelligence artifacts:
  - embeddings for sessions, exchanges and memory files
  - session summaries and topic tags
  - anomaly alerts for high-heat or recovery sessions
  - review recommendations for session follow-up
"""

import json
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOCAL_DIR = ROOT_DIR / "local"
DB_PATH = LOCAL_DIR / "data" / "vscode-ark.db"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
MAX_EMBED_TEXT = 1400

MODEL = None


def get_model():
    global MODEL
    if MODEL is not None:
        return MODEL
    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "Install sentence-transformers to use semantic intelligence: "
            "pip install sentence-transformers"
        ) from exc
    MODEL = SentenceTransformer(MODEL_NAME)
    return MODEL


def db():
    conn = sqlite3.connect(str(DB_PATH), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn


def _serialize_embedding(vector):
    import numpy as np

    if vector is None:
        return None
    return np.asarray(vector, dtype="float32").tobytes()


def _deserialize_embedding(blob):
    import numpy as np

    if blob is None:
        return None
    return np.frombuffer(blob, dtype="float32")


def _truncate_text(text: str, length: int = MAX_EMBED_TEXT) -> str:
    if not text:
        return ""
    text = text.replace("\n", " ").strip()
    return text[:length]


def ensure_tables(conn):
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS embeddings (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        entity_type TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        workspace_id TEXT,
        session_id TEXT,
        exchange_index INTEGER,
        content_type TEXT,
        content_text TEXT,
        metadata TEXT,
        embedding BLOB,
        created_at TEXT DEFAULT (datetime('now')),
        UNIQUE(entity_type, entity_id)
    );
    CREATE INDEX IF NOT EXISTS idx_embeddings_entity ON embeddings(entity_type, entity_id);
    CREATE INDEX IF NOT EXISTS idx_embeddings_session ON embeddings(session_id);

    CREATE VIRTUAL TABLE IF NOT EXISTS fts_embeddings USING fts5(
        entity_type UNINDEXED,
        entity_id UNINDEXED,
        session_id UNINDEXED,
        exchange_index UNINDEXED,
        content_text,
        metadata
    );

    CREATE TABLE IF NOT EXISTS session_summaries (
        session_id TEXT PRIMARY KEY,
        summary_text TEXT,
        topic_tags TEXT,
        updated_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS anomaly_alerts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        alert_type TEXT,
        severity TEXT,
        message TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );

    CREATE TABLE IF NOT EXISTS recommendations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT,
        recommendation_text TEXT,
        source TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    );
    """)
    conn.commit()


def _fetch_session_title(conn, session_id: str) -> str:
    row = conn.execute("SELECT title FROM sessions WHERE session_id=?", (session_id,)).fetchone()
    return row[0] if row else ""


def _get_session_content(conn, session_id: str) -> str:
    rows = conn.execute(
        "SELECT user_message, reasoning_text, response_text, tool_calls "
        "FROM exchanges WHERE session_id=? ORDER BY user_ts LIMIT 50",
        (session_id,),
    ).fetchall()
    pieces = []
    for row in rows:
        if row["user_message"]:
            pieces.append(f"USER: {row['user_message']}")
        if row["reasoning_text"]:
            pieces.append(f"ASSISTANT_THINK: {row['reasoning_text']}")
        if row["response_text"]:
            pieces.append(f"ASSISTANT: {row['response_text']}")
        if row["tool_calls"]:
            pieces.append(f"TOOL: {row['tool_calls']}")
    if not pieces:
        return _truncate_text(_fetch_session_title(conn, session_id))
    return _truncate_text(" \n ".join(pieces))


def _get_exchange_content(row) -> str:
    text = " ".join(
        str(row[field] or "") for field in (
            "user_message", "reasoning_text", "response_text", "tool_calls"
        )
    )
    return _truncate_text(text)


def _get_memory_content(row) -> str:
    return _truncate_text(str(row["content"] or ""))


def _embed_texts(texts: List[str]):
    model = get_model()
    vectors = model.encode(texts, convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)
    return [v.astype("float32") for v in vectors]


def upsert_embedding(
    conn,
    entity_type: str,
    entity_id: str,
    workspace_id: Optional[str],
    session_id: Optional[str],
    exchange_index: Optional[int],
    content_type: str,
    content_text: str,
    metadata: Dict,
):
    if not content_text:
        return
    vector = _embed_texts([content_text])[0]
    blob = _serialize_embedding(vector)
    existing = conn.execute(
        "SELECT id FROM embeddings WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    ).fetchone()
    if existing:
        rowid = existing[0]
        conn.execute(
            """
            UPDATE embeddings SET
              workspace_id=?,
              session_id=?,
              exchange_index=?,
              content_type=?,
              content_text=?,
              metadata=?,
              embedding=?,
              created_at=datetime('now')
            WHERE id=?
            """,
            (
                workspace_id,
                session_id,
                exchange_index,
                content_type,
                content_text,
                json.dumps(metadata, ensure_ascii=False),
                blob,
                rowid,
            ),
        )
    else:
        cur = conn.execute(
            """
            INSERT INTO embeddings
            (entity_type, entity_id, workspace_id, session_id, exchange_index, content_type, content_text, metadata, embedding)
            VALUES (?,?,?,?,?,?,?,?,?)
            """,
            (
                entity_type,
                entity_id,
                workspace_id,
                session_id,
                exchange_index,
                content_type,
                content_text,
                json.dumps(metadata, ensure_ascii=False),
                blob,
            ),
        )
        rowid = cur.lastrowid

    # Maintain a fast FTS index for embedding content and metadata.
    conn.execute(
        "INSERT OR REPLACE INTO fts_embeddings(rowid, entity_type, entity_id, session_id, exchange_index, content_text, metadata) VALUES (?,?,?,?,?,?,?)",  # noqa: E501
        (
            rowid,
            entity_type,
            entity_id,
            session_id,
            exchange_index,
            content_text,
            json.dumps(metadata, ensure_ascii=False),
        ),
    )


def build_session_summaries(conn, session_id: Optional[str] = None):
    session_query = "SELECT session_id FROM sessions"
    args: Tuple = ()
    if session_id:
        session_query += " WHERE session_id=?"
        args = (session_id,)

    for row in conn.execute(session_query, args).fetchall():
        sid = row[0]
        analytics = conn.execute(
            "SELECT * FROM session_analysis WHERE session_id=?", (sid,)
        ).fetchone()
        if not analytics:
            continue
        title = _fetch_session_title(conn, sid)

        parts = []
        if title:
            parts.append(title)

        heat = analytics["heat_score"] or 0
        corrections = analytics["total_corrections"] or 0
        frustrations = analytics["total_frustrations"] or 0
        redirects = analytics["total_redirects"] or 0
        tools = analytics["total_tool_calls"] or 0
        compactions = analytics["compaction_count"] or 0
        saved = bool(analytics["saved_session"])
        clean = bool(analytics["clean_run"])

        if heat >= 75:
            parts.append("High-heat session with friction and corrections.")
        elif heat >= 40:
            parts.append("Moderate-heat session with some friction.")
        elif clean:
            parts.append("Clean session with few corrections and stable flow.")
        else:
            parts.append("Session with a normal effort profile.")

        if frustrations:
            parts.append(f"{frustrations} frustration signal(s) detected.")
        if corrections:
            parts.append(f"{corrections} correction signal(s) detected.")
        if redirects:
            parts.append(f"{redirects} scope-change signal(s) detected.")
        if tools:
            parts.append(f"{tools} tool call(s) were used.")
        if compactions:
            parts.append(f"{compactions} context compaction event(s) occurred.")
        if saved:
            parts.append("The session recovered after friction.")

        summary_text = " ".join(parts)
        topic_tags = _infer_topic_tags(title, analytics)
        conn.execute(
            """
            INSERT INTO session_summaries(session_id, summary_text, topic_tags)
            VALUES (?,?,?)
            ON CONFLICT(session_id) DO UPDATE SET
              summary_text=excluded.summary_text,
              topic_tags=excluded.topic_tags,
              updated_at=datetime('now')
            """,
            (sid, summary_text, ",".join(topic_tags)),
        )
        build_anomaly_alerts(conn, sid, analytics)
        build_recommendations(conn, sid, analytics, topic_tags)
    conn.commit()


def _infer_topic_tags(title: str, analytics) -> List[str]:
    tags: List[str] = []
    title_lower = (title or "").lower()
    heat = analytics["heat_score"] or 0
    corrections = analytics["total_corrections"] or 0
    frustrations = analytics["total_frustrations"] or 0
    redirects = analytics["total_redirects"] or 0
    tools = analytics["total_tool_calls"] or 0
    compactions = analytics["compaction_count"] or 0
    saved = bool(analytics["saved_session"])
    clean = bool(analytics["clean_run"])

    if heat >= 70:
        tags.append("high-heat")
    elif heat >= 40:
        tags.append("medium-heat")
    else:
        tags.append("low-heat")

    if corrections >= 3:
        tags.append("correction-heavy")
    if frustrations >= 1:
        tags.append("frustration")
    if redirects >= 2:
        tags.append("scope-change")
    if tools:
        tags.append("tool-driven")
    if compactions:
        tags.append("self-summary")
    if saved:
        tags.append("recovery")
    if clean:
        tags.append("clean-run")
    if any(k in title_lower for k in ["git", "branch", "commit", "merge"]):
        tags.append("git")
    if any(k in title_lower for k in ["error", "fail", "exception", "crash"]):
        tags.append("bug")
    if any(k in title_lower for k in ["refactor", "cleanup", "format", "optimize"]):
        tags.append("refactor")
    if any(k in title_lower for k in ["deploy", "publish", "release"]):
        tags.append("deployment")

    return sorted(set(tags))


def build_anomaly_alerts(conn, session_id: str, analytics=None):
    if analytics is None:
        analytics = conn.execute(
            "SELECT * FROM session_analysis WHERE session_id=?", (session_id,)
        ).fetchone()
    if not analytics:
        return
    conn.execute("DELETE FROM anomaly_alerts WHERE session_id=?", (session_id,))
    alerts = []
    heat = analytics["heat_score"] or 0
    corrections = analytics["total_corrections"] or 0
    frustrations = analytics["total_frustrations"] or 0
    saved = bool(analytics["saved_session"])

    if heat >= 80:
        alerts.append(("high_heat", "high", "Session has very high heat and may indicate repeated failure or stuck troubleshooting."))
    elif heat >= 55:
        alerts.append(("elevated_heat", "medium", "Session shows elevated heat and may warrant review."))

    if frustrations >= 2:
        alerts.append(("multiple_frustrations", "medium", "Multiple frustration signals were detected."))

    if corrections >= 4 and not saved:
        alerts.append(("corrective_cycle", "high", "Multiple corrections without clear recovery were detected."))

    if saved and heat >= 25:
        alerts.append(("recovery", "low", "Session recovered from friction, worth studying for successful resolution patterns."))

    for alert_type, severity, message in alerts:
        conn.execute(
            "INSERT INTO anomaly_alerts(session_id, alert_type, severity, message) VALUES (?,?,?,?)",
            (session_id, alert_type, severity, message),
        )


def build_recommendations(conn, session_id: str, analytics, topic_tags: List[str]):
    conn.execute("DELETE FROM recommendations WHERE session_id=?", (session_id,))
    recs: List[Tuple[str, str]] = []
    heat = analytics["heat_score"] or 0
    corrections = analytics["total_corrections"] or 0
    tools = analytics["total_tool_calls"] or 0
    saved = bool(analytics["saved_session"])

    if heat >= 70 and not saved:
        recs.append(("followup", "Review this session for stuck issue patterns and possible unresolved errors."))
    if saved and heat >= 40:
        recs.append(("review_recovery", "Inspect the recovery path and tool outputs for best-practice behavior."))
    if tools >= 2:
        recs.append(("inspect_tools", "Confirm tool call outputs and any file changes associated with this session."))
    if corrections >= 3:
        recs.append(("focus_scope", "Review the session scope and prompts to reduce correction cycles."))
    if not recs:
        recs.append(("no_action", "No immediate recommendations; session appears stable."))

    for source, text in recs:
        conn.execute(
            "INSERT INTO recommendations(session_id, recommendation_text, source) VALUES (?,?,?)",
            (session_id, text, source),
        )


def build_session_embedding(conn, session_id: str):
    text = _get_session_content(conn, session_id)
    if not text:
        return
    upsert_embedding(
        conn,
        entity_type="session",
        entity_id=session_id,
        workspace_id=None,
        session_id=session_id,
        exchange_index=None,
        content_type="session",
        content_text=text,
        metadata={"stage": "session"},
    )


def build_exchange_embeddings(conn):
    rows = conn.execute(
        "SELECT id, session_id, workspace_id, exchange_index, user_message, reasoning_text, response_text, tool_calls "
        "FROM exchanges ORDER BY session_id, exchange_index"
    ).fetchall()
    for row in rows:
        text = _get_exchange_content(row)
        if not text:
            continue
        upsert_embedding(
            conn,
            entity_type="exchange",
            entity_id=f"{row['session_id']}:{row['exchange_index']}",
            workspace_id=row["workspace_id"],
            session_id=row["session_id"],
            exchange_index=row["exchange_index"],
            content_type="exchange",
            content_text=text,
            metadata={"stage": "exchange"},
        )
    conn.commit()


def build_memory_embeddings(conn):
    rows = conn.execute(
        "SELECT id, scope, workspace_id, session_id, filename, content FROM memory_files"
    ).fetchall()
    for row in rows:
        text = _get_memory_content(row)
        if not text:
            continue
        upsert_embedding(
            conn,
            entity_type="memory",
            entity_id=f"memory:{row['id']}",
            workspace_id=row["workspace_id"],
            session_id=row["session_id"],
            exchange_index=None,
            content_type=row["scope"],
            content_text=text,
            metadata={"filename": row["filename"] or "", "scope": row["scope"]},
        )
    conn.commit()


def _session_behavior_score(conn, base_session_id: str, candidate_session_id: str) -> float:
    base = conn.execute(
        "SELECT heat_score, total_tool_calls, saved_session, clean_run FROM session_analysis WHERE session_id=?",
        (base_session_id,),
    ).fetchone()
    cand = conn.execute(
        "SELECT heat_score, total_tool_calls, saved_session, clean_run FROM session_analysis WHERE session_id=?",
        (candidate_session_id,),
    ).fetchone()
    if not base or not cand:
        return 0.0

    score = 0.0
    score += 1.0 if base[2] == cand[2] else 0.0
    score += 0.5 if base[3] == cand[3] else 0.0

    def heat_bucket(value):
        if value is None:
            return -1
        if value < 40:
            return 0
        if value < 70:
            return 1
        return 2

    score += 0.5 if heat_bucket(base[0]) == heat_bucket(cand[0]) else 0.0
    if base[1] is not None and cand[1] is not None:
        tool_diff = abs(base[1] - cand[1])
        max_tools = max(base[1], cand[1], 1)
        score += max(0.0, 0.5 * (1.0 - (tool_diff / max_tools)))
    return score


def find_similar_sessions(conn, session_id: str, top_k: int = 5):
    row = conn.execute(
        "SELECT embedding FROM embeddings WHERE entity_type='session' AND entity_id=?",
        (session_id,),
    ).fetchone()
    if not row or not row[0]:
        return []

    import numpy as np

    target = _deserialize_embedding(row[0])
    rows = conn.execute(
        "SELECT entity_type, entity_id, session_id, exchange_index, content_text, metadata, embedding FROM embeddings WHERE entity_type='session' AND entity_id!=?",  # noqa: E501
        (session_id,),
    ).fetchall()
    candidates = []
    for item in rows:
        emb = _deserialize_embedding(item[6])
        if emb is None or emb.shape != target.shape:
            continue
        semantic_score = float(np.dot(target, emb))
        behavioral_score = _session_behavior_score(conn, session_id, item['session_id'] or item['entity_id'])
        score = semantic_score + (behavioral_score * 0.15)
        candidates.append((score, item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [(item, score) for score, item in candidates[:top_k]]


def find_similar_entities(conn, entity_type: str, entity_id: str, top_k: int = 5):
    if entity_type == 'session':
        return find_similar_sessions(conn, entity_id, top_k)

    row = conn.execute(
        "SELECT embedding FROM embeddings WHERE entity_type=? AND entity_id=?",
        (entity_type, entity_id),
    ).fetchone()
    if not row or not row[0]:
        return []
    import numpy as np

    target = _deserialize_embedding(row[0])
    query = "SELECT entity_type, entity_id, session_id, exchange_index, content_text, metadata, embedding "
    query += "FROM embeddings WHERE entity_type='session' AND entity_id!=?" if entity_type == "session" else "FROM embeddings WHERE entity_type IN ('session','exchange') AND entity_id!=?"  # noqa: E501
    rows = conn.execute(query, (entity_id,)).fetchall()
    candidates = []
    for item in rows:
        emb = _deserialize_embedding(item[6])
        if emb is None or emb.shape != target.shape:
            continue
        score = float(np.dot(target, emb))
        candidates.append((score, item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [(item, score) for score, item in candidates[:top_k]]


def semantic_search(conn, query_text: str, top_k: int = 5):
    if not query_text:
        return []
    import numpy as np

    model = get_model()
    query_vec = model.encode([query_text], convert_to_numpy=True, normalize_embeddings=True, show_progress_bar=False)[0].astype("float32")
    rows = []
    try:
        candidate_ids = [r[0] for r in conn.execute(
            "SELECT rowid FROM fts_embeddings WHERE fts_embeddings MATCH ? LIMIT ?",
            (query_text, top_k * 5),
        ).fetchall()]
        if candidate_ids:
            placeholder = ",".join("?" for _ in candidate_ids)
            rows = conn.execute(
                f"SELECT entity_type, entity_id, session_id, exchange_index, content_text, metadata, embedding FROM embeddings WHERE id IN ({placeholder})",  # noqa: E501
                candidate_ids,
            ).fetchall()
    except Exception:
        rows = []

    if not rows:
        rows = conn.execute(
            "SELECT entity_type, entity_id, session_id, exchange_index, content_text, metadata, embedding "
            "FROM embeddings WHERE entity_type IN ('session','exchange','memory')"
        ).fetchall()

    candidates = []
    for item in rows:
        emb = _deserialize_embedding(item[6])
        if emb is None or emb.shape != query_vec.shape:
            continue
        score = float(np.dot(query_vec, emb))
        candidates.append((score, item))
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [(item, score) for score, item in candidates[:top_k]]


def get_session_summary(conn, session_id: str) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT session_id, summary_text, topic_tags, updated_at FROM session_summaries WHERE session_id=?",
        (session_id,),
    ).fetchone()


def get_session_alerts(conn, session_id: str) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT alert_type, severity, message, created_at FROM anomaly_alerts WHERE session_id=? ORDER BY id",
        (session_id,),
    ).fetchall()


def get_session_recommendations(conn, session_id: str) -> List[sqlite3.Row]:
    return conn.execute(
        "SELECT recommendation_text, source, created_at FROM recommendations WHERE session_id=? ORDER BY id",
        (session_id,),
    ).fetchall()


def get_topic_counts(conn, limit: int = 20) -> List[Tuple[str, int]]:
    rows = conn.execute(
        "SELECT topic_tags FROM session_summaries WHERE topic_tags != ''"
    ).fetchall()
    counter: Dict[str, int] = {}
    for row in rows:
        tags = [t.strip() for t in (row[0] or "").split(",") if t.strip()]
        for tag in tags:
            counter[tag] = counter.get(tag, 0) + 1
    items = sorted(counter.items(), key=lambda x: x[1], reverse=True)
    return items[:limit]


def build(conn: Optional[sqlite3.Connection] = None):
    own_conn = conn is None
    if conn is None:
        conn = db()
    ensure_tables(conn)
    build_session_summaries(conn)
    print("Building session embeddings...")
    session_ids = [r[0] for r in conn.execute("SELECT session_id FROM sessions").fetchall()]
    for i, sid in enumerate(session_ids, 1):
        build_session_embedding(conn, sid)
        if i % 20 == 0:
            conn.commit()
            print(f"  [{i}/{len(session_ids)}] sessions embedded")
    conn.commit()
    print("Building exchange embeddings...")
    build_exchange_embeddings(conn)
    print("Building memory embeddings...")
    build_memory_embeddings(conn)
    if own_conn:
        conn.close()


def build_session_intelligence(conn, session_id: str):
    ensure_tables(conn)
    build_session_summaries(conn, session_id)
    try:
        build_session_embedding(conn, session_id)
    except Exception:
        pass
    conn.commit()


def run():
    conn = db()
    ensure_tables(conn)
    build(conn)
    conn.close()
    print("Semantic intelligence build complete.")


if __name__ == "__main__":
    run()
