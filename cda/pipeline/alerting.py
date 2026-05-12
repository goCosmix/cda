"""cda.pipeline.alerting — health checks and macOS push notifications.

Checks:
  - watcher_health  : PID file present and process alive
  - queue_depth     : pending queue operations (*.json in QUEUE_DIR)

Notifications fire via osascript (macOS Notification Center).
Silent and non-blocking if osascript is unavailable.

Thresholds:
  QUEUE_DEPTH_WARN  = 50   (warning)
  QUEUE_DEPTH_CRIT  = 200  (critical)
"""

import json
import os
import subprocess
from pathlib import Path
from typing import Dict, List, Optional

from cda.kernel.paths import PID_FILE, QUEUE_DIR

QUEUE_DEPTH_WARN = 50
QUEUE_DEPTH_CRIT = 200


# ── notification ──────────────────────────────────────────────────────────────

def send_notification(
    title: str,
    message: str,
    subtitle: str = "Code Data Ark",
) -> None:
    """Fire a macOS Notification Center alert via osascript. Silent on failure."""
    script = (
        f"display notification {json.dumps(message)} "
        f"with title {json.dumps(title)} "
        f"subtitle {json.dumps(subtitle)}"
    )
    try:
        subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            timeout=5,
        )
    except Exception:
        pass


# ── checks ────────────────────────────────────────────────────────────────────

def check_watcher_health() -> Dict:
    """Return health dict for the watcher daemon.

    Keys: healthy (bool), pid (int|None), reason (str|None)
    """
    if not PID_FILE.exists():
        return {"healthy": False, "pid": None, "reason": "pid_file_missing"}

    try:
        pid = int(PID_FILE.read_text().strip())
    except (ValueError, OSError):
        return {"healthy": False, "pid": None, "reason": "pid_file_corrupt"}

    try:
        os.kill(pid, 0)  # signal 0 = existence check, no actual signal sent
        return {"healthy": True, "pid": pid, "reason": None}
    except ProcessLookupError:
        return {"healthy": False, "pid": pid, "reason": "process_dead"}
    except PermissionError:
        # Process exists but we can't send signals to it — still alive.
        return {"healthy": True, "pid": pid, "reason": None}


def check_queue_depth() -> Dict:
    """Return queue depth metrics.

    Keys: pending (int), completed (int), level ("ok"|"warn"|"crit")
    """
    if not QUEUE_DIR.exists():
        return {"pending": 0, "completed": 0, "level": "ok"}

    pending = len(list(QUEUE_DIR.glob("*.json")))
    completed = len(list(QUEUE_DIR.glob("*.completed")))

    if pending >= QUEUE_DEPTH_CRIT:
        level = "crit"
    elif pending >= QUEUE_DEPTH_WARN:
        level = "warn"
    else:
        level = "ok"

    return {"pending": pending, "completed": completed, "level": level}


# ── aggregate ─────────────────────────────────────────────────────────────────

def run_health_check(notify: bool = True) -> Dict:
    """Run all health checks and optionally fire macOS notifications for issues.

    Returns:
        {
            "healthy": bool,
            "issues": List[str],
            "watcher": {...},
            "queue": {...},
        }
    """
    watcher = check_watcher_health()
    queue = check_queue_depth()
    issues: List[str] = []

    if not watcher["healthy"]:
        reason = watcher.get("reason", "unknown")
        issues.append(f"Watcher is down ({reason})")
        if notify:
            send_notification(
                title="CDA Watcher Down",
                message=f"Ark watcher is not running ({reason}). Run: cda eak start watcher",
            )

    level = queue["level"]
    pending = queue["pending"]
    if level == "crit":
        issues.append(f"Queue backlog critical: {pending} pending operations")
        if notify:
            send_notification(
                title="CDA Queue Backlog — Critical",
                message=f"{pending} operations queued. Data may be delayed. Restart watcher.",
            )
    elif level == "warn":
        issues.append(f"Queue backlog warning: {pending} pending operations")
        if notify:
            send_notification(
                title="CDA Queue Warning",
                message=f"{pending} operations queued. Consider restarting watcher.",
            )

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "watcher": watcher,
        "queue": queue,
    }
