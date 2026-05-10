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
  color-scheme: dark;
  font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: #070a0f;
  color: #eef2ff;
}
* {
  box-sizing: border-box;
}
html, body {
  margin: 0;
  min-height: 100%;
}
body {
  display: flex;
  min-height: 100vh;
  background: radial-gradient(circle at top left, rgba(59,130,246,0.08), transparent 30%), linear-gradient(180deg, #0b1220 0%, #07090f 100%);
}
.app-shell {
  display: grid;
  grid-template-columns: 280px 1fr;
  width: 100%;
}
.sidebar {
  background: rgba(7, 11, 20, 0.96);
  border-right: 1px solid rgba(255,255,255,0.06);
  display: flex;
  flex-direction: column;
  padding: 28px 20px;
  gap: 18px;
}
.sidebar h1 {
  margin: 0 0 8px;
  font-size: 1.45rem;
  letter-spacing: -0.03em;
}
.sidebar p {
  margin: 0;
  color: #94a3b8;
  font-size: 0.95rem;
  line-height: 1.7;
}
.nav-list {
  list-style: none;
  padding: 0;
  margin: 0;
  display: grid;
  gap: 10px;
}
.nav-item {
  border-radius: 16px;
  padding: 14px 16px;
  cursor: pointer;
  color: #d1d5db;
  border: 1px solid transparent;
  background: rgba(255,255,255,0.02);
  transition: transform 0.18s ease, background 0.18s ease, border-color 0.18s ease;
}
.nav-item:hover {
  transform: translateY(-1px);
  background: rgba(255,255,255,0.05);
}
.nav-item.active {
  background: rgba(59,130,246,0.16);
  border-color: rgba(59,130,246,0.35);
  color: #eff6ff;
}
.content {
  padding: 30px;
  overflow: auto;
}
.page-title {
  margin: 0 0 8px;
  font-size: clamp(2rem, 2.4vw, 2.6rem);
  letter-spacing: -0.04em;
}
.page-subtitle {
  margin: 0 0 26px;
  color: #a5b4fc;
  font-size: 0.98rem;
  max-width: 720px;
  line-height: 1.7;
}
.grid {
  display: grid;
  gap: 18px;
  grid-template-columns: repeat(auto-fit,minmax(240px,1fr));
}
.card {
  background: rgba(15, 23, 42, 0.92);
  border: 1px solid rgba(148,163,184,0.08);
  border-radius: 22px;
  padding: 24px;
  box-shadow: 0 24px 80px rgba(10, 15, 31, 0.14);
}
.card h2 {
  margin-top: 0;
  font-size: 1.2rem;
}
.button-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}
.button,
button {
  border: 1px solid transparent;
  background: #2563eb;
  color: white;
  padding: 12px 18px;
  border-radius: 14px;
  cursor: pointer;
  transition: transform 0.18s ease, background 0.18s ease, box-shadow 0.18s ease;
}
.button:hover,
button:hover {
  transform: translateY(-1px);
  box-shadow: 0 10px 30px rgba(37,99,235,0.24);
}
.button.secondary,
button.secondary {
  background: rgba(148,163,184,0.08);
  color: #e2e8f0;
}
.button:disabled,
button:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}
.search-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
  margin-bottom: 18px;
}
.search-input,
.select-input {
  flex: 1 1 260px;
  min-width: 220px;
  padding: 14px 16px;
  border-radius: 16px;
  border: 1px solid rgba(148,163,184,0.12);
  background: rgba(15,23,42,0.95);
  color: #e2e8f0;
}
.search-input::placeholder {
  color: #94a3b8;
}
.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border-radius: 999px;
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(148,163,184,0.12);
  font-size: 0.88rem;
}
.chart-row {
  display: grid;
  gap: 12px;
  margin-top: 16px;
}
.chart-label {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  color: #cbd5e1;
  font-size: 0.95rem;
}
.chart-bar {
  height: 16px;
  background: linear-gradient(90deg, #60a5fa, #2563eb);
  border-radius: 999px;
  min-width: 32px;
}
.small-note {
  color: #94a3b8;
  font-size: 0.92rem;
  margin-top: 8px;
}
.table-container {
  overflow: auto;
}
table {
  width: 100%;
  border-collapse: collapse;
}
th, td {
  text-align: left;
  padding: 14px 12px;
  border-bottom: 1px solid rgba(148,163,184,0.08);
}
th {
  color: #94a3b8;
  font-size: 0.92rem;
}
tbody tr:hover {
  background: rgba(255,255,255,0.05);
}
.status-pill {
  display: inline-flex;
  align-items: center;
  padding: 5px 12px;
  border-radius: 999px;
  background: rgba(255,255,255,0.05);
  border: 1px solid rgba(148,163,184,0.12);
  color: #dbeafe;
  font-size: 0.85rem;
}
.metric-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit,minmax(180px,1fr));
  gap: 18px;
}
.metric-card {
  background: rgba(255,255,255,0.04);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 22px;
  padding: 22px;
  min-height: 120px;
}
.metric-card strong {
  display: block;
  font-size: 1.8rem;
  margin-bottom: 10px;
}
.pre {
  background: rgba(15,23,42,0.98);
  border: 1px solid rgba(148,163,184,0.10);
  border-radius: 18px;
  padding: 16px;
  overflow: auto;
  white-space: pre-wrap;
}
@media (max-width: 980px) {
  .app-shell {
    grid-template-columns: 1fr;
  }
  .sidebar {
    border-right: none;
    padding: 18px 16px;
  }
  .content {
    padding: 20px;
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

function createMetricCard(label, value, description) {
  const card = document.createElement('div');
  card.className = 'metric-card';
  card.innerHTML = `<strong>${value}</strong><div>${label}</div><div style="margin-top:6px;color:#94a3b8;">${description || ''}</div>`;
  return card;
}

function createSearchBar({ placeholder, value = '', onSearch, label }) {
  const wrapper = document.createElement('div');
  wrapper.className = 'search-bar';
  if (label) {
    const labelEl = document.createElement('div');
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
    bar.style.width = `${Math.max(6, Math.round((count / total) * 100))}%`;
  } else {
    bar.style.width = '6%';
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
    item.innerHTML = `<strong>${page.title}</strong><div style="font-size:0.9rem;color:#94a3b8;">${page.description}</div>`;
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
  content.appendChild(subtitle);
  await currentPage.load(content);
}

async function refreshCurrentPage() {
  if (currentPage && currentPage.refresh) {
    await currentPage.refresh();
  }
}

function updateActionLog(text) {
  const log = document.getElementById('action-log');
  if (log) log.textContent = text;
}

registerPage({
  id: 'dashboard',
  title: 'Dashboard',
  description: 'Real-time behavioral signals, frustration heatmap, and pipeline health.',
  async load(container) {
    const overview = await fetchJson('/api/overview');
    const metrics = document.createElement('div');
    metrics.className = 'metric-grid';
    const metricData = [
      { label: 'Sessions Analyzed', value: formatNumber(overview.stats.tables.sessions), detail: 'Total session history' },
      { label: 'Avg Heat Score', value: overview.heat.summary.avg_heat ? overview.heat.summary.avg_heat.toFixed(1) : '0', detail: 'Behavioral frustration' },
      { label: 'Critical Sessions', value: formatNumber(overview.heat.summary.very_hot_sessions), detail: 'Heat >= 50' },
      { label: 'Alerts Triggered', value: formatNumber(overview.stats.tables.anomaly_alerts), detail: 'Semantic anomalies' },
    ];
    metricData.forEach((m) => metrics.appendChild(createMetricCard(m.label, m.value, m.detail)));
    container.appendChild(metrics);

    const pipelineCard = document.createElement('div');
    pipelineCard.className = 'card';
    pipelineCard.innerHTML = '<h2>Pipeline Status</h2>';
    const status = [
      `<div class="status-pill">Watcher: ${overview.watcher.watcher}</div>`,
      `<div class="status-pill">Queue: ${overview.watcher.queue} pending</div>`,
      `<div class="status-pill">DB: ${overview.stats.db_size}</div>`,
      `<div class="status-pill">Workspaces: ${overview.stats.tables.workspaces}</div>`,
    ];
    pipelineCard.innerHTML += status.join('');
    container.appendChild(pipelineCard);

    const heatCard = document.createElement('div');
    heatCard.className = 'card';
    heatCard.innerHTML = `<h2>Heat Distribution</h2>`;
    const total = overview.heat.summary.total_sessions || 1;
    overview.heat.distribution.forEach((bucket) => heatCard.appendChild(createBarRow(bucket.bucket, bucket.count, total)));
    container.appendChild(heatCard);

    const keywordsCard = document.createElement('div');
    keywordsCard.className = 'card';
    keywordsCard.innerHTML = '<h2>Top Signal Keywords</h2>';
    const keywordsList = document.createElement('div');
    keywordsList.style.display = 'grid';
    keywordsList.style.gap = '8px';
    overview.keywords.slice(0, 12).forEach((kw) => {
      const chip = document.createElement('div');
      chip.className = 'tag-chip';
      chip.innerHTML = `${kw.keyword} <span style="color:#94a3b8;">${kw.signal_type}: ${kw.count}</span>`;
      keywordsList.appendChild(chip);
    });
    keywordsCard.appendChild(keywordsList);
    container.appendChild(keywordsCard);

    const recentCard = document.createElement('div');
    recentCard.className = 'card';
    recentCard.innerHTML = '<h2>Recent Sessions</h2>';
    recentCard.appendChild(createTable(
      [
        { label: 'ID', key: 'session_id' },
        { label: 'Title', key: 'title' },
        { label: 'Heat', key: 'heat_score' },
        { label: 'Requests', key: 'request_count' },
      ],
      overview.recent_sessions.slice(0, 8),
      (row) => navigate('sessions')
    ));
    container.appendChild(recentCard);
  },
});

registerPage({
  id: 'sessions',
  title: 'Sessions',
  description: 'Browse behavioral records, filter by workspace and keywords, drill into session transcripts.',
  selectedSession: null,
  filter: {
    query: '',
    workspace: '',
  },
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
      label: 'Search',
      placeholder: 'Filter by title, workspace, or session ID...',
      value: this.filter.query,
      onSearch: (value) => {
        this.filter.query = value;
        this.renderSessionList(container);
      },
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

    this.sessions = await fetchJson('/api/sessions?limit=200');
    await this.renderSessionList(container);

    const detail = document.createElement('div');
    detail.id = 'session-detail';
    detail.style.marginTop = '24px';
    container.appendChild(detail);
    if (this.selectedSession) {
      await this.openSession(this.selectedSession);
    }
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
    listCard.innerHTML = `<h2>Sessions — ${rows.length} results</h2><div class="small-note">Click any row to view detailed signals, exchanges, and behavior.</div>`;
    listCard.appendChild(createTable(
      [
        { label: 'ID', key: 'session_id' },
        { label: 'Title', key: 'title' },
        { label: 'Workspace', key: 'workspace_id' },
        { label: 'Heat', key: 'heat_score' },
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
      header.innerHTML = `<h2>${data.session.title || data.session.session_id}</h2><div class="status-pill">Workspace: ${data.session.workspace_id}</div><div class="status-pill">Heat: ${data.session.heat_score || 0}</div><div class="status-pill">Requests: ${data.session.request_count || 0}</div><div class="status-pill">Saved: ${data.session.saved_session ? 'yes' : 'no'}</div>`;
      detail.appendChild(header);

      const metadata = document.createElement('div');
      metadata.className = 'card';
      const createdAt = data.session.created_at ? new Date(data.session.created_at).toLocaleString() : '—';
      metadata.innerHTML = `<h3>Metadata</h3><div class="small-note">Created: ${createdAt}</div><div class="small-note">Peak heat: ${data.session.peak_heat || 0}</div><div class="small-note">Final heat: ${data.session.final_heat || 0}</div>`;
      detail.appendChild(metadata);

      const signalsCard = document.createElement('div');
      signalsCard.className = 'card';
      signalsCard.innerHTML = '<h3>Behavioral Signals</h3>';
      if (data.signals.length === 0) {
        signalsCard.innerHTML += '<div class="small-note">No signals detected in this session.</div>';
      } else {
        signalsCard.appendChild(createTable(
          [
            { label: 'Type', key: 'signal_type' },
            { label: 'Keyword', key: 'matched_keyword' },
            { label: 'Hits', key: 'count' },
          ],
          data.signals
        ));
      }
      detail.appendChild(signalsCard);

      const exchangesCard = document.createElement('div');
      exchangesCard.className = 'card';
      exchangesCard.innerHTML = `<h3>Exchanges — ${data.exchanges.length} turns</h3>`;
      exchangesCard.appendChild(createTable(
        [
          { label: '#', key: 'exchange_index' },
          { label: 'Tools', key: 'tool_call_count' },
          { label: 'Output', key: 'has_tool_output' },
          { label: 'Message preview', key: 'user_message' },
        ],
        data.exchanges.map((exchange) => ({
          ...exchange,
          has_tool_output: exchange.has_tool_output ? 'yes' : 'no',
          user_message: exchange.user_message ? exchange.user_message.slice(0, 100) : '',
        }))
      ));
      detail.appendChild(exchangesCard);
    } catch (err) {
      detail.innerHTML = `<div class="card"><p>Error loading session: ${err.message}</p></div>`;
    }
  },
});

registerPage({
  id: 'workspaces',
  title: 'Workspaces',
  description: 'Browse registered workspaces, usage patterns, and session coverage.',
  async load(container) {
    const workspaces = await fetchJson('/api/workspaces');
    const summary = document.createElement('div');
    summary.className = 'card';
    summary.innerHTML = '<h2>Workspace coverage</h2><div class="small-note">Click a workspace row to filter sessions for that workspace.</div>';
    container.appendChild(summary);

    const tableCard = document.createElement('div');
    tableCard.className = 'card';
    tableCard.innerHTML = '<h2>Workspaces</h2>';
    tableCard.appendChild(createTable(
      [
        { label: 'Workspace ID', key: 'workspace_id' },
        { label: 'Name', key: 'name' },
        { label: 'Type', key: 'type' },
        { label: 'Sessions', key: 'session_count' },
        { label: 'URI', key: 'uri' },
      ],
      workspaces,
      (row) => {
        const sessionsPage = getPage('sessions');
        if (sessionsPage) {
          sessionsPage.filter.workspace = row.workspace_id;
          sessionsPage.filter.query = '';
        }
        navigate('sessions');
      }
    ));
    container.appendChild(tableCard);
  },
});

registerPage({
  id: 'heat',
  title: 'Heat',
  description: 'Frustration intelligence and heat distribution analytics.',
  async load(container) {
    const heat = await fetchJson('/api/heat');
    const cards = document.createElement('div');
    cards.className = 'metric-grid';
    cards.appendChild(createMetricCard('Total sessions', formatNumber(heat.summary.total_sessions), 'Session analysis total.'));
    cards.appendChild(createMetricCard('Hot sessions', formatNumber(heat.summary.hot_sessions), 'Heat score >= 20.'));
    cards.appendChild(createMetricCard('Very hot', formatNumber(heat.summary.very_hot_sessions), 'Heat score >= 50.'));
    cards.appendChild(createMetricCard('Average heat', heat.summary.avg_heat ? heat.summary.avg_heat.toFixed(1) : '0', 'Mean heat score.'));
    container.appendChild(cards);

    const distribution = document.createElement('div');
    distribution.className = 'card';
    distribution.innerHTML = '<h2>Heat distribution</h2>';
    const total = heat.summary.total_sessions || 1;
    heat.distribution.forEach((bucket) => distribution.appendChild(createBarRow(bucket.bucket, bucket.count, total)));
    container.appendChild(distribution);

    const top = document.createElement('div');
    top.className = 'card';
    top.innerHTML = '<h2>Top heat sessions</h2>';
    top.appendChild(createTable(
      [
        { label: 'Session', key: 'session_id' },
        { label: 'Heat', key: 'heat_score' },
        { label: 'Peak', key: 'peak_heat' },
        { label: 'Final', key: 'final_heat' },
        { label: 'Saved', key: 'saved_session' },
      ],
      heat.top_sessions.map((row) => ({ ...row, saved_session: row.saved_session ? 'yes' : 'no' }))
    ));
    container.appendChild(top);
  },
});

registerPage({
  id: 'keywords',
  title: 'Keywords',
  description: 'Ranked signal keywords and frequency across the corpus.',
  async load(container) {
    const keywords = await fetchJson('/api/keywords?limit=120');
    const note = document.createElement('div');
    note.className = 'small-note';
    note.textContent = 'Top keywords represent the most common matched signal tokens across all sessions.';
    container.appendChild(note);
    container.appendChild(createTable(
      [
        { label: 'Keyword', key: 'keyword' },
        { label: 'Signal type', key: 'signal_type' },
        { label: 'Count', key: 'count' },
      ],
      keywords
    ));
  },
});

registerPage({
  id: 'alerts',
  title: 'Alerts',
  description: 'Anomaly and safety alerts surfaced from session intelligence.',
  async load(container) {
    const alerts = await fetchJson('/api/alerts?limit=120');
    container.appendChild(createTable(
      [
        { label: 'Session', key: 'session_id' },
        { label: 'Alert type', key: 'alert_type' },
        { label: 'Severity', key: 'severity' },
        { label: 'Message', key: 'message' },
        { label: 'Detected', key: 'created_at' },
      ],
      alerts
    ));
  },
});

registerPage({
  id: 'recommendations',
  title: 'Recommendations',
  description: 'Session-level recommendations and recovery actions.',
  async load(container) {
    const recs = await fetchJson('/api/recommendations?limit=120');
    container.appendChild(createTable(
      [
        { label: 'Session', key: 'session_id' },
        { label: 'Category', key: 'category' },
        { label: 'Recommendation', key: 'recommendation' },
        { label: 'Score', key: 'score' },
      ],
      recs
    ));
  },
});

registerPage({
  id: 'actions',
  title: 'Actions',
  description: 'Run pipeline commands and view live execution status.',
  async load(container) {
    const card = document.createElement('div');
    card.className = 'card';
    card.innerHTML = '<h2>Pipeline Actions</h2>';
    const row = document.createElement('div');
    row.className = 'button-row';
    ['sync', 'reconstruct', 'embed-build', 'watch-start', 'watch-stop', 'watch-restart'].forEach((action) => {
      const button = document.createElement('button');
      button.textContent = action.replace(/-/g, ' ');
      button.onclick = async () => {
        button.disabled = true;
        try {
          const resp = await fetchJson('/api/action', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action }),
          });
          updateActionLog(resp.message);
        } catch (err) {
          updateActionLog('Action failed: ' + err.message);
        } finally {
          button.disabled = false;
        }
      };
      row.appendChild(button);
    });
    card.appendChild(row);
    const log = document.createElement('pre');
    log.id = 'action-log';
    log.className = 'pre';
    log.textContent = 'No actions run yet.';
    card.appendChild(log);
    container.appendChild(card);
    await this.refresh();
  },
  async refresh() {
    try {
      const action = await fetchJson('/api/action');
      updateActionLog(action.running ? `Running ${action.action}...\n\n${action.output}` : `Last action: ${action.action || 'none'}\nStatus: ${action.exit_code === null ? 'idle' : action.exit_code === 0 ? 'success' : 'failed'}\n\n${action.output}`);
    } catch (err) {
      updateActionLog('Unable to load action status.');
    }
  },
});

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
      <p>Intelligence portal for behavioral signals, heat analysis, and workspace insights.</p>
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
    headers = [
        ("Content-Type", "application/json"),
        ("Content-Length", str(len(body))),
        ("Cache-Control", "no-store"),
    ]
    return status, headers, [body]


def html_response(body):
    payload = body.encode("utf-8")
    headers = [
        ("Content-Type", "text/html; charset=utf-8"),
        ("Content-Length", str(len(payload))),
        ("Cache-Control", "no-store"),
    ]
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
    tables = [
        "workspaces", "sessions", "exchanges", "tool_calls", "edit_sessions", "edited_files",
        "transcript_events", "chat_messages", "vfs", "state_items", "memory_files",
        "embeddings", "session_summaries", "anomaly_alerts", "recommendations",
    ]
    counts = {}
    with db_connection() as conn:
        for table in tables:
            try:
                counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except Exception:
                counts[table] = None
    size_kb = DB_PATH.stat().st_size // 1024
    return {
        "tables": counts,
        "db_size": f"{size_kb} KB",
    }


def get_watcher_info():
    watcher = "stopped"
    queue = 0
    last_ingested = None
    queue_dir = ROOT_DIR / "watcher-queue"
    if queue_dir.exists():
        queue = len(list(queue_dir.glob("*.json")))
    pid_file = ROOT_DIR / "watcher.pid"
    if pid_file.exists():
        pid = pid_file.read_text().strip()
        try:
            os.kill(int(pid), 0)
            watcher = f"running ({pid})"
        except Exception:
            watcher = f"stale pid ({pid})"
    try:
        with db_connection() as conn:
            row = conn.execute("SELECT MAX(ingested_at) AS last_ingested FROM transcript_events").fetchone()
            last_ingested = row[0]
    except Exception:
        last_ingested = None
    return {
        "watcher": watcher,
        "queue": queue,
        "last_ingested": last_ingested,
    }


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
        "keywords": get_keyword_ranking(limit=10),
        "top_signals": get_top_signals(limit=10),
        "recent_sessions": get_sessions(limit=10),
    }


def get_sessions(limit=50, workspace=None):
    sql = "SELECT s.session_id, s.workspace_id, s.title, s.created_at, s.last_message_at, s.request_count, sa.heat_score, sa.peak_heat, sa.final_heat, sa.saved_session FROM sessions s LEFT JOIN session_analysis sa USING(session_id)"
    params = []
    if workspace:
        sql += " WHERE s.workspace_id LIKE ?"
        params.append(f"{workspace}%")
    sql += " ORDER BY s.last_message_at DESC LIMIT ?"
    params.append(limit)
    return query_rows(sql, params)


def get_session_detail(session_id):
    session = query_one(
        "SELECT s.*, sa.* FROM sessions s LEFT JOIN session_analysis sa USING(session_id) WHERE s.session_id LIKE ? LIMIT 1",
        (f"{session_id}%",)
    )
    if not session:
        return None
    session_id_full = session["session_id"]
    exchanges = query_rows(
        "SELECT exchange_index, user_ts, user_message, reasoning_text, response_text, tool_call_count, has_tool_output FROM exchanges WHERE session_id=? ORDER BY exchange_index",
        (session_id_full,)
    )
    signals = query_rows(
        "SELECT signal_type, matched_keyword, COUNT(*) AS count FROM exchange_signals WHERE session_id=? AND matched_keyword IS NOT NULL AND matched_keyword != '' GROUP BY signal_type, matched_keyword ORDER BY count DESC LIMIT 50",
        (session_id_full,)
    )
    return {
        "session": session,
        "exchanges": exchanges,
        "signals": signals,
    }


