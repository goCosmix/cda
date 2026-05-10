import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

ROOT_DIR = Path(__file__).resolve().parent.parent
DB_PATH = ROOT_DIR / "vscode-ark.db"

ACTION_COMMANDS = {
    "sync": [sys.executable, "-m", "vscode_ark.cli", "sync"],
    "reconstruct": [sys.executable, "-m", "vscode_ark.cli", "reconstruct"],
    "embed-build": [sys.executable, "-m", "vscode_ark.cli", "embed", "build"],
    "watch-start": [sys.executable, "-m", "vscode_ark.cli", "watch", "start"],
    "watch-stop": [sys.executable, "-m", "vscode_ark.cli", "watch", "stop"],
    "watch-restart": [sys.executable, "-m", "vscode_ark.cli", "watch", "restart"],
}

ACTION_STATE = {
    "running": False,
    "action": None,
    "exit_code": None,
    "output": "",
    "started_at": None,
    "completed_at": None,
}

STYLE_CSS = """
:root {
  --bg-0: #ffffff;
  --bg-1: #f8fafc;
  --bg-2: #f1f5f9;
  --text-0: #0f172a;
  --text-1: #334155;
  --text-2: #64748b;
  --blue: #3b82f6;
  --blue-dark: #1d4ed8;
  --blue-light: #e0e7ff;
  --green: #10b981;
  --orange: #f59e0b;
  --red: #ef4444;
  --border: #e2e8f0;
  --shadow: 0 4px 12px rgba(15, 23, 42, 0.08);
  --shadow-sm: 0 2px 4px rgba(15, 23, 42, 0.04);
}
* {
  box-sizing: border-box;
}
html, body {
  margin: 0;
  min-height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px;
  line-height: 1.6;
  background: var(--bg-0);
  color: var(--text-0);
}
body {
  display: flex;
  min-height: 100vh;
}
.app-shell {
  display: grid;
  grid-template-columns: 260px 1fr;
  width: 100%;
}
.sidebar {
  background: var(--bg-1);
  border-right: 1px solid var(--border);
  display: flex;
  flex-direction: column;
  padding: 24px 16px;
  gap: 20px;
  overflow-y: auto;
}
.sidebar h1 {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 800;
  letter-spacing: -0.02em;
  color: var(--text-0);
}
.sidebar p {
  margin: 0;
  color: var(--text-2);
  font-size: 0.8rem;
  line-height: 1.5;
}
.sidebar-section {
  border-top: 1px solid var(--border);
  padding-top: 12px;
}
.sidebar-section-title {
  margin: 0 0 8px 0;
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--text-2);
}
.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 4px;
}
.nav-item {
  border-radius: 8px;
  padding: 9px 11px;
  cursor: pointer;
  color: var(--text-1);
  border: 1px solid transparent;
  background: transparent;
  transition: all 0.15s ease;
  font-size: 0.9rem;
  font-weight: 500;
}
.nav-item:hover {
  background: var(--bg-2);
  color: var(--text-0);
}
.nav-item.active {
  background: var(--blue-light);
  border-color: var(--blue);
  color: var(--blue-dark);
}
.content {
  padding: 32px 40px;
  overflow: auto;
}
.page-title {
  margin: 0 0 6px;
  font-size: 1.8rem;
  font-weight: 800;
  letter-spacing: -0.03em;
  color: var(--text-0);
}
.page-subtitle {
  margin: 0 0 32px;
  color: var(--text-2);
  font-size: 0.9rem;
  max-width: 800px;
}
.card {
  background: var(--bg-0);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 24px;
  box-shadow: var(--shadow-sm);
  margin-bottom: 20px;
}
.card h2 {
  margin: 0 0 16px;
  font-size: 1rem;
  font-weight: 700;
  color: var(--text-0);
}
.card h3 {
  margin: 0 0 12px;
  font-size: 0.92rem;
  font-weight: 600;
  color: var(--text-0);
}
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 16px;
}
button, .button {
  border: 1px solid transparent;
  background: var(--blue);
  color: white;
  padding: 9px 14px;
  border-radius: 8px;
  cursor: pointer;
  font-size: 0.85rem;
  font-weight: 600;
  transition: all 0.15s ease;
}
button:hover, .button:hover {
  background: var(--blue-dark);
  box-shadow: 0 2px 8px rgba(59, 130, 246, 0.2);
}
button:disabled, .button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}
button.secondary {
  background: var(--bg-2);
  color: var(--text-1);
  border: 1px solid var(--border);
}
button.secondary:hover {
  background: var(--border);
  color: var(--text-0);
}
button.success {
  background: var(--green);
}
button.success:hover {
  background: #059669;
}
button.danger {
  background: var(--red);
}
button.danger:hover {
  background: #dc2626;
}
.search-bar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 16px;
}
.search-input, .select-input {
  flex: 1 1 240px;
  min-width: 180px;
  padding: 9px 11px;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--bg-1);
  color: var(--text-0);
  font-size: 0.85rem;
}
.search-input::placeholder {
  color: var(--text-2);
}
.search-input:focus, .select-input:focus {
  outline: none;
  border-color: var(--blue);
  box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.1);
}
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 11px;
  border-radius: 999px;
  background: var(--blue-light);
  border: 1px solid rgba(59, 130, 246, 0.3);
  color: var(--blue-dark);
  font-size: 0.8rem;
  font-weight: 600;
  margin-right: 6px;
  margin-bottom: 6px;
}
.status-pill.green {
  background: #dcfce7;
  border-color: rgba(16, 185, 129, 0.3);
  color: #047857;
}
.status-pill.orange {
  background: #fef3c7;
  border-color: rgba(245, 158, 11, 0.3);
  color: #d97706;
}
.status-pill.red {
  background: #fee2e2;
  border-color: rgba(239, 68, 68, 0.3);
  color: #dc2626;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 12px;
  margin-bottom: 20px;
}
.metric-card {
  background: var(--bg-1);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 16px;
  box-shadow: var(--shadow-sm);
}
.metric-card strong {
  display: block;
  font-size: 1.5rem;
  font-weight: 800;
  margin-bottom: 4px;
  color: var(--blue);
}
.metric-card div {
  font-size: 0.85rem;
  font-weight: 500;
  color: var(--text-1);
  margin-bottom: 3px;
}
.metric-card div:last-child {
  margin-bottom: 0;
  font-size: 0.8rem;
  color: var(--text-2);
}
.table-container {
  overflow-x: auto;
  border-radius: 10px;
  border: 1px solid var(--border);
  box-shadow: var(--shadow-sm);
}
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.85rem;
}
th {
  background: var(--bg-2);
  padding: 11px 12px;
  text-align: left;
  font-weight: 700;
  color: var(--text-1);
  border-bottom: 1px solid var(--border);
}
td {
  padding: 11px 12px;
  border-bottom: 1px solid var(--border);
  color: var(--text-0);
}
tbody tr:hover {
  background: var(--bg-2);
  cursor: pointer;
}
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 11px;
  border-radius: 10px;
  background: rgba(99, 102, 241, 0.1);
  border: 1px solid rgba(99, 102, 241, 0.3);
  color: #4f46e5;
  font-size: 0.8rem;
  font-weight: 500;
  margin-right: 6px;
  margin-bottom: 6px;
}
.chart-row {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}
.chart-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.85rem;
  color: var(--text-1);
  font-weight: 600;
  margin-bottom: 4px;
}
.chart-bar {
  height: 18px;
  background: linear-gradient(90deg, var(--blue), #6366f1);
  border-radius: 999px;
  min-width: 2%;
  box-shadow: 0 1px 3px rgba(59, 130, 246, 0.15);
}
.small-note {
  color: var(--text-2);
  font-size: 0.85rem;
  margin: 6px 0;
}
.pre {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  overflow: auto;
  white-space: pre-wrap;
  font-size: 0.8rem;
  font-family: "Monaco", "Courier New", monospace;
  color: var(--text-1);
}
.command-builder {
  background: var(--bg-2);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 16px;
}
.command-field {
  margin-bottom: 12px;
}
.command-field label {
  display: block;
  font-size: 0.85rem;
  font-weight: 600;
  color: var(--text-1);
  margin-bottom: 4px;
}
.command-field input, .command-field select {
  width: 100%;
  padding: 9px 11px;
  border: 1px solid var(--border);
  border-radius: 6px;
  background: var(--bg-0);
  color: var(--text-0);
  font-size: 0.85rem;
}
.command-output {
  background: var(--text-0);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 12px;
  color: #16a34a;
  font-family: monospace;
  font-size: 0.8rem;
  min-height: 100px;
  max-height: 300px;
  overflow: auto;
  white-space: pre-wrap;
}
.command-output.error {
  color: #dc2626;
}
.section-divider {
  margin: 24px 0;
  border-top: 2px solid var(--border);
  padding-top: 24px;
}
@media (max-width: 1200px) {
  .content {
    padding: 24px 28px;
  }
}
@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: none;
    border-bottom: 1px solid var(--border);
  }
}
"""

