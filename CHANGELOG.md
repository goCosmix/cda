# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-05-09

### Added
- Initial release of VS Code Ark analysis system
- Complete data pipeline for VS Code/Copilot Chat session analysis
- Behavioral signal extraction with 200+ keywords across 6 signal types
- Heat score computation (0-100 scale) for frustration analysis
- Live monitoring daemon with crash-resistant file-based queue system
- Full-text search with FTS5 indexing
- Code symbol indexing and search capabilities
- Policy-based access control with allow/deny patterns
- Rich analytics including token usage, compaction events, and session recovery
- Export functionality in JSON, JSONL, and text formats
- Professional CLI with 25+ commands
- Comprehensive test suite
- GitHub Actions CI/CD pipeline
- Modern Python packaging with pyproject.toml
- Full documentation and README
- MIT License

### Features
- **ingest.py** - Data ingestion from VS Code storage with VFS compression
- **reconstruct.py** - Conversation reconstruction and FTS indexing
- **extract.py** - Behavioral signal extraction and heat scoring
- **watcher.py** - Live monitoring with incremental updates and queue resilience
- **cda** - Command-line interface with 25+ commands
- **Policy System** - Allow/deny pattern-based data filtering
- **Symbol Index** - Code symbol search (extensible to AST parsing)

### Infrastructure
- GitHub Actions CI/CD for Python 3.8-3.12
- Modern development tooling (black, isort, flake8, mypy, pytest)
- Makefile for common tasks
- Comprehensive documentation

---

## Unreleased

### Planned Features
- Streaming responses for long-running operations
- Federation context integration
- Session history and conversation search
- Message bookmarks and annotations
- Anomaly detection daemon
- Memory semantic search
- Agentic watches and monitoring
- Chart visualization artifacts
- Voice input support
- Multi-model support
- PMF bus publishing capabilities
