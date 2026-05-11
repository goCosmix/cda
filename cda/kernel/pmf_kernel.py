import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from cda.kernel.paths import (
    LOG_DIR, RUNTIME_FILE, PMF_LOG_DIR,
    PID_FILE as WATCHER_PID_FILE, UI_PID_FILE, CDA_HOME,
    ensure_dirs,
)

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10001

# ── launchd integration ──────────────────────────────────────────────────────

PLIST_LABEL = "com.gocosmix.cda"


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
        <string>pmf</string>
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
        raise PMFKernelError("cda binary not found on PATH — cannot generate plist")

    target = plist_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(generate_plist(cda_bin, cda_home))

    # Unload any stale registration first
    subprocess.run(["launchctl", "unload", str(target)], capture_output=True)

    result = subprocess.run(
        ["launchctl", "load", str(target)],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise PMFKernelError(f"launchctl load failed: {result.stderr.strip()}")

    return target


def uninstall_launchd() -> None:
    """Unload and remove the LaunchAgent plist."""
    target = plist_path()
    if target.exists():
        subprocess.run(["launchctl", "unload", str(target)], capture_output=True)
        target.unlink(missing_ok=True)


def open_browser_when_ready(
    url: str,
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    timeout: float = 12.0,
) -> threading.Thread:
    """
    Spawn a daemon thread that polls host:port and opens a browser when ready.
    For foreground (serve) use: the thread outlives the caller because serve blocks.
    For background (pmf up / ui start): call wait_for_port() instead so we poll
    synchronously before the process exits.
    """
    def _wait_and_open():
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
    Use this when the caller process will exit after starting a background service.
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


ensure_dirs()


def now_ts():
    return int(time.time() * 1000)


def now_iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())


@dataclass
class ServiceSpec:
    service_id: str
    label: str
    service_type: str
    description: str
    command: Optional[List[str]] = None
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    pid_file: Optional[Path] = None
    log_file: Optional[Path] = None
    allowed_actions: Optional[List[str]] = None

    def build_command(self, options: Dict[str, str] = None) -> List[str]:
        if self.service_id == "ui":
            host = options.get("host", DEFAULT_HOST) if options else DEFAULT_HOST
            port = options.get("port", DEFAULT_PORT) if options else DEFAULT_PORT
            return [
                sys.executable,
                "-c",
                (
                    "import cda.ui.web as w; "
                    f"w.start_server(host={json.dumps(host)}, port={port})"
                ),
            ]

        if self.service_id == "watcher":
            return [sys.executable, "-m", "cda.pipeline.watcher"]

        if self.command is not None:
            return list(self.command)

        raise RuntimeError(f"No command configured for service: {self.service_id}")


SERVICE_SPECS: Dict[str, ServiceSpec] = {
    "watcher": ServiceSpec(
        service_id="watcher",
        label="Watcher Daemon",
        service_type="daemon",
        description="Live VS Code data watcher and incremental ingest process.",
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
        cwd=CDA_HOME,
        pid_file=UI_PID_FILE,
        log_file=LOG_DIR / "ui.log",
        allowed_actions=["start", "stop", "restart", "status"],
    ),
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
}


def default_state():
    return {"services": {service_id: {
        "service_id": service_id,
        "status": "stopped",
        "pid": None,
        "exit_code": None,
        "started_at": None,
        "updated_at": None,
        "last_error": None,
    } for service_id in SERVICE_SPECS}}


class PMFKernelError(Exception):
    pass


