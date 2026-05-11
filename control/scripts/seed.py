#!/usr/bin/env python3
"""
Control plane seed script for cda/vscode-ark.
Creates and populates the control.db with identity and manifest tables.
"""

import hashlib
import os
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTROL_DIR = Path(__file__).resolve().parent.parent / "data"
DB_PATH = CONTROL_DIR / "control.db"


def get_git_info():
    def git(*args):
        try:
            return subprocess.check_output(
                ["git", "-C", str(REPO_ROOT)] + list(args),
                stderr=subprocess.DEVNULL,
            ).decode().strip()
        except subprocess.CalledProcessError:
            return None

    return {
        "git_remote": git("remote", "get-url", "origin"),
        "git_branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "git_commit": git("rev-parse", "HEAD"),
        "git_commit_short": git("rev-parse", "--short", "HEAD"),
        "git_commit_date": git("log", "-1", "--format=%cI"),
    }


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    try:
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, PermissionError):
        return None


def is_gitignored(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "check-ignore", "-q", str(path)],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def is_git_tracked(path: Path) -> bool:
    try:
        result = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--error-unmatch", str(path)],
            capture_output=True,
        )
        return result.returncode == 0
    except Exception:
        return False


def seed_identity(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS identity (
            id          INTEGER PRIMARY KEY,
            key         TEXT NOT NULL UNIQUE,
            value       TEXT,
            updated_at  TEXT NOT NULL
        )
    """)

    now = datetime.now(timezone.utc).isoformat()
    version_path = REPO_ROOT / "source" / "VERSION"
    version = version_path.read_text().strip() if version_path.exists() else "unknown"

    git = get_git_info()

    identity_data = {
        "system_name":       "vscode-ark",
        "acronym":           "cda",
        "display_name":      "VS Code Ark",
        "description":       "VS Code/Copilot session data pipeline — ingestion, signal extraction, behavioral analysis",
        "version":           version,
        "language":          "Python",
        "cli_name":          "cda",
        "cli_bin":           str(Path.home() / "Library" / "Python" / "3.9" / "bin" / "cda"),
        "repo_root":         str(REPO_ROOT),
        # 3-layer layout
        "source_dir":        str(REPO_ROOT / "source"),
        "local_dir":         str(REPO_ROOT / "local"),
        "local_data":        str(REPO_ROOT / "local" / "data"),
        "local_run":         str(REPO_ROOT / "local" / "run"),
        "local_queue":       str(REPO_ROOT / "local" / "queue"),
        "control_dir":       str(REPO_ROOT / "control"),
        "control_db":        str(DB_PATH),
        "github_org":        "goCosmix",
        "github_repo":       "vscode-ark",
        "git_remote":        git["git_remote"],
        "git_branch":        git["git_branch"],
        "git_commit":        git["git_commit"],
        "git_commit_short":  git["git_commit_short"],
        "git_commit_date":   git["git_commit_date"],
        "python_runtime":    str(Path(os.sys.executable).resolve()),
        "install_path":      str(REPO_ROOT),
        "license":           "MIT",
        "author":            "Ernie Butcher <ernie@fiosii.com>",
        "seeded_at":         now,
    }

    conn.executemany(
        "INSERT OR REPLACE INTO identity (key, value, updated_at) VALUES (?, ?, ?)",
        [(k, v, now) for k, v in identity_data.items()],
    )
    print(f"  identity: {len(identity_data)} records written")


def seed_manifest(conn):
    conn.execute("""
        CREATE TABLE IF NOT EXISTS manifest (
            id              INTEGER PRIMARY KEY,
            path            TEXT NOT NULL UNIQUE,
            relative_path   TEXT NOT NULL,
            filename        TEXT NOT NULL,
            extension       TEXT,
            size_bytes      INTEGER,
            sha256          TEXT,
            is_gitignored   INTEGER NOT NULL DEFAULT 0,
            is_tracked      INTEGER NOT NULL DEFAULT 0,
            is_binary       INTEGER NOT NULL DEFAULT 0,
            file_type       TEXT,
            mtime           TEXT,
            scanned_at      TEXT NOT NULL
        )
    """)

    TEXT_EXTENSIONS = {
        ".py", ".md", ".txt", ".toml", ".cfg", ".ini", ".json", ".yaml", ".yml",
        ".sh", ".env", ".gitignore", ".in", ".rst", ".html", ".css", ".js",
        ".ts", ".sql", ".csv", ".xml", ".lock",
    }

    # Classify file type by path/extension
    def classify(p: Path) -> str:
        parts = set(p.parts)
        if "tests" in parts:
            return "test"
        if "docs" in parts:
            return "docs"
        if p.suffix == ".py":
            if p.name in ("setup.py", "release.py"):
                return "build"
            return "source"
        if p.suffix in (".toml", ".cfg", ".ini", ".in"):
            return "config"
        if p.suffix == ".md":
            return "docs"
        if p.suffix in (".db", ".db-shm", ".db-wal", ".sqlite3", ".sqlite"):
            return "data"
        if p.suffix in (".omxk",):
            return "container"
        if p.name in ("VERSION", "LICENSE", "CHANGELOG.md", "README.md"):
            return "meta"
        if p.suffix in (".sh",):
            return "script"
        if p.name == ".gitignore":
            return "config"
        return "other"

    now = datetime.now(timezone.utc).isoformat()
    rows = []
    skipped = 0

    for entry in sorted(REPO_ROOT.rglob("*")):
        if not entry.is_file():
            continue
        # Skip the control db itself and venv/build artifacts
        rel = entry.relative_to(REPO_ROOT)
        parts = rel.parts
        if parts[0] in ("local", ".git", "venv", ".venv", "__pycache__"):
            skipped += 1
            continue
        if any(p.endswith(".egg-info") for p in parts):
            skipped += 1
            continue

        stat = entry.stat()
        ext = entry.suffix.lower() or None
        is_bin = 0 if (ext in TEXT_EXTENSIONS or ext is None) else 1
        checksum = sha256(entry)
        gitignored = is_gitignored(rel)
        tracked = is_git_tracked(rel) if not gitignored else False
        mtime = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat()

        rows.append((
            str(entry),
            str(rel),
            entry.name,
            ext,
            stat.st_size,
            checksum,
            1 if gitignored else 0,
            1 if tracked else 0,
            is_bin,
            classify(rel),
            mtime,
            now,
        ))

    conn.executemany("""
        INSERT OR REPLACE INTO manifest (
            path, relative_path, filename, extension, size_bytes, sha256,
            is_gitignored, is_tracked, is_binary, file_type, mtime, scanned_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, rows)

    print(f"  manifest: {len(rows)} files indexed ({skipped} dirs/excluded skipped)")


def main():
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Control DB: {DB_PATH}")
    print(f"Repo root:  {REPO_ROOT}")
    print()

    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    with conn:
        print("Seeding identity...")
        seed_identity(conn)
        print("Seeding manifest...")
        seed_manifest(conn)

    conn.close()
    print()
    print("Done.")


if __name__ == "__main__":
    main()
