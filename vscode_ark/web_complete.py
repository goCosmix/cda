#!/usr/bin/env python3
"""
vscode-ark Intelligence Portal — Complete Edition
Light-themed web UI with comprehensive CLI command access.
All 40+ CLI commands accessible as browser UI pages instead of terminal.
"""

import os, sys, json, sqlite3, threading, time, gzip, traceback, subprocess, re
from pathlib import Path
from datetime import datetime, timedelta
from wsgiref.simple_server import make_server, WSGIServer
from urllib.parse import parse_qs, urlparse, urlencode, quote, unquote

# Get DB path relative to this file
PACKAGE_DIR = Path(__file__).resolve().parent
ARK_DIR = PACKAGE_DIR.parent
DB_PATH = ARK_DIR / "vscode-ark.db"

# ─────────────────────────────────────────────
# Light Theme CSS with all components
# ─────────────────────────────────────────────

STYLE_CSS = """
:root {
  --bg-primary: #f8fafc;
  --bg-secondary: #eef2ff;
  --bg-tertiary: #dbeafe;
  --text-primary: #1e293b;
  --text-secondary: #475569;
  --text-tertiary: #64748b;
  --accent: #0ea5e9;
  --accent-hover: #0284c7;
  --danger: #ef4444;
  --success: #10b981;
  --warning: #f59e0b;
  --border: #cbd5e1;
  --input-bg: #ffffff;
  --input-border: #cbd5e1;
  --input-focus: #0ea5e9;
  --shadow: 0 1px 3px rgba(0,0,0,0.1);
  --shadow-md: 0 4px 6px rgba(0,0,0,0.1);
  --transition: all 0.2s ease-in-out;
}

* { margin: 0; padding: 0; box-sizing: border-box; }
html, body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
body {
  background: var(--bg-primary);
  color: var(--text-primary);
  overflow-x: hidden;
}

#root {
  display: flex;
  height: 100vh;
}

.sidebar {
  width: 240px;
  background: #ffffff;
  border-right: 1px solid var(--border);
  overflow-y: auto;
  padding: 20px 0;
}

.sidebar-header {
  padding: 0 20px 20px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 10px;
}

.sidebar-title {
  font-weight: 700;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.nav-group {
  margin-bottom: 15px;
}

.nav-group-title {
  padding: 8px 20px;
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-top: 10px;
}

.nav-item {
  padding: 10px 20px;
  cursor: pointer;
  color: var(--text-secondary);
  font-size: 13px;
  transition: var(--transition);
  border-left: 3px solid transparent;
}

.nav-item:hover {
  background: var(--bg-secondary);
  color: var(--accent);
}

.nav-item.active {
  background: var(--bg-tertiary);
  color: var(--accent);
  border-left-color: var(--accent);
  font-weight: 600;
}

.content {
  flex: 1;
  overflow-y: auto;
  padding: 30px;
}

.page-header {
  margin-bottom: 30px;
  border-bottom: 2px solid var(--border);
  padding-bottom: 20px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-primary);
  margin-bottom: 5px;
}

.page-subtitle {
  font-size: 14px;
  color: var(--text-secondary);
}

.grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }
.grid-4 { display: grid; grid-template-columns: 1fr 1fr 1fr 1fr; gap: 20px; margin-bottom: 20px; }

.card {
  background: #ffffff;
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 20px;
  box-shadow: var(--shadow);
  transition: var(--transition);
}

.card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-2px);
}

.card-header {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 12px;
}

.card-value {
  font-size: 32px;
  font-weight: 700;
  color: var(--accent);
  margin-bottom: 8px;
}

.card-label {
  font-size: 13px;
  color: var(--text-tertiary);
}

.form-group {
  margin-bottom: 15px;
}

.form-label {
  display: block;
  font-weight: 600;
  font-size: 13px;
  margin-bottom: 6px;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.form-input, .form-select, .form-textarea {
  width: 100%;
  padding: 10px 12px;
  border: 1px solid var(--input-border);
  border-radius: 6px;
  background: var(--input-bg);
  color: var(--text-primary);
  font-size: 13px;
  transition: var(--transition);
  font-family: inherit;
}

.form-input:focus, .form-select:focus, .form-textarea:focus {
  outline: none;
  border-color: var(--input-focus);
  box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.1);
}

.form-textarea {
  resize: vertical;
  min-height: 100px;
}

.button {
  padding: 10px 16px;
  border: none;
  border-radius: 6px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  transition: var(--transition);
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.button-primary {
  background: var(--accent);
  color: white;
}

.button-primary:hover {
  background: var(--accent-hover);
}

.button-secondary {
  background: var(--bg-secondary);
  color: var(--text-primary);
  border: 1px solid var(--border);
}

.button-secondary:hover {
  background: var(--bg-tertiary);
}

.button-danger {
  background: var(--danger);
  color: white;
}

.button-danger:hover {
  opacity: 0.9;
}

.button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  margin-bottom: 20px;
}

.table thead {
  background: var(--bg-secondary);
  border-bottom: 2px solid var(--border);
}

.table th {
  padding: 12px;
  text-align: left;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  font-size: 11px;
  letter-spacing: 0.5px;
}

.table td {
  padding: 12px;
  border-bottom: 1px solid var(--border);
}

.table tr:hover {
  background: var(--bg-secondary);
}

.table tr.clickable {
  cursor: pointer;
}

.truncate {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 400px;
}

.badge {
  display: inline-block;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.badge-info { background: var(--bg-tertiary); color: var(--accent); }
.badge-success { background: #d1fae5; color: var(--success); }
.badge-warning { background: #fef3c7; color: var(--warning); }
.badge-danger { background: #fee2e2; color: var(--danger); }

.alert {
  padding: 12px 16px;
  border-radius: 6px;
  margin-bottom: 15px;
  font-size: 13px;
  border-left: 4px solid;
}

.alert-info {
  background: #cffafe;
  border-left-color: var(--accent);
  color: var(--accent);
}

.alert-success {
  background: #d1fae5;
  border-left-color: var(--success);
  color: var(--success);
}

.alert-warning {
  background: #fef3c7;
  border-left-color: var(--warning);
  color: var(--warning);
}

.alert-danger {
  background: #fee2e2;
  border-left-color: var(--danger);
  color: var(--danger);
}

.hidden { display: none; }
.text-center { text-align: center; }
.text-muted { color: var(--text-tertiary); }
.mt-20 { margin-top: 20px; }
.mb-20 { margin-bottom: 20px; }
.gap-10 { gap: 10px; }

.loading {
  text-align: center;
  padding: 30px;
  color: var(--text-tertiary);
}

.spinner {
  border: 3px solid var(--bg-secondary);
  border-top: 3px solid var(--accent);
  border-radius: 50%;
  width: 30px;
  height: 30px;
  animation: spin 1s linear infinite;
  margin: 0 auto 10px;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

.button-group {
  display: flex;
  gap: 10px;
  margin-bottom: 20px;
}

.button-group .button {
  flex: 1;
}

.details-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 20px;
  margin-bottom: 20px;
}

.detail-item {
  background: var(--bg-secondary);
  padding: 15px;
  border-radius: 6px;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 14px;
  color: var(--text-primary);
  word-break: break-all;
}

.code-block {
  background: var(--bg-secondary);
  padding: 15px;
  border-radius: 6px;
  overflow-x: auto;
  font-family: "Monaco", "Menlo", monospace;
  font-size: 12px;
  color: var(--text-primary);
  margin-bottom: 20px;
}

.status-indicator {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: 50%;
  margin-right: 6px;
}

.status-online { background: var(--success); }
.status-offline { background: var(--danger); }
.status-idle { background: var(--warning); }
"""

# ─────────────────────────────────────────────
# Database Helpers
# ─────────────────────────────────────────────

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

def execute_stmt(sql, params=()):
    """Execute INSERT/UPDATE/DELETE statement."""
    try:
        conn = get_db()
        cursor = conn.execute(sql, params)
        conn.commit()
        conn.close()
        return {"ok": True}
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
# Data Retrieval Functions
# ─────────────────────────────────────────────

def get_overview():
    """Dashboard overview stats."""
    try:
        stats = query_one("""
            SELECT 
                (SELECT COUNT(*) FROM sessions) as total_sessions,
                (SELECT COUNT(*) FROM exchanges) as total_exchanges,
                (SELECT AVG(heat_score) FROM sessions WHERE heat_score IS NOT NULL) as avg_heat,
                (SELECT COUNT(*) FROM sessions WHERE heat_score >= 50) as critical_sessions,
                (SELECT COUNT(*) FROM anomaly_alerts) as alert_count,
                (SELECT COUNT(DISTINCT workspace_id) FROM sessions) as workspace_count,
                (SELECT MAX(created_at) FROM sessions) as last_session
        """)
        
        heat_dist = query_rows("""
            SELECT 
                CASE 
                    WHEN heat_score < 20 THEN '0-19'
                    WHEN heat_score < 40 THEN '20-39'
                    WHEN heat_score < 60 THEN '40-59'
                    WHEN heat_score < 80 THEN '60-79'
                    ELSE '80-100'
                END as range,
                COUNT(*) as count
            FROM sessions
            WHERE heat_score IS NOT NULL
            GROUP BY range
            ORDER BY range
        """)
        
        keywords = query_rows("""
            SELECT keyword, SUM(count) as total_count
            FROM (
                SELECT keyword, COUNT(*) as count
                FROM exchange_signals
                WHERE keyword IS NOT NULL
                GROUP BY keyword
            )
            GROUP BY keyword
            ORDER BY total_count DESC
            LIMIT 15
        """)
        
        recent = query_rows("""
            SELECT id, title, heat_score, 
                   (SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = sessions.id) as exchange_count,
                   created_at
            FROM sessions
            ORDER BY created_at DESC
            LIMIT 10
        """)
        
        return {
            "stats": dict(stats) if stats else {},
            "heat_distribution": heat_dist,
            "keywords": keywords,
            "recent_sessions": recent
        }
    except Exception as e:
        return {"error": str(e)}

