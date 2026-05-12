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
        case 'tokens':
            initTokens();
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

function initTokens() {
    const summary = document.getElementById('tokens-summary');
    const table = document.getElementById('tokens-table');
    if (!summary) return;
    summary.innerHTML = '<div class="spinner"></div> Loading...';
    fetch('/api/tokens').then(r => r.json()).then(data => {
        const t = (data.tokens || [])[0] || {};
        const fmt = n => (n || 0).toLocaleString();
        summary.innerHTML = `
            <div class="grid-4">
                <div class="card"><div class="card-header">Total Tokens</div><div class="card-value">${fmt(t.total_tokens)}</div></div>
                <div class="card"><div class="card-header">Prompt</div><div class="card-value">${fmt(t.total_prompt)}</div></div>
                <div class="card"><div class="card-header">Completion</div><div class="card-value">${fmt(t.total_completion)}</div></div>
                <div class="card"><div class="card-header">Cached</div><div class="card-value">${fmt(t.total_cached)}</div></div>
                <div class="card"><div class="card-header">Sessions</div><div class="card-value">${fmt(t.session_count)}</div></div>
                <div class="card"><div class="card-header">Turns</div><div class="card-value">${fmt(t.turn_count)}</div></div>
            </div>
            <div class="card" style="margin-top:12px"><b>Models:</b> ${t.models || 'n/a'}</div>
        `;
    }).catch(() => {
        summary.innerHTML = '<div class="alert alert-danger">Failed to load token data.</div>';
    });
    if (table) {
        table.innerHTML = '<div class="spinner"></div> Loading sessions...';
        const sql = 'SELECT s.title, tu.session_id, SUM(tu.prompt_tokens) as prompt, SUM(tu.completion_tokens) as completion, SUM(tu.cached_tokens) as cached, SUM(tu.prompt_tokens + tu.completion_tokens) as total, COUNT(*) as turns, GROUP_CONCAT(DISTINCT tu.model_id) as models FROM token_usage tu JOIN sessions s ON tu.session_id = s.session_id GROUP BY tu.session_id ORDER BY total DESC LIMIT 50';
        fetch('/api/query', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({sql: sql})})
            .then(r => r.json()).then(data => {
                const rows = data.rows || [];
                if (!rows.length) { table.innerHTML = '<p>No per-session data.</p>'; return; }
                const fmt = n => (n || 0).toLocaleString();
                let html = '<div class="card"><div class="card-header">Top Sessions by Token Usage</div><table class="table"><thead><tr><th>Session</th><th>Total</th><th>Prompt</th><th>Completion</th><th>Cached</th><th>Turns</th><th>Models</th></tr></thead><tbody>';
                rows.forEach(r => {
                    html += '<tr><td class="truncate">' + (r.title || r.session_id) + '</td><td>' + fmt(r.total) + '</td><td>' + fmt(r.prompt) + '</td><td>' + fmt(r.completion) + '</td><td>' + fmt(r.cached) + '</td><td>' + r.turns + '</td><td class="truncate">' + (r.models || '') + '</td></tr>';
                });
                html += '</tbody></table></div>';
                table.innerHTML = html;
            }).catch(() => { table.innerHTML = '<p>Failed to load session breakdown.</p>'; });
    }
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
    // Load pipeline status / coverage
    fetch('/api/pipeline/status').then(r => r.json()).then(d => {
        const cards = document.getElementById('pipeline-status-cards');
        if (cards) {
            const w = d.watcher || {};
            const qPending = (w.queue_pending || 0);
            const qColor = qPending > 500 ? 'var(--danger)' : qPending > 50 ? 'var(--warning)' : 'var(--success)';
            cards.innerHTML = `
                <div class="stat-card"><div class="stat-value">${w.alive ? '<span style="color:var(--success)">LIVE</span>' : '<span style="color:var(--danger)">DOWN</span>'}</div><div class="stat-label">Watcher</div></div>
                <div class="stat-card"><div class="stat-value" style="color:${qColor}">${qPending}</div><div class="stat-label">Queue Pending</div></div>
                <div class="stat-card"><div class="stat-value">${d.totals?.symbols || 0}</div><div class="stat-label">Symbols</div></div>
                <div class="stat-card"><div class="stat-value">${d.totals?.signals || 0}</div><div class="stat-label">Signals</div></div>
            `;
        }
        const cov = document.getElementById('pipeline-coverage');
        if (cov && d.sessions) {
            const s = d.sessions;
            const bar = (pct) => {
                const color = pct >= 90 ? 'var(--success)' : pct >= 60 ? 'var(--warning)' : 'var(--danger)';
                return `<div style="background:var(--bg-tertiary);border-radius:4px;height:8px;margin-top:4px;"><div style="background:${color};width:${pct}%;height:8px;border-radius:4px;"></div></div>`;
            };
            cov.innerHTML = `
                <table class="table">
                    <thead><tr><th>Dimension</th><th>Coverage</th><th>Count</th><th>Missing</th></tr></thead>
                    <tbody>
                        <tr><td>Analysis</td><td>${bar(s.analysis_pct)} ${s.analysis_pct}%</td><td>${s.with_analysis}/${s.with_vfs} extractable</td><td>${s.missing_analysis > 0 ? '<span style="color:var(--warning)">' + s.missing_analysis + '</span>' : '—'}</td></tr>
                        <tr><td>Signals</td><td>${bar(s.signals_pct)} ${s.signals_pct}%</td><td>${s.with_signals}/${s.with_vfs} extractable</td><td>${s.missing_signals > 0 ? '<span style="color:var(--warning)">' + s.missing_signals + '</span>' : '—'}</td></tr>
                        <tr><td>Token Usage</td><td>${bar(s.tokens_pct)} ${s.tokens_pct}%</td><td>${s.with_tokens}/${s.with_vfs} extractable</td><td>—</td></tr>
                        <tr><td>Embeddings</td><td>${bar(s.embeddings_pct)} ${s.embeddings_pct}%</td><td>${s.with_embeddings}/${s.total}</td><td>—</td></tr>
                    </tbody>
                </table>
                <div style="margin-top:8px;font-size:12px;color:var(--text-tertiary);">
                    Totals: ${d.totals?.exchanges||0} exchanges &nbsp;·&nbsp; ${d.totals?.signals||0} signals &nbsp;·&nbsp; ${d.totals?.symbols||0} symbols &nbsp;·&nbsp; ${d.totals?.recommendations||0} recommendations &nbsp;·&nbsp; ${d.totals?.alerts||0} alerts
                </div>
            `;
        }
    }).catch(() => {
        const cards = document.getElementById('pipeline-status-cards');
        if (cards) cards.innerHTML = '<div class="alert alert-danger">Could not load pipeline status</div>';
    });

    // Load PMF services
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
