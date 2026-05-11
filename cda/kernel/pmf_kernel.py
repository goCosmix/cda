import json
import os
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent.parent.parent
LOCAL_DIR = ROOT_DIR / "local"
PACKAGE_DIR = Path(__file__).resolve().parent
RUNTIME_FILE = LOCAL_DIR / "pmf" / "runtime.json"
LOG_DIR = LOCAL_DIR / "pmf" / "logs"
WATCHER_PID_FILE = LOCAL_DIR / "run" / "watcher.pid"
UI_PID_FILE = LOCAL_DIR / "run" / "ui.pid"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 10001

(LOCAL_DIR / "data").mkdir(parents=True, exist_ok=True)
(LOCAL_DIR / "run").mkdir(parents=True, exist_ok=True)
LOG_DIR.mkdir(parents=True, exist_ok=True)


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
    allowed_actions: List[str] = None

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
            return [sys.executable, str(PACKAGE_DIR.parent / "pipeline" / "watcher.py")]

        if self.command is not None:
            return list(self.command)

        raise RuntimeError(f"No command configured for service: {self.service_id}")


SERVICE_SPECS: Dict[str, ServiceSpec] = {
    "watcher": ServiceSpec(
        service_id="watcher",
        label="Watcher Daemon",
        service_type="daemon",
        description="Live VS Code data watcher and incremental ingest process.",
        cwd=ROOT_DIR,
        pid_file=WATCHER_PID_FILE,
        log_file=LOCAL_DIR / "logs" / "watcher.log",
        allowed_actions=["start", "stop", "restart", "status"],
    ),
    "ui": ServiceSpec(
        service_id="ui",
        label="Web UI",
        service_type="daemon",
        description="Local web dashboard for Ark runtime and session analytics.",
        cwd=ROOT_DIR,
        pid_file=UI_PID_FILE,
        log_file=LOCAL_DIR / "logs" / "ui.log",
        allowed_actions=["start", "stop", "restart", "status"],
    ),
    "sync": ServiceSpec(
        service_id="sync",
        label="Full Sync",
        service_type="task",
        description="Full ingest and rebuild pipeline for Ark data.",
        command=[sys.executable, str(PACKAGE_DIR.parent / "pipeline" / "ingest.py")],
        cwd=ROOT_DIR,
        log_file=LOG_DIR / "sync.log",
        allowed_actions=["start", "status"],
    ),
    "reconstruct": ServiceSpec(
        service_id="reconstruct",
        label="Reconstruct",
        service_type="task",
        description="Reconstruct conversations and rebuild the full text search index.",
        command=[sys.executable, str(PACKAGE_DIR.parent / "pipeline" / "reconstruct.py")],
        cwd=ROOT_DIR,
        log_file=LOG_DIR / "reconstruct.log",
        allowed_actions=["start", "status"],
    ),
    "embed-build": ServiceSpec(
        service_id="embed-build",
        label="Embed Build",
        service_type="task",
        description="Build semantic embeddings and session intelligence.",
        command=[sys.executable, str(PACKAGE_DIR.parent / "pipeline" / "embed.py"), "build"],
        cwd=ROOT_DIR,
        log_file=LOG_DIR / "embed.log",
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
                cwd=spec.cwd or ROOT_DIR,
                env={**os.environ, **(spec.env or {}), "PYTHONPATH": str(ROOT_DIR)},
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
