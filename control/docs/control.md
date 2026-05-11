# vscode-ark Control System

The `control/` layer is the management plane for the vscode-ark (cda) system.
It is separate from the operational data (`local/`) and source code (`source/`),
and is intentionally host-bound — it is gitignored except for `control/scripts/`.

---

## Directory Layout

```
control/
  data/
    control.db          SQLite — identity, manifest, health, runs, events
    control.db-shm
    control.db-wal
  scripts/
    seed.py             Initialise / refresh the control DB (tracked in git)
  audit/
    *.json              Output from `audit` engine runs
  scan/
    vscode-locations.json   VS Code storage paths discovered at scan time
    vscode-map.json         Workspace + session topology map
  docs/
    CONTROL.md          This file
    SCHEMA.md           control.db table schemas
    RUNBOOK.md          Operator runbook — seeding, querying, troubleshooting
```

---

## What the Control System Tracks

| Table      | Purpose                                                       |
|------------|---------------------------------------------------------------|
| `identity` | System snapshot — version, paths, git state, runtime         |
| `manifest` | File inventory — every file in the repo, git & hash status   |
| `health`   | Timestamped log of every `cda check` run (per-check results) |
| `runs`     | Log of every `cda sync` pipeline execution with counts       |
| `events`   | Append-only audit trail of significant system state changes  |

---

## CLI Interface

```
cda control status          Show identity snapshot (who/what/where)
cda control health          Recent selfcheck history (last 14 runs)
cda control health --check watcher_state
                            Filter to a specific check
cda control runs            Recent sync pipeline runs (last 10)
cda control events          System event log (last 20)
cda control events --kind sync.complete
                            Filter by event kind
```

---

## Auto-Writes

The control DB is written automatically by two commands — both silently skip
if `control.db` doesn't exist (so control is always optional):

- **`cda check`** → writes one row per check to `health` (with shared `run_at` timestamp)
- **`cda sync`** → creates a `runs` row on start, updates it with counts on completion;
  appends a `sync.complete` event to `events`

---

## Seeding / Refreshing

Re-seed whenever any of the following change:
- Version bump
- Git push (commit / branch)
- Layout changes (new paths, new layers)

```bash
cd /Volumes/intel/systems/cda
python control/scripts/seed.py
```

The seed script is idempotent (`INSERT OR REPLACE`) and safe to re-run at any time.
It refreshes `identity` and `manifest` and creates the `health`, `runs`, `events`
tables if they don't exist (it does **not** clear historical data).

---

## Design Principles

1. **Optional** — nothing in the main pipeline depends on control.db. All writes
   are silent no-ops if the DB is absent.
2. **Append-only history** — `health`, `runs`, `events` are never truncated by
   the seed script. Full history is preserved.
3. **Host-bound** — `control/data/` is gitignored. The DB lives only on the
   machine where cda is installed.
4. **No foreign keys enforced** — tables are independent. Query them freely
   with `cda query` or any SQLite client.
