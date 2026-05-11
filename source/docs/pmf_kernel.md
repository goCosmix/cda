# PMF Ebbed Kernel

## Purpose

The PMF Ebbed Kernel is Ark's embedded process management framework. It sits between the application and the host environment and provides a local runtime kernel for Ark services.

It is intentionally:

- lightweight and local
- not a full federation control plane
- a reusable seed for future standalone apps
- a host-agnostic boundary for process lifecycle and health

## Architecture

The kernel consists of three layers:

1. **Kernel core**
   - Service registry
   - Lifecycle management
   - Runtime state persistence
   - Local event/bus surface

2. **Ark service definitions**
   - watcher daemon
   - web UI daemon
   - sync task
   - reconstruct task
   - embed-build task

3. **Host adapter**
   - local process management via subprocess
   - PID file and log file handling
   - runtime status detection
   - action invocation and task supervision

## Service contract

Each service is defined by:

- `service_id`
- `label`
- `service_type` (`daemon` or `task`)
- `description`
- `command`
- `cwd`
- `env`
- `pid_file` (for daemons)
- `log_file`
- allowed actions (`start`, `stop`, `restart`, `status`)

## Runtime state

Runtime state is stored in `pmf_runtime.json` at the project root and is intentionally ignored by source control.

Each service state contains:

- `service_id`
- `status`
- `pid`
- `exit_code`
- `started_at`
- `updated_at`
- `last_error`

## CLI integration

New `cda pmf` commands provide kernel control:

- `cda pmf services`
- `cda pmf status [service]`
- `cda pmf start <service>`
- `cda pmf stop <service>`
- `cda pmf restart <service>`
- `cda pmf logs <service>`

The `cda watch` and `cda ui` commands are now implemented through the PMF kernel.

## Web UI integration

The web UI can query the kernel for runtime service status and execute service actions through API endpoints.

Planned API surface:

- `/api/pmf/services`
- `/api/pmf/service?action=start|stop|restart&service=<id>`
- `/api/pmf/logs?service=<id>&tail=<n>`

## Future extension

The PMF Ebbed Kernel is designed to grow into a more general embedded app kernel.

Future work includes:

- adding a local bus for runtime events and alerts
- providing a plugin interface for additional app services
- supporting federation adapters that map local services into a broader control plane
- enabling standalone applications built on the same kernel contract
