#!/usr/bin/env python3
"""
vscode-ark Intelligence Portal — Complete Edition
Light-themed web UI with comprehensive CLI command access.
All 40+ CLI commands accessible as browser UI pages instead of terminal.
"""

import os, sys, json, sqlite3, threading, time, gzip, traceback, subprocess, re, socket
from pathlib import Path
from datetime import datetime, timedelta
from wsgiref.simple_server import make_server, WSGIServer
from urllib.parse import parse_qs, urlparse, urlencode, quote, unquote
from cda.kernel.pmf_kernel import PMFKernel, PMFKernelError

# Get DB path relative to this file
PACKAGE_DIR = Path(__file__).resolve().parent
LOCAL_DIR = PACKAGE_DIR.parent.parent.parent / "local"
DB_PATH = LOCAL_DIR / "data" / "vscode-ark.db"
kernel = PMFKernel()

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

.content {
  flex: 1;
  min-width: 0;
  overflow: auto;
  padding: 24px;
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
  display: flex;
  align-items: center;
}

.nav-item .icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  margin-right: 10px;
  stroke: currentColor;
  fill: none;
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

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 16px;
  margin-bottom: 20px;
}

.page-title {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-primary);
}

.page-subtitle {
  color: var(--text-secondary);
  font-size: 13px;
  line-height: 1.4;
}

.drawer {
  position: fixed;
  inset: 0;
  z-index: 1000;
  display: flex;
  pointer-events: none;
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.3s ease, backdrop-filter 0.3s ease;
  backdrop-filter: blur(0px);
}

.drawer.open {
  pointer-events: auto;
  opacity: 1;
  visibility: visible;
  backdrop-filter: blur(4px);
}

.drawer-backdrop {
  position: absolute;
  inset: 0;
  background: rgba(15, 23, 42, 0.6);
  cursor: pointer;
}

.drawer-panel {
  position: absolute;
  inset: 40px;
  top: 40px;
  bottom: 40px;
  background: #ffffff;
  border-radius: 12px;
  box-shadow: 0 20px 60px rgba(15, 23, 42, 0.3);
  transform: scale(0.95) translateY(20px);
  transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.drawer.open .drawer-panel {
  transform: scale(1) translateY(0);
}

.drawer-header {
  padding: 24px 24px 0;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
  flex-shrink: 0;
}

.drawer-title {
  display: flex;
  flex-direction: column;
  gap: 4px;
  flex: 1;
}

.drawer-title .title {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  letter-spacing: -0.3px;
}

.drawer-title .subtitle {
  color: var(--text-secondary);
  font-size: 13px;
  font-weight: 500;
}

.drawer-tabs {
  display: flex;
  gap: 8px;
  padding: 16px 24px 6px;
  border-bottom: 1px solid var(--border);
  overflow-x: auto;
  flex-shrink: 0;
}

.drawer-tab {
  padding: 12px 18px 14px;
  border-radius: 8px 8px 0 0;
  background: transparent;
  color: var(--text-tertiary);
  text-align: center;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: var(--transition);
  white-space: nowrap;
  border-bottom: 3px solid transparent;
  margin-bottom: 0;
}

.drawer-tab:hover {
  color: var(--text-secondary);
  background: rgba(236, 244, 255, 0.8);
}

.drawer-tab.active {
  color: var(--accent);
  box-shadow: inset 0 -3px 0 0 var(--accent);
  background: transparent;
}

.drawer-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.drawer-list li {
  background: var(--bg-secondary);
  border-radius: 8px;
  padding: 12px;
  border-left: 3px solid var(--accent);
}

.drawer-list li strong {
  display: block;
  color: var(--text-primary);
  font-weight: 600;
  margin-bottom: 4px;
}

.drawer-list li span {
  display: block;
  color: var(--text-secondary);
  font-size: 12px;
  word-break: break-word;
}

.drawer-close {
  border: none;
  background: transparent;
  color: var(--text-tertiary);
  font-size: 28px;
  cursor: pointer;
  line-height: 1;
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 6px;
  transition: var(--transition);
  flex-shrink: 0;
}

.drawer-close:hover {
  background: var(--bg-secondary);
  color: var(--text-primary);
}

.drawer-body {
  padding: 24px;
  overflow-y: auto;
  flex: 1;
  min-height: 0;
}

.drawer-section {
  margin-bottom: 28px;
}

.drawer-section:last-child {
  margin-bottom: 0;
}

.drawer-section h3 {
  margin-bottom: 14px;
  font-size: 12px;
  text-transform: uppercase;
  letter-spacing: 0.6px;
  color: var(--text-secondary);
  font-weight: 700;
}

.chat-bubble {
  border-radius: 12px;
  padding: 14px 16px;
  background: var(--bg-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
  border-left: 3px solid var(--border);
}

.chat-bubble.assistant {
  background: var(--bg-tertiary);
  border-left-color: var(--accent);
}

.chat-meta {
  margin-bottom: 8px;
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
}

.chat-body {
  white-space: pre-wrap;
  word-wrap: break-word;
  color: var(--text-primary);
}

.card-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
  color: var(--text-secondary);
  font-size: 13px;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border);
}

