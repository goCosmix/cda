import subprocess
import sys
import threading
from datetime import datetime
from typing import Any, Dict


ACTION_STATE: Dict[str, Any] = {}
ACTION_LOCK = threading.Lock()


def run_action_background(action_id, action_name):
    """Execute pipeline action in background thread."""
    with ACTION_LOCK:
        ACTION_STATE[action_id] = {
            "status": "running",
            "action": action_name,
            "started_at": datetime.now().isoformat(),
            "output": ""
        }

    try:
        if action_name == "sync":
            result = subprocess.run(
                [sys.executable, "-m", "cda.pipeline.ingest"],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "reconstruct":
            result = subprocess.run(
                [sys.executable, "-m", "cda.pipeline.reconstruct"],
                capture_output=True,
                text=True,
                timeout=300
            )
        elif action_name == "embed-build":
            result = subprocess.run(
                [sys.executable, "-m", "cda.pipeline.embed", "build"],
                capture_output=True,
                text=True,
                timeout=600
            )
        elif action_name == "watch-start":
            result = subprocess.run(
                [sys.executable, "-m", "cda.pipeline.watcher", "start"],
                capture_output=True,
                text=True,
                timeout=30
            )
        else:
            result = None

        with ACTION_LOCK:
            if result:
                ACTION_STATE[action_id]["status"] = "completed" if result.returncode == 0 else "failed"
                ACTION_STATE[action_id]["output"] = result.stdout + result.stderr
                ACTION_STATE[action_id]["returncode"] = result.returncode
            ACTION_STATE[action_id]["completed_at"] = datetime.now().isoformat()
    except Exception as e:
        with ACTION_LOCK:
            ACTION_STATE[action_id]["status"] = "error"
            ACTION_STATE[action_id]["output"] = str(e)
            ACTION_STATE[action_id]["completed_at"] = datetime.now().isoformat()