def get_sessions(limit=50, offset=0):
    """List all sessions with heat scores."""
    try:
        sessions = query_rows("""
            SELECT id, title, heat_score, workspace_id,
                   (SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = sessions.id) as exchange_count,
                   created_at
            FROM sessions
            ORDER BY created_at DESC
            LIMIT ? OFFSET ?
        """, (limit, offset))
        
        total = query_one("SELECT COUNT(*) as count FROM sessions")
        
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
    try:
        session = query_one("SELECT * FROM sessions WHERE id = ?", (session_id,))
        
        exchanges = query_rows("""
            SELECT id, user_input, assistant_response, tool_name, created_at
            FROM exchanges
            WHERE session_id = ?
            ORDER BY created_at ASC
        """, (session_id,))
        
        signals = query_rows("""
            SELECT * FROM exchange_signals
            WHERE session_id = ?
            ORDER BY created_at DESC
        """, (session_id,))
        
        return {
            "session": dict(session) if session else None,
            "exchanges": exchanges,
            "signals": signals
        }
    except Exception as e:
        return {"error": str(e)}

def get_search_results(query, limit=50):
    """Full-text search across exchanges."""
    try:
        results = query_rows("""
            SELECT DISTINCT
                s.id as session_id,
                s.title,
                s.heat_score,
                e.id as exchange_id,
                e.user_input,
                e.assistant_response,
                RANK() OVER (ORDER BY rank) as relevance
            FROM sessions s
            JOIN exchanges e ON s.id = e.session_id
            JOIN full_text_search fts ON e.id = fts.exchange_id
            WHERE fts.full_text_search MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        return {"results": results, "query": query, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}

def get_workspaces():
    """List all workspaces with session counts."""
    try:
        workspaces = query_rows("""
            SELECT DISTINCT workspace_id, 
                   COUNT(*) as session_count,
                   MAX(created_at) as last_session
            FROM sessions
            WHERE workspace_id IS NOT NULL
            GROUP BY workspace_id
            ORDER BY session_count DESC
        """)
        return {"workspaces": workspaces}
    except Exception as e:
        return {"error": str(e)}

def get_workspace_detail(workspace_id):
    """Get all sessions for a workspace."""
    try:
        sessions = query_rows("""
            SELECT id, title, heat_score,
                   (SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = sessions.id) as exchange_count,
                   created_at
            FROM sessions
            WHERE workspace_id = ?
            ORDER BY created_at DESC
        """, (workspace_id,))
        return {"workspace_id": workspace_id, "sessions": sessions}
    except Exception as e:
        return {"error": str(e)}

def get_memory():
    """Get all memory files."""
    try:
        memory = query_rows("""
            SELECT id, name, size, created_at, updated_at
            FROM memory_files
            ORDER BY updated_at DESC
        """)
        return {"memory": memory}
    except Exception as e:
        return {"error": str(e)}

def get_tool_calls(query_str=None, limit=50):
    """Search tool calls."""
    try:
        if query_str:
            results = query_rows("""
                SELECT tc.*, e.session_id, s.title as session_title
                FROM tool_calls tc
                JOIN exchanges e ON tc.exchange_id = e.id
                JOIN sessions s ON e.session_id = s.id
                WHERE tc.tool_name LIKE ? OR tc.arguments LIKE ?
                ORDER BY tc.created_at DESC
                LIMIT ?
            """, (f"%{query_str}%", f"%{query_str}%", limit))
        else:
            results = query_rows("""
                SELECT tc.*, e.session_id, s.title as session_title
                FROM tool_calls tc
                JOIN exchanges e ON tc.exchange_id = e.id
                JOIN sessions s ON e.session_id = s.id
                ORDER BY tc.created_at DESC
                LIMIT ?
            """, (limit,))
        return {"tool_calls": results, "query": query_str, "count": len(results)}
    except Exception as e:
        return {"error": str(e)}

def get_vfs(session_id):
    """List VFS files for a session."""
    try:
        vfs = query_rows("""
            SELECT id, session_id, path, size, created_at
            FROM vfs
            WHERE session_id = ?
            ORDER BY path
        """, (session_id,))
        return {"vfs": vfs, "session_id": session_id}
    except Exception as e:
        return {"error": str(e)}

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
                sess = query_one("SELECT title FROM sessions WHERE id = ?", (alert["session_id"],))
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

def get_tokens(session_id=None):
    """Get token usage analysis."""
    try:
        if session_id:
            tokens = query_rows("""
                SELECT 
                    SUM(CAST(json_extract(metadata, '$.token_count') AS INTEGER)) as total_tokens,
                    COUNT(*) as exchange_count
                FROM exchanges
                WHERE session_id = ?
            """, (session_id,))
        else:
            tokens = query_rows("""
                SELECT 
                    SUM(CAST(json_extract(metadata, '$.token_count') AS INTEGER)) as total_tokens,
                    COUNT(*) as exchange_count
                FROM exchanges
            """)
        return {"tokens": tokens}
    except Exception as e:
        return {"error": str(e)}

# ─────────────────────────────────────────────
# Action Execution (Background Threading)
# ─────────────────────────────────────────────

ACTION_STATE = {}
ACTION_LOCK = threading.Lock()

def run_action_background(action_id, action_name):
    """Execute pipeline action in background thread."""
    with ACTION_LOCK:
        ACTION_STATE[action_id] = {
            "status": "running",
            "action": action_name,
            "started_at": datetime.now().isoformat(),
            "output": ""
        }
    
    try:
        if action_name == "sync":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR / "ingest.py")],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "reconstruct":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR / "reconstruct.py")],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "embed-build":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR / "embed.py"), "build"],
                capture_output=True,
                text=True,
                timeout=600
            )
        elif action_name == "watch-start":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR / "watcher.py"), "start"],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            result = None
        
        with ACTION_LOCK:
            if result:
                ACTION_STATE[action_id]["status"] = "completed" if result.returncode == 0 else "failed"
                ACTION_STATE[action_id]["output"] = result.stdout + result.stderr
                ACTION_STATE[action_id]["returncode"] = result.returncode
            ACTION_STATE[action_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        with ACTION_LOCK:
            ACTION_STATE[action_id]["status"] = "error"
            ACTION_STATE[action_id]["output"] = str(e)
            ACTION_STATE[action_id]["completed_at"] = datetime.now().isoformat()

# ─────────────────────────────────────────────
# WSGI Application
# ─────────────────────────────────────────────

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>vscode-ark Intelligence Portal</title>
    <style>%s</style>
</head>
<body>
    <div id="root">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">🎯 vscode-ark</div>
                <div style="font-size: 11px; color: var(--text-tertiary); margin-top: 5px;">
                    Intelligence & Analysis
                </div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Core</div>
                <div class="nav-item active" data-page="dashboard">📊 Dashboard</div>
                <div class="nav-item" data-page="sessions">📋 Sessions</div>
                <div class="nav-item" data-page="search">🔍 Search</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Analysis</div>
                <div class="nav-item" data-page="heat">🔥 Heat Analysis</div>
                <div class="nav-item" data-page="keywords">🏷️ Keywords</div>
                <div class="nav-item" data-page="signals">📡 Signals</div>
                <div class="nav-item" data-page="behavior">🧠 Behavior</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Navigation</div>
                <div class="nav-item" data-page="workspaces">📁 Workspaces</div>
                <div class="nav-item" data-page="tools">⚙️ Tool Calls</div>
                <div class="nav-item" data-page="memory">💾 Memory</div>
                <div class="nav-item" data-page="tokens">🔢 Tokens</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Intelligence</div>
                <div class="nav-item" data-page="alerts">⚠️ Alerts</div>
                <div class="nav-item" data-page="recommendations">💡 Recommendations</div>
                <div class="nav-item" data-page="topics">🏷️ Topics</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">System</div>
                <div class="nav-item" data-page="pipeline">⚙️ Pipeline</div>
                <div class="nav-item" data-page="query">📝 Raw Query</div>
            </div>
        </div>
        
        <div class="content" id="main-content">
            <!-- Pages rendered here -->
        </div>
    </div>
    
    <script>%s</script>
</body>
</html>
""" % (STYLE_CSS, "")

def render_page(page_name):
    """Render page based on name."""
    if page_name == "dashboard":
        return render_dashboard()
    elif page_name == "sessions":
        return render_sessions()
    elif page_name == "search":
        return render_search()
    elif page_name == "heat":
        return render_heat()
    elif page_name == "keywords":
        return render_keywords()
    elif page_name == "signals":
        return render_signals()
    elif page_name == "behavior":
        return render_behavior()
    elif page_name == "workspaces":
        return render_workspaces()
    elif page_name == "tools":
        return render_tools()
    elif page_name == "memory":
        return render_memory()
    elif page_name == "tokens":
        return render_tokens()
    elif page_name == "alerts":
        return render_alerts()
    elif page_name == "recommendations":
        return render_recommendations()
    elif page_name == "topics":
        return render_topics()
    elif page_name == "pipeline":
        return render_pipeline()
    elif page_name == "query":
        return render_query()
    else:
        return render_dashboard()

def render_dashboard():
    """Dashboard page."""
    return """
    <div class="page-header">
        <div class="page-title">Dashboard</div>
        <div class="page-subtitle">Behavioral intelligence summary, heat distribution, and pipeline status.</div>
    </div>
    <div id="dashboard-content" class="loading">
        <div class="spinner"></div>
        Loading overview...
    </div>
    <script>
        fetch('/api/overview').then(r => r.json()).then(data => {
            if (data.error) {
                document.getElementById('dashboard-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                return;
            }
            const s = data.stats;
            const html = `
                <div class="grid-4">
                    <div class="card">
                        <div class="card-header">Total Sessions</div>
                        <div class="card-value">${s.total_sessions || 0}</div>
                        <div class="card-label">Analyzed</div>
                    </div>
                    <div class="card">
                        <div class="card-header">Avg Heat</div>
                        <div class="card-value">${(s.avg_heat || 0).toFixed(1)}</div>
                        <div class="card-label">Frustration Score</div>
                    </div>
                    <div class="card">
                        <div class="card-header">Critical</div>
                        <div class="card-value">${s.critical_sessions || 0}</div>
                        <div class="card-label">Heat > 50</div>
                    </div>
                    <div class="card">
                        <div class="card-header">Workspaces</div>
                        <div class="card-value">${s.workspace_count || 0}</div>
                        <div class="card-label">Active</div>
                    </div>
                </div>
                
                <div class="card mb-20">
                    <div class="card-header">Heat Distribution</div>
                    <table class="table">
                        <thead><tr><th>Range</th><th>Sessions</th></tr></thead>
                        <tbody>
                            ${data.heat_distribution.map(h => `<tr><td>${h.range}</td><td>${h.count}</td></tr>`).join('')}
                        </tbody>
                    </table>
                </div>
                
                <div class="card mb-20">
                    <div class="card-header">Top Keywords</div>
                    <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                        ${data.keywords.map(k => `<span class="badge badge-info">${k.keyword} (${k.total_count})</span>`).join('')}
                    </div>
                </div>
                
                <div class="card">
                    <div class="card-header">Recent Sessions</div>
                    <table class="table">
                        <thead><tr><th>Title</th><th>Heat</th><th>Exchanges</th><th>Date</th></tr></thead>
                        <tbody>
                            ${data.recent_sessions.map(s => `
                                <tr class="clickable" onclick="showPage('sessions')">
                                    <td class="truncate">${s.title || 'Untitled'}</td>
                                    <td>${(s.heat_score || 0).toFixed(1)}</td>
                                    <td>${s.exchange_count || 0}</td>
                                    <td>${new Date(s.created_at).toLocaleDateString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('dashboard-content').innerHTML = html;
        });
    </script>
    """

def render_sessions():
    """Sessions list page."""
    return """
    <div class="page-header">
        <div class="page-title">Sessions</div>
        <div class="page-subtitle">Browse all recorded sessions with heat scores and metrics.</div>
    </div>
    <div id="sessions-content" class="loading">
        <div class="spinner"></div>
        Loading sessions...
    </div>
    <script>
        fetch('/api/sessions').then(r => r.json()).then(data => {
            if (data.error) {
                document.getElementById('sessions-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                return;
            }
            const html = `
                <div class="card">
                    <div class="card-header">All Sessions (${data.total})</div>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>ID</th>
                                <th>Title</th>
                                <th>Heat</th>
                                <th>Exchanges</th>
                                <th>Workspace</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.sessions.map(s => `
                                <tr>
                                    <td class="truncate" style="max-width: 150px;">${s.id}</td>
                                    <td class="truncate">${s.title || 'Untitled'}</td>
                                    <td><strong>${(s.heat_score || 0).toFixed(1)}</strong></td>
                                    <td>${s.exchange_count || 0}</td>
                                    <td class="truncate">${s.workspace_id || '—'}</td>
                                    <td>${new Date(s.created_at).toLocaleDateString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('sessions-content').innerHTML = html;
        });
    </script>
    """

def render_search():
    """Full-text search page."""
    return """
    <div class="page-header">
        <div class="page-title">Search</div>
        <div class="page-subtitle">Full-text search across all exchanges and content.</div>
    </div>
    <div class="card mb-20">
        <div class="form-group">
            <label class="form-label">Search Query</label>
            <input type="text" id="search-input" class="form-input" placeholder="Enter search terms...">
        </div>
        <button class="button button-primary" onclick="performSearch()">Search</button>
    </div>
    <div id="search-results" class="loading" style="display: none;">
        <div class="spinner"></div>
        Searching...
    </div>
    <script>
        function performSearch() {
            const query = document.getElementById('search-input').value;
            if (!query) return alert('Enter a search query');
            document.getElementById('search-results').style.display = 'block';
            fetch('/api/search?q=' + encodeURIComponent(query))
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('search-results').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                        return;
                    }
                    const html = `
                        <div class="card">
                            <div class="card-header">Results for "${data.query}" (${data.count})</div>
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Session</th>
                                        <th>Exchange</th>
                                        <th>User Input</th>
                                        <th>Heat</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${data.results.slice(0, 50).map(r => `
                                        <tr>
                                            <td class="truncate">${r.title || 'Untitled'}</td>
                                            <td>${r.relevance}</td>
                                            <td class="truncate">${r.user_input || '—'}</td>
                                            <td>${(r.heat_score || 0).toFixed(1)}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                    document.getElementById('search-results').innerHTML = html;
                });
        }
        document.getElementById('search-input').addEventListener('keypress', e => {
            if (e.key === 'Enter') performSearch();
        });
    </script>
    """

def render_heat():
    """Heat analysis page."""
    return """
    <div class="page-header">
        <div class="page-title">Heat Analysis</div>
        <div class="page-subtitle">Frustration and behavioral heat patterns.</div>
    </div>
    <div id="heat-content" class="loading">
        <div class="spinner"></div>
        Loading heat analysis...
    </div>
    <script>
        fetch('/api/overview').then(r => r.json()).then(data => {
            const html = `<div class="card">Heat data visualization placeholder</div>`;
            document.getElementById('heat-content').innerHTML = html;
        });
    </script>
    """

def render_keywords():
    """Keywords page."""
    return """
    <div class="page-header">
        <div class="page-title">Keywords</div>
        <div class="page-subtitle">Most common behavioral signal keywords.</div>
    </div>
    <div id="keywords-content" class="loading">
        <div class="spinner"></div>
        Loading keywords...
    </div>
    <script>
        fetch('/api/overview').then(r => r.json()).then(data => {
            const html = `
                <div class="card">
                    <div class="card-header">Top Keywords</div>
                    <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 10px;">
                        ${data.keywords.map(k => `
                            <div style="background: var(--bg-secondary); padding: 15px; border-radius: 6px; text-align: center;">
                                <div style="font-weight: 600; color: var(--accent);">${k.keyword}</div>
                                <div style="font-size: 20px; font-weight: 700; color: var(--text-primary);">${k.total_count}</div>
                            </div>
                        `).join('')}
                    </div>
                </div>
            `;
            document.getElementById('keywords-content').innerHTML = html;
        });
    </script>
    """

def render_signals():
    """Behavioral signals page."""
    return """
    <div class="page-header">
        <div class="page-title">Behavioral Signals</div>
        <div class="page-subtitle">Correction, frustration, redirects, and approval patterns.</div>
    </div>
    <div class="card">
        <p>Behavioral signal analysis coming soon.</p>
    </div>
    """

def render_behavior():
    """Behavior intelligence page."""
    return """
    <div class="page-header">
        <div class="page-title">Behavior Intelligence</div>
        <div class="page-subtitle">Aggregate behavioral patterns and trends.</div>
    </div>
    <div class="card">
        <p>Behavior intelligence analysis coming soon.</p>
    </div>
    """

def render_workspaces():
    """Workspaces page."""
    return """
    <div class="page-header">
        <div class="page-title">Workspaces</div>
        <div class="page-subtitle">Browse sessions by workspace.</div>
    </div>
    <div id="workspaces-content" class="loading">
        <div class="spinner"></div>
        Loading workspaces...
    </div>
    <script>
        fetch('/api/workspaces').then(r => r.json()).then(data => {
            if (data.error) {
                document.getElementById('workspaces-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                return;
            }
            const html = `
                <div class="card">
                    <div class="card-header">All Workspaces</div>
                    <table class="table">
                        <thead>
                            <tr><th>Workspace</th><th>Sessions</th><th>Last Activity</th></tr>
                        </thead>
                        <tbody>
                            ${data.workspaces.map(w => `
                                <tr>
                                    <td class="truncate">${w.workspace_id}</td>
                                    <td>${w.session_count}</td>
                                    <td>${new Date(w.last_session).toLocaleDateString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('workspaces-content').innerHTML = html;
        });
    </script>
    """

def render_tools():
    """Tool calls page."""
    return """
    <div class="page-header">
        <div class="page-title">Tool Calls</div>
        <div class="page-subtitle">Search and analyze tool invocations.</div>
    </div>
    <div class="card mb-20">
        <div class="form-group">
            <label class="form-label">Search Tools</label>
            <input type="text" id="tool-search" class="form-input" placeholder="Enter tool name or pattern...">
        </div>
        <button class="button button-primary" onclick="searchTools()">Search</button>
    </div>
    <div id="tools-content" class="loading" style="display: none;">
        <div class="spinner"></div>
        Searching...
    </div>
    <script>
        function searchTools() {
            const query = document.getElementById('tool-search').value;
            document.getElementById('tools-content').style.display = 'block';
            fetch('/api/tools?q=' + encodeURIComponent(query))
                .then(r => r.json())
                .then(data => {
                    if (data.error) {
                        document.getElementById('tools-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                        return;
                    }
                    const html = `
                        <div class="card">
                            <div class="card-header">Tool Calls (${data.count})</div>
                            <table class="table">
                                <thead>
                                    <tr>
                                        <th>Tool Name</th>
                                        <th>Session</th>
                                        <th>Arguments</th>
                                        <th>Date</th>
                                    </tr>
                                </thead>
                                <tbody>
                                    ${data.tool_calls.slice(0, 50).map(t => `
                                        <tr>
                                            <td><strong>${t.tool_name}</strong></td>
                                            <td class="truncate">${t.session_title}</td>
                                            <td class="truncate" style="max-width: 300px;">${t.arguments || '—'}</td>
                                            <td>${new Date(t.created_at).toLocaleDateString()}</td>
                                        </tr>
                                    `).join('')}
                                </tbody>
                            </table>
                        </div>
                    `;
                    document.getElementById('tools-content').innerHTML = html;
                });
        }
    </script>
    """

def render_memory():
    """Memory files page."""
    return """
    <div class="page-header">
        <div class="page-title">Memory</div>
        <div class="page-subtitle">Stored memory files and knowledge base.</div>
    </div>
    <div id="memory-content" class="loading">
        <div class="spinner"></div>
        Loading memory...
    </div>
    <script>
        fetch('/api/memory').then(r => r.json()).then(data => {
            if (data.error) {
                document.getElementById('memory-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                return;
            }
            const html = `
                <div class="card">
                    <div class="card-header">Memory Files</div>
                    <table class="table">
                        <thead>
                            <tr><th>Name</th><th>Size</th><th>Created</th><th>Updated</th></tr>
                        </thead>
                        <tbody>
                            ${data.memory.map(m => `
                                <tr>
                                    <td class="truncate">${m.name}</td>
                                    <td>${(m.size / 1024).toFixed(1)}KB</td>
                                    <td>${new Date(m.created_at).toLocaleDateString()}</td>
                                    <td>${new Date(m.updated_at).toLocaleDateString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('memory-content').innerHTML = html;
        });
    </script>
    """

def render_tokens():
    """Token usage page."""
    return """
    <div class="page-header">
        <div class="page-title">Token Usage</div>
        <div class="page-subtitle">Token consumption analysis by session.</div>
    </div>
    <div class="card">
        <p>Token usage analysis coming soon.</p>
    </div>
    """

def render_alerts():
    """Alerts page."""
    return """
    <div class="page-header">
        <div class="page-title">Alerts</div>
        <div class="page-subtitle">Semantic anomaly detection and alerts.</div>
    </div>
    <div id="alerts-content" class="loading">
        <div class="spinner"></div>
        Loading alerts...
    </div>
    <script>
        fetch('/api/alerts').then(r => r.json()).then(data => {
            if (data.error) {
                document.getElementById('alerts-content').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                return;
            }
            const html = `
                <div class="card">
                    <div class="card-header">Anomaly Alerts</div>
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Type</th>
                                <th>Session</th>
                                <th>Message</th>
                                <th>Severity</th>
                                <th>Date</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${data.alerts.map(a => `
                                <tr>
                                    <td>${a.alert_type}</td>
                                    <td class="truncate">${a.session_title}</td>
                                    <td class="truncate">${a.message}</td>
                                    <td><span class="badge badge-${a.severity === 'high' ? 'danger' : 'warning'}">${a.severity}</span></td>
                                    <td>${new Date(a.created_at).toLocaleDateString()}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            `;
            document.getElementById('alerts-content').innerHTML = html;
        });
    </script>
    """

def render_recommendations():
    """Recommendations page."""
    return """
    <div class="page-header">
        <div class="page-title">Recommendations</div>
        <div class="page-subtitle">AI-generated session recommendations.</div>
    </div>
    <div class="card">
        <p>Session recommendations coming soon.</p>
    </div>
    """

def render_topics():
    """Topics page."""
    return """
    <div class="page-header">
        <div class="page-title">Topics</div>
        <div class="page-subtitle">Semantic topic extraction and tagging.</div>
    </div>
    <div class="card">
        <p>Topic analysis coming soon.</p>
    </div>
    """

def render_pipeline():
    """Pipeline management page."""
    return """
    <div class="page-header">
        <div class="page-title">Pipeline</div>
        <div class="page-subtitle">Execute and monitor data pipeline commands.</div>
    </div>
    <div class="card mb-20">
        <div class="card-header">Available Commands</div>
        <div class="button-group">
            <button class="button button-primary" onclick="runAction('sync')">Full Sync</button>
            <button class="button button-primary" onclick="runAction('reconstruct')">Reconstruct</button>
            <button class="button button-primary" onclick="runAction('embed-build')">Build Embeddings</button>
        </div>
        <p style="font-size: 12px; color: var(--text-tertiary); margin-top: 10px;">
            These commands can take several minutes to complete.
        </p>
    </div>
    <div id="action-status" class="hidden">
        <div class="alert alert-info">
            <strong>Status:</strong> <span id="status-text">Running...</span>
        </div>
    </div>
    <script>
        function runAction(action) {
            document.getElementById('action-status').classList.remove('hidden');
            document.getElementById('status-text').innerHTML = action + ' started...';
            fetch('/api/action', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({action: action})
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('status-text').innerHTML = data.message || 'Command executed';
            });
        }
    </script>
    """

def render_query():
    """Raw SQL query page."""
    return """
    <div class="page-header">
        <div class="page-title">Raw Query</div>
        <div class="page-subtitle">Execute SQL queries directly against the database.</div>
    </div>
    <div class="card mb-20">
        <div class="form-group">
            <label class="form-label">SQL Query</label>
            <textarea id="query-input" class="form-textarea" placeholder="SELECT * FROM sessions LIMIT 10"></textarea>
        </div>
        <button class="button button-primary" onclick="executeQuery()">Execute</button>
    </div>
    <div id="query-results" class="hidden">
        <div class="card">
            <div class="card-header">Results</div>
            <div id="results-table"></div>
        </div>
    </div>
    <script>
        function executeQuery() {
            const sql = document.getElementById('query-input').value;
            if (!sql) return alert('Enter a SQL query');
            fetch('/api/query', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({sql: sql})
            })
            .then(r => r.json())
            .then(data => {
                document.getElementById('query-results').classList.remove('hidden');
                if (data.error) {
                    document.getElementById('results-table').innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
                } else {
                    let html = '<table class="table"><thead><tr>';
                    if (data.rows && data.rows.length > 0) {
                        Object.keys(data.rows[0]).forEach(k => html += '<th>' + k + '</th>');
                        html += '</tr></thead><tbody>';
                        data.rows.forEach(row => {
                            html += '<tr>';
                            Object.values(row).forEach(v => html += '<td class="truncate">' + v + '</td>');
                            html += '</tr>';
                        });
                    }
                    html += '</tbody></table>';
                    document.getElementById('results-table').innerHTML = html;
                }
            });
        }
    </script>
    """

APP_JS = """
// Page registry
const PAGE_REGISTRY = {
    'dashboard': () => `%s`,
    'sessions': () => `%s`,
    'search': () => `%s`,
    'heat': () => `%s`,
    'keywords': () => `%s`,
    'signals': () => `%s`,
    'behavior': () => `%s`,
    'workspaces': () => `%s`,
    'tools': () => `%s`,
    'memory': () => `%s`,
    'tokens': () => `%s`,
    'alerts': () => `%s`,
    'recommendations': () => `%s`,
    'topics': () => `%s`,
    'pipeline': () => `%s`,
    'query': () => `%s`
};

// Navigation
document.addEventListener('DOMContentLoaded', () => {
    document.querySelectorAll('.nav-item').forEach(item => {
        item.addEventListener('click', e => {
            const page = item.dataset.page;
            showPage(page);
        });
    });
    showPage('dashboard');
});

function showPage(page) {
    if (!PAGE_REGISTRY[page]) page = 'dashboard';
    
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
    document.querySelector(`[data-page="${page}"]`).classList.add('active');
    
    const renderer = PAGE_REGISTRY[page];
    document.getElementById('main-content').innerHTML = renderer();
    
    window.scrollTo(0, 0);
}
""" % (
    render_dashboard().replace("'", "\\'").replace("\n", "\\n"),
    render_sessions().replace("'", "\\'").replace("\n", "\\n"),
    render_search().replace("'", "\\'").replace("\n", "\\n"),
    render_heat().replace("'", "\\'").replace("\n", "\\n"),
    render_keywords().replace("'", "\\'").replace("\n", "\\n"),
    render_signals().replace("'", "\\'").replace("\n", "\\n"),
    render_behavior().replace("'", "\\'").replace("\n", "\\n"),
    render_workspaces().replace("'", "\\'").replace("\n", "\\n"),
    render_tools().replace("'", "\\'").replace("\n", "\\n"),
    render_memory().replace("'", "\\'").replace("\n", "\\n"),
    render_tokens().replace("'", "\\'").replace("\n", "\\n"),
    render_alerts().replace("'", "\\'").replace("\n", "\\n"),
    render_recommendations().replace("'", "\\'").replace("\n", "\\n"),
    render_topics().replace("'", "\\'").replace("\n", "\\n"),
    render_pipeline().replace("'", "\\'").replace("\n", "\\n"),
    render_query().replace("'", "\\'").replace("\n", "\\n")
)

def application(environ, start_response):
    """WSGI application."""
    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']
    query = parse_qs(environ.get('QUERY_STRING', ''))
    
    try:
        if path == '/':
            response = (INDEX_HTML % APP_JS).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'text/html; charset=utf-8')])
            return [response]
        
        elif path == '/api/overview':
            data = get_overview()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/sessions':
            limit = int(query.get('limit', ['50'])[0])
            offset = int(query.get('offset', ['0'])[0])
            data = get_sessions(limit, offset)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/search':
            q = query.get('q', [''])[0]
            data = get_search_results(q)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/workspaces':
            data = get_workspaces()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/tools':
            q = query.get('q', [''])[0]
            data = get_tool_calls(q if q else None)
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/memory':
            data = get_memory()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/alerts':
            data = get_alerts()
            response = json.dumps(data).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/action' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            action = payload.get('action', '')
            
            action_id = f"{action}_{int(time.time() * 1000)}"
            thread = threading.Thread(target=run_action_background, args=(action_id, action))
            thread.daemon = True
            thread.start()
            
            response = json.dumps({
                "ok": True,
                "action": action,
                "action_id": action_id,
                "message": f"Started {action}..."
            }).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        elif path == '/api/query' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            sql = payload.get('sql', '')
            
            rows = query_rows(sql)
            response = json.dumps({"rows": rows}).encode('utf-8')
            start_response('200 OK', [('Content-Type', 'application/json')])
            return [response]
        
        else:
            response = b'Not Found'
            start_response('404 Not Found', [('Content-Type', 'text/plain')])
            return [response]
    
    except Exception as e:
        traceback.print_exc()
        response = json.dumps({"error": str(e)}).encode('utf-8')
        start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
        return [response]

def start_server(host='127.0.0.1', port=10001):
    """Start WSGI server."""
    print(f"Starting vscode-ark Intelligence Portal at http://{host}:{port}")
    print("Press Ctrl+C to stop.")
    
    # Use custom server to allow address reuse
    class ReusableTCPServer(WSGIServer):
        def server_bind(self):
            self.socket.setsockopt(1, 15, 1)  # SO_REUSEADDR
            super().server_bind()
    
    httpd = make_server(host, port, application, server_class=ReusableTCPServer)
    httpd.serve_forever()

if __name__ == '__main__':
    start_server()
