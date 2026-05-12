from .base import query_rows


def get_workspaces():
    """List all workspaces with session counts."""
    try:
        workspaces = query_rows("""
            SELECT w.workspace_id, w.uri, w.name, w.type, w.session_count,
                   (SELECT MAX(s.created_at) FROM sessions s
                    WHERE s.workspace_id = w.workspace_id) as last_session
            FROM workspaces w
            ORDER BY w.session_count DESC
        """)
        return {"workspaces": workspaces}
    except Exception as e:
        return {"error": str(e)}


def get_workspace_detail(workspace_id):
    """Get all sessions for a workspace."""
    try:
        sessions = query_rows("""
            SELECT s.session_id as id, s.title, sa.heat_score,
                   (SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id) as exchange_count,
                   s.created_at
            FROM sessions s
            LEFT JOIN session_analysis sa ON sa.session_id = s.session_id
            WHERE s.workspace_id = ?
            ORDER BY s.created_at DESC
        """, (workspace_id,))
        return {"workspace_id": workspace_id, "sessions": sessions}
    except Exception as e:
        return {"error": str(e)}
