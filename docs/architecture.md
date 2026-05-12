# Architecture Guide

## System Overview

Code Data Ark is a multi-stage data pipeline that transforms raw VS Code storage data into actionable intelligence about user-AI interactions. It measures both the human side (behavioral signals: frustration, corrections, redirects) and the AI side (cognitive quality signals: evidence-grounding, assumption-surfacing, self-correction).

```
┌─────────────────────────────────────────────────────────────────┐
│                       VS Code Storage                            │
│  (workspaceStorage, globalStorage, transcripts, state files)    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │   INGEST STAGE           │
        │  (cda/pipeline/ingest.py)   │
        │                          │
        │ - Parse storage files    │
        │ - Gzip compress blobs    │
        │ - Create session records │
        │ - Build VFS index        │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   SQLite Database   │
        │  (cda.db)           │
        │                     │
        │ - workspaces        │
        │ - sessions          │
        │ - vfs               │
        │ - file_offsets      │
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │  RECONSTRUCT STAGE       │
        │  (cda/pipeline/reconstruct.py)
        │                          │
        │ - Parse exchanges        │
        │ - Link tool calls        │
        │ - Build threads          │
        │ - Create FTS index       │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   EMBED STAGE        │
        │   (cda/pipeline/embed.py)
        │                     │
        │ - Build miniLM vectors
        │ - Generate session summaries
        │ - Create alerts/recommendations
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │   SQLite Database   │
        │                     │
        │ - exchanges         │
        │ - fts_exchanges     │
        │ - transcript_events │
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   EXTRACT STAGE          │
        │   (cda/pipeline/extract.py)
        │                          │
        │ - Analyze signals        │
        │ - Compute heat scores    │
        │ - Extract tokens         │
        │ - Aggregate analysis     │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   SQLite Database   │
        │                     │
        │ - exchange_signals  │
        │ - token_usage       │
        │ - session_analysis  │
        │ - symbols           │
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   REASONING STAGE        │
        │  (cda/pipeline/reasoning.py)
        │                          │
        │ - AI output signals      │
        │ - Extended thinking      │
        │ - Cognitive score        │
        │ - Contradiction detect   │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   SQLite Database   │
        │                     │
        │ - reasoning_signals │
        │ - reasoning_score   │
        │   (session_analysis)│
        └──────────┬──────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   LIVE MONITORING        │
        │   (cda/pipeline/watcher.py) │
        │                          │
        │ - Watch file changes     │
        │ - Queue operations       │
        │ - Incremental updates    │
        │ - Periodic health checks │
        │ - Maintain FTS index     │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   QUERY INTERFACE        │
        │   (cda CLI)              │
        │                          │
        │ - 50+ commands           │
        │ - Policy filtering       │
        │ - Rich output formatting │
        └──────────────────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   LOCAL RUNTIME          │
        │   (EAK Kernel)           │
        │                          │
        │ - Service lifecycle      │
        │ - Local status + logs    │
        │ - Health checks + alerts │
        └──────────────────────────┘
```

## EAK Embedded Kernel — Embedded Runtime Management

The EAK (Embedded App Kernel) is Ark's local embedded runtime layer. It is a two-layer split:

- **`kernel_core.py`** — shared bottom layer: service lifecycle, start/stop/restart, PID tracking, state JSON, event journal, run_count, task completion threads. Shared DNA across all goCosmix embedded kernels.
- **`eak_kernel.py`** — cda-specific top layer: 7 service definitions (watcher, ui, sync, reconstruct, embed-build, backfill, symbol-index), launchd integration, browser helpers.
- **`pmf_kernel.py`** — backwards-compat shim; re-exports all EAK names so legacy callers work unchanged.

Key EAK responsibilities:
- Manage service lifecycle with PID files, background subprocesses, and log files.
- Expose local service state for CLI and UI control via `cda eak` commands.
- Persist runtime metadata and health status in `local/eak/runtime.json`.
- Provide a lightweight event journal for runtime actions and alerts.
- Run periodic health checks (watcher liveness, queue depth) with macOS notifications via `alerting.py`.