def get_workspaces():
    return query_rows("SELECT workspace_id, name, type, session_count, uri FROM workspaces ORDER BY session_count DESC")


def get_heat_summary():
    summary = query_one(
        "SELECT COUNT(*) AS total_sessions, SUM(CASE WHEN heat_score >= 20 THEN 1 ELSE 0 END) AS hot_sessions, SUM(CASE WHEN heat_score >= 50 THEN 1 ELSE 0 END) AS very_hot_sessions, AVG(heat_score) AS avg_heat FROM session_analysis"
    )
    if summary is None:
        summary = {
            "total_sessions": 0,
            "hot_sessions": 0,
            "very_hot_sessions": 0,
            "avg_heat": 0,
        }
    top_sessions = query_rows(
        "SELECT session_id, heat_score, peak_heat, final_heat, saved_session FROM session_analysis ORDER BY heat_score DESC LIMIT 15"
    )
    distribution = query_rows(
        "SELECT CASE WHEN heat_score < 20 THEN '0-19' WHEN heat_score < 50 THEN '20-49' WHEN heat_score < 80 THEN '50-79' ELSE '80-100' END AS bucket, COUNT(*) AS count FROM session_analysis GROUP BY bucket ORDER BY bucket"
    )
    return {
        "summary": summary,
        "top_sessions": top_sessions,
        "distribution": distribution,
    }


