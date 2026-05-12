from .base import query_rows, query_one, safe_rows, safe_one, table_exists


def get_overview():
    """Dashboard overview stats."""
    try:
        has_analysis = table_exists('session_analysis')
        has_exchanges = table_exists('exchanges')
        has_signals = table_exists('exchange_signals')
        has_alerts = table_exists('anomaly_alerts')

        stats = query_one(f"""
            SELECT
                (SELECT COUNT(*) FROM sessions) as total_sessions,
                {("(SELECT COUNT(*) FROM exchanges)" if has_exchanges else "0")} as total_exchanges,
                {("(SELECT AVG(heat_score) FROM session_analysis WHERE heat_score IS NOT NULL)" if has_analysis else "0")} as avg_heat,
                {("(SELECT COUNT(*) FROM session_analysis WHERE heat_score >= 50)" if has_analysis else "0")} as critical_sessions,
                {("(SELECT COUNT(*) FROM anomaly_alerts)" if has_alerts else "0")} as alert_count,
                (SELECT COUNT(*) FROM workspaces) as workspace_count,
                (SELECT MAX(created_at) FROM sessions) as last_session
        """)

        heat_dist = safe_rows(query_rows("""
            SELECT
                CASE
                    WHEN heat_score < 20 THEN '0-19'
                    WHEN heat_score < 40 THEN '20-39'
                    WHEN heat_score < 60 THEN '40-59'
                    WHEN heat_score < 80 THEN '60-79'
                    ELSE '80-100'
                END as range,
                COUNT(*) as count
            FROM session_analysis
            WHERE heat_score IS NOT NULL
            GROUP BY range
            ORDER BY range
        """)) if has_analysis else []

        keywords = safe_rows(query_rows("""
            SELECT matched_keyword as keyword, SUM(count) as total_count
            FROM (
                SELECT matched_keyword, COUNT(*) as count
                FROM exchange_signals
                WHERE matched_keyword IS NOT NULL
                GROUP BY matched_keyword
            )
            GROUP BY matched_keyword
            ORDER BY total_count DESC
            LIMIT 15
        """)) if has_signals else []

        exchange_count_expr = (
            "(SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id)"
            if has_exchanges else "0"
        )
        if has_analysis:
            recent = safe_rows(query_rows(f"""
                SELECT s.session_id as id, s.title, sa.heat_score,
                       {exchange_count_expr} as exchange_count,
                       s.created_at
                FROM sessions s
                LEFT JOIN session_analysis sa ON sa.session_id = s.session_id
                ORDER BY s.created_at DESC
                LIMIT 10
            """))
        else:
            recent = safe_rows(query_rows(f"""
                SELECT s.session_id as id, s.title, NULL as heat_score,
                       {exchange_count_expr} as exchange_count,
                       s.created_at
                FROM sessions s
                ORDER BY s.created_at DESC
                LIMIT 10
            """))

        stats = safe_one(stats)
        return {
            "stats": dict(stats) if stats else {},
            "heat_distribution": heat_dist,
            "keywords": keywords,
            "recent_sessions": recent
        }
    except Exception as e:
        return {"error": str(e)}