## Data Flow Details

### Stage 1: Ingestion (ingest.py)

**Input**: VS Code storage directories
**Output**: SQLite database with workspaces, sessions, VFS blobs

```python
# Key operations
1. Scan ~/Library/Application Support/Code/User/
2. Parse workspace metadata and session files
3. Read and gzip-compress transcript logs
4. Calculate SHA256 hashes for verification
5. Insert into VFS table with metadata
6. Track file offsets for incremental updates
```

**Performance**: ~740 sessions ingested in seconds
**Storage**: Raw data compressed 10-50x with gzip

### Stage 2: Reconstruction (reconstruct.py)

**Input**: Raw transcript events and tool calls
**Output**: Structured exchanges with linked contexts

```python
# Key operations
1. Parse JSONL transcript events
2. Group events by exchange index
3. Match tool calls to user messages
4. Build exchange objects with full context
5. Populate FTS index for searching
6. Create bidirectional links between entities
```

**Indexing**: FTS5 full-text search with snippet support
**Linking**: Tool outputs connected to requests

### Stage 3: Extraction (extract.py)

**Input**: Structured exchanges
**Output**: Behavioral signals, heat scores, analytics

```python
# Key operations
1. Pattern match 200+ keywords against user messages
2. Classify signals (correction, frustration, pre_correction, redirect, etc.)
3. Calculate heat score (weighted sum, 0-100)
4. Track token usage per request
5. Detect context compaction events
6. Aggregate per-session metrics into session_analysis
```

**Signals**: 6 types with 200+ keywords
**Heat Formula**: min(100, Σ(weight × count))

### Stage 3b: Reasoning Analysis (reasoning.py)

**Input**: `transcript_events` rows where `event_type='assistant.message'`
**Output**: AI cognitive quality signals, per-session reasoning_score

```python
# Key operations
1. Read assistant content + reasoningText (extended thinking) per message
2. Pattern match 10 signal types against AI output
3. Detect cross-message contradictions
4. Compute weighted cognitive score (0-100)
5. Store per-match rows in reasoning_signals
6. Upsert reasoning_score into session_analysis
```

**Signal axes**: epistemic virtue, process transparency, failure modes
**Score formula**: min(100, max(0, Σ(signal_count × weight)))

### Stage 4: Live Monitoring (watcher.py)

**Input**: File system events
**Output**: Queue of pending operations, database updates

```python
# Key operations
1. Monitor VS Code directories for changes
2. Queue operations before committing
3. Replay queue on restart (crash resilience)
4. Incremental database updates (extract + reasoning + embed per session)
5. Maintain FTS index
6. Periodic health checks every 300s (watcher liveness, queue depth)
7. Fire macOS notifications on WARN/CRIT thresholds
```

**Queue**: File-based JSON persistence
**Resilience**: Automatic replay on daemon restart

## Database Schema

### Core Tables

