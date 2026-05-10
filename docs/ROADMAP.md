# VS Code Ark Roadmap

This roadmap captures the product direction for VS Code Ark, with a focus on delivering a polished local analytics platform for VS Code + Copilot Chat.

## Vision

VS Code Ark is the local observability and intelligence layer for Copilot Chat sessions. It should make session behavior easy to understand, surface friction, and provide rapid search and review for developers who want to improve AI-assisted workflows.

## Near-Term Priorities (0.1.x)

- Publish and stabilize the PyPI package as `vscode-ark`.
- Harden `cda` CLI workflows: install, sync, watch, embed, and UI lifecycle commands.
- Ship the background web UI service (`cda ui start/stop/status`) and foreground dashboard (`cda serve`).
- Clean up documentation and install instructions across `README.md`, `CONTRIBUTING.md`, and `docs/ARCHITECTURE.md`.
- Ensure the watcher daemon and ingest pipeline work reliably on supported VS Code data paths.
- Validate packaging metadata and version consistency in `pyproject.toml` and `setup.py`.

## Mid-Term Initiatives (0.2.x)

- Expand behavioral signal coverage and heat scoring accuracy.
- Improve semantic search and related-session discovery with better embedding workflows.
- Add richer session drilldown in the web UI: alerts, recommendations, tool-call views, and code/VFS inspection.
- Add documented export flows for JSON, JSONL, and text outputs.
- Strengthen development hygiene with tests, linting, formatting, and CI-focused docs.
- Add policy filtering and access control guidance for workspace-level data selection.
- Build the PMF Ebbed Kernel as an embedded runtime manager for Ark services, with UI monitoring and local service control.

## Long-Term Ambitions (1.0+)

- Support larger scale and advanced query performance through caching, optimized indices, and streaming results.
- Add federation and external-node integration for distributed analysis.
- Deliver anomaly detection and recovery analytics as first-class insights.
- Expand source support beyond VS Code/Copilot Chat to a broader set of editor/session logs.
- Build a polished project experience: onboarding docs, release notes, and packaged CLI workflows.

## Recent progress

- `v0.1.0` delivered the core VS Code Ark pipeline: ingest, reconstruct, extract, watcher, CLI, search, export, packaging, and documentation.
- `v0.1.1` delivered the professional web UI session drawer, structured data panels, alert and tool-call tables, and complete package distribution of web UI assets.
- `v0.1.2` delivered release automation, version sync tooling, packaging metadata consolidation, and documentation cleanup.

## PMF Ebbed Kernel — Local Runtime Plan

The PMF Ebbed Kernel is the planned embedded runtime layer for Ark. It is a lightweight, package-contained process management framework and monitoring surface that enables:

- Local lifecycle control for watcher, web UI, ingest, reconstruction, and embedding workflows.
- Service health, PID/log management, and crash resilience.
- A UI-visible runtime dashboard, with manual start/stop/restart actions.
- A lightweight local bus surface for action and alert events.

This is intentionally not the full PMF federation control plane; it is an embedded Ark runtime that can later be mapped into federation concepts when the project grows.

## Transferred backlog from changelog

The following items were still listed as `Unreleased` in `CHANGELOG.md` and have now been captured in the roadmap as future work:

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

## Milestones

- `v0.1.2`: Documented install, CLI, and web UI service parity.
- `v0.2.0`: Enhanced semantic search, better UX, and broader analytics coverage.
- `v1.0.0`: Stable release with polished dashboards, scalable ingestion, and strong local observability.

## Metrics for Success

- `cda` commands work consistently on a fresh environment.
- Web UI service can be started/stopped reliably from the CLI.
- Session and search workflows return useful results for real VS Code Copilot Chat data.
- Documentation is complete enough for a user to install, configure, and explore without guessing.
- Packaging is aligned and deployable to PyPI.

## How to use this roadmap

- Keep this file updated as priorities shift.
- Use it as a planning guide for doc cleanups, release notes, and feature gating.
- Link backlog items and issue work to the milestone headings above.
