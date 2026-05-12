from .base import query_rows, query_one


def get_alerts(limit=50):
    """Get anomaly alerts."""
    try:
        alerts = query_rows("""
            SELECT id, session_id, alert_type, message, severity, created_at
            FROM anomaly_alerts
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))

        session_titles = {}
        for alert in alerts:
            if alert["session_id"] not in session_titles:
                sess = query_one(
                    "SELECT title FROM sessions WHERE session_id = ?",
                    (alert["session_id"],)
                )
                session_titles[alert["session_id"]] = sess["title"] if sess else "Unknown"

        for alert in alerts:
            alert["session_title"] = session_titles.get(alert["session_id"], "Unknown")

        return {"alerts": alerts}
    except Exception as e:
        return {"error": str(e)}


def get_behavioral_signals(session_id=None):
    """Get behavioral signal analysis."""
    try:
        if session_id:
            signals = query_rows("""
                SELECT signal_type, COUNT(*) as count
                FROM exchange_signals
                WHERE session_id = ?
                GROUP BY signal_type
            """, (session_id,))
        else:
            signals = query_rows("""
                SELECT signal_type, COUNT(*) as count
                FROM exchange_signals
                GROUP BY signal_type
            """)
        return {"signals": signals}
    except Exception as e:
        return {"error": str(e)}
