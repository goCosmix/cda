from .base import query_rows


def get_search_results(query, limit=50):
    """Full-text search across exchanges."""
    try:
        results = query_rows("""
            SELECT
                e.session_id,
                s.title,
                sa.heat_score,
                e.id as exchange_id,
                e.exchange_index,
                e.user_message,
                e.response_text,
                e.user_ts
            FROM fts_exchanges fts
            JOIN exchanges e ON fts.rowid = e.id
            JOIN sessions s ON e.session_id = s.session_id
            LEFT JOIN session_analysis sa ON sa.session_id = e.session_id
            WHERE fts_exchanges MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        return {"results": results, "query": query, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}