def get_keyword_ranking(limit=50):
    return query_rows(
        "SELECT matched_keyword AS keyword, signal_type, COUNT(*) AS count FROM exchange_signals WHERE matched_keyword IS NOT NULL AND matched_keyword != '' GROUP BY matched_keyword, signal_type ORDER BY count DESC LIMIT ?",
        (limit,)
    )


def get_top_signals(limit=50):
    return query_rows(
        "SELECT signal_type, matched_keyword AS keyword, COUNT(*) AS count FROM exchange_signals WHERE matched_keyword IS NOT NULL AND matched_keyword != '' GROUP BY signal_type, matched_keyword ORDER BY count DESC LIMIT ?",
        (limit,)
    )


def get_alerts(limit=50):
    try:
        return query_rows(
            "SELECT session_id, alert_type, severity, message, created_at FROM anomaly_alerts ORDER BY created_at DESC LIMIT ?",
            (limit,)
        )
    except Exception:
        return []


def get_recommendations(limit=50):
    try:
        return query_rows(
            "SELECT session_id, category, recommendation, score FROM recommendations ORDER BY score DESC LIMIT ?",
            (limit,)
        )
    except Exception:
        return []


def run_action(action):
    if action not in ACTION_COMMANDS:
        return {"error": f"Unsupported action: {action}"}
    if ACTION_STATE["running"]:
        return {"message": "Another action is already running."}

    ACTION_STATE.update({
        "running": True,
        "action": action,
        "output": "",
        "exit_code": None,
        "started_at": time.time(),
        "completed_at": None,
    })

    def target():
        try:
            proc = subprocess.run(ACTION_COMMANDS[action], capture_output=True, text=True, cwd=ROOT_DIR, env={**os.environ, "PYTHONPATH": str(ROOT_DIR)})
            ACTION_STATE["exit_code"] = proc.returncode
            ACTION_STATE["output"] = proc.stdout + "\n" + proc.stderr
        except Exception as exc:
            ACTION_STATE["exit_code"] = -1
            ACTION_STATE["output"] = str(exc)
        finally:
            ACTION_STATE["running"] = False
            ACTION_STATE["completed_at"] = time.time()

    threading.Thread(target=target, daemon=True).start()
    return {"message": f"Started {action}."}


