from .base import query_rows, query_one, safe_rows, safe_one, table_exists


def get_sessions(limit=50, offset=0):
    """List all sessions with heat scores."""
    try:
        has_analysis = table_exists('session_analysis')
        has_exchanges = table_exists('exchanges')
        exchange_count_expr = (
            "(SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id)"
            if has_exchanges else "0"
        )

        if has_analysis:
            sessions = safe_rows(query_rows(f"""
                SELECT s.session_id as id, s.title, sa.heat_score, s.workspace_id,
                       {exchange_count_expr} as exchange_count,
                       s.created_at
                FROM sessions s
                LEFT JOIN session_analysis sa ON sa.session_id = s.session_id
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)))
        else:
            sessions = safe_rows(query_rows(f"""
                SELECT s.session_id as id, s.title, NULL as heat_score, s.workspace_id,
                       {exchange_count_expr} as exchange_count,
                       s.created_at
                FROM sessions s
                ORDER BY s.created_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)))

        total = safe_one(query_one("SELECT COUNT(*) as count FROM sessions"))

        return {
            "sessions": sessions,
            "total": total["count"] if total else 0,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        return {"error": str(e)}


def get_session_detail(session_id):
    """Get full session with all exchanges and signals."""
    if not session_id:
        return {"error": "Missing session_id"}

    try:
        has_exchanges = table_exists('exchanges')
        has_tool_calls = table_exists('tool_calls')
        has_vfs = table_exists('vfs')
        has_alerts = table_exists('anomaly_alerts')
        has_signals = table_exists('exchange_signals')
        has_analysis = table_exists('session_analysis')

        session = safe_one(query_one(
            "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
        ))
        if not session:
            return {"error": "Session not found"}

        exchanges = safe_rows(query_rows("""
            SELECT id, exchange_index, user_message as user_input, response_text as assistant_response,
                   tool_calls, tool_call_count, ingested_at as created_at
            FROM exchanges
            WHERE session_id = ?
            ORDER BY ingested_at ASC
        """, (session_id,))) if has_exchanges else []

        tool_calls = safe_rows(query_rows("""
            SELECT id, session_id, exchange_index, request_id, tool_call_id, tool_name,
                   file_path, arguments_json, has_output, ingested_at
            FROM tool_calls
            WHERE session_id = ?
            ORDER BY ingested_at ASC
        """, (session_id,))) if has_tool_calls else []

        vfs_entries = safe_rows(query_rows("""
            SELECT id, source_type, source_path, filename, content_type, size_bytes, sha256, ingested_at
            FROM vfs
            WHERE session_id = ?
            ORDER BY filename ASC
        """, (session_id,))) if has_vfs else []

        alerts = safe_rows(query_rows("""
            SELECT id, alert_type, severity, message, created_at
            FROM anomaly_alerts
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))) if has_alerts else []

        signals = safe_rows(query_rows("""
            SELECT * FROM exchange_signals
            WHERE session_id = ?
            ORDER BY ts DESC
        """, (session_id,))) if has_signals else []

        signal_summary = safe_rows(query_rows("""
            SELECT signal_type, COUNT(*) as count
            FROM exchange_signals
            WHERE session_id = ?
            GROUP BY signal_type
        """, (session_id,))) if has_signals else []

        analysis = safe_one(query_one("""
            SELECT * FROM session_analysis
            WHERE session_id = ?
            LIMIT 1
        """, (session_id,))) if has_analysis else None

        return {
            "session": dict(session),
            "analysis": analysis,
            "exchanges": exchanges,
            "tool_calls": tool_calls,
            "vfs": vfs_entries,
            "alerts": alerts,
            "signals": signals,
            "signal_summary": signal_summary
        }
    except Exception as e:
        return {"error": str(e)}