APP_JS = """
const PAGE_REGISTRY = [];
let currentPage = null;

function registerPage(page) {
  PAGE_REGISTRY.push(page);
}

function getPage(id) {
  return PAGE_REGISTRY.find((page) => page.id === id);
}

async function fetchJson(path, options = {}) {
  const res = await fetch(path, options);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return await res.json();
}

function formatNumber(value) {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'number') return value.toLocaleString();
  return value;
}

function createTable(columns, rows, onRowClick) {
  const container = document.createElement('div');
  container.className = 'table-container';
  const table = document.createElement('table');
  const thead = document.createElement('thead');
  const headerRow = document.createElement('tr');
  columns.forEach((col) => {
    const th = document.createElement('th');
    th.textContent = col.label;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);
  const tbody = document.createElement('tbody');
  rows.forEach((row) => {
    const tr = document.createElement('tr');
    if (onRowClick) {
      tr.style.cursor = 'pointer';
      tr.addEventListener('click', () => onRowClick(row));
    }
    columns.forEach((col) => {
      const td = document.createElement('td');
      const value = col.format ? col.format(row[col.key]) : (row[col.key] ?? '—');
      td.textContent = value;
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);
  container.appendChild(table);
  return container;
}

function createMetricCard(label, value, detail) {
  const card = document.createElement('div');
  card.className = 'metric-card';
  card.innerHTML = `<strong>${value}</strong><div>${label}</div><div style="margin-top:4px;">${detail || ''}</div>`;
  return card;
}

function createSearchBar({ placeholder, value = '', onSearch, label }) {
  const wrapper = document.createElement('div');
  wrapper.className = 'search-bar';
  if (label) {
    const labelEl = document.createElement('span');
    labelEl.style.cssText = 'color: var(--text-2); font-size: 0.85rem; font-weight: 600; width: 100%;';
    labelEl.textContent = label;
    wrapper.appendChild(labelEl);
  }
  const input = document.createElement('input');
  input.className = 'search-input';
  input.type = 'search';
  input.placeholder = placeholder;
  input.value = value;
  input.addEventListener('input', () => onSearch(input.value));
  wrapper.appendChild(input);
  return { wrapper, input };
}

function createBarRow(label, count, total) {
  const row = document.createElement('div');
  const labelLine = document.createElement('div');
  labelLine.className = 'chart-label';
  labelLine.innerHTML = `<span>${label}</span><span>${count}</span>`;
  row.appendChild(labelLine);
  const bar = document.createElement('div');
  bar.className = 'chart-bar';
  if (typeof total === 'number' && total > 0) {
    bar.style.width = `${Math.max(2, Math.round((count / total) * 100))}%`;
  } else {
    bar.style.width = '2%';
  }
  row.appendChild(bar);
  return row;
}

function renderNavigation() {
  const nav = document.getElementById('nav-list');
  nav.innerHTML = '';
  PAGE_REGISTRY.forEach((page) => {
    const item = document.createElement('div');
    item.className = 'nav-item';
    item.dataset.page = page.id;
    item.textContent = page.title;
    item.addEventListener('click', () => navigate(page.id));
    nav.appendChild(item);
  });
}

function setActiveNav(pageId) {
  document.querySelectorAll('.nav-item').forEach((item) => {
    item.classList.toggle('active', item.dataset.page === pageId);
  });
}

async function navigate(pageId) {
  currentPage = getPage(pageId);
  if (!currentPage) return;
  setActiveNav(pageId);
  const content = document.getElementById('page-content');
  content.innerHTML = '';
  const title = document.createElement('h1');
  title.className = 'page-title';
  title.textContent = currentPage.title;
  const subtitle = document.createElement('p');
  subtitle.className = 'page-subtitle';
  subtitle.textContent = currentPage.description || '';
  content.appendChild(title);
  if (subtitle.textContent) content.appendChild(subtitle);
  await currentPage.load(content);
}

async function refreshCurrentPage() {
  if (currentPage && currentPage.refresh) {
    await currentPage.refresh();
  }
}

registerPage({
  id: 'dashboard',
  title: 'Dashboard',
  description: 'Real-time intelligence overview, metrics, and system status.',
  async load(container) {
    const overview = await fetchJson('/api/overview');
    const metrics = document.createElement('div');
    metrics.className = 'metric-grid';
    metrics.appendChild(createMetricCard('Sessions', formatNumber(overview.stats.tables.sessions), 'Recorded'));
    metrics.appendChild(createMetricCard('Heat Avg', overview.heat.summary.avg_heat ? overview.heat.summary.avg_heat.toFixed(1) : '0', 'Score'));
    metrics.appendChild(createMetricCard('Critical', formatNumber(overview.heat.summary.very_hot_sessions), 'High heat'));
    metrics.appendChild(createMetricCard('Alerts', formatNumber(overview.stats.tables.anomaly_alerts), 'Anomalies'));
    container.appendChild(metrics);

    const pipelineCard = document.createElement('div');
    pipelineCard.className = 'card';
    pipelineCard.innerHTML = '<h2>Pipeline Status</h2>';
    const watcher_class = overview.watcher.watcher.includes('running') ? 'green' : 'orange';
    pipelineCard.innerHTML += [
      `<div class="status-pill ${watcher_class}">${overview.watcher.watcher}</div>`,
      `<div class="status-pill">Queue: ${overview.watcher.queue} items</div>`,
      `<div class="status-pill">DB: ${overview.stats.db_size}</div>`,
    ].join('');
    container.appendChild(pipelineCard);

    const heatCard = document.createElement('div');
    heatCard.className = 'card';
    heatCard.innerHTML = '<h2>Heat Distribution</h2>';
    const total = overview.heat.summary.total_sessions || 1;
    overview.heat.distribution.forEach((bucket) => heatCard.appendChild(createBarRow(bucket.bucket, bucket.count, total)));
    container.appendChild(heatCard);

    const keywordsCard = document.createElement('div');
    keywordsCard.className = 'card';
    keywordsCard.innerHTML = '<h2>Top Signal Keywords</h2>';
    const keywordsList = document.createElement('div');
    overview.keywords.slice(0, 20).forEach((kw) => {
      const chip = document.createElement('div');
      chip.className = 'tag-chip';
      chip.innerHTML = `${kw.keyword} <span style="opacity:0.7;">(${kw.count})</span>`;
      keywordsList.appendChild(chip);
    });
    keywordsCard.appendChild(keywordsList);
    container.appendChild(keywordsCard);
  },
});

registerPage({
  id: 'sessions',
  title: 'Sessions',
  description: 'Search, browse, and analyze all recorded sessions with behavioral signals.',
  selectedSession: null,
  filter: { query: '', workspace: '' },
  sessions: [],
  workspaceOptions: [],
  async load(container) {
    const controls = document.createElement('div');
    controls.className = 'button-row';
    const refresh = document.createElement('button');
    refresh.textContent = 'Refresh';
    refresh.onclick = () => this.load(container);
    controls.appendChild(refresh);
    container.appendChild(controls);

    const searchBar = createSearchBar({
      label: 'Search Sessions',
      placeholder: 'Title, workspace, or session ID...',
      value: this.filter.query,
      onSearch: (value) => { this.filter.query = value; this.renderSessionList(container); },
    });
    container.appendChild(searchBar.wrapper);

    const workspaceFilter = document.createElement('select');
    workspaceFilter.className = 'select-input';
    workspaceFilter.innerHTML = '<option value="">All workspaces</option>';
    this.workspaceOptions = await fetchJson('/api/workspaces');
    this.workspaceOptions.forEach((workspace) => {
      const option = document.createElement('option');
      option.value = workspace.workspace_id;
      option.textContent = `${workspace.name || workspace.workspace_id} (${workspace.session_count})`;
      workspaceFilter.appendChild(option);
    });
    workspaceFilter.value = this.filter.workspace;
    workspaceFilter.addEventListener('change', () => {
      this.filter.workspace = workspaceFilter.value;
      this.renderSessionList(container);
    });
    const workspaceWrapper = document.createElement('div');
    workspaceWrapper.className = 'search-bar';
    workspaceWrapper.appendChild(workspaceFilter);
    container.appendChild(workspaceWrapper);

    this.sessions = await fetchJson('/api/sessions?limit=500');
    await this.renderSessionList(container);

    const detail = document.createElement('div');
    detail.id = 'session-detail';
    detail.style.marginTop = '24px';
    container.appendChild(detail);
    if (this.selectedSession) await this.openSession(this.selectedSession);
  },
  async renderSessionList(container) {
    const existing = container.querySelector('#sessions-card');
    if (existing) existing.remove();

    const rows = this.sessions.filter((session) => {
      const query = this.filter.query.trim().toLowerCase();
      const matchesQuery = !query || [session.session_id, session.title, session.workspace_id].some((value) => String(value || '').toLowerCase().includes(query));
      const matchesWorkspace = !this.filter.workspace || session.workspace_id === this.filter.workspace;
      return matchesQuery && matchesWorkspace;
    });

    const listCard = document.createElement('div');
    listCard.id = 'sessions-card';
    listCard.className = 'card';
    listCard.innerHTML = `<h2>Sessions — ${rows.length} results</h2>`;
    listCard.appendChild(createTable(
      [
        { label: 'ID', key: 'session_id', format: (v) => v.slice(0, 12) },
        { label: 'Title', key: 'title' },
        { label: 'Workspace', key: 'workspace_id' },
        { label: 'Heat', key: 'heat_score', format: (v) => v ? v.toFixed(0) : '—' },
        { label: 'Requests', key: 'request_count' },
      ],
      rows,
      (row) => this.openSession(row.session_id)
    ));
    container.insertBefore(listCard, container.querySelector('#session-detail'));
  },
  async openSession(sessionId) {
    this.selectedSession = sessionId;
    const detail = document.getElementById('session-detail');
    detail.innerHTML = '<div class="card"><h2>Loading session details...</h2></div>';
    try {
      const data = await fetchJson(`/api/session/${sessionId}`);
      detail.innerHTML = '';
      const header = document.createElement('div');
      header.className = 'card';
      header.innerHTML = `<h2>${data.session.title || data.session.session_id}</h2>` + [
        `<div class="status-pill">Workspace: ${data.session.workspace_id}</div>`,
        `<div class="status-pill">Heat: ${data.session.heat_score || 0}</div>`,
        `<div class="status-pill">Requests: ${data.session.request_count || 0}</div>`,
        `<div class="status-pill ${data.session.saved_session ? 'green' : ''}">Saved: ${data.session.saved_session ? 'yes' : 'no'}</div>`,
      ].join('');
      detail.appendChild(header);

      if (data.signals.length > 0) {
        const signalsCard = document.createElement('div');
        signalsCard.className = 'card';
        signalsCard.innerHTML = '<h3>Behavioral Signals</h3>';
        signalsCard.appendChild(createTable([
          { label: 'Type', key: 'signal_type' },
          { label: 'Keyword', key: 'matched_keyword' },
          { label: 'Count', key: 'count' },
        ], data.signals.slice(0, 20)));
        detail.appendChild(signalsCard);
      }

      const exchangesCard = document.createElement('div');
      exchangesCard.className = 'card';
      exchangesCard.innerHTML = `<h3>Exchanges — ${data.exchanges.length} turns</h3>`;
      exchangesCard.appendChild(createTable([
        { label: '#', key: 'exchange_index' },
        { label: 'Tools', key: 'tool_call_count' },
        { label: 'Output', key: 'has_tool_output' },
        { label: 'Preview', key: 'user_message' },
      ], data.exchanges.map((exchange) => ({
        ...exchange,
        has_tool_output: exchange.has_tool_output ? 'yes' : 'no',
        user_message: exchange.user_message ? exchange.user_message.slice(0, 80) : '',
      }))));
      detail.appendChild(exchangesCard);
    } catch (err) {
      detail.innerHTML = `<div class="card"><p>Error: ${err.message}</p></div>`;
    }
  },
});

registerPage({
  id: 'heat',
  title: 'Heat Analytics',
  description: 'Frustration metrics, behavior patterns, and session scoring.',
  async load(container) {
    const heat = await fetchJson('/api/heat');
    const metrics = document.createElement('div');
    metrics.className = 'metric-grid';
    metrics.appendChild(createMetricCard('Total', formatNumber(heat.summary.total_sessions), 'Sessions'));
    metrics.appendChild(createMetricCard('Hot', formatNumber(heat.summary.hot_sessions), 'Heat ≥ 20'));
    metrics.appendChild(createMetricCard('Critical', formatNumber(heat.summary.very_hot_sessions), 'Heat ≥ 50'));
    metrics.appendChild(createMetricCard('Average', heat.summary.avg_heat ? heat.summary.avg_heat.toFixed(1) : '0', 'Heat Score'));
    container.appendChild(metrics);

    const distribution = document.createElement('div');
    distribution.className = 'card';
    distribution.innerHTML = '<h2>Heat Distribution</h2>';
    const total = heat.summary.total_sessions || 1;
    heat.distribution.forEach((bucket) => distribution.appendChild(createBarRow(bucket.bucket, bucket.count, total)));
    container.appendChild(distribution);

    const top = document.createElement('div');
    top.className = 'card';
    top.innerHTML = '<h2>Highest Heat Sessions</h2>';
    top.appendChild(createTable([
      { label: 'Session ID', key: 'session_id', format: (v) => v.slice(0, 12) },
      { label: 'Current', key: 'heat_score', format: (v) => v ? v.toFixed(0) : '—' },
      { label: 'Peak', key: 'peak_heat', format: (v) => v ? v.toFixed(0) : '—' },
      { label: 'Final', key: 'final_heat', format: (v) => v ? v.toFixed(0) : '—' },
    ], heat.top_sessions.slice(0, 30)));
    container.appendChild(top);
  },
});

registerPage({
  id: 'keywords',
  title: 'Keywords & Signals',
  description: 'Behavioral signal keyword ranking across all sessions.',
  async load(container) {
    const keywords = await fetchJson('/api/keywords?limit=300');
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>Signal Keywords</h2>';
    card.appendChild(createTable([
      { label: 'Keyword', key: 'keyword' },
      { label: 'Signal Type', key: 'signal_type' },
      { label: 'Occurrences', key: 'count' },
    ], keywords));
    container.appendChild(card);
  },
});

registerPage({
  id: 'alerts',
  title: 'Alerts & Anomalies',
  description: 'Detected anomalies and safety alerts from semantic analysis.',
  async load(container) {
    const alerts = await fetchJson('/api/alerts?limit=200');
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>Anomaly Alerts</h2>';
    card.appendChild(createTable([
      { label: 'Session', key: 'session_id', format: (v) => v.slice(0, 12) },
      { label: 'Type', key: 'alert_type' },
      { label: 'Severity', key: 'severity' },
      { label: 'Message', key: 'message' },
    ], alerts));
    container.appendChild(card);
  },
});

registerPage({
  id: 'commands',
  title: 'Command Center',
  description: 'Execute ark operations and monitor pipeline activity.',
  async load(container) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>Pipeline Operations</h2>';
    card.innerHTML += '<p style="color: var(--text-2);">Click to execute data pipeline commands. Operations run in background.</p>';
    
    const row = document.createElement('div');
    row.className = 'button-row';
    const actions = [
      { name: 'sync', label: 'Sync Data', class: 'secondary' },
      { name: 'reconstruct', label: 'Reconstruct Exchanges', class: 'secondary' },
      { name: 'embed-build', label: 'Build Embeddings', class: 'secondary' },
      { name: 'watch-start', label: 'Start Watcher', class: 'success' },
      { name: 'watch-stop', label: 'Stop Watcher', class: 'danger' },
      { name: 'watch-restart', label: 'Restart Watcher', class: 'secondary' },
    ];
    
    actions.forEach((action) => {
      const button = document.createElement('button');
      button.className = action.class;
      button.textContent = action.label;
      button.onclick = async () => {
        button.disabled = true;
        try {
          const resp = await fetchJson('/api/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: action.name }),
          });
          updateActionLog(resp.message);
        } catch (err) {
          updateActionLog('Error: ' + err.message);
        } finally {
          button.disabled = false;
        }
      };
      row.appendChild(button);
    });
    card.appendChild(row);
    
    const log = document.createElement('pre');
    log.id = 'action-log';
    log.className = 'command-output';
    log.textContent = 'Ready for commands';
    card.appendChild(log);
    container.appendChild(card);
    
    await this.refresh();
  },
  async refresh() {
    try {
      const action = await fetchJson('/api/action');
      const msg = action.running ? `Running ${action.action}...\\n${action.output}` : `Status: ${action.exit_code === null ? 'idle' : action.exit_code === 0 ? 'success' : 'failed'}\\n${action.output}`;
      updateActionLog(msg);
    } catch (err) {
      updateActionLog('Unable to load status');
    }
  },
});

registerPage({
  id: 'system',
  title: 'System Status',
  description: 'Database tables, coverage metrics, and system health.',
  async load(container) {
    const overview = await fetchJson('/api/overview');
    const stats = overview.stats.tables;
    
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>Database Overview</h2>';
    card.innerHTML += `<p style="color: var(--text-2);">Size: <strong>${overview.stats.db_size}</strong></p>`;
    
    const tables = [
      { name: 'Sessions', key: 'sessions' },
      { name: 'Exchanges', key: 'exchanges' },
      { name: 'Tool Calls', key: 'tool_calls' },
      { name: 'Edit Sessions', key: 'edit_sessions' },
      { name: 'VFS Blobs', key: 'vfs' },
      { name: 'Embeddings', key: 'embeddings' },
      { name: 'Alerts', key: 'anomaly_alerts' },
      { name: 'Recommendations', key: 'recommendations' },
    ];
    
    card.appendChild(createTable([
      { label: 'Table', key: 'name' },
      { label: 'Records', key: 'count', format: (v) => v ? formatNumber(v) : '0' },
    ], tables.map(t => ({ name: t.name, count: stats[t.key] }))));
    
    container.appendChild(card);
    
    const watcherCard = document.createElement('div');
    watcherCard.className = 'card';
    watcherCard.innerHTML = '<h2>Watcher Status</h2>';
    const watcher_class = overview.watcher.watcher.includes('running') ? 'green' : 'orange';
    watcherCard.innerHTML += [
      `<div class="status-pill ${watcher_class}">${overview.watcher.watcher}</div>`,
      `<div class="status-pill">Queue: ${overview.watcher.queue} items</div>`,
    ].join('');
    container.appendChild(watcherCard);
  },
});

function updateActionLog(text) {
  const log = document.getElementById('action-log');
  if (log) log.textContent = text;
}

window.addEventListener('DOMContentLoaded', () => {
  renderNavigation();
  navigate('dashboard');
  setInterval(refreshCurrentPage, 10000);
});
"""