def parse_json_request(environ):
    try:
        length = int(environ.get("CONTENT_LENGTH", "0") or 0)
    except ValueError:
        length = 0
    body = environ["wsgi.input"].read(length) if length else b""
    if not body:
        return {}
    try:
        return json.loads(body.decode("utf-8"))
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
        headers = [("Content-Type", "text/css; charset=utf-8"), ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")]
        status = "200 OK"
        start_response(status, headers)
        return [payload]
    elif path == "/app.js":
        payload = APP_JS.encode("utf-8")
        headers = [("Content-Type", "application/javascript; charset=utf-8"), ("Content-Length", str(len(payload))), ("Cache-Control", "no-store")]
        status = "200 OK"
        start_response(status, headers)
        return [payload]
    elif path == "/api/status" and method == "GET":
        status, headers, body = json_response(get_watcher_info())
    elif path == "/api/stats" and method == "GET":
        status, headers, body = json_response(get_stats())
    elif path == "/api/overview" and method == "GET":
        status, headers, body = json_response(get_overview())
    elif path == "/api/sessions" and method == "GET":
        limit = int(query.get("limit", [50])[0])
        workspace = query.get("workspace", [None])[0]
        status, headers, body = json_response(get_sessions(limit=limit, workspace=workspace))
    elif path.startswith("/api/session/") and method == "GET":
        session_id = path[len("/api/session/"):]
        payload = get_session_detail(session_id)
        if payload is None:
            status, headers, body = json_response({"error": "Session not found"}, status_code=404)
        else:
            status, headers, body = json_response(payload)
    elif path == "/api/workspaces" and method == "GET":
        status, headers, body = json_response(get_workspaces())
    elif path == "/api/heat" and method == "GET":
        status, headers, body = json_response(get_heat_summary())
    elif path == "/api/keywords" and method == "GET":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_keyword_ranking(limit=limit))
    elif path == "/api/alerts" and method == "GET":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_alerts(limit=limit))
    elif path == "/api/recommendations" and method == "GET":
        limit = int(query.get("limit", [50])[0])
        status, headers, body = json_response(get_recommendations(limit=limit))
    elif path == "/api/action":
        if method == "POST":
            payload = parse_json_request(environ)
            action = payload.get("action")
            status, headers, body = json_response(run_action(action))
        else:
            status, headers, body = json_response(ACTION_STATE)
    else:
        status, headers, body = json_response({"error": "Not found"}, status_code=404)

    start_response(status, headers)
    return body


def start_server(host="127.0.0.1", port=10001):
    print(f"Starting vscode-ark web UI at http://{host}:{port}")
    with make_server(host, port, app) as httpd:
        print("Press Ctrl+C to stop.")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down local web UI.")
