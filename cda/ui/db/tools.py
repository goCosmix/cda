from .base import query_rows


def get_tool_calls(query_str=None, limit=50):
    """Search tool calls."""
    try:
        if query_str:
            results = query_rows("""
                SELECT tc.id, tc.session_id, tc.exchange_index, tc.request_id,
                       tc.tool_call_id, tc.tool_name, tc.file_path,
                       tc.arguments_json, tc.has_output, tc.ingested_at,
                       s.title as session_title
                FROM tool_calls tc
                JOIN sessions s ON tc.session_id = s.session_id
                WHERE tc.tool_name LIKE ? OR tc.arguments_json LIKE ?
                ORDER BY tc.ingested_at DESC
                LIMIT ?
            """, (f"%{query_str}%", f"%{query_str}%", limit))
        else:
            results = query_rows("""
                SELECT tc.id, tc.session_id, tc.exchange_index, tc.request_id,
                       tc.tool_call_id, tc.tool_name, tc.file_path,
                       tc.arguments_json, tc.has_output, tc.ingested_at,
                       s.title as session_title
                FROM tool_calls tc
                JOIN sessions s ON tc.session_id = s.session_id
                ORDER BY tc.ingested_at DESC
                LIMIT ?
            """, (limit,))
        return {"tool_calls": results, "query": query_str, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}


def get_vfs(session_id):
    """List VFS files for a session."""
    try:
        vfs = query_rows("""
            SELECT id, session_id, source_type, source_path, filename,
                   content_type, size_bytes, sha256, ingested_at
            FROM vfs
            WHERE session_id = ?
            ORDER BY filename
        """, (session_id,))
        return {"vfs": vfs, "session_id": session_id}
    except Exception as e:
        return {"error": str(e)}
