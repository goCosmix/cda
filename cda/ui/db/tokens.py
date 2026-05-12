from .base import query_rows


def get_tokens(session_id=None):
    """Get token usage analysis."""
    try:
        if session_id:
            tokens = query_rows("""
                SELECT
                    SUM(prompt_tokens) as total_prompt,
                    SUM(completion_tokens) as total_completion,
                    SUM(cached_tokens) as total_cached,
                    SUM(prompt_tokens + completion_tokens) as total_tokens,
                    COUNT(*) as turn_count,
                    GROUP_CONCAT(DISTINCT model_id) as models
                FROM token_usage
                WHERE session_id = ?
            """, (session_id,))
        else:
            tokens = query_rows("""
                SELECT
                    SUM(prompt_tokens) as total_prompt,
                    SUM(completion_tokens) as total_completion,
                    SUM(cached_tokens) as total_cached,
                    SUM(prompt_tokens + completion_tokens) as total_tokens,
                    COUNT(*) as turn_count,
                    COUNT(DISTINCT session_id) as session_count,
                    GROUP_CONCAT(DISTINCT model_id) as models
                FROM token_usage
            """)
        return {"tokens": tokens}
    except Exception as e:
        return {"error": str(e)}