.card-row:last-child {
  border-bottom: none;
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

@media (max-width: 768px) {
  .drawer-panel {
    inset: 20px;
    border-radius: 8px;
  }
  
  .drawer-header {
    padding: 16px 16px 0;
  }
  
  .drawer-tabs {
    padding: 12px 16px 0;
  }
  
  .drawer-body {
    padding: 16px;
  }
  
  .drawer-tab {
    padding: 10px 12px;
    font-size: 12px;
  }
}

@media (max-width: 480px) {
  .drawer-panel {
    inset: 0;
    border-radius: 0;
  }
  
  .drawer {
    backdrop-filter: none;
  }
  
  .drawer-backdrop {
    display: none;
  }
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
  background: rgba(255, 255, 255, 0.92);
  border: 1px solid rgba(148, 163, 184, 0.18);
  padding: 18px;
  border-radius: 12px;
  min-height: 86px;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}

.detail-label {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  text-transform: uppercase;
  letter-spacing: 0.5px;
  margin-bottom: 10px;
}

.detail-value {
  font-size: 16px;
  color: var(--text-primary);
  font-weight: 700;
  word-break: break-word;
}

.metadata-grid,
.metric-grid {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  grid-template-columns: repeat(3, minmax(220px, 1fr));
  gap: 0;
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.metadata-item,
.metric-item {
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 14px 18px;
  border-bottom: 1px solid var(--border);
  border-right: 1px solid var(--border);
  background: transparent;
  min-width: 0;
}

.metadata-item:nth-child(3n),
.metric-item:nth-child(3n) {
  border-right: none;
}

.metadata-item:nth-last-child(-n+3),
.metric-item:nth-last-child(-n+3) {
  border-bottom: none;
}

.metadata-item span,
.metric-item span {
  text-transform: uppercase;
  letter-spacing: 0.5px;
  color: var(--text-secondary);
  font-size: 11px;
  margin-bottom: 8px;
}

.metadata-item strong,
.metric-item strong {
  color: var(--text-primary);
  font-size: 15px;
  font-weight: 700;
  text-align: right;
  word-break: break-word;
  max-width: 100%;
}

.session-panel {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
}

.session-panel .data-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 18px;
  border-bottom: 1px solid var(--border);
}

.session-panel .data-row:last-child {
  border-bottom: none;
}

.session-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  line-height: 1.7;
  color: var(--text-primary);
  white-space: pre-wrap;
}

.session-panel .data-row:last-child {
  border-bottom: none;
}

.session-panel .data-label {
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.session-panel .data-value {
  color: var(--text-primary);
  font-size: 14px;
  font-weight: 700;
  text-align: right;
  min-width: 100px;
}

.chat-thread {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.chat-message {
  border: 1px solid var(--border);
  border-radius: 12px;
  overflow: hidden;
  background: var(--bg-secondary);
}

.chat-message-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 16px;
  padding: 14px 16px;
  background: var(--bg-primary);
  border-bottom: 1px solid var(--border);
}

.chat-role {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-primary);
}

.chat-meta {
  color: var(--text-secondary);
  font-size: 12px;
}

.chat-message-block {
  padding: 14px 16px;
  line-height: 1.65;
  color: var(--text-primary);
}

.chat-message-block.user {
  background: var(--bg-primary);
}

.chat-message-block.assistant {
  background: var(--bg-secondary);
}

.chat-message-label {
  font-weight: 700;
  margin-bottom: 10px;
}

.alert-text {
  color: var(--text-secondary);
  margin-top: 8px;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 1120px) {
  .metadata-grid,
  .metric-grid {
    grid-template-columns: repeat(2, minmax(220px, 1fr));
  }
}

