"""cda.kernel.eak_kernel — Embedded App Kernel (EAK) for Code Data Ark.

EAK layers:
- bottom 40% shared DNA in kernel_core.py (service lifecycle, state, events)
- top 60% CDA-specific: watcher/ui daemons, pipeline task catalog, launchd

Architecture mirrors OTK (Ops Tool Kernel) in dev, but tuned for
an embedded app runtime that manages long-lived watchers and data pipelines.

Service catalog (7 services):
  Daemons:  watcher, ui
  Tasks:    sync, reconstruct, embed-build, backfill, symbol-index
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Dict, List, Optional

from cda.kernel.kernel_core import KernelCore, KernelCoreError, ServiceSpec
from cda.kernel.paths import (
    LOG_DIR,
    RUNTIME_FILE,
    PMF_LOG_DIR,
    PID_FILE as WATCHER_PID_FILE,
    UI_PID_FILE,
    CDA_HOME,
    ensure_dirs,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10001
PLIST_LABEL = "com.gocosmix.cda"

_SOURCE_ROOT = Path(__file__).resolve().parents[2]
_CONTROL_SCRIPTS = _SOURCE_ROOT.parent / "control" / "scripts"


# ── launchd integration ───────────────────────────────────────────────────────

def plist_path() -> Path:
    return Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"


def generate_plist(cda_bin: str, cda_home: Path) -> str:
    log = cda_home / "logs" / "launchd.log"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{PLIST_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{cda_bin}</string>
        <string>eak</string>
        <string>up</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <false/>
    <key>StandardOutPath</key>
    <string>{log}</string>
    <key>StandardErrorPath</key>
    <string>{log}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>CDA_HOME</key>
        <string>{cda_home}</string>
        <key>PATH</key>
        <string>{os.path.dirname(cda_bin)}:/usr/local/bin:/usr/bin:/bin</string>
    </dict>
</dict>
</plist>
"""