class PMFKernel:
    def __init__(self):
        self.state_path = RUNTIME_FILE
        self.state = self._load_state()

    def _load_state(self):
        if self.state_path.exists():
            try:
                return json.loads(self.state_path.read_text())
            except Exception:
                pass
        state = default_state()
        self._save_state(state)
        return state

    def _save_state(self, state=None):
        if state is None:
            state = self.state
        self.state_path.write_text(json.dumps(state, indent=2))

    def _touch_state(self, service_id: str, **updates):
        svc_state = self.state["services"].get(service_id)
        if svc_state is None:
            raise PMFKernelError(f"Unknown service: {service_id}")
        svc_state.update(updates)
        svc_state["updated_at"] = now_iso()
        self._save_state()
        return svc_state

    def _is_process_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _refresh_service(self, service_id: str):
        spec = SERVICE_SPECS[service_id]
        state = self.state["services"][service_id]

        pid = state.get("pid")
        if pid and self._is_process_alive(pid):
            if state["status"] not in ["running", "starting"]:
                state["status"] = "running"
                state["updated_at"] = now_iso()
            return state

        if spec.pid_file and spec.pid_file.exists():
            try:
                file_pid = int(spec.pid_file.read_text().strip())
                if self._is_process_alive(file_pid):
                    state["pid"] = file_pid
                    state["status"] = "running"
                    state["updated_at"] = now_iso()
                    self._save_state()
                    return state
            except Exception:
                pass

        if pid and not self._is_process_alive(pid):
            state["status"] = "stopped"
            state["pid"] = None
            self._save_state()

        return state

    def service_spec(self, service_id: str) -> ServiceSpec:
        spec = SERVICE_SPECS.get(service_id)
        if not spec:
            raise PMFKernelError(f"Unknown service: {service_id}")
        return spec

    def services(self) -> List[Dict]:
        results = []
        for service_id in SERVICE_SPECS:
            spec = SERVICE_SPECS[service_id]
            state = self._refresh_service(service_id)
            results.append({
                "service_id": service_id,
                "label": spec.label,
                "description": spec.description,
                "service_type": spec.service_type,
                "status": state["status"],
                "pid": state.get("pid"),
                "exit_code": state.get("exit_code"),
                "started_at": state.get("started_at"),
                "updated_at": state.get("updated_at"),
                "log_file": str(spec.log_file) if spec.log_file else None,
                "allowed_actions": spec.allowed_actions,
            })
        return results

    def service_status(self, service_id: str) -> Dict:
        spec = self.service_spec(service_id)
        state = self._refresh_service(service_id)
        return {
            "service_id": service_id,
            "label": spec.label,
            "description": spec.description,
            "service_type": spec.service_type,
            "status": state["status"],
            "pid": state.get("pid"),
            "exit_code": state.get("exit_code"),
            "started_at": state.get("started_at"),
            "updated_at": state.get("updated_at"),
            "log_file": str(spec.log_file) if spec.log_file else None,
            "allowed_actions": spec.allowed_actions,
        }

    def start_service(self, service_id: str, options: Dict[str, str] = None) -> Dict:
        spec = self.service_spec(service_id)
        state = self.state["services"][service_id]

        if service_id in ["watcher", "ui"] and spec.pid_file and spec.pid_file.exists():
            try:
                existing_pid = int(spec.pid_file.read_text().strip())
                if self._is_process_alive(existing_pid):
                    raise PMFKernelError(f"{spec.label} is already running (pid={existing_pid})")
                spec.pid_file.unlink(missing_ok=True)
            except ValueError:
                spec.pid_file.unlink(missing_ok=True)

        command = spec.build_command(options or {})
        log_file = spec.log_file or LOG_DIR / f"{service_id}.log"
        with open(log_file, "a") as fh:
            proc = subprocess.Popen(
                command,
                cwd=spec.cwd or CDA_HOME,
                env={**os.environ, **(spec.env or {})},
                stdout=fh,
                stderr=fh,
                preexec_fn=os.setsid if spec.service_type == "daemon" else None,
            )

        state["pid"] = proc.pid
        state["status"] = "starting"
        state["started_at"] = now_iso()
        state["exit_code"] = None
        state["last_error"] = None
        state["updated_at"] = now_iso()
        self._save_state()

        if spec.pid_file:
            wait_seconds = 0.0
            while wait_seconds < 3.0:
                if spec.pid_file.exists():
                    try:
                        pid = int(spec.pid_file.read_text().strip())
                        if self._is_process_alive(pid):
                            state["pid"] = pid
                            state["status"] = "running"
                            state["updated_at"] = now_iso()
                            self._save_state()
                            return self.service_status(service_id)
                    except Exception:
                        pass
                time.sleep(0.25)
                wait_seconds += 0.25

        if spec.service_type == "daemon":
            state["status"] = "running"
        else:
            state["status"] = "running"
        self._save_state()
        return self.service_status(service_id)

    def stop_service(self, service_id: str) -> Dict:
        spec = self.service_spec(service_id)
        state = self.state["services"][service_id]

        pid = None
        if spec.pid_file and spec.pid_file.exists():
            try:
                pid = int(spec.pid_file.read_text().strip())
            except Exception:
                pid = None

        if pid is None:
            pid = state.get("pid")

        if pid is None:
            raise PMFKernelError(f"No running PID found for {spec.label}")

        if not self._is_process_alive(pid):
            state["status"] = "stopped"
            state["pid"] = None
            self._save_state()
            return self.service_status(service_id)

        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except OSError as exc:
            raise PMFKernelError(f"Failed to stop {spec.label}: {exc}")

        if spec.pid_file and spec.pid_file.exists():
            spec.pid_file.unlink(missing_ok=True)

        state["status"] = "stopped"
        state["pid"] = None
        state["updated_at"] = now_iso()
        self._save_state()
        return self.service_status(service_id)

    def restart_service(self, service_id: str, options: Dict[str, str] = None) -> Dict:
        self.stop_service(service_id)
        time.sleep(0.5)
        return self.start_service(service_id, options=options or {})

    def tail_log(self, service_id: str, lines: int = 200) -> str:
        spec = self.service_spec(service_id)
        if not spec.log_file or not spec.log_file.exists():
            return ""
        with open(spec.log_file, "rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            chunk = bytearray()
            while pos > 0 and len(chunk) < 8192 * lines:
                step = min(4096, pos)
                pos -= step
                fh.seek(pos)
                chunk[:0] = fh.read(step)
                if chunk.count(b"\n") > lines:
                    break
            text = chunk.decode("utf-8", errors="replace")
        return "\n".join(text.strip().splitlines()[-lines:])
