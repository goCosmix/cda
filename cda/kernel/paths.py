"""
cda.kernel.paths — canonical path resolution for Code Data Ark.

CDA_HOME is the single root for all runtime state (DB, PID files, logs,
queue, PMF runtime).  It is resolved exactly once at import time via:

  1. CDA_HOME environment variable (absolute path)
  2. ~/Library/goCosmix/apps/code-data-ark/  (macOS default)
  3. ~/.gocosmix/apps/code-data-ark/          (fallback on non-macOS)

All goCosmix apps share the ~/Library/goCosmix/ namespace:

  ~/Library/goCosmix/
  ├── apps/
  │   ├── code-data-ark/   ← CDA_HOME
  │   └── ...              ← future goCosmix apps
  └── system/              ← shared goCosmix infrastructure
"""

import os
from pathlib import Path

# ── home resolution ──────────────────────────────────────────────────────────


def _default_cda_home() -> Path:
    """Platform-appropriate default for CDA_HOME."""
    library = Path.home() / "Library"
    if library.exists():  # macOS
        return library / "goCosmix" / "apps" / "code-data-ark"
    return Path.home() / ".gocosmix" / "apps" / "code-data-ark"


def get_cda_home() -> Path:
    """Return the CDA home directory, creating it if it doesn't exist."""
    env = os.environ.get("CDA_HOME")
    if env:
        home = Path(env).expanduser().resolve()
    else:
        home = _default_cda_home()
    home.mkdir(parents=True, exist_ok=True)
    return home


# ── goCosmix namespace (shared across all goCosmix apps) ────────────────────

def get_gocosmix_home() -> Path:
    """Return ~/Library/goCosmix (macOS) or ~/.gocosmix (other)."""
    library = Path.home() / "Library"
    if library.exists():
        return library / "goCosmix"
    return Path.home() / ".gocosmix"


GOCOSMIX_HOME = get_gocosmix_home()
GOCOSMIX_APPS = GOCOSMIX_HOME / "apps"
GOCOSMIX_SYSTEM = GOCOSMIX_HOME / "system"


# ── canonical paths (module-level constants, computed once) ─────────────────

CDA_HOME   = get_cda_home()
LOCAL_DIR  = CDA_HOME                         # CDA_HOME *is* the local root
DATA_DIR   = CDA_HOME / "data"
RUN_DIR    = CDA_HOME / "run"
LOG_DIR    = CDA_HOME / "logs"
QUEUE_DIR  = CDA_HOME / "queue"
PMF_DIR    = CDA_HOME / "pmf"
CONFIG_DIR = CDA_HOME / "config"

DB_PATH        = DATA_DIR / "cda.db"
PID_FILE       = RUN_DIR / "watcher.pid"
UI_PID_FILE    = RUN_DIR / "ui.pid"
UI_LOG_FILE    = LOG_DIR / "ui.log"
POLICY_FILE    = CONFIG_DIR / "policy.txt"
PMF_LOG_DIR    = PMF_DIR / "logs"
RUNTIME_FILE   = PMF_DIR / "runtime.json"


def ensure_dirs() -> None:
    """Create all runtime directories (including goCosmix namespace). Safe to call multiple times."""
    for d in (GOCOSMIX_HOME, GOCOSMIX_APPS, GOCOSMIX_SYSTEM,
              DATA_DIR, RUN_DIR, LOG_DIR, QUEUE_DIR, PMF_DIR, PMF_LOG_DIR, CONFIG_DIR):
        d.mkdir(parents=True, exist_ok=True)