```sql
-- Workspaces and Sessions
workspaces(
  workspace_id TEXT PRIMARY KEY,
  path TEXT,
  name TEXT,
  created_at INTEGER,
  modified_at INTEGER
)

sessions(
  session_id TEXT PRIMARY KEY,
  workspace_id TEXT,
  title TEXT,
  created_at INTEGER,
  exchange_count INTEGER
)

-- Data Storage
vfs(
  id INTEGER PRIMARY KEY,
  workspace_id TEXT,
  session_id TEXT,
  source_type TEXT,  -- "transcript", "state", "memory"
  source_path TEXT,
  filename TEXT,
  content_type TEXT,  -- "jsonl", "json"
  content BLOB,      -- gzip-compressed
  size_bytes INTEGER,
  sha256 TEXT,
  ingested_at INTEGER
)

-- Conversations
exchanges(
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  workspace_id TEXT,
  exchange_index INTEGER,
  user_ts TEXT,
  user_message TEXT,
  response_text TEXT,
  reasoning_text TEXT,
  tool_call_count INTEGER,
  tool_calls TEXT,  -- JSON array
  attachments TEXT,  -- JSON array
  duration_ms INTEGER
)

-- Search Index
fts_exchanges USING fts5(
  session_id UNINDEXED,
  user_message,
  reasoning_text,
  response_text,
  content=exchanges
)

-- Behavioral Analysis (user signals)
exchange_signals(
  session_id TEXT,
  exchange_index INTEGER,
  signal_type TEXT,  -- "correction", "frustration", etc.
  matched_keyword TEXT,
  user_message TEXT,
  ts TEXT
)

-- AI Cognitive Quality Signals
reasoning_signals(
  id INTEGER PRIMARY KEY,
  session_id TEXT,
  request_id TEXT,
  ts TEXT,
  signal_type TEXT,  -- "metacognitive", "evidence_grounded", "false_certainty", etc.
  excerpt TEXT,      -- matched text snippet
  valence INTEGER    -- +1 positive, -1 negative
)

session_analysis(
  session_id TEXT PRIMARY KEY,
  total_corrections INTEGER,
  total_frustrations INTEGER,
  total_pre_corrections INTEGER,
  total_affirmations INTEGER,
  total_redirects INTEGER,
  total_approvals INTEGER,
  heat_score INTEGER,
  peak_heat INTEGER,
  final_heat INTEGER,
  turning_point_ts TEXT,
  turning_point_text TEXT,
  saved_session INTEGER,
  total_tokens_prompt INTEGER,
  total_tokens_completion INTEGER,
  compaction_count INTEGER,
  model_ids TEXT,
  reasoning_score INTEGER,        -- AI cognitive quality score (0-100)
  reasoning_analyzed_at TEXT,
  analyzed_at TEXT
)

-- Code Symbols
symbols(
  id INTEGER PRIMARY KEY,
  workspace_id TEXT,
  file_path TEXT,
  symbol_name TEXT,
  symbol_type TEXT,  -- "function", "class", "method", etc.
  line_number INTEGER,
  context TEXT,
  indexed_at INTEGER
)
```

## Command Architecture

### CLI Command Groups

```
cda
├── Core
│   ├── stats          # System statistics
│   ├── status         # Daemon status
│   ├── sync           # Full ingest
│   └── reconstruct    # Rebuild exchanges
│
├── Browse
│   ├── sessions       # List sessions
│   ├── session        # View session
│   ├── workspaces     # List workspaces
│   └── workspace      # View workspace
│
├── Search
│   ├── search         # Full-text search
│   ├── code-search    # Symbol and code content search
│   ├── semantic-search # Semantic search using embeddings
│   ├── similar        # Similar sessions by semantic similarity
│   ├── related        # Alias for semantically related sessions
│   ├── summarize      # Session summary, topics, recommendations
│   ├── topics         # Semantic topic tags
│   ├── alerts         # Semantic anomaly alerts
│   ├── recommend      # Session recommendations
│   ├── tools          # Tool call search
│   ├── memory         # Memory files
│   └── query          # Raw SQL
│
├── Analyze
│   ├── signals        # Behavioral signals
│   ├── heat           # Frustration analysis
│   ├── behavior       # Aggregate report
│   ├── saved          # Recovered sessions
│   ├── tokens         # Token analysis
│   ├── compactions    # Compaction events
│   └── edits          # Edit analytics
│
├── Export
│   ├── export         # Export session
│   ├── replay         # Print conversation
│   └── vfs            # VFS operations
│
├── Management
│   ├── eak            # EAK kernel control (canonical)
│   │   ├── services
│   │   ├── status
│   │   ├── start
│   │   ├── stop
│   │   ├── restart
│   │   ├── logs
│   │   ├── events
│   │   ├── check
│   │   ├── up
│   │   ├── down
│   │   ├── install
│   │   └── uninstall
│   ├── pmf            # Alias for eak (backwards compat)
│   ├── watch          # Daemon control (legacy direct)
│   │   ├── start
│   │   ├── stop
│   │   └── restart
│   ├── policy         # Access control
│   │   ├── allow
│   │   ├── deny
│   │   └── list
│   └── exchange       # View exchange detail
```

