# Code Data Ark Roadmap

This roadmap captures the product direction for Code Data Ark, with a focus on delivering a polished local analytics platform for VS Code + Copilot Chat.

## Vision

Code Data Ark is the local observability and intelligence layer for Copilot Chat sessions. It should make session behavior easy to understand, surface friction, and provide rapid search and review for developers who want to improve AI-assisted workflows.

## Near-Term Priorities (2.0.x)

- Stabilize `cda` CLI and watcher daemon reliability across VS Code data path changes.
- Expand web UI session drilldown: richer alerts, recommendation panels, and tool-call inspection.
- Improve semantic search quality: better embedding workflows and topic clustering.
- Add documented export flows and onboarding guidance for first-time installs.
- Harden CI and development hygiene: control-plane vet checks, audit-engine integration.

## Mid-Term Initiatives (2.1.x)

- Streaming results for long-running queries and pipeline stages.
- Stronger anomaly detection and recovery analytics as first-class insights.
- Policy filtering and workspace-level access control improvements.
- Broader source support: extend beyond VS Code/Copilot Chat to other editor session logs.

## Long-Term Ambitions (3.0+)

- Federation and external-node integration for distributed analysis.
- PMF full control-plane interoperability: map local Ark services to federated node concepts.
- Polished project experience: onboarding wizard, interactive setup, and packaged distribution workflows.

## Recent progress

- `v0.1.0` delivered the core Code Data Ark pipeline: ingest, reconstruct, extract, watcher, CLI, search, export, packaging, and documentation.
- `v0.1.1` delivered the professional web UI session drawer, structured data panels, alert and tool-call tables, and complete package distribution of web UI assets.
- `v0.1.2` delivered release automation, version sync tooling, packaging metadata consolidation, and documentation cleanup.
- `v2.0.0` delivered the PMF Embedded Kernel for service lifecycle management, 3-layer repo structure (source/local/control), full package reorganization into pipeline/ui/kernel subpackages, and system-wide cleanup.

## PMF Embedded Kernel — Shipped in v2.0.0

The PMF Embedded Kernel is Ark's local embedded runtime layer. It is a lightweight, package-contained process management framework that provides:

- Local lifecycle control for watcher, web UI, ingest, reconstruction, and embedding workflows.
- Service health, PID/log management, and crash resilience.
- A UI-visible runtime dashboard, with manual start/stop/restart actions.
- A lightweight local bus surface for action and alert events.

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

- `v0.1.x`: Core pipeline, CLI, web UI, packaging, FTS search. ✓
- `v2.0.0`: PMF Embedded Kernel, 3-layer repo architecture (source/local/control), pipeline/ui/kernel subpackage split. ✓
- `v2.0.2`: Repo hygiene fixes, audit-engine integration, control-plane vet system. ✓
- `v2.1.0`: Enhanced semantic search, richer UI drilldown, broader analytics coverage.
- `v3.0.0`: Federation, stable API, polished distribution.

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
