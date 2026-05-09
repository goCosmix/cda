# VS Code Ark

[![Python Version](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![CI](https://github.com/yourusername/vscode-ark/workflows/CI/badge.svg)](https://github.com/yourusername/vscode-ark/actions)

A comprehensive data pipeline and analysis system for VS Code/Copilot Chat sessions. Extract behavioral signals, compute heat scores, and gain deep insights into human-AI interaction patterns.

## ✨ Features

- **Behavioral Signal Analysis** - Extract 200+ keywords across 6 signal types (corrections, frustrations, affirmations, etc.)
- **Heat Score Computation** - Quantify user frustration and agent performance (0-100 scale)
- **Real-time Monitoring** - Live sync daemon with crash-resistant queue system
- **Full-text Search** - FTS5-powered search across all conversations
- **Semantic Intelligence** - miniLM embeddings, session summaries, related sessions, anomaly alerts, and recommendations
- **Code Symbol Indexing** - Search functions, classes, and symbols (extensible to AST parsing)
- **Package-centric Layout** - All runtime code lives under `vscode_ark/` for a clean root.
- **Policy-based Access Control** - Allow/deny patterns for data filtering
- **Rich Analytics** - Token usage, context compaction, session recovery analysis
- **Export Capabilities** - JSON, JSONL, and text export formats
- **Professional CLI** - Comprehensive command-line interface with 25+ commands

## 📋 Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [CLI Reference](#cli-reference)
- [Data Analysis](#data-analysis)
- [Configuration](#configuration)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🚀 Installation

### Prerequisites

- Python 3.8+
- VS Code with Copilot Chat extension

### From Source

```bash
git clone https://github.com/yourusername/vscode-ark.git
cd vscode-ark
pip install -e .
```

### With Development Dependencies

```bash
pip install -e ".[dev]"
```

### From PyPI (Future)

```bash
pip install vscode-ark
```

## ⚡ Quick Start

1. **Initialize the database:**
   ```bash
   cda sync
   ```

2. **Start live monitoring:**
   ```bash
   cda watch start
   ```

3. **Build semantic intelligence:**
   ```bash
   cda embed build
   ```

4. **Explore your data:**
   ```bash
   cda stats          # System overview
   cda sessions       # Recent sessions
   cda search "error" # Search conversations
   cda semantic-search "confused" # Semantic search
   cda heat           # Frustration analysis
   ```

## 🧠 SQLite limits and mitigation

- **Single writer in WAL mode**: the system uses one writer process for ingest/reconstruct/extract/embed and allows many concurrent readers via SQLite WAL.
- **Large VFS blob handling**: for very large raw artifacts, the clean approach is chunked storage or external file references instead of a single enormous BLOB.
- **Default 8KB page size / cache**: this code now sets `PRAGMA cache_size=-2000`, `PRAGMA mmap_size=268435456`, and `PRAGMA temp_store=MEMORY` to improve read/cache performance on larger databases.
- **Further tuning**: rebuild the DB with a larger page size (e.g. `PRAGMA page_size=32768`) if you need more efficient storage for very large session history.

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
| **ingest.py** | Data ingestion | VFS storage, gzip compression, session metadata |
| **reconstruct.py** | Conversation processing | Exchange threading, tool call linking, FTS indexing |
| **extract.py** | Signal analysis | Behavioral pattern recognition, heat scoring, token accounting |
| **watcher.py** | Live monitoring | File watching, incremental updates, crash recovery |
| **cda** | Query interface | 25+ commands, policy filtering, rich formatting |

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

# Session Analysis
cda sessions            # List all sessions (newest first)
cda session <id>        # Show detailed session information
cda workspace <id>      # Show sessions for a workspace
cda workspaces          # List all workspaces

# Search & Query
cda search <query>      # Full-text search across conversations
cda code-search <pattern> [--symbol]  # Search code symbols
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
```

### Command Examples

```bash
# Search for error handling discussions
cda search "error handling" --limit 20

# Find sessions with high frustration
cda heat --limit 10

# Search for specific functions in code
cda code-search "def process_data" --symbol

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

VS Code Ark automatically detects paths using standard locations:

- **macOS**: `~/Library/Application Support/Code/User/`
- **Windows**: `%APPDATA%\Code\User\`
- **Linux**: `~/.config/Code/User/`

### Environment Variables

```bash
export VSCODE_ARK_DB=/path/to/custom.db    # Custom database location
export VSCODE_ARK_CONFIG=/path/to/config   # Custom config directory
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
make install-dev
```

### Running Tests

```bash
make test              # Run test suite
make test-cov          # Run with coverage report
```

### Code Quality

```bash
make lint              # Run flake8 and mypy
make format            # Format with black and isort
```

### Building

```bash
make build             # Build distribution packages
make publish           # Publish to PyPI (requires credentials)
```

### Project Structure

```
vscode-ark/
├── vscode_ark/           # Main package
│   ├── __init__.py
│   └── cli.py           # Command-line interface
├── scripts/             # Utility scripts
│   ├── ingest.py        # Data ingestion
│   ├── reconstruct.py   # Conversation processing
│   ├── extract.py       # Signal analysis
│   └── watcher.py       # Live monitoring
├── tests/               # Test suite
├── docs/                # Documentation
├── pyproject.toml       # Package configuration
├── setup.py            # Legacy setup
├── Makefile            # Development tasks
└── README.md           # This file
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

- **Type Hints**: All functions should have type annotations
- **Docstrings**: Comprehensive docstrings for public APIs
- **Tests**: Unit tests for all new functionality
- **Linting**: Code must pass flake8 and mypy checks
- **Formatting**: Code must be formatted with black and isort

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Built for analyzing VS Code/Copilot Chat interaction patterns
- Inspired by the need for better human-AI interaction insights
- Uses SQLite FTS5 for high-performance full-text search
- Implements behavioral signal processing for conversation analysis

---

**VS Code Ark** - Understanding the human side of AI conversations.