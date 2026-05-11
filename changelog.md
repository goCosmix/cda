# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.0.5] - 2026-05-11

### Added
- **`cda setup`** — master onboarding command: init → pmf install → sync → up. Replaces the four-step manual process with a single command. Idempotent, safe to re-run. Accepts `--skip-sync` and `--no-browser`.
- **PMF-first architecture**: all background processes (watcher, web UI) start exclusively through the PMF kernel. `cda watch start` and `cda ui start` now display an advisory if the LaunchAgent is not installed.
- `_pmf_warn_if_not_installed()` helper — emitted before any background service start when the LaunchAgent plist is absent.

### Changed
- README quickstart simplified to two commands: `pip install code-data-ark` + `cda setup`
- Added PMF architecture diagram and process management reference to README

## [2.0.4] - 2026-05-11

### Added
- **`cda pmf install`** — generates and loads a macOS `~/Library/LaunchAgents/com.gocosmix.cda.plist`; CDA starts automatically on login
- **`cda pmf uninstall`** — unloads and removes the LaunchAgent plist
- **`cda pmf up`** — starts watcher + web UI in one command; opens browser when the server is ready; called by launchd on login
- **Browser auto-open**: `cda serve`, `cda ui start`, and `cda pmf start ui` now open a browser tab when the server is ready (`--no-browser` to disable)
- `cda.kernel.pmf_kernel`: `install_launchd()`, `uninstall_launchd()`, `generate_plist()`, `plist_path()`, `open_browser_when_ready()`, `wait_for_port_and_open_browser()`

## [2.0.3] - 2026-05-11

### Fixed
- **Install path resolution**: `LOCAL_DIR`/`DB_PATH` no longer derived from `__file__` — now resolves to `~/.cda/` (or `$CDA_HOME`). Survives `pip install` into site-packages.
- All pipeline stages (`ingest`, `reconstruct`, `extract`, `embed`, `watcher`, `parse_edits`) import canonical paths from new `cda.kernel.paths` module.
- `PMFKernel` and `selfcheck` updated to use `cda.kernel.paths`.
- All subprocess pipeline invocations switched from script file paths to `python -m cda.pipeline.<stage>` module calls.

### Added
- `cda.kernel.paths` — single source of truth for `CDA_HOME`, `DB_PATH`, `PID_FILE`, `QUEUE_DIR`, `POLICY_FILE`, `ensure_dirs()`.
- `cda init` command — first-run setup: creates `~/.cda/` directory tree, writes starter policy, validates VS Code data path.

### Changed
- README quickstart now reflects correct install flow: `pip install` → `cda init` → `cda sync` → `cda watch start` → `cda serve`.

## [2.0.2] - 2026-05-11

### Fixed
- `.gitignore`: add `.mypy_cache/` to ignore patterns (flagged by audit engine)

## [2.0.1] - 2026-05-11

### Changed
- **3-layer repo architecture**: repo root now has `source/` (tracked code), `local/` (runtime state), `control/` (management artifacts) — `local/` and `control/` are host-only and gitignored
- **Package reorganization**: `cda/` split into `pipeline/` (ingest, reconstruct, extract, embed, watcher, parse_edits), `ui/` (cli, web), `kernel/` (pmf_kernel, selfcheck) subpackages
- **Lowercase filenames**: all doc/meta filenames normalized to lowercase throughout `source/`
- `local/data/cda.db` is the canonical DB path; all module path depths updated
- Entry point updated: `cda.cli:main` → `cda.ui.cli:main`

### Fixed
- `release.py`: removed stale `SETUP_FILE` reference (setup.py was deleted); `sync_version` no longer fails on missing file
- `ci.yml`: added `working-directory: source` to all jobs so lint/test/build run from the correct root
- `pyproject.toml`: moved mypy options out of `[tool.flake8]` where they were silently ignored into `[tool.mypy]`
- `.gitignore`: replaced double-template bloat with a clean minimal project-specific ignore file
- Removed `pypi.py` from `cda/` package — dead code, not imported, belongs in the pypi system
- Fixed stale `DB_PATH` in `extract`, `embed`, `reconstruct`, `parse_edits` (were pointing to wrong directory)

## [2.0.0] - 2026-05-10

### Added
- **PMF Embedded App Kernel (PMF.EAK)**: Local process management framework for VS Code services
- Service lifecycle management (start, stop, restart) with PID and log tracking
- Runtime service registry with status persistence in `pmf_runtime.json`
- CLI commands for PMF service control (`cda pmf services`, `cda pmf start <service>`, etc.)
- Web API endpoints for runtime status and service actions (`/api/pmf/services`, `/api/pmf/service/<id>`)
- Web UI dashboard with service table, status indicators, and control buttons
- Service log tailing support for debugging and monitoring
- Automatic service state restoration on kernel restart

### Changed
- **Major Architecture Overhaul**: Ark runtime now uses embedded kernel instead of direct subprocess handling
- Refactored CLI and web UI to integrate with PMF.EAK kernel
- `cda watch` and `cda ui` commands now managed through kernel lifecycle
- Updated all documentation to reflect embedded kernel architecture

### Fixed
- Consolidated service management into single kernel interface
- Improved runtime reliability with persistent state tracking

## [0.1.2] - 2026-05-10

### Added
- Release automation with a version sync and tagging script
- `VERSION` tracking file as the single source of truth for package versioning
- `Makefile` release target for consistent build/publish workflow
- `MANIFEST.in` packaging updates to include docs and release metadata in the source distribution

### Changed
- Consolidated packaging configuration for PyPI release tracking
- Added version tracking and sync tooling across setup.py, pyproject.toml, and package runtime version

### Fixed
- Resolved package metadata drift between Git and PyPI releases

## [0.1.1] - 2026-05-10

### Added
- Professional session drawer UI with structured panels and tables
- Session metadata panel with clean data-row layout
- Improved session snapshot display using data panels instead of metric cards
- Signal summary table for better signal data presentation
- Chat message display with thread-based rendering
- Tool calls table with inline arguments display
- Alert and file listing tables with enhanced formatting
- Session-block styling for summary and turning-point text

### Changed
- Replaced all metric-card grids with structured session panels for drawer tabs
- Updated drawer tab content rendering for consistency and depth
- Improved data presentation with table-based layouts

### Fixed
- Package distribution now includes all web UI files and documentation
- Updated package metadata and MANIFEST.in for complete distribution

## [0.1.0] - 2026-05-09

### Added
- Initial release of Code Data Ark analysis system
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

### Fixed
- Watcher daemon startup issues with PYTHONPATH and working directory configuration
- Improved subprocess handling for proper daemon detachment

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
