from .base import query_rows


def get_memory():
    """Get all memory files."""
    try:
        memory = query_rows("""
            SELECT id, scope, workspace_id, session_id, filename, size_bytes, ingested_at
            FROM memory_files
            ORDER BY ingested_at DESC
        """)
        return {"memory": memory}
    except Exception as e:
        return {"error": str(e)}
