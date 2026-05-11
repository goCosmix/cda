# control.db Schema Reference

SQLite database at `control/data/control.db`.
Journal mode: WAL. Foreign keys: declared but not enforced.

---

## identity

Key/value snapshot of the system's self-description. One row per key.
Written by `seed.py`. Overwritten on each seed run.

```sql
CREATE TABLE identity (
    id          INTEGER PRIMARY KEY,
    key         TEXT NOT NULL UNIQUE,
    value       TEXT,
    updated_at  TEXT NOT NULL       -- ISO 8601 UTC
);
```

### Keys Written by seed.py

| Key               | Example Value                                  |
|-------------------|------------------------------------------------|
| system_name       | vscode-ark                                     |
| acronym           | cda                                            |
| display_name      | VS Code Ark                                    |
| version           | 2.0.1                                          |
| language          | Python                                         |
| cli_name          | cda                                            |
| cli_bin           | ~/Library/Python/3.9/bin/cda                  |
| repo_root         | /Volumes/intel/systems/cda                     |
| source_dir        | /Volumes/intel/systems/cda/source              |
| local_dir         | /Volumes/intel/systems/cda/local               |
| local_data        | /Volumes/intel/systems/cda/local/data          |
| local_run         | /Volumes/intel/systems/cda/local/run           |
| local_queue       | /Volumes/intel/systems/cda/local/queue         |
| control_dir       | /Volumes/intel/systems/cda/control             |
| control_db        | /Volumes/intel/systems/cda/control/data/control.db |
| github_org        | goCosmix                                       |
| github_repo       | vscode-ark                                     |
| git_remote        | git@github.com:goCosmix/vscode-ark.git        |
| git_branch        | main                                           |
| git_commit        | cda7433...                                     |
| git_commit_short  | cda7433                                        |
| git_commit_date   | 2026-05-11T...                                 |
| python_runtime    | /Library/.../Python3.framework/.../python3.9  |
| install_path      | /Volumes/intel/systems/cda                     |
| license           | MIT                                            |
| author            | Ernie Butcher <ernie@fiosii.com>              |
| seeded_at         | 2026-05-11T19:32:39.238199+00:00               |

---

## manifest

File inventory of the repository. One row per file. Written by `seed.py`.
Overwritten on each seed run. Excludes `local/` and `.git/`.

```sql
CREATE TABLE manifest (
    id              INTEGER PRIMARY KEY,
    path            TEXT NOT NULL UNIQUE,   -- absolute path
    relative_path   TEXT NOT NULL,          -- relative to repo_root
    filename        TEXT NOT NULL,
    extension       TEXT,
    size_bytes      INTEGER,
    sha256          TEXT,
    is_gitignored   INTEGER NOT NULL DEFAULT 0,
    is_tracked      INTEGER NOT NULL DEFAULT 0,
    is_binary       INTEGER NOT NULL DEFAULT 0,
    file_type       TEXT,   -- source | test | docs | config | data | meta | script | other
    mtime           TEXT,   -- ISO 8601 UTC
    scanned_at      TEXT NOT NULL
);
```

---

## health

Timestamped record of every `cda check` run. One row per check per run.
All checks in a single `cda check` invocation share the same `run_at`.
Never truncated — full history is retained.

```sql
CREATE TABLE health (
    id          INTEGER PRIMARY KEY,
    run_at      TEXT NOT NULL,    -- ISO 8601 UTC — shared across one cda check run
    check_name  TEXT NOT NULL,    -- e.g. version, watcher_state, db_tables
    passed      INTEGER NOT NULL, -- 1 = pass, 0 = fail
    message     TEXT
);
```

### Useful Queries

```sql
-- Most recent full run
SELECT check_name, passed, message
FROM health
WHERE run_at = (SELECT MAX(run_at) FROM health)
ORDER BY id;

-- History of a specific check
SELECT run_at, passed, message FROM health
WHERE check_name = 'watcher_state'
ORDER BY run_at DESC LIMIT 20;

-- Failure rate per check
SELECT check_name,
       COUNT(*) as runs,
       SUM(CASE WHEN passed=0 THEN 1 ELSE 0 END) as failures
FROM health GROUP BY check_name ORDER BY failures DESC;
```

---

## runs

One row per `cda sync` pipeline execution.
A row is inserted at start, then updated on completion.

```sql
CREATE TABLE runs (
    id              INTEGER PRIMARY KEY,
    started_at      TEXT NOT NULL,          -- ISO 8601 UTC
    finished_at     TEXT,                   -- NULL while in progress
    trigger         TEXT NOT NULL DEFAULT 'manual',  -- manual | watcher | scheduled
    stages          TEXT,                   -- comma-separated: ingest,reconstruct,extract,embed
    sessions        INTEGER,
    exchanges       INTEGER,
    tool_calls      INTEGER,
    vfs_files       INTEGER,
    errors          INTEGER DEFAULT 0,
    exit_code       INTEGER,                -- 0 = success
    notes           TEXT                    -- error detail if failed
);
```

### Useful Queries

```sql
-- Last 5 runs
SELECT started_at, finished_at, stages, sessions, exchanges, exit_code
FROM runs ORDER BY id DESC LIMIT 5;

-- Average duration (seconds)
SELECT AVG(
    (julianday(finished_at) - julianday(started_at)) * 86400
) as avg_duration_secs
FROM runs WHERE finished_at IS NOT NULL;
```

---

## events

Append-only audit trail of significant system state changes.
Written by `cda sync`, watcher start/stop, version bumps, and any code
that calls `control_db.log_event()`.

```sql
CREATE TABLE events (
    id          INTEGER PRIMARY KEY,
    occurred_at TEXT NOT NULL,   -- ISO 8601 UTC
    kind        TEXT NOT NULL,   -- e.g. sync.complete, watcher.start, version.bump
    actor       TEXT,            -- e.g. cda, watcher
    subject     TEXT,            -- optional context (session_id, version string, etc.)
    detail      TEXT             -- free-form detail string
);
```

### Event Kinds

| Kind              | Written by            | Meaning                          |
|-------------------|-----------------------|----------------------------------|
| sync.complete     | `cda sync`            | Full pipeline run completed      |
| watcher.start     | `cda watch start`     | Watcher daemon started           |
| watcher.stop      | `cda watch stop`      | Watcher daemon stopped           |
| version.bump      | release tooling       | Version was incremented          |

### Useful Queries

```sql
-- All sync completions
SELECT occurred_at, detail FROM events
WHERE kind = 'sync.complete' ORDER BY id DESC LIMIT 10;

-- Full event timeline
SELECT occurred_at, kind, actor, subject, detail
FROM events ORDER BY id DESC LIMIT 50;
```
