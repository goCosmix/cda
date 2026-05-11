"""
cda selfcheck — the system knows itself.

Checks:
  version         — VERSION file exists, valid semver, matches __version__
  install_path    — editable install of cda resolves to this project dir
  db_present      — local/data/vscode-ark.db exists on disk
  db_accessible   — DB opens and WAL mode is confirmed
  db_integrity    — PRAGMA integrity_check passes
  db_tables       — all expected tables are present
  db_counts       — core tables have rows (non-empty)
  db_wal          — no abandoned WAL/SHM files blocking writes
  watcher_state   — watcher.pid present and process is alive (or cleanly absent)
  queue_depth     — local/queue/ exists and reports pending file count
  data_gitignored — local/ is gitignored in git
  cli_path        — this binary is on PATH and resolves correctly
  python_runtime  — running on expected Python (3.9, not Homebrew 3.14+)
  dependencies    — all required imports load without error
"""

import importlib
import os
import shutil
import signal
import sqlite3
import subprocess
import sys
from pathlib import Path

# ── paths the system knows about itself ─────────────────────────────────────
PACKAGE_DIR  = Path(__file__).resolve().parent
SOURCE_DIR   = PACKAGE_DIR.parent.parent          # source/  — tracked repo root
PROJECT_DIR  = PACKAGE_DIR.parent.parent.parent   # repo root — where layers live
LOCAL_DIR    = PROJECT_DIR / "local"
DB_PATH      = LOCAL_DIR / "data" / "vscode-ark.db"
PID_FILE     = LOCAL_DIR / "run" / "watcher.pid"
QUEUE_DIR    = LOCAL_DIR / "queue"
VERSION_FILE = SOURCE_DIR / "version"

REQUIRED_TABLES = [
    "sessions", "exchanges", "tool_calls", "vfs", "workspaces",
    "memory_files", "embeddings", "exchange_signals", "ingest_log",
    "transcript_events", "token_usage", "compactions",
    "session_analysis", "session_summaries",
    "recommendations", "anomaly_alerts", "symbols", "file_offsets",
    "state_items", "chat_messages",
]

CORE_COUNT_TABLES = ["sessions", "exchanges", "tool_calls", "vfs"]

REQUIRED_IMPORTS = [
    "click", "sqlite3", "watchfiles", "pathlib", "json", "gzip",
]


# ── result helpers ────────────────────────────────────────────────────────────

def _ok(name, message, details=None):
    r = {"name": name, "passed": True, "message": message}
    if details:
        r["details"] = details
    return r

def _fail(name, message, details=None):
    r = {"name": name, "passed": False, "message": message}
    if details:
        r["details"] = details
    return r


# ── individual checks ─────────────────────────────────────────────────────────

def check_version():
    import re
    if not VERSION_FILE.exists():
        return _fail("version", "VERSION file not found")
    version = VERSION_FILE.read_text().strip()
    if not re.fullmatch(r"\d+\.\d+\.\d+", version):
        return _fail("version", f"VERSION is not valid semver: {version!r}")
    try:
        from cda import __version__
        if __version__ != version:
            return _fail("version",
                f"VERSION file ({version}) does not match __version__ ({__version__})")
    except (ImportError, AttributeError):
        pass  # __version__ not defined — just check the file
    return _ok("version", f"VERSION is valid semver: {version}")


