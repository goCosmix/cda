import sqlite3
from cda.kernel.paths import DB_PATH


def get_db():
    """Get database connection with proper settings."""
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def query_rows(sql, params=()):
    """Execute SELECT and return rows as dicts."""
    try:
        conn = get_db()
        cursor = conn.execute(sql, params)
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows
    except Exception as e:
        return {"error": str(e)}


def query_one(sql, params=()):
    """Execute SELECT and return single row or None."""
    rows = query_rows(sql, params)
    if isinstance(rows, dict) and "error" in rows:
        return rows
    return rows[0] if rows else None


def safe_rows(rows):
    """Normalize query_rows output to an array for APIs."""
    if isinstance(rows, dict) and "error" in rows:
        return []
    return rows or []


def safe_one(row):
    """Normalize query_one output to a dict or None."""
    if isinstance(row, dict) and "error" in row:
        return None
    return row


def table_exists(table_name):
    """Return True if a table exists in the current database."""
    try:
        row = query_one(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        )
        return bool(row)
    except Exception:
        return False


def execute_stmt(sql, params=()):
    """Execute INSERT/UPDATE/DELETE statement."""
    try:
        conn = get_db()
        conn.execute(sql, params)
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}
