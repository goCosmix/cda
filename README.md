# vscode-ark

A data pipeline for analyzing VS Code/Copilot Chat sessions, extracting behavioral signals, and computing session heat scores.

## Overview

vscode-ark processes VS Code/Copilot Chat session data to:
- Extract behavioral signals (corrections, frustrations, affirmations)
- Compute heat scores based on user-agent interaction patterns
- Provide rich querying and analysis capabilities
- Enable live monitoring of active sessions

## Installation

### From Source

```bash
git clone <repository-url>
cd vscode-ark
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

### From PyPI (when published)

```bash
pip install vscode-ark
```

## Architecture

```
VS Code Storage → ingest.py → vfs + sessions + transcripts
                      ↓
               reconstruct.py → exchanges (structured conversations)
                      ↓
               extract.py → signals + tokens + heat scores + analysis
                      ↓
               watcher.py → live sync + FTS indexing
                      ↓
               cda → query interface
```

## Dependencies

- `watchfiles>=0.20` - File system monitoring for live sync
- `click>=8.0` - CLI framework

## Usage

### Initial Setup

1. **Ingest VS Code data:**
   ```bash
   python ingest.py
   ```

2. **Reconstruct conversations:**
   ```bash
   python reconstruct.py
   ```

3. **Extract signals and analytics:**
   ```bash
   python extract.py
   ```

### Live Monitoring

Start the watcher daemon for real-time updates:
```bash
python watcher.py &
```

Stop the daemon:
```bash
python cda watch stop
```

### Querying Data

Use the `cda` CLI tool for analysis:

```bash
# Show system stats
cda stats

# Search conversations
cda search "error handling"

# Show session details
cda session <session_id>

# Analyze behavioral signals
cda signals

# Show heat scores
cda heat
```

## Data Flow

### ingest.py
- Extracts all VS Code storage artifacts
- Stores raw data in SQLite VFS (gzip-compressed)
- Creates session and workspace metadata

### reconstruct.py
- Processes transcript events into structured exchanges
- Links tool outputs to conversations
- Builds conversation threads

### extract.py
- Analyzes exchanges for behavioral signals
- Computes heat scores (0-100 scale)
- Extracts token usage and compaction events

### watcher.py
- Monitors VS Code directories for changes
- Updates database incrementally
- Maintains FTS search index

## Signal Classification

The system recognizes 6 signal types with 200+ keywords:

- **correction** (weight: 3) - User correcting agent behavior
- **pre_correction** (weight: 2) - Early signs of frustration
- **redirect** (weight: 1) - User changing direction
- **affirmation** (weight: 0) - Positive feedback
- **approval** (weight: 0) - Explicit task approval
- **frustration** (weight: 5) - Strong negative signals

## Heat Score Algorithm

Heat score = min(100, Σ(signal_weights))
- Tracks peak heat and recovery patterns
- Identifies "saved sessions" (heat recovery with affirmations)

## Database Schema

- **workspaces** - VS Code workspace metadata
- **sessions** - Chat session information
- **vfs** - Gzip-compressed file storage
- **exchanges** - Structured conversations
- **exchange_signals** - Behavioral signal annotations
- **token_usage** - Token accounting per request
- **compactions** - Context window summaries
- **session_analysis** - Per-session rollup metrics

## Configuration

Paths are automatically detected using `Path.home()`. The system expects VS Code data in:
- `~/Library/Application Support/Code/User/workspaceStorage/`
- `~/Library/Application Support/Code/User/globalStorage/`

## Troubleshooting

### Common Issues

1. **Missing dependencies:** Run `pip install -r requirements.txt`
2. **Permission errors:** Ensure access to VS Code storage directories
3. **Database locked:** Check for running watcher daemon
4. **FTS index issues:** Re-run `python reconstruct.py` to rebuild

### Logs

Check logs in the terminal output. The system uses Python logging with timestamps.

## Development

### Running Tests

```bash
python -m pytest tests/ -v
```

### Code Structure

- `ingest.py` - Data ingestion and VFS storage
- `reconstruct.py` - Conversation reconstruction
- `extract.py` - Signal extraction and analysis
- `watcher.py` - Live monitoring daemon
- `cda` - CLI query interface
- `audit.py` - Coverage analysis utilities

## Development

### Setup Development Environment

```bash
make install-dev
```

### Run Tests

```bash
make test
# or with coverage
make test-cov
```

### Code Quality

```bash
make lint    # Run flake8 and mypy
make format  # Format with black and isort
```

### Build and Publish

```bash
make build
make publish  # Requires PyPI credentials
```

## License

This is internal tooling for VS Code/Copilot analysis.