INDEX_HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>vscode-ark Intelligence Portal</title>
  <link rel="stylesheet" href="/style.css" />
</head>
<body>
  <div class="app-shell">
    <aside class="sidebar">
      <h1>vscode-ark</h1>
      <p>Intelligence portal for VS Code/Copilot Chat session analysis.</p>
      <div class="nav-list" id="nav-list"></div>
    </aside>
    <main class="content">
      <div id="page-content"></div>
    </main>
  </div>
  <script src="/app.js"></script>
</body>
</html>
"""

def json_response(data, status_code=200):
    body = json.dumps(data, indent=2).encode("utf-8")
    status = f"{status_code} {'OK' if status_code == 200 else 'ERROR'}"
    headers = [("Content-Type", "application/json"), ("Content-Length", str(len(body))), ("Cache-Control", "no-store")]
    return status, headers, [body]

def html_response(body):
    payload = body.encode("utf-8")
    headers = [("Content-Type", "text/html; charset=utf-8"), ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")]
    return "200 OK", headers, [payload]

def db_connection():
    if not DB_PATH.exists():
        raise FileNotFoundError(f"DB not found: {DB_PATH}")
    conn = sqlite3.connect(str(DB_PATH), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-2000")
    conn.execute("PRAGMA mmap_size=268435456")
    conn.execute("PRAGMA temp_store=MEMORY")
    return conn

def get_stats():
    tables = ["workspaces", "sessions", "exchanges", "tool_calls", "edit_sessions", "edited_files", "transcript_events", "chat_messages", "vfs", "state_items", "memory_files", "embeddings", "session_summaries", "anomaly_alerts", "recommendations"]
    counts = {}
    with db_connection() as conn:
        for table in tables:
            try:
                counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                counts[table] = None
    size_kb = DB_PATH.stat().st_size // 1024
    return {"tables": counts, "db_size": f"{size_kb} KB"}

def get_watcher_info():
    watcher, queue = "stopped", 0
    queue_dir = ROOT_DIR / "watcher-queue"
    if queue_dir.exists():
        queue = len(list(queue_dir.glob("*")))
    pid_file = ROOT_DIR / "watcher.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            watcher = f"running (PID {pid})"
        except Exception:
            watcher = "stopped"
    return {"watcher": watcher, "queue": queue}

def query_rows(sql, params=()):
    with db_connection() as conn:
        return [dict(row) for row in conn.execute(sql, params).fetchall()]

def query_one(sql, params=()):
    with db_connection() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None

def get_overview():
    return {
        "stats": get_stats(),
        "watcher": get_watcher_info(),
        "heat": get_heat_summary(),
        "keywords": get_keyword_ranking(limit=15),
    }

def get_sessions(limit=50, workspace=None):
    sql = "SELECT s.session_id, s.workspace_id, s.title, s.created_at, s.request_count, sa.heat_score FROM sessions s LEFT JOIN session_analysis sa USING(session_id)"
    params = []
    if workspace:
        sql += " WHERE s.workspace_id LIKE ?"
        params.append(f"{workspace}%")
    sql += " ORDER BY s.created_at DESC LIMIT ?"
    params.append(limit)
    return query_rows(sql, params)

def get_session_detail(session_id):
    session = query_one("SELECT s.*, sa.* FROM sessions s LEFT JOIN session_analysis sa USING(session_id) WHERE s.session_id LIKE ? LIMIT 1", (f"{session_id}%",))
    if not session:
        return None
    session_id_full = session["session_id"]
    exchanges = query_rows("SELECT exchange_index, user_message, tool_call_count, has_tool_output FROM exchanges WHERE session_id=? ORDER BY exchange_index", (session_id_full,))
    signals = query_rows("SELECT signal_type, matched_keyword, COUNT(*) AS count FROM exchange_signals WHERE session_id=? AND matched_keyword IS NOT NULL GROUP BY signal_type, matched_keyword ORDER BY count DESC LIMIT 50", (session_id_full,))
    return {"session": session, "exchanges": exchanges, "signals": signals}

def get_workspaces():
    return query_rows("SELECT workspace_id, name, session_count FROM workspaces ORDER BY session_count DESC")

def get_heat_summary():
    summary = query_one("SELECT COUNT(*) AS total_sessions, SUM(CASE WHEN heat_score >= 20 THEN 1 ELSE 0 END) AS hot_sessions, SUM(CASE WHEN heat_score >= 50 THEN 1 ELSE 0 END) AS very_hot_sessions, AVG(heat_score) AS avg_heat FROM session_analysis")
    if summary is None:
        summary = {"total_sessions": 0, "hot_sessions": 0, "very_hot_sessions": 0, "avg_heat": 0}
    top_sessions = query_rows("SELECT session_id, heat_score, peak_heat, final_heat FROM session_analysis ORDER BY heat_score DESC LIMIT 50")
    distribution = query_rows("SELECT CASE WHEN heat_score < 20 THEN '0-19' WHEN heat_score < 50 THEN '20-49' WHEN heat_score < 80 THEN '50-79' ELSE '80-100' END AS bucket, COUNT(*) AS count FROM session_analysis GROUP BY bucket ORDER BY bucket")
    return {"summary": summary, "top_sessions": top_sessions, "distribution": distribution}

def get_keyword_ranking(limit=50):
    return query_rows("SELECT matched_keyword AS keyword, signal_type, COUNT(*) AS count FROM exchange_signals WHERE matched_keyword IS NOT NULL AND matched_keyword != '' GROUP BY matched_keyword, signal_type ORDER BY count DESC LIMIT ?", (limit,))

def get_alerts(limit=50):
    try:
        return query_rows("SELECT session_id, alert_type, severity, message FROM anomaly_alerts ORDER BY created_at DESC LIMIT ?", (limit,))
    except Exception:
        return []

def run_action(action):
    if action not in ACTION_COMMANDS:
        return {"error": f"Unsupported action: {action}"}
    if ACTION_STATE["running"]:
        return {"message": "Another action is already running."}
    ACTION_STATE.update({"running": True, "action": action, "output": "", "exit_code": None, "started_at": time.time()})
    def target():
        try:
            proc = subprocess.run(ACTION_COMMANDS[action], capture_output=True, text=True, cwd=ROOT_DIR)
            ACTION_STATE["exit_code"] = proc.returncode
            ACTION_STATE["output"] = proc.stdout + proc.stderr
        except Exception as exc:
            ACTION_STATE["exit_code"] = -1
            ACTION_STATE["output"] = str(exc)
        finally:
            ACTION_STATE["running"] = False
    threading.Thread(target=target, daemon=True).start()
    return {"message": f"Started {action}."}

def parse_json_request(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH", "0") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if length else b""
    try:
        return json.loads(body.decode("utf-8")) if body else {}
    except Exception:
        return {}

def app(environ, start_response):
    path = environ.get("PATH_INFO", "")
    method = environ.get("REQUEST_METHOD", "GET")
    query = parse_qs(environ.get("QUERY_STRING", ""))

    if path == "/":
        status, headers, body = html_response(INDEX_HTML)
    elif path == "/style.css":
        payload = STYLE_CSS.encode("utf-8")
        headers = [("Content-Type", "text/css; charset=utf-8"), ("Content-Length", str(len(payload)))]
        status = "200 OK"
        start_response(status, headers)
        return [payload]
    elif path == "/app.js":
        payload = APP_JS.encode("utf-8")
        headers = [("Content-Type", "application/javascript; charset=utf-8"), ("Content-Length", str(len(payload)))]
        status = "200 OK"
        start_response(status, headers)
        return [payload]
    elif path == "/api/overview":
        status, headers, body = json_response(get_overview())
    elif path == "/api/sessions":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_sessions(limit=limit))
    elif path.startswith("/api/session/"):
        session_id = path[len("/api/session/"):]
        result = get_session_detail(session_id)
        if result is None:
            status, headers, body = json_response({"error": "Not found"}, 404)
        else:
            status, headers, body = json_response(result)
    elif path == "/api/workspaces":
        status, headers, body = json_response(get_workspaces())
    elif path == "/api/heat":
        status, headers, body = json_response(get_heat_summary())
    elif path == "/api/keywords":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_keyword_ranking(limit=limit))
    elif path == "/api/alerts":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_alerts(limit=limit))
    elif path == "/api/action":
        if method == "POST":
            payload = parse_json_request(environ)
            status, headers, body = json_response(run_action(payload.get("action")))
        else:
            status, headers, body = json_response(ACTION_STATE)
    else:
        status, headers, body = json_response({"error": "Not found"}, 404)

    start_response(status, headers)
    return body

def start_server(host="127.0.0.1", port=10001):
    print(f"Starting vscode-ark portal at http://{host}:{port}")
    with make_server(host, port, app) as httpd:
        httpd.serve_forever()

if __name__ == "__main__":
    start_server()
