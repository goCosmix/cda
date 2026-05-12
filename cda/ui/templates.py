import json

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Code Data Ark</title>
    <style>{{STYLE_CSS}}</style>
</head>
<body>
    <div id="root">
        <div class="sidebar">
            <div class="sidebar-header">
                <div class="sidebar-title">Code Data Ark</div>
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
        <div class="page-subtitle">Token consumption across all sessions.</div>
    </div>
    <div id="tokens-summary" class="loading"><div class="spinner"></div>Loading...</div>
    <div id="tokens-table" style="margin-top:16px"></div>
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

PAGE_REGISTRY_JS = "const PAGE_REGISTRY = {\n"
PAGE_REGISTRY_JS += ",\n".join(
    f"    '{name}': () => {template}"
    for name, template in PAGE_TEMPLATES.items()
)
PAGE_REGISTRY_JS += "\n};\n\n"