def check_install_path():
    try:
        result = subprocess.run(
            [sys.executable, "-c",
             "import cda, pathlib; "
             "print(pathlib.Path(cda.__file__).parent.parent.resolve())"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            return _fail("install_path", "cda not importable — editable install broken")
        install_dir = Path(result.stdout.strip()).resolve()
        if install_dir == SOURCE_DIR:
            return _ok("install_path", f"editable install → {install_dir}")
        return _fail("install_path",
            f"editable install points to wrong path: {install_dir} (expected {SOURCE_DIR})")
    except Exception as exc:
        return _fail("install_path", f"install_path check error: {exc}")


def check_db_present():
    if not DB_PATH.exists():
        return _fail("db_present", f"vscode-ark.db not found at {DB_PATH}")
    size_mb = DB_PATH.stat().st_size / (1024 * 1024)
    return _ok("db_present", f"vscode-ark.db present ({size_mb:.0f} MB)")


def check_db_accessible():
    if not DB_PATH.exists():
        return _fail("db_accessible", "vscode-ark.db not found — skipping")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        row = conn.execute("PRAGMA journal_mode").fetchone()
        conn.close()
        mode = row[0] if row else "unknown"
        if mode != "wal":
            return _fail("db_accessible", f"DB is accessible but journal_mode={mode} (expected wal)")
        return _ok("db_accessible", f"DB accessible, journal_mode=wal")
    except sqlite3.DatabaseError as exc:
        return _fail("db_accessible", f"DB is corrupt or unreadable: {exc}")


def check_db_integrity():
    if not DB_PATH.exists():
        return _fail("db_integrity", "vscode-ark.db not found — skipping")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=10)
        row = conn.execute("PRAGMA integrity_check(1)").fetchone()
        conn.close()
        result = row[0] if row else "unknown"
        if result == "ok":
            return _ok("db_integrity", "PRAGMA integrity_check: ok")
        return _fail("db_integrity", f"PRAGMA integrity_check: {result}")
    except sqlite3.DatabaseError as exc:
        return _fail("db_integrity", f"integrity_check failed: {exc}")


def check_db_tables():
    if not DB_PATH.exists():
        return _fail("db_tables", "vscode-ark.db not found — skipping")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        present = {r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        missing = [t for t in REQUIRED_TABLES if t not in present]
        if missing:
            return _fail("db_tables", f"Missing tables: {', '.join(missing)}")
        return _ok("db_tables", f"All {len(REQUIRED_TABLES)} expected tables present")
    except sqlite3.DatabaseError as exc:
        return _fail("db_tables", f"Table check failed: {exc}")


def check_db_counts():
    if not DB_PATH.exists():
        return _fail("db_counts", "vscode-ark.db not found — skipping")
    try:
        conn = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True, timeout=5)
        counts = {}
        for t in CORE_COUNT_TABLES:
            row = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()
            counts[t] = row[0] if row else 0
        conn.close()
        empty = [t for t, c in counts.items() if c == 0]
        summary = ", ".join(f"{t}={c:,}" for t, c in counts.items())
        if empty:
            return _fail("db_counts", f"Empty core tables: {', '.join(empty)}", summary)
        return _ok("db_counts", f"Core table counts: {summary}")
    except sqlite3.DatabaseError as exc:
        return _fail("db_counts", f"Count check failed: {exc}")


def check_db_wal():
    wal = DB_PATH.with_suffix(".db-wal")
    shm = DB_PATH.with_suffix(".db-shm")
    issues = []
    if wal.exists():
        size_kb = wal.stat().st_size // 1024
        if size_kb > 100 * 1024:  # > 100MB WAL may indicate abandoned writer
            # Only flag as bad if the watcher is NOT running (active writer is fine)
            watcher_active = False
            if PID_FILE.exists():
                try:
                    os.kill(int(PID_FILE.read_text().strip()), 0)
                    watcher_active = True
                except (ProcessLookupError, ValueError, OSError):
                    pass
            if not watcher_active:
                issues.append(f"WAL file is large ({size_kb // 1024} MB) — may indicate abandoned writer")
    if shm.exists() and not wal.exists():
        issues.append("SHM file present without WAL — possible unclean shutdown")
    if issues:
        return _fail("db_wal", "; ".join(issues))
    return _ok("db_wal", "WAL/SHM state looks healthy")


def check_watcher_state():
    if not PID_FILE.exists():
        return _ok("watcher_state", "watcher not running (no PID file)")
    try:
        pid = int(PID_FILE.read_text().strip())
        os.kill(pid, 0)  # signal 0 = existence check, no actual signal
        return _ok("watcher_state", f"watcher running (PID {pid})")
    except ProcessLookupError:
        return _fail("watcher_state",
            f"watcher.pid exists (PID {pid}) but process is dead — stale PID file")
    except ValueError:
        return _fail("watcher_state", "watcher.pid contains invalid PID")


def check_queue_depth():
    if not QUEUE_DIR.exists():
        return _fail("queue_depth", f"watcher-queue/ not found at {QUEUE_DIR}")
    pending = [f for f in QUEUE_DIR.iterdir() if not f.name.endswith(".completed")]
    count = len(pending)
    if count > 500:
        return _fail("queue_depth", f"queue backlog is high: {count} files pending")
    return _ok("queue_depth", f"watcher-queue/ exists, {count} files pending")


def check_data_gitignored():
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", "local"],
            cwd=PROJECT_DIR,
            capture_output=True,
        )
        if result.returncode == 0:
            return _ok("data_gitignored", "local/ is gitignored")
        return _fail("data_gitignored", "local/ is NOT gitignored — sensitive data at risk")  # noqa: E501
    except FileNotFoundError:
        return _fail("data_gitignored", "git not available")


def check_cli_path():
    cda_bin = shutil.which("cda")
    if not cda_bin:
        return _fail("cli_path", "cda not found on PATH")
    resolved = Path(cda_bin).resolve()
    return _ok("cli_path", f"cda found at {resolved}")


def check_python_runtime():
    major, minor = sys.version_info[:2]
    version_str = f"{major}.{minor}.{sys.version_info[2]}"
    if major == 3 and minor == 9:
        return _ok("python_runtime", f"Python {version_str} (system 3.9 — correct)")
    if major == 3 and minor >= 14:
        return _fail("python_runtime",
            f"Python {version_str} — running under Homebrew Python. Use system Python 3.9.")
    return _ok("python_runtime", f"Python {version_str}")


def check_dependencies():
    failed = []
    for mod in REQUIRED_IMPORTS:
        try:
            importlib.import_module(mod)
        except ImportError:
            failed.append(mod)
    if failed:
        return _fail("dependencies", f"Missing imports: {', '.join(failed)}")
    return _ok("dependencies", f"All {len(REQUIRED_IMPORTS)} required imports available")


# ── public interface ──────────────────────────────────────────────────────────

CHECKS = [
    check_version,
    check_install_path,
    check_db_present,
    check_db_accessible,
    check_db_integrity,
    check_db_tables,
    check_db_counts,
    check_db_wal,
    check_watcher_state,
    check_queue_depth,
    check_data_gitignored,
    check_cli_path,
    check_python_runtime,
    check_dependencies,
]


def run_all():
    """Run all self-checks. Returns (passed: bool, results: list[dict])."""
    results = [c() for c in CHECKS]
    passed = all(r["passed"] for r in results)
    return passed, results
