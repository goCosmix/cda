# EAK Embedded Kernel

> Note: The original name for this layer was PMF. `cda pmf` commands and `PMFKernel` are
> backwards-compat aliases. The canonical name is EAK everywhere going forward.

## Purpose

The EAK (Embedded App Kernel) is Ark's local embedded runtime layer. It manages the lifecycle
of all Ark background services — watcher daemon, web UI, and pipeline tasks — as a self-contained
process kernel embedded in the package.

It is intentionally:

- lightweight and local
- not a full federation control plane
- a reusable seed for other goCosmix apps (shared via `kernel_core.py`)
- a host-agnostic boundary for process lifecycle and health

## Architecture

The kernel is split into two layers:

### 1. `kernel_core.py` — Shared Bottom Layer

Shared DNA across all goCosmix embedded kernels. Extracted to allow dev/other systems to reuse.

- Service registry and lifecycle management (start/stop/restart)
- PID file and log file tracking
- Runtime state persistence (`local/eak/runtime.json`)
- Event journal (`_emit_event`, stored in state)
- Run count tracking
- Task completion watcher thread (updates state to `completed`/`failed` when process exits)

### 2. `eak_kernel.py` — CDA-Specific Top Layer

Extends `KernelCore` with cda-specific service definitions and host integration.

**7 services:**

| Service | Type | Description |
|---------|------|-------------|
| `watcher` | daemon | Live VS Code data watcher and incremental ingest pipeline |
| `ui` | daemon | Background web UI server on port 10001 |
| `sync` | task | Full ingest pipeline run |
| `reconstruct` | task | Rebuild exchanges and FTS index |
| `embed-build` | task | Build semantic embeddings |
| `backfill` | task | Re-run extract + reasoning + embed over historical sessions |
| `symbol-index` | task | Build code symbol index |

**Host integration:**
- `up(host, port)` / `down()` — start/stop watcher + UI in order
- `generate_plist()` / `install_launchd()` / `uninstall_launchd()` — macOS LaunchAgent
- `open_browser_when_ready()` — waits for UI port then opens browser

### 3. `pmf_kernel.py` — Backwards-Compat Shim

35-line shim. `PMFKernel(EAKKernel)`, `PMFKernelError(EAKKernelError)`, all helper
functions re-exported from `eak_kernel`. Existing code using PMF names works unchanged.

## Service Contract

Each service is defined by a spec dict:

```python
{
    "service_id": "watcher",
    "label": "Watcher Daemon",
    "service_type": "daemon",       # or "task"
    "description": "Live VS Code data watcher",
    "command": [sys.executable, "-m", "cda.pipeline.watcher"],
    "cwd": str(CDA_HOME),
    "env": {},
    "pid_file": str(CDA_HOME / "watcher.pid"),   # daemons only
    "log_file": str(CDA_HOME / "logs/watcher.log"),
}
```

## Runtime State

State is persisted in `local/eak/runtime.json` (gitignored). Per-service state:

```json
{
  "status": "running",
  "pid": 12345,
  "exit_code": null,
  "started_at": "2026-05-12T10:00:00",
  "updated_at": "2026-05-12T10:00:01",
  "run_count": 3,
  "last_error": null
}
```

Task services update `status` to `"completed"` or `"failed"` automatically when the
subprocess exits (background completion thread in `kernel_core.py`).

## Health Monitoring (`alerting.py`)

`cda/pipeline/alerting.py` provides:

- `check_watcher_health()` — PID file present + `os.kill(pid, 0)` alive probe
- `check_queue_depth()` — counts `*.json` (pending) vs `*.completed` in QUEUE_DIR
  - WARN threshold: 50 pending
  - CRIT threshold: 200 pending
- `send_notification(title, message, subtitle)` — macOS osascript, silent on failure
- `run_health_check(notify=True)` — aggregates both, fires notifications for issues

Watcher calls `run_health_check()` every 300s automatically. `cda eak check` runs it on demand.

## CLI Integration

`cda eak` commands (canonical):

```bash
cda eak services           # List all services with status and PID
cda eak status [service]   # Show runtime status
cda eak start <service>    # Start a service
cda eak stop <service>     # Stop a service
cda eak restart <service>  # Restart a service
cda eak logs <service>     # Tail the service log
cda eak events             # Show kernel event journal
cda eak check              # Health check: watcher liveness + queue depth
cda eak up                 # Start watcher + UI (opens browser)
cda eak down               # Stop UI + watcher in order
cda eak install            # Register LaunchAgent
cda eak uninstall          # Remove LaunchAgent
```

`cda pmf <command>` — identical alias for all of the above.

## LaunchAgent

Installed at `~/Library/LaunchAgents/com.gocosmix.cda.plist`. Entry point:

```
cda eak up
```

Reinstall after any entry-point change: `cda eak uninstall && cda eak install`.

## Future Extension

- Local bus for runtime events and alerts
- Plugin interface for additional app services
- Federation adapters mapping local services to a broader control plane