## UI and Web Service

### Local Web UI

- The local dashboard is implemented in `cda/ui/web.py`.
- `cda serve` runs the web server in the foreground on port `10001` by default.
- `cda ui start` launches the same service as a background daemon using a PID file and log file.
- `cda ui stop` and `cda ui status` manage the lifecycle of the background UI.

### Background UI Lifecycle

- `ui start` checks for a running PID, starts the server with `subprocess.Popen`, and records the process state.
- `ui stop` reads the PID file and terminates the server process cleanly.
- `ui status` reports whether the background UI is active and which port is being served.

### Web Service Architecture

- The UI is a lightweight local web service built for rapid inspection and debugging of session analytics.
- It exposes session drilldown, signal summaries, search, and tool-call detail in a browser-based dashboard.
- The service is intended for local use only and does not depend on external servers.

## Performance Characteristics

### Database Performance

- **Full-text search**: <100ms for typical queries
- **Session lookup**: <10ms
- **Aggregation queries**: <500ms for all sessions
- **Concurrent reads**: Supported via WAL mode

### Memory Usage

- **Process baseline**: ~50MB
- **Large sessions**: ~500MB (fully loaded)
- **Search operations**: ~100MB for FTS cache

### Storage

- **Raw data**: ~50-100MB per 1000 sessions
- **Compressed (gzip)**: ~5-10MB per 1000 sessions
- **With indices**: ~20-30MB per 1000 sessions

## Scalability

### Designed for

- ✅ 100-10,000 sessions
- ✅ 1 million+ exchanges
- ✅ Real-time monitoring
- ✅ Concurrent queries (readers)

### Limitations

- ⚠️ Single writer (WAL mode)
- ⚠️ 100MB VFS blob size limit
- ⚠️ 8KB memory page cache by default

## Extension Points

### Adding New Signal Types (user behavioral)

1. Add keyword list to `SIGNAL_PATTERNS` in `extract.py`
2. Update `HEAT_WEIGHT` if needed
3. Re-run `cda backfill --force` to retroactively apply

### Adding New Reasoning Signal Types (AI output)

1. Add compiled regex pattern to `REASONING_SIGNAL_PATTERNS` in `reasoning.py`
2. Set weight in same tuple (positive = virtue, negative = failure)
3. Re-run `cda backfill --force`

### Custom Analysis

1. Query `session_analysis`, `exchange_signals`, or `reasoning_signals` directly
2. Write analysis to results table
3. Export via `cda query` or `cda export`

### Policy Integration

1. Implement allow/deny patterns in `policy.txt`
2. System automatically filters search results
3. Extend `check_policy()` for custom logic

## Deployment Considerations

### Development
```bash
pip install -e .
python3 /Volumes/intel/systems/cda/control/scripts/vet.py  # vet checks
dev check --project . --compile --tests --lint              # full check
cda sync
cda eak up
```

### Production
```bash
pip install -e .
cda setup          # init + eak install + sync + up
cda eak check      # verify health
```

### Monitoring
```bash
cda eak check              # watcher liveness + queue depth
cda eak services           # all service statuses
cda stats                  # system health
cda query "SELECT COUNT(*) FROM sessions"  # activity
```

## Troubleshooting

### Common Issues

**Database Locked**
```bash
cda watch stop
cda watch start
```

**FTS Index Corrupted**
```bash
cda reconstruct
```

**Missing Data**
```bash
cda sync  # Full rebuild
```

**Performance Degradation**
```bash
# Check database size
sqlite3 cda.db ".tables"
sqlite3 cda.db "SELECT COUNT(*) FROM sessions"

# Vacuum and optimize
sqlite3 cda.db "VACUUM; ANALYZE;"
```

## Future Architecture

- **Streaming**: Real-time result streaming for large operations
- **Federation**: Connect to external nodes via PMF control plane
- **Reasoning UI**: Web UI panels showing AI cognitive quality trends per session
- **Caching**: Redis-backed query cache
- **Clustering**: Sharded databases for massive scale
- **ML Integration**: Anomaly detection daemon
