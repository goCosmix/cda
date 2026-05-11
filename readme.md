# Code Data Ark

[![Python Version](https://img.shields.io/badge/python-3.9%2B-blue.svg)](https://www.python.org/downloads/)
[![PyPI](https://img.shields.io/pypi/v/code-data-ark.svg)](https://pypi.org/project/code-data-ark)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Code Data Ark** (`cda`) is a local observability and intelligence platform for VS Code + GitHub Copilot Chat sessions. It ingests everything VS Code writes to disk — transcripts, tool calls, VFS blobs, workspace state — and runs a multi-stage pipeline to turn that raw activity into structured data you can actually reason about.

The core insight is that your chat history is not just logs. It carries behavioral signals: moments you corrected the agent, redirected it, expressed frustration, or confirmed that something finally worked. Ark extracts those signals, scores session quality with a heat model, and surfaces the patterns — so you can understand how you work with AI, not just what was said.

On top of that signal layer, Ark builds a semantic intelligence layer: embeddings over all your sessions, full-text and code-symbol search, anomaly alerts, session summaries, and related-session discovery. All of this lives in a local SQLite database, queryable via a 40+ command CLI or a background web dashboard.

The runtime is managed by an embedded process kernel (PMF) that supervises the watcher daemon, web UI, and pipeline tasks as background services — giving the whole system a lifecycle you can control without touching a process manager.

**In short**: point it at your VS Code data directory, run `cda sync`, and you have a searchable, annotated, semantically indexed record of every Copilot session you've ever had — with behavioral scores and anomaly detection included.

## ✨ Key Capabilities

- **Multi-stage pipeline**: ingest → reconstruct → extract → embed — each stage enriches the data further
- **Behavioral signal detection**: 200+ keyword patterns across 6 signal types; frustration, correction, recovery
- **Heat scoring**: weighted session quality score (0–100) that tracks arc from friction to resolution
- **Semantic search**: miniLM embeddings over all sessions for similarity, related-session discovery, and topic clustering
- **Full-text search**: FTS5 index over all exchanges, tool calls, and code symbols
- **Live watcher daemon**: monitors VS Code directories, queues changes, replays on crash
- **Background web UI**: session drilldown, signal summaries, alert views, tool-call detail, VFS inspection
- **PMF Embedded Kernel**: local service lifecycle management — start, stop, restart, status for all Ark daemons
- **Export workflows**: JSON, JSONL, and plain-text session export

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Web UI](#web-ui)
- [CLI Reference](#cli-reference)
- [Architecture](#architecture)
- [Roadmap](#roadmap)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🚀 Installation

### Prerequisites

- Python 3.8+
- VS Code with the Copilot Chat extension installed

### Install from PyPI

```bash
pip install code-data-ark
```

> **macOS / system Python note**: pip installs the `cda` binary to `~/Library/Python/3.x/bin/` which is not on `PATH` by default. Use the fallback below — `cda setup` will fix PATH for you automatically:
>
> ```bash
> python3 -m cda setup
> ```

### Install with pipx

```bash
pipx install code-data-ark
# pipx automatically manages PATH — `cda setup` works immediately
```

### Install from source

```bash
git clone https://github.com/goCosmix/cda.git
cd cda/source
pip install -e .
```

### Install development dependencies

```bash
pip install -e ".[dev]"
# or
make install-dev
```

> The `cda` console command is installed into your Python environment's `bin` directory. If it isn't on PATH yet, use `python3 -m cda setup` — setup patches `~/.zprofile` automatically.

## ⚡ Quick Start

```bash
pip install code-data-ark
python3 -m cda setup   # use this if `cda` isn't on PATH yet
```

After the first run, `cda setup` patches `~/.zprofile` so `cda` is on PATH in every new terminal.

`cda setup` runs four steps in sequence:

| Step | What it does |
|------|-------------|
| **1. Init** | Creates `~/Library/goCosmix/apps/code-data-ark/` — all app data in one organized namespace. Also patches `~/.zprofile` if `cda` isn't on PATH yet. |
| **2. PMF install** | Registers a macOS LaunchAgent — CDA starts automatically on every login via `cda pmf up` |
| **3. Sync** | Ingests all VS Code + Copilot session data into `cda.db` |
| **4. Up** | Starts the watcher daemon and web UI via the PMF kernel, opens browser |

All data lives in `~/Library/goCosmix/apps/code-data-ark/`. After setup, everything is managed by the **PMF kernel** — no terminal interaction required.

### Options

```bash
cda setup --skip-sync     # Skip initial ingest (run `cda sync` manually later)
cda setup --no-browser    # Don't open browser when the UI starts
```

### After setup

```bash
cda check           # Full system health diagnostic
cda sync            # Re-ingest after significant new session activity
cda pmf services    # View all running services and their status
cda pmf uninstall   # Remove the auto-start LaunchAgent registration
```

## 🔧 Process Management (PMF)

All background processes run through the embedded PMF kernel. The LaunchAgent is the entry point — nothing starts directly on the host outside of PMF.

```
launchd (login)
  └─ cda pmf up
       ├─ PMF kernel → watcher daemon   (cda.pipeline.watcher)
       └─ PMF kernel → web UI server    (cda.ui.web)
```

### PMF commands

```bash
cda pmf services           # List all services with status and PID
cda pmf start <service>    # Start a service (watcher, ui, sync, reconstruct, embed-build)
cda pmf stop <service>     # Stop a service
cda pmf restart <service>  # Restart a service
cda pmf logs <service>     # Tail the service log
cda pmf up                 # Start watcher + UI (opens browser) — same as launchd trigger
cda pmf install            # Register LaunchAgent (done automatically by cda setup)
cda pmf uninstall          # Remove LaunchAgent
```

## 🌐 Web UI

- **Background service** (default after setup): managed by PMF, starts on login
- **Foreground mode**: `cda serve` — runs in the terminal, opens browser, Ctrl+C to stop
- **Access**: `http://127.0.0.1:10001`

The web UI includes:

- Session drilldown panels and charts
- Behavioral signal summaries
- Alert and recommendation views
- Searchable transcript and tool-call detail
- File/VFS browsing and raw session inspection

## 🧠 Core Features

- Behavioral signals with 200+ keyword patterns across six categories
- Frustration heat scoring and recovery analytics
- Full-text search and semantic search with embeddings
- Code symbol indexing for Python/JS/TS
- Incremental ingestion with crash-resilient queue replay
- Export workflows for JSON, JSONL, and text

## 📦 Package and Release

- Published on PyPI as `code-data-ark`
- Current release version: `2.0.2`
- CLI entry point: `cda`
- License: MIT

## 🛣 Roadmap

See `docs/roadmap.md` for product direction, milestone planning, and release priorities.

## 🤝 Contributing

See `contributing.md` for development setup, test guidance, and PR workflow.

## 📜 License

This project is licensed under the MIT License.

## 🧠 SQLite limits and mitigation

- **Single writer in WAL mode**: the system uses one writer process for ingest/reconstruct/extract/embed and allows many concurrent readers via SQLite WAL.
- **Large VFS blob handling**: for very large raw artifacts, the clean approach is chunked storage or external file references instead of a single enormous BLOB.
- **Default 8KB page size / cache**: this code now sets `PRAGMA cache_size=-2000`, `PRAGMA mmap_size=268435456`, and `PRAGMA temp_store=MEMORY` to improve read/cache performance on larger databases.
- **Further tuning**: rebuild the DB with a larger page size (e.g. `PRAGMA page_size=32768`) if you need more efficient storage for very large session history.

## 🔧 Configuration

- **VS Code Data Directory**: By default, assumes macOS paths (`~/Library/Application Support/Code/User`). Override with `export VSCODE_DATA_DIR=/path/to/vscode/data` (e.g., on Linux: `~/.config/Code/User`).
- **No other config needed**: Everything is CLI-driven with local SQLite.

## 🏗️ Architecture

```
VS Code Storage → ingest.py → vfs + sessions + transcripts
                      ↓
               reconstruct.py → exchanges (structured conversations)
                      ↓
               extract.py → signals + tokens + heat scores + analysis
                      ↓
               embed.py → semantic embeddings + summaries + alerts
                      ↓
               watcher.py → live sync + FTS indexing + queue resilience
                      ↓
               cda → query interface + policy enforcement
```

### Core Components

| Component | Purpose | Key Features |
|-----------|---------|--------------|
| **pipeline/ingest.py** | Data ingestion | VFS storage, gzip compression, session metadata |
| **pipeline/reconstruct.py** | Conversation processing | Exchange threading, tool call linking, FTS indexing |
| **pipeline/extract.py** | Signal analysis | Behavioral pattern recognition, heat scoring, token accounting |
| **pipeline/watcher.py** | Live monitoring | File watching, incremental updates, crash recovery |
| **pipeline/embed.py** | Semantic intelligence | Embeddings, session summaries, anomaly alerts |
| **kernel/pmf_kernel.py** | Service management | Daemon lifecycle, PID/log tracking, runtime state |
| **kernel/selfcheck.py** | System diagnostics | Health checks, install validation, DB integrity |
| **ui/cli.py** | CLI entry point | 40+ commands, policy filtering, rich formatting |
| **ui/web.py** | Web dashboard | Browser UI for all CLI features, service control |

### Database Schema

- **workspaces** - VS Code workspace metadata
- **sessions** - Chat session information and metadata
- **vfs** - Gzip-compressed file storage with SHA256 hashes
- **exchanges** - Structured conversation turns with tool calls
- **exchange_signals** - Behavioral signal annotations
- **symbols** - Code symbol index (functions, classes, etc.)
- **token_usage** - Per-request token consumption tracking
- **compactions** - Context window summarization events
- **session_analysis** - Aggregated session metrics and heat scores

## 🖥️ CLI Reference

### Core Commands

```bash
# System Management
cda status              # Show daemon status and queue information
cda stats               # System-wide statistics and coverage
cda sync                # Full data ingestion and rebuild
cda reconstruct         # Rebuild conversations and search index
cda pmf services        # List embedded PMF runtime services
cda pmf status [service] # Show runtime status for PMF services
cda pmf start <service>  # Start a PMF-managed Ark service
cda pmf stop <service>   # Stop a PMF-managed Ark service
cda pmf restart <service> # Restart a PMF-managed Ark service
cda pmf logs <service>   # Tail runtime logs for a PMF service

# Session Analysis
cda sessions            # List all sessions (newest first)
cda session <id>        # Show detailed session information
cda workspace <id>      # Show sessions for a workspace
cda workspaces          # List all workspaces

# Search & Query
cda search <query>      # Full-text search across conversations
cda code-search <pattern> [--symbol] [--regex]  # Search code symbols or code content
cda semantic-search <query> # Semantic search using embeddings
cda similar <session>     # Find sessions similar to a session
cda related <session>     # Alias for semantic related sessions
cda summarize <session>   # Show session summary, topics, and recommendations
cda topics                # List semantic topic tags
cda alerts <session>      # Show semantic anomaly alerts
cda recommend <session>   # Show session recommendations
cda tools <query>       # Search tool call arguments
cda memory              # Show memory files and global state

# Behavioral Analysis
cda signals [session]   # Show behavioral signals
cda heat [session]      # Frustration and heat analysis
cda behavior            # Aggregate behavioral intelligence
cda saved               # Sessions that recovered from high heat

# Data Export
cda export <session>    # Export session as JSON/JSONL/text
cda replay <session>    # Print conversation as readable text

# Advanced
cda query <sql>         # Execute raw SQL queries
cda tokens [session]    # Token usage analysis
cda compactions [session] # Context compaction events
cda edits               # Edit session analytics

# Policy Management
cda policy allow <pattern>   # Add allow pattern
cda policy deny <pattern>    # Add deny pattern
cda policy list              # Show current policies

# Live Monitoring
cda watch start             # Start watcher daemon
cda watch stop              # Stop watcher daemon
cda watch restart           # Restart watcher daemon
cda ui start                # Start web UI background service
cda ui stop                 # Stop web UI background service
cda ui status               # Show web UI background service status
```

### Command Examples

```bash
# Search for error handling discussions
cda search "error handling" --limit 20

# Find sessions with high frustration
cda heat --limit 10

# Search for specific functions in code
cda code-search "def process_data" --symbol

# Search code content with regex or plain text
cda code-search "timeout" --regex

# Find semantically related sessions
cda related abc123

# Summarize a session with semantic topics and recommendations
cda summarize abc123

# Export a session for external analysis
cda export abc123 --format jsonl --output session.jsonl

# Monitor live sessions
cda watch start
cda status  # Check queue status
```

## 📊 Data Analysis

### Behavioral Signals

The system recognizes 6 signal types with 200+ keyword patterns:

| Signal Type | Weight | Description | Example Keywords |
|-------------|--------|-------------|------------------|
| **correction** | 3 | User correcting agent behavior | "stop", "wrong", "nope", "wait" |
| **pre_correction** | 2 | Early frustration signs | "actually", "hold on", "slow down" |
| **redirect** | 1 | User changing direction | "pivot", "change direction", "instead" |
| **affirmation** | 0 | Positive feedback | "good", "right", "perfect", "thanks" |
| **approval** | 0 | Task completion approval | "that works", "looks good", "approved" |
| **frustration** | 5 | Strong negative signals | "this is broken", "not working", "terrible" |

### Heat Score Algorithm

```
Heat Score = min(100, Σ(signal_weights))
```

- **Peak Heat**: Maximum heat reached in session
- **Final Heat**: Heat at session end
- **Recovery**: Sessions that return to low heat after high peaks
- **Saved Sessions**: High-heat sessions that recover with affirmations

### Token Usage Tracking

- Per-request token consumption (prompt + completion)
- Model identification and version tracking
- Context compaction event logging
- Cost estimation capabilities

## ⚙️ Configuration

### Automatic Detection

Code Data Ark automatically detects paths using standard locations:

- **macOS**: `~/Library/Application Support/Code/User/`
- **Windows**: `%APPDATA%\Code\User\`
- **Linux**: `~/.config/Code/User/`

### Environment Variables

```bash
export CDA_DB=/path/to/custom.db          # Custom database location
export CDA_CONFIG=/path/to/config         # Custom config directory
```

### Policy Configuration

Data access policies are stored in `policy.txt`:

```
ALLOW important-project
DENY sensitive-data
ALLOW *.py
```

## 🔧 Development

### Setup Development Environment

```bash
pip install -e ".[dev]"
```

### Running Tests

```bash
pytest tests/ -q
```

### Code Quality

```bash
flake8 cda tests
mypy cda
```

### Building

```bash
python -m build
```

### Project Structure

```
cda/
├── .gitignore
├── source/                  # all tracked code (pushed to git)
│   ├── cda/
│   │   ├── pipeline/        # ingest, reconstruct, extract, embed, watcher, parse_edits
│   │   ├── ui/              # cli, web
│   │   └── kernel/          # pmf_kernel, selfcheck
│   ├── bin/release.py
│   ├── tests/
│   ├── docs/
│   └── pyproject.toml
├── local/               # runtime state (gitignored, host-only)
│   ├── data/            # cda.db
│   ├── logs/
│   ├── queue/
│   ├── run/
│   ├── config/
│   └── pmf/
└── control/             # management artifacts (gitignored, host-only)
    ├── data/            # control.db
    ├── scripts/
    ├── audit/
    └── scan/
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Run the test suite: `make test`
5. Format code: `make format`
6. Commit your changes: `git commit -m 'Add amazing feature'`
7. Push to the branch: `git push origin feature/amazing-feature`
8. Open a Pull Request

### Development Guidelines

- **Tests**: Unit tests for all new functionality
- **Linting**: Code must pass `flake8` and `mypy` before pushing
- **Versioning**: Keep `version`, `pyproject.toml`, and `changelog.md` in sync

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for analyzing VS Code/Copilot Chat interaction patterns
- Inspired by the need for better human-AI interaction insights
- Uses SQLite FTS5 for high-performance full-text search
- Implements behavioral signal processing for conversation analysis

---

**Code Data Ark** (`cda`) - Understanding the human side of AI conversations.