def install_launchd(cda_home: Path) -> Path:
    """Write the LaunchAgent plist and load it with launchctl."""
    cda_bin = shutil.which("cda")
    if not cda_bin:
        raise EAKKernelError("cda binary not found on PATH — cannot generate plist")

    target = plist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_plist(cda_bin, cda_home))

    subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
    result = subprocess.run(
        ["launchctl", "load", str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise EAKKernelError(f"launchctl load failed: {result.stderr.strip()}")

    return target


def uninstall_launchd() -> None:
    """Unload and remove the LaunchAgent plist."""
    target = plist_path()
    if target.exists():
        subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
        target.unlink(missing_ok=True)


# ── browser helpers ───────────────────────────────────────────────────────────

def open_browser_when_ready(
    url: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 12.0,
) -> threading.Thread:
    """
    Spawn a daemon thread that polls host:port and opens browser when ready.
    For foreground (serve) use: thread outlives the caller because serve blocks.
    For background (eak up / pmf up): use wait_for_port_and_open_browser instead.
    """
    def _wait_and_open() -> None:
        elapsed = 0.0
        while elapsed < timeout:
            try:
                with socket.create_connection((host, port), timeout=0.5):
                    webbrowser.open(url)
                    return
            except OSError:
                time.sleep(0.25)
                elapsed += 0.25

    t = threading.Thread(target=_wait_and_open, daemon=True)
    t.start()
    return t


def wait_for_port_and_open_browser(
    url: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 8.0,
) -> bool:
    """
    Block until host:port accepts connections (or timeout), then open browser.
    Use when the caller process will exit after starting a background service.
    Returns True if port came up, False on timeout.
    """
    elapsed = 0.0
    while elapsed < timeout:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                webbrowser.open(url)
                return True
        except OSError:
            time.sleep(0.25)
            elapsed += 0.25
    return False


# ── command builders ──────────────────────────────────────────────────────────

def _ui_command_builder(options: Optional[Dict[str, str]] = None) -> List[str]:
    opts = options or {}
    host = opts.get("host", DEFAULT_HOST)
    port = int(opts.get("port", DEFAULT_PORT))
    return [
        sys.executable,
        "-c",
        (
            "import cda.ui.web as w; "
            f"w.start_server(host={json.dumps(host)}, port={port})"
        ),
    ]


# ── service catalog ───────────────────────────────────────────────────────────

SERVICE_SPECS: Dict[str, ServiceSpec] = {
    # ── Daemons ──────────────────────────────────────────────────────────────
    "watcher": ServiceSpec(
        service_id="watcher",
        label="Watcher Daemon",
        service_type="daemon",
        description="Live VS Code data watcher and incremental ingest pipeline.",
        command=[sys.executable, "-m", "cda.pipeline.watcher"],
        cwd=CDA_HOME,
        pid_file=WATCHER_PID_FILE,
        log_file=LOG_DIR / "watcher.log",
        allowed_actions=["start", "stop", "restart", "status"],
    ),
    "ui": ServiceSpec(
        service_id="ui",
        label="Web UI",
        service_type="daemon",
        description="Local web dashboard for Ark runtime and session analytics.",
        command_builder=_ui_command_builder,
        cwd=CDA_HOME,
        pid_file=UI_PID_FILE,
        log_file=LOG_DIR / "ui.log",
        allowed_actions=["start", "stop", "restart", "status"],
    ),
    # ── Pipeline tasks ────────────────────────────────────────────────────────
    "sync": ServiceSpec(
        service_id="sync",
        label="Full Sync",
        service_type="task",
        description="Full ingest and rebuild pipeline for Ark data.",
        command=[sys.executable, "-m", "cda.pipeline.ingest"],
        cwd=CDA_HOME,
        log_file=PMF_LOG_DIR / "sync.log",
        allowed_actions=["start", "status"],
    ),
    "reconstruct": ServiceSpec(
        service_id="reconstruct",
        label="Reconstruct",
        service_type="task",
        description="Reconstruct conversations and rebuild the full text search index.",
        command=[sys.executable, "-m", "cda.pipeline.reconstruct"],
        cwd=CDA_HOME,
        log_file=PMF_LOG_DIR / "reconstruct.log",
        allowed_actions=["start", "status"],
    ),
    "embed-build": ServiceSpec(
        service_id="embed-build",
        label="Embed Build",
        service_type="task",
        description="Build semantic embeddings and session intelligence.",
        command=[sys.executable, "-m", "cda.pipeline.embed", "build"],
        cwd=CDA_HOME,
        log_file=PMF_LOG_DIR / "embed.log",
        allowed_actions=["start", "status"],
    ),
    "backfill": ServiceSpec(
        service_id="backfill",
        label="Backfill",
        service_type="task",
        description="Re-run extract+embed for sessions missing analysis.",
        command=[sys.executable, "-m", "cda.pipeline.backfill"],
        cwd=CDA_HOME,
        log_file=PMF_LOG_DIR / "backfill.log",
        allowed_actions=["start", "status"],
    ),
    "symbol-index": ServiceSpec(
        service_id="symbol-index",
        label="Symbol Index",
        service_type="task",
        description="Rebuild the code symbol index from VFS edit content.",
        command=[sys.executable, "-m", "cda.pipeline.backfill", "--symbols-only"],
        cwd=CDA_HOME,
        log_file=PMF_LOG_DIR / "symbol-index.log",
        allowed_actions=["start", "status"],
    ),
}


# ── kernel class ──────────────────────────────────────────────────────────────

class EAKKernelError(KernelCoreError):
    """Embedded App Kernel exception."""


class EAKKernel(KernelCore):
    """
    Embedded App Kernel for Code Data Ark.

    Manages the full CDA runtime: watcher daemon, web UI daemon,
    and the pipeline task catalog (sync, reconstruct, embed, backfill, symbols).

    State is persisted at RUNTIME_FILE (~/.../cda/pmf/runtime.json).
    """

    def __init__(self) -> None:
        ensure_dirs()
        super().__init__(
            state_path=RUNTIME_FILE,
            home_dir=CDA_HOME,
            services=SERVICE_SPECS,
        )

    def _default_state(self) -> Dict:
        state = super()._default_state()
        state["kernel"]["kind"] = "eak"
        state["kernel"]["app"] = "code-data-ark"
        return state

    def up(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
    ) -> List[Dict]:
        """Start all daemons (watcher + ui). Returns list of service status dicts."""
        results = []
        for sid in ("watcher", "ui"):
            state = self._refresh(sid)
            if state["status"] == "running":
                results.append(self.service_status(sid))
                continue
            opts = {"host": host, "port": str(port)} if sid == "ui" else {}
            try:
                results.append(self.start_service(sid, options=opts))
            except EAKKernelError as exc:
                results.append({**self.service_status(sid), "error": str(exc)})
        return results

    def down(self) -> List[Dict]:
        """Stop all daemons (ui + watcher). Returns list of service status dicts."""
        results = []
        for sid in ("ui", "watcher"):
            try:
                results.append(self.stop_service(sid))
            except EAKKernelError:
                results.append(self.service_status(sid))
        return results