@media (max-width: 768px) {
  .metadata-grid,
  .metric-grid {
    grid-template-columns: 1fr;
  }
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
        row = query_one("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
        return bool(row)
    except Exception:
        return False

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
                (SELECT COUNT(DISTINCT workspace_id) FROM sessions) as workspace_count,
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

        if has_analysis:
            recent = safe_rows(query_rows("""
                SELECT s.session_id as id, s.title, sa.heat_score,
                       {("(SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id)" if has_exchanges else "0")} as exchange_count,
                       s.created_at
                FROM sessions s
                LEFT JOIN session_analysis sa ON sa.session_id = s.session_id
                ORDER BY s.created_at DESC
                LIMIT 10
            """))
        else:
            recent = safe_rows(query_rows("""
                SELECT s.session_id as id, s.title, NULL as heat_score,
                       {("(SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id)" if has_exchanges else "0")} as exchange_count,
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

def get_sessions(limit=50, offset=0):
    """List all sessions with heat scores."""
    try:
        has_analysis = table_exists('session_analysis')
        has_exchanges = table_exists('exchanges')
        exchange_count_expr = "(SELECT COUNT(*) FROM exchanges WHERE exchanges.session_id = s.session_id)" if has_exchanges else "0"

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

        session = safe_one(query_one("SELECT * FROM sessions WHERE session_id = ?", (session_id,)))
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
            ORDER BY created_at DESC
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
                sess = query_one("SELECT title FROM sessions WHERE session_id = ?", (alert["session_id"],))
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
                ["python3", str(PACKAGE_DIR.parent / "pipeline" / "ingest.py")],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "reconstruct":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR.parent / "pipeline" / "reconstruct.py")],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "embed-build":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR.parent / "pipeline" / "embed.py"), "build"],
                capture_output=True,
                text=True,
                timeout=600
            )
        elif action_name == "watch-start":
            result = subprocess.run(
                ["python3", str(PACKAGE_DIR.parent / "pipeline" / "watcher.py"), "start"],
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
    <style>{{STYLE_CSS}}</style>
</head>
<body>
    <div id="root">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">vscode-ark</div>
                <div style="font-size: 11px; color: var(--text-tertiary); margin-top: 5px;">
                    Intelligence & Analysis
                </div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Core</div>
                <div class="nav-item active" data-page="dashboard"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><rect x="3" y="3" width="7" height="8" rx="1"/><rect x="14" y="3" width="7" height="5" rx="1"/><rect x="14" y="12" width="7" height="9" rx="1"/><rect x="3" y="14" width="7" height="6" rx="1"/></svg>Dashboard</div>
                <div class="nav-item" data-page="sessions"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><line x1="10" y1="9" x2="8" y2="9"/></svg>Sessions</div>
                <div class="nav-item" data-page="search"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>Search</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Analysis</div>
                <div class="nav-item" data-page="heat"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 14.5a4 4 0 0 1 8 0c0 2.2-2.5 5.5-4 7.5-1.5-2-4-5.3-4-7.5z"/><path d="M12 2.5c0 4.5-2 7.5-2 10.5a4 4 0 0 0 4 4c1.5 0 2-1 2-1s2 1 2-2c0-5-5-8-6-11.5z"/></svg>Heat Analysis</div>
                <div class="nav-item" data-page="keywords"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M20.59 13.41 13.41 20.59a2 2 0 0 1-2.83 0L3.59 13.6a2 2 0 0 1 0-2.83L10.77 3.59a2 2 0 0 1 2.83 0l7.17 7.17a2 2 0 0 1 0 2.83z"/><path d="M7 7h.01"/></svg>Keywords</div>
                <div class="nav-item" data-page="signals"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.55a11 11 0 0 1 14.08 0"/><path d="M8.5 16.5a6 6 0 0 1 7 0"/><path d="M12 20a2 2 0 0 1 2-2 2 2 0 0 1 2 2"/></svg>Signals</div>
                <div class="nav-item" data-page="behavior"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 22a4 4 0 0 0 4-4v-1.5a3.5 3.5 0 0 0-3.5-3.5H11.5A3.5 3.5 0 0 0 8 16.5V18a4 4 0 0 0 4 4z"/><path d="M8 2c-1.11 0-2 .9-2 2v3h12V4c0-1.1-.89-2-2-2H8z"/></svg>Behavior</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Navigation</div>
                <div class="nav-item" data-page="workspaces"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M4 5a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v11a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2Z"/></svg>Workspaces</div>
                <div class="nav-item" data-page="tools"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M14.7 10.3 13.4 11.6 14.1 12.3a2 2 0 0 1 0 2.83l-5.7 5.7a2 2 0 0 1-2.83 0L3.4 17.7a2 2 0 0 1 0-2.83l5.7-5.7a2 2 0 0 1 2.83 0l.7.7 1.3-1.3"/><path d="M9 14.6l-2-2"/></svg>Tool Calls</div>
                <div class="nav-item" data-page="memory"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><ellipse cx="12" cy="5" rx="8" ry="3"/><path d="M4 5v6c0 1.66 3.58 3 8 3s8-1.34 8-3V5"/><path d="M4 11v6c0 1.66 3.58 3 8 3s8-1.34 8-3v-6"/></svg>Memory</div>
                <div class="nav-item" data-page="tokens"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M7 12h10"/><path d="M8 8h8"/><path d="M8 16h8"/><path d="M12 4v16"/></svg>Tokens</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">Intelligence</div>
                <div class="nav-item" data-page="alerts"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/><line x1="12" y1="9" x2="12" y2="13"/><line x1="12" y1="17" x2="12.01" y2="17"/></svg>Alerts</div>
                <div class="nav-item" data-page="recommendations"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M9 18h6"/><path d="M10 22h4"/><path d="M9 9a3 3 0 0 1 6 0c0 1.38-.56 2.63-1.5 3.5A3 3 0 0 0 12 17a3 3 0 0 0-1.5-4.5C9.56 11.63 9 10.38 9 9z"/></svg>Recommendations</div>
                <div class="nav-item" data-page="topics"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="M12 2 2 7l10 5 10-5-10-5z"/><path d="M2 17l10 5 10-5"/><path d="M2 12l10 5 10-5"/></svg>Topics</div>
            </div>
            
            <div class="nav-group">
                <div class="nav-group-title">System</div>
                <div class="nav-item" data-page="pipeline"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><circle cx="6" cy="18" r="3"/><circle cx="6" cy="6" r="3"/><circle cx="18" cy="6" r="3"/><path d="M6 9v6h12"/></svg>Pipeline</div>
                <div class="nav-item" data-page="query"><svg class="icon" viewBox="0 0 24 24" aria-hidden="true"><path d="m8 9 4-4 4 4"/><path d="m8 15 4-4 4 4"/></svg>Raw Query</div>
            </div>
        </div>
        
        <div class="content" id="main-content">
            <!-- Pages rendered here -->
        </div>
    </div>
    <div id="detail-drawer" class="drawer">
        <div class="drawer-backdrop" onclick="closeSessionDrawer()"></div>
        <div class="drawer-panel">
            <div class="drawer-header">
                <div class="drawer-title">
                    <div class="title" id="drawer-session-title">Session Details</div>
                    <div class="subtitle" id="drawer-session-subtitle">Full chat history and session metadata.</div>
                </div>
                <button class="drawer-close" onclick="closeSessionDrawer()" aria-label="Close session details">×</button>
            </div>
            <div class="drawer-tabs" id="drawer-tabs">
                <div class="drawer-tab active" data-tab="overview" onclick="switchDrawerTab('overview')">Overview</div>
                <div class="drawer-tab" data-tab="analysis" onclick="switchDrawerTab('analysis')">Analysis</div>
                <div class="drawer-tab" data-tab="chat" onclick="switchDrawerTab('chat')">Chat</div>
                <div class="drawer-tab" data-tab="tools" onclick="switchDrawerTab('tools')">Tool Calls</div>
                <div class="drawer-tab" data-tab="signals" onclick="switchDrawerTab('signals')">Signals</div>
                <div class="drawer-tab" data-tab="files" onclick="switchDrawerTab('files')">Files</div>
                <div class="drawer-tab" data-tab="alerts" onclick="switchDrawerTab('alerts')">Alerts</div>
                <div class="drawer-tab" data-tab="raw" onclick="switchDrawerTab('raw')">Raw</div>
            </div>
            <div class="drawer-body" id="drawer-body">
                <div class="spinner"></div>
                Loading session details...
            </div>
        </div>
    </div>
    
    <script>{{APP_JS}}</script>
</body>
</html>
"""

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
    <div class="card mb-20">
        <div class="card-header">Runtime Services</div>
        <div id="pmf-services" class="loading">
            <div class="spinner"></div>
            Loading runtime services...
        </div>
    </div>
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
    """

PAGE_TEMPLATES = {
    'dashboard': json.dumps(render_dashboard()),
    'sessions': json.dumps(render_sessions()),
    'search': json.dumps(render_search()),
    'heat': json.dumps(render_heat()),
    'keywords': json.dumps(render_keywords()),
    'signals': json.dumps(render_signals()),
    'behavior': json.dumps(render_behavior()),
    'workspaces': json.dumps(render_workspaces()),
    'tools': json.dumps(render_tools()),
    'memory': json.dumps(render_memory()),
    'tokens': json.dumps(render_tokens()),
    'alerts': json.dumps(render_alerts()),
    'recommendations': json.dumps(render_recommendations()),
    'topics': json.dumps(render_topics()),
    'pipeline': json.dumps(render_pipeline()),
    'query': json.dumps(render_query())
}

APP_JS = "const PAGE_REGISTRY = {\n"
APP_JS += ",\n".join(
    f"    '{name}': () => {template}"
    for name, template in PAGE_TEMPLATES.items()
)
APP_JS += "\n};\n\n"
APP_JS += """
const safeArray = arr => Array.isArray(arr) ? arr : [];
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
    initializePage(page);
    
    window.scrollTo(0, 0);
}

function initializePage(page) {
    switch (page) {
        case 'dashboard':
            initDashboard();
            break;
        case 'sessions':
            initSessions();
            break;
        case 'search':
            initSearch();
            break;
        case 'heat':
            initHeat();
            break;
        case 'keywords':
            initKeywords();
            break;
        case 'workspaces':
            initWorkspaces();
            break;
        case 'tools':
            initTools();
            break;
        case 'memory':
            initMemory();
            break;
        case 'alerts':
            initAlerts();
            break;
        case 'pipeline':
            initPipeline();
            break;
        case 'query':
            initQuery();
            break;
        default:
            break;
    }
}

function initDashboard() {
    const container = document.getElementById('dashboard-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading overview...';
    fetch('/api/overview').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            return;
        }
        const s = data.stats;
        const heatDistribution = safeArray(data.heat_distribution);
        const keywords = safeArray(data.keywords);
        const recentSessions = safeArray(data.recent_sessions);
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
                        ${heatDistribution.map(h => `<tr><td>${h.range}</td><td>${h.count}</td></tr>`).join('')}
                    </tbody>
                </table>
            </div>
            <div class="card mb-20">
                <div class="card-header">Top Keywords</div>
                <div style="display: flex; flex-wrap: wrap; gap: 8px;">
                    ${keywords.map(k => `<span class="badge badge-info">${k.keyword} (${k.total_count})</span>`).join('')}
                </div>
            </div>
            <div class="card">
                <div class="card-header">Recent Sessions</div>
                <table class="table">
                    <thead><tr><th>Title</th><th>Heat</th><th>Exchanges</th><th>Date</th></tr></thead>
                    <tbody>
                        ${recentSessions.map(s => `
                            <tr class="clickable session-row" data-session-id="${s.id}">
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
        container.innerHTML = html;
        document.querySelectorAll('#dashboard-content .session-row').forEach(row => {
            row.addEventListener('click', () => openSessionDrawer(row.dataset.sessionId));
        });
    });
}

function initSessions() {
    const container = document.getElementById('sessions-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading sessions...';
    fetch('/api/sessions').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            return;
        }
        const sessions = safeArray(data.sessions);
        const html = `
            <div class="card">
                <div class="card-header">All Sessions (${data.total || 0})</div>
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
                        ${sessions.map(s => `
                            <tr class="clickable session-row" data-session-id="${s.id}">
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
        container.innerHTML = html;
        document.querySelectorAll('#sessions-content .session-row').forEach(row => {
            row.addEventListener('click', () => openSessionDrawer(row.dataset.sessionId));
        });
    });
}

function openSessionDrawer(sessionId) {
    const drawer = document.getElementById('detail-drawer');
    const titleEl = document.getElementById('drawer-session-title');
    const subtitleEl = document.getElementById('drawer-session-subtitle');
    const body = document.getElementById('drawer-body');
    const tabButtons = document.querySelectorAll('.drawer-tab');

    titleEl.textContent = 'Loading…';
    subtitleEl.textContent = 'Fetching session details...';
    body.innerHTML = '<div class="spinner"></div> Loading session details...';
    tabButtons.forEach(btn => btn.classList.remove('active'));
    document.querySelector('.drawer-tab[data-tab="overview"]').classList.add('active');
    drawer.classList.add('open');

    fetch('/api/session?session_id=' + encodeURIComponent(sessionId)).then(r => r.json()).then(data => {
        if (data.error) {
            body.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            titleEl.textContent = 'Session Error';
            subtitleEl.textContent = '';
            window.currentSessionDetail = null;
            return;
        }
        const session = data.session || {};

        window.currentSessionDetail = data;

        titleEl.textContent = session.title || `Session ${session.session_id || sessionId}`;
        subtitleEl.textContent = `Workspace ${session.workspace_id || '—'} · ${session.created_at ? new Date(session.created_at).toLocaleString() : 'Unknown date'}`;

        body.innerHTML = renderDrawerTabContent('overview', window.currentSessionDetail);
    }).catch(err => {
        body.innerHTML = '<div class="alert alert-danger">Error loading session details.</div>';
        titleEl.textContent = 'Session Error';
        subtitleEl.textContent = '';
        window.currentSessionDetail = null;
    });
}

function switchDrawerTab(tab) {
    const tabButtons = document.querySelectorAll('.drawer-tab');
    tabButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.tab === tab));
    const body = document.getElementById('drawer-body');
    if (!window.currentSessionDetail) {
        body.innerHTML = '<div class="spinner"></div> Loading session details...';
        return;
    }
    body.innerHTML = renderDrawerTabContent(tab, window.currentSessionDetail);
}

function renderDrawerTabContent(tab, data) {
    const session = data.session || {};
    const analysis = data.analysis || {};
    const exchanges = Array.isArray(data.exchanges) ? data.exchanges : [];
    const signals = Array.isArray(data.signals) ? data.signals : [];
    const toolCalls = Array.isArray(data.tool_calls) ? data.tool_calls : [];
    const vfsEntries = Array.isArray(data.vfs) ? data.vfs : [];
    const alerts = Array.isArray(data.alerts) ? data.alerts : [];

    const heatScore = analysis.heat_score !== undefined && analysis.heat_score !== null ? analysis.heat_score : 'N/A';
    const metadataSection = `
        <div class="drawer-section">
            <h3>Session Metadata</h3>
            <div class="session-panel">
                ${[
                    ['Session ID', session.session_id || 'Unknown'],
                    ['Title', session.title || 'Untitled'],
                    ['Workspace', session.workspace_id || '—'],
                    ['Requests', session.request_count || '—'],
                    ['State', session.response_state || '—'],
                    ['Location', session.initial_location || '—'],
                    ['Heat Score', `<span style="color: ${heatScore !== 'N/A' && heatScore >= 50 ? 'var(--danger)' : 'var(--accent)'};">${heatScore}</span>`],
                    ['Created At', session.created_at ? new Date(session.created_at).toLocaleString() : 'Unknown']
                ].map(([label, value]) => `
                    <div class="data-row">
                        <div class="data-label">${label}</div>
                        <div class="data-value">${value}</div>
                    </div>
                `).join('')}
            </div>
        </div>
    `;

    const sanitize = text => String(text || '').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    const sessionSummary = sanitize(session.summary || analysis.summary || '');
    const turnPoint = analysis.turning_point_text ? sanitize(analysis.turning_point_text.substring(0, 300)) + (analysis.turning_point_text.length > 300 ? '…' : '') : '';

    if (tab === 'overview') {
        const chatCount = exchanges.length;
        const signalCount = signals.length;
        const toolCallsCount = toolCalls.length;
        const fileCount = vfsEntries.length;
        const alertCount = alerts.length;
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Session Snapshot</h3>
                <div class="session-panel">
                    ${[
                        ['Chat Turns', chatCount],
                        ['Signals', signalCount],
                        ['Tool Calls', toolCallsCount],
                        ['Files', fileCount],
                        ['Alerts', `<span style="color: ${alertCount > 0 ? 'var(--danger)' : 'var(--success)'};">${alertCount}</span>`]
                    ].map(([label, value]) => `
                        <div class="data-row">
                            <div class="data-label">${label}</div>
                            <div class="data-value">${value}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
            ${sessionSummary ? `<div class="drawer-section">
                <h3>Summary</h3>
                <div class="session-block">${sessionSummary}</div>
            </div>` : ''}
            ${turnPoint ? `<div class="drawer-section">
                <h3>Turning Point</h3>
                <div class="session-block">${turnPoint}</div>
            </div>` : ''}
        `;
    }

    if (tab === 'analysis') {
        const details = [
            ['Heat Score', heatScore],
            ['Peak Heat', analysis.peak_heat],
            ['Final Heat', analysis.final_heat],
            ['Frustrations', analysis.total_frustrations],
            ['Corrections', analysis.total_corrections],
            ['Pre-corrections', analysis.total_pre_corrections],
            ['Redirects', analysis.total_redirects],
            ['Tool Calls', analysis.total_tool_calls],
            ['Compactions', analysis.compaction_count],
            ['Token Prompt', analysis.total_tokens_prompt],
            ['Token Completion', analysis.total_tokens_completion],
            ['Token Cached', analysis.total_tokens_cached],
            ['Duration (min)', analysis.session_duration_min],
            ['Model IDs', analysis.model_ids],
            ['Analyzed At', analysis.analyzed_at],
            ['Saved Session', analysis.saved_session],
            ['Clean Run', analysis.clean_run]
        ];
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Analysis Details</h3>
                <div class="session-panel">
                    ${details.filter(([label, value]) => value !== undefined && value !== null && value !== '').map(([label, value]) => `
                        <div class="data-row">
                            <div class="data-label">${label}</div>
                            <div class="data-value">${typeof value === 'number' ? value : String(value)}</div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    if (tab === 'chat') {
        const exchangesHtml = exchanges.length ? `<div class="chat-thread">${exchanges.map((e, i) => `
            <div class="chat-message">
                <div class="chat-message-header">
                    <div>
                        <div class="chat-role">Turn ${e.exchange_index || i + 1}</div>
                        <div class="chat-meta">${e.created_at ? new Date(e.created_at).toLocaleString() : 'Unknown'}</div>
                    </div>
                    <div class="chat-role">Exchange</div>
                </div>
                <div class="chat-message-block user">
                    <div class="chat-message-label">User</div>
                    <div>${(e.user_input || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                </div>
                <div class="chat-message-block assistant">
                    <div class="chat-message-label">Assistant</div>
                    <div>${(e.assistant_response || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div>
                </div>
            </div>
        `).join('')}</div>` : '<div class="alert alert-info">No exchanges found for this session.</div>';
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Chat History (${exchanges.length} turns)</h3>
            </div>
            ${exchangesHtml}
        `;
    }

    if (tab === 'tools') {
        const embeddedCalls = exchanges.flatMap(e => {
            if (!e.tool_calls) return [];
            try {
                const parsed = JSON.parse(e.tool_calls);
                return Array.isArray(parsed) ? parsed.map(call => ({...call, created_at: e.created_at, exchange_index: e.exchange_index})) : [];
            } catch (err) {
                return [];
            }
        });
        const allToolCalls = toolCalls.length ? toolCalls : embeddedCalls;
        const toolsHtml = allToolCalls.length ? `<table class="table"><thead><tr><th>#</th><th>Tool</th><th>Exchange</th><th>When</th></tr></thead><tbody>${allToolCalls.map((call, i) => `<tr><td>${i + 1}</td><td>${call.tool_name || call.name || 'Tool'}</td><td>${call.exchange_index || ''}</td><td>${call.created_at ? new Date(call.created_at).toLocaleString() : ''}</td></tr><tr><td colspan="4"><div class="code-block" style="margin: 0; padding: 12px;">${(call.arguments_json || call.arguments || call.args || 'No arguments').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div></td></tr>`).join('')}</tbody></table>` : '<div class="alert alert-info">No tool calls recorded for this session.</div>';
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Tool Calls (${allToolCalls.length} total)</h3>
                ${toolsHtml}
            </div>
        `;
    }

    if (tab === 'signals') {
        const summaryHtml = Array.isArray(data.signal_summary) && data.signal_summary.length ? `
            <div class="drawer-section">
                <h3>Signal Summary</h3>
                <table class="table">
                    <thead>
                        <tr><th>Signal Type</th><th>Count</th></tr>
                    </thead>
                    <tbody>
                        ${data.signal_summary.map(s => `<tr><td>${s.signal_type}</td><td>${s.count}</td></tr>`).join('')}
                    </tbody>
                </table>
            </div>
        ` : '';
        const signalsHtml = signals.length ? `<table class="table"><thead><tr><th>#</th><th>Signal</th><th>Created</th><th>Details</th></tr></thead><tbody>${signals.map((s, i) => `<tr><td>${i + 1}</td><td>${s.signal_type || s.matched_keyword || 'Signal'}</td><td>${s.created_at ? new Date(s.created_at).toLocaleString() : ''}</td><td>${(s.signal_text || s.user_message || s.matched_keyword || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</td></tr>`).join('')}</tbody></table>` : '<div class="alert alert-info">No exchange signals available.</div>';
        return `
            ${metadataSection}
            ${summaryHtml}
            <div class="drawer-section">
                <h3>Signal Details (${signals.length} total)</h3>
                ${signalsHtml}
            </div>
        `;
    }

    if (tab === 'files') {
        const fileHtml = vfsEntries.length ? `<table class="table"><thead><tr><th>#</th><th>File</th><th>Type</th><th>Size</th><th>Path</th></tr></thead><tbody>${vfsEntries.map((file, i) => `<tr><td>${i + 1}</td><td>${file.filename || file.source_path || file.source_type}</td><td>${file.content_type || 'unknown'}</td><td>${file.size_bytes ? (file.size_bytes / 1024).toFixed(2) + ' KB' : 'unknown'}</td><td class="truncate">${file.source_path || ''}</td></tr>`).join('')}</tbody></table>` : '<div class="alert alert-info">No session files found.</div>';
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Session Files (${vfsEntries.length} total)</h3>
                ${fileHtml}
            </div>
        `;
    }

    if (tab === 'alerts') {
        const alertsHtml = alerts.length ? `<table class="table"><thead><tr><th>#</th><th>Alert</th><th>Severity</th><th>Created</th></tr></thead><tbody>${alerts.map((alert, i) => `<tr><td>${i + 1}</td><td>${alert.alert_type || 'Alert'}<div class="alert-text">${(alert.message || '').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</div></td><td>${alert.severity || 'unknown'}</td><td>${alert.created_at ? new Date(alert.created_at).toLocaleString() : ''}</td></tr>`).join('')}</tbody></table>` : '<div class="alert alert-info">No alerts recorded for this session.</div>';
        return `
            ${metadataSection}
            <div class="drawer-section">
                <h3>Alerts (${alerts.length} total)</h3>
                ${alertsHtml}
            </div>
        `;
    }

    if (tab === 'raw') {
        const raw = JSON.stringify(data, null, 2).replace(/</g, '&lt;').replace(/>/g, '&gt;');
        return `
            <div class="drawer-section">
                <h3>Raw Session Payload</h3>
                <pre class="code-block" style="white-space: pre-wrap; word-break: break-word;">${raw}</pre>
            </div>
        `;
    }

    return '<p>Tab content unavailable.</p>';
}

function closeSessionDrawer() {
    const drawer = document.getElementById('detail-drawer');
    drawer.classList.remove('open');
}

function initSearch() {
    const results = document.getElementById('search-results');
    if (!results) return;
    results.style.display = 'none';
    const input = document.getElementById('search-input');
    if (input) {
        input.addEventListener('keypress', e => {
            if (e.key === 'Enter') performSearch();
        });
    }
}

function initHeat() {
    const container = document.getElementById('heat-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading heat analysis...';
    fetch('/api/overview').then(r => r.json()).then(data => {
        container.innerHTML = '<div class="card">Heat data visualization placeholder</div>';
    });
}

function initKeywords() {
    const container = document.getElementById('keywords-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading keywords...';
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
        container.innerHTML = html;
    });
}

function initWorkspaces() {
    const container = document.getElementById('workspaces-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading workspaces...';
    fetch('/api/workspaces').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
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
        container.innerHTML = html;
    });
}

function initTools() {
    const container = document.getElementById('tools-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Searching...';
}

function initMemory() {
    const container = document.getElementById('memory-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading memory...';
    fetch('/api/memory').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
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
        container.innerHTML = html;
    });
}

function initAlerts() {
    const container = document.getElementById('alerts-content');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading alerts...';
    fetch('/api/alerts').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
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
        container.innerHTML = html;
    });
}

function initPipeline() {
    const status = document.getElementById('action-status');
    if (status) {
        status.classList.add('hidden');
    }

    const container = document.getElementById('pmf-services');
    if (!container) return;
    container.innerHTML = '<div class="spinner"></div> Loading runtime services...';
    fetch('/api/pmf/services').then(r => r.json()).then(data => {
        if (data.error) {
            container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            return;
        }
        const html = `
            <table class="table">
                <thead>
                    <tr>
                        <th>Service</th>
                        <th>Status</th>
                        <th>PID</th>
                        <th>Updated</th>
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.services.map(s => `
                        <tr>
                            <td><strong>${s.label}</strong><div class="truncate" style="font-size:12px;color:var(--text-tertiary);">${s.description}</div></td>
                            <td>${s.status}</td>
                            <td>${s.pid || '—'}</td>
                            <td>${s.updated_at || '—'}</td>
                            <td>
                                ${s.allowed_actions.includes('start') ? `<button class="button button-secondary small" onclick="runPmfServiceAction('${s.service_id}','start')">Start</button>` : ''}
                                ${s.allowed_actions.includes('stop') ? `<button class="button button-secondary small" onclick="runPmfServiceAction('${s.service_id}','stop')">Stop</button>` : ''}
                                ${s.allowed_actions.includes('restart') ? `<button class="button button-secondary small" onclick="runPmfServiceAction('${s.service_id}','restart')">Restart</button>` : ''}
                            </td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
        container.innerHTML = html;
    });
}

function runPmfServiceAction(service, action) {
    const status = document.getElementById('action-status');
    if (status) {
        status.classList.remove('hidden');
        document.getElementById('status-text').innerHTML = action + ' ' + service + '...';
    }
    fetch('/api/pmf/service', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({service: service, action: action})
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            if (status) document.getElementById('status-text').innerHTML = 'Error: ' + data.error;
            return;
        }
        if (status) document.getElementById('status-text').innerHTML = data.message || 'Command executed';
        setTimeout(initPipeline, 1000);
    });
}

function initQuery() {
    const results = document.getElementById('query-results');
    if (!results) return;
    results.classList.add('hidden');
}

function performSearch() {
    const query = document.getElementById('search-input').value;
    if (!query) return alert('Enter a search query');
    const results = document.getElementById('search-results');
    results.style.display = 'block';
    results.innerHTML = '<div class="spinner"></div> Searching...';
    fetch('/api/search?q=' + encodeURIComponent(query))
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                results.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
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
            results.innerHTML = html;
        });
}

function searchTools() {
    const query = document.getElementById('tool-search').value;
    const container = document.getElementById('tools-content');
    if (!container) return;
    container.style.display = 'block';
    container.innerHTML = '<div class="spinner"></div> Searching...';
    fetch('/api/tools?q=' + encodeURIComponent(query))
        .then(r => r.json())
        .then(data => {
            if (data.error) {
                container.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
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
            container.innerHTML = html;
        });
}

function runAction(action) {
    const status = document.getElementById('action-status');
    if (!status) return;
    status.classList.remove('hidden');
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

function executeQuery() {
    const sql = document.getElementById('query-input').value;
    if (!sql) return alert('Enter a SQL query');
    const results = document.getElementById('query-results');
    if (!results) return;
    results.classList.remove('hidden');
    results.innerHTML = '<div class="spinner"></div> Running query...';
    fetch('/api/query', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({sql: sql})
    })
    .then(r => r.json())
    .then(data => {
        if (data.error) {
            results.innerHTML = '<div class="alert alert-danger">Error: ' + data.error + '</div>';
            return;
        }
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
    });
}
"""
def application(environ, start_response):
    """WSGI application."""
    method = environ['REQUEST_METHOD']
    path = environ['PATH_INFO']
    query = parse_qs(environ.get('QUERY_STRING', ''))
    
    try:
        if path == '/':
            response = INDEX_HTML.replace('{{STYLE_CSS}}', STYLE_CSS).replace('{{APP_JS}}', APP_JS).encode('utf-8')
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
        
        elif path == '/api/session':
            session_id = query.get('session_id', [''])[0]
            data = get_session_detail(session_id)
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
        
        elif path == '/api/pmf/services' and method == 'GET':
            try:
                services = kernel.services()
                response = json.dumps({"services": services}).encode('utf-8')
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [response]
            except Exception as e:
                response = json.dumps({"error": str(e)}).encode('utf-8')
                start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
                return [response]
        
        elif path == '/api/pmf/service' and method == 'POST':
            body = environ['wsgi.input'].read()
            payload = json.loads(body.decode('utf-8'))
            service_id = payload.get('service')
            action = payload.get('action')
            if not service_id or not action:
                raise ValueError('service and action are required')
            try:
                if action == 'start':
                    result = kernel.start_service(service_id, options=payload.get('options', {}))
                elif action == 'stop':
                    result = kernel.stop_service(service_id)
                elif action == 'restart':
                    result = kernel.restart_service(service_id, options=payload.get('options', {}))
                else:
                    raise ValueError('unsupported action: ' + action)
                response = json.dumps({
                    "ok": True,
                    "service": service_id,
                    "action": action,
                    "message": f"{action} requested for {service_id}",
                    "result": result,
                }).encode('utf-8')
                start_response('200 OK', [('Content-Type', 'application/json')])
                return [response]
            except Exception as e:
                response = json.dumps({"error": str(e)}).encode('utf-8')
                start_response('500 Internal Server Error', [('Content-Type', 'application/json')])
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
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            super().server_bind()
    
    httpd = make_server(host, port, application, server_class=ReusableTCPServer)
    httpd.serve_forever()

if __name__ == '__main__':
    start_server()
