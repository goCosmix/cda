# Architecture Guide

## System Overview

VS Code Ark is a multi-stage data pipeline that transforms raw VS Code storage data into actionable intelligence about user-AI interactions.

```
┌─────────────────────────────────────────────────────────────────┐
│                       VS Code Storage                            │
│  (workspaceStorage, globalStorage, transcripts, state files)    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
        ┌──────────────────────────┐
        │   INGEST STAGE           │
        │  (vscode_ark/ingest.py)   │
        │                          │
        │ - Parse storage files    │
        │ - Gzip compress blobs    │
        │ - Create session records │
        │ - Build VFS index        │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   SQLite Database   │
        │  (vscode-ark.db)    │
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
        │  (vscode_ark/reconstruct.py)
        │                          │
        │ - Parse exchanges        │
        │ - Link tool calls        │
        │ - Build threads          │
        │ - Create FTS index       │
        └──────────┬───────────────┘
                   │
        ┌──────────▼──────────┐
        │   EMBED STAGE        │
        │   (vscode_ark/embed.py)
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
        │   (vscode_ark/extract.py)
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
        │   LIVE MONITORING        │
        │   (vscode_ark/watcher.py) │
        │                          │
        │ - Watch file changes     │
        │ - Queue operations       │
        │ - Incremental updates    │
        │ - Maintain FTS index     │
        └──────────┬───────────────┘
                   │
                   ▼
        ┌──────────────────────────┐
        │   QUERY INTERFACE        │
        │   (cda CLI)              │
        │                          │
        │ - 25+ commands           │
        │ - Policy filtering       │
        │ - Rich output formatting │
        └──────────────────────────┘
```

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
1. Pattern match 200+ keywords against messages
2. Classify signals (correction, frustration, etc.)
3. Calculate heat score (weighted sum, 0-100)
4. Track token usage per request
5. Detect context compaction events
6. Aggregate per-session metrics
```

**Signals**: 6 types with 200+ keywords
**Heat Formula**: min(100, Σ(weight × count))

### Stage 4: Live Monitoring (watcher.py)

**Input**: File system events
**Output**: Queue of pending operations, database updates

```python
# Key operations
1. Monitor VS Code directories for changes
2. Queue operations before committing
3. Replay queue on restart (crash resilience)
4. Incremental database updates
5. Maintain FTS index
6. Track operation status
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

-- Behavioral Analysis
exchange_signals(
  session_id TEXT,
  exchange_index INTEGER,
  signal_type TEXT,  -- "correction", "frustration", etc.
  matched_keyword TEXT,
  user_message TEXT,
  ts TEXT
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
  analysis_date INTEGER
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
│   ├── code-search    # Symbol search
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
│   ├── watch          # Daemon control
│   │   ├── start
│   │   ├── stop
│   │   └── restart
│   ├── policy         # Access control
│   │   ├── allow
│   │   ├── deny
│   │   └── list
│   └── exchange       # View exchange detail
```

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

### Adding New Signal Types

1. Add keyword list to `SIGNAL_PATTERNS` in `extract.py`
2. Update `HEAT_WEIGHT` if needed
3. Re-run `extract.py`

### Custom Analysis

1. Query `session_analysis` or `exchange_signals` directly
2. Write analysis to results table
3. Export via `cda query` or `cda export`

### Policy Integration

1. Implement allow/deny patterns in `policy.txt`
2. System automatically filters search results
3. Extend `check_policy()` for custom logic

## Deployment Considerations

### Development
```bash
make install-dev
make test
make format
cda sync
```

### Production
```bash
pip install -e .
cda sync           # Initial setup
cda watch start    # Start monitoring
cda status         # Verify
```

### Monitoring
```bash
cda status         # Check daemon
cda stats          # System health
cda query "SELECT COUNT(*) FROM sessions"  # Activity
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
sqlite3 vscode-ark.db ".tables"
sqlite3 vscode-ark.db "SELECT COUNT(*) FROM sessions"

# Vacuum and optimize
sqlite3 vscode-ark.db "VACUUM; ANALYZE;"
```

## Future Architecture

- **Streaming**: Real-time result streaming for large operations
- **Federation**: Connect to external nodes via PMF
- **Caching**: Redis-backed query cache
- **Clustering**: Sharded databases for massive scale
- **ML Integration**: Anomaly detection daemon
