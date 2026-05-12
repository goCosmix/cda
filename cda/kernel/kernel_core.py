"""Shared kernel core (bottom 40%) for goCosmix embedded kernels.

Provides a stable service lifecycle contract:
- service registry + metadata
- start/stop/restart/status
- pid/log/state persistence
- runtime event journal
"""

import json
import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional


CommandBuilder = Callable[[Optional[Dict[str, str]]], List[str]]


@dataclass
class ServiceSpec:
    service_id: str
    label: str
    service_type: str  # daemon | task
    description: str
    command: Optional[List[str]] = None
    command_builder: Optional[CommandBuilder] = None
    cwd: Optional[Path] = None
    env: Optional[Dict[str, str]] = None
    pid_file: Optional[Path] = None
    log_file: Optional[Path] = None
    allowed_actions: Optional[List[str]] = None

    def build_command(self, options: Optional[Dict[str, str]] = None) -> List[str]:
        if self.command_builder is not None:
            return list(self.command_builder(options or {}))
        if self.command is not None:
            return list(self.command)
        raise RuntimeError(f"No command configured for service: {self.service_id}")


class KernelCoreError(Exception):
    """Shared kernel core exception."""


class KernelCore:
    def __init__(self, *, state_path: Path, home_dir: Path, services: Dict[str, ServiceSpec]) -> None:
        self.state_path = state_path
        self.home_dir = home_dir
        self.service_specs = services
        self.state = self._load_state()

    def _now_iso(self) -> str:
        return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime())

    def _default_state(self) -> Dict:
        return {
            "kernel": {
                "kind": "generic",
                "updated_at": self._now_iso(),
            },
            "events": [],
            "services": {
                sid: {
                    "service_id": sid,
                    "status": "stopped",
                    "pid": None,
                    "exit_code": None,
                    "started_at": None,
                    "updated_at": None,
                    "last_error": None,
                    "run_count": 0,
                }
                for sid in self.service_specs
            },
        }

    def _load_state(self) -> Dict:
        if self.state_path.exists():
            try:
                state = json.loads(self.state_path.read_text())
                state.setdefault("events", [])
                state.setdefault("services", {})
                for sid in self.service_specs:
                    state["services"].setdefault(
                        sid,
                        {
                            "service_id": sid,
                            "status": "stopped",
                            "pid": None,
                            "exit_code": None,
                            "started_at": None,
                            "updated_at": None,
                            "last_error": None,
                            "run_count": 0,
                        },
                    )
                return state
            except Exception:
                pass
        state = self._default_state()
        self._save_state(state)
        return state

    def _save_state(self, state: Optional[Dict] = None) -> None:
        if state is None:
            state = self.state
        state.setdefault("kernel", {})
        state["kernel"]["updated_at"] = self._now_iso()
        self.state_path.write_text(json.dumps(state, indent=2))

    def _emit_event(self, kind: str, service_id: str, detail: str, level: str = "info") -> None:
        events = self.state.setdefault("events", [])
        events.append(
            {
                "ts": self._now_iso(),
                "kind": kind,
                "service_id": service_id,
                "detail": detail,
                "level": level,
            }
        )
        if len(events) > 200:
            self.state["events"] = events[-200:]
        self._save_state()

    def recent_events(self, limit: int = 50) -> List[Dict]:
        events = self.state.get("events", [])
        return events[-max(1, limit):]

    def _is_alive(self, pid: int) -> bool:
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False

    def _spec(self, service_id: str) -> ServiceSpec:
        spec = self.service_specs.get(service_id)
        if not spec:
            raise KernelCoreError(f"Unknown service: {service_id}")
        return spec

    def _refresh(self, service_id: str) -> Dict:
        spec = self._spec(service_id)
        state = self.state["services"][service_id]

        pid = state.get("pid")
        if pid and self._is_alive(pid):
            if state["status"] != "running":
                state["status"] = "running"
                state["updated_at"] = self._now_iso()
                self._save_state()
            return state

        if spec.pid_file and spec.pid_file.exists():
            try:
                file_pid = int(spec.pid_file.read_text().strip())
                if self._is_alive(file_pid):
                    state["pid"] = file_pid
                    state["status"] = "running"
                    state["updated_at"] = self._now_iso()
                    self._save_state()
                    return state
            except Exception:
                pass

        if pid and not self._is_alive(pid):
            state["status"] = "stopped"
            state["pid"] = None
            state["updated_at"] = self._now_iso()
            self._save_state()

        return state

    def _service_view(self, service_id: str, spec: ServiceSpec, state: Dict) -> Dict:
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
            "run_count": state.get("run_count", 0),
        }

    def services(self) -> List[Dict]:
        rows = []
        for sid, spec in self.service_specs.items():
            state = self._refresh(sid)
            rows.append(self._service_view(sid, spec, state))
        return rows

    def service_status(self, service_id: str) -> Dict:
        spec = self._spec(service_id)
        state = self._refresh(service_id)
        return self._service_view(service_id, spec, state)

    def start_service(self, service_id: str, options: Optional[Dict[str, str]] = None) -> Dict:
        spec = self._spec(service_id)
        state = self.state["services"][service_id]

        if spec.pid_file and spec.pid_file.exists():
            try:
                existing_pid = int(spec.pid_file.read_text().strip())
                if self._is_alive(existing_pid):
                    raise KernelCoreError(f"{spec.label} is already running (pid={existing_pid})")
                spec.pid_file.unlink(missing_ok=True)
            except ValueError:
                spec.pid_file.unlink(missing_ok=True)

        command = spec.build_command(options or {})
        log_file = spec.log_file or (self.home_dir / "logs" / f"{service_id}.log")

        with open(log_file, "a") as fh:
            proc = subprocess.Popen(
                command,
                cwd=str(spec.cwd or self.home_dir),
                env={**os.environ, **(spec.env or {})},
                stdout=fh,
                stderr=fh,
                preexec_fn=os.setsid if spec.service_type == "daemon" else None,
            )

        state["pid"] = proc.pid
        state["status"] = "starting"
        state["started_at"] = self._now_iso()
        state["exit_code"] = None
        state["last_error"] = None
        state["updated_at"] = self._now_iso()
        state["run_count"] = int(state.get("run_count", 0)) + 1
        self._save_state()

        if spec.pid_file:
            for _ in range(12):
                if spec.pid_file.exists():
                    try:
                        file_pid = int(spec.pid_file.read_text().strip())
                        if self._is_alive(file_pid):
                            state["pid"] = file_pid
                            state["status"] = "running"
                            state["updated_at"] = self._now_iso()
                            self._emit_event("service.started", service_id, f"pid={file_pid}")
                            return self.service_status(service_id)
                    except Exception:
                        pass
                time.sleep(0.25)

            if self._is_alive(proc.pid):
                try:
                    spec.pid_file.write_text(str(proc.pid))
                    state["pid"] = proc.pid
                except Exception:
                    pass

        state["status"] = "running"
        self._save_state()
        self._emit_event("service.started", service_id, f"pid={state['pid']}")

        # For task services, watch completion in background and update state.
        if spec.service_type == "task":
            def _watch(p, sid=service_id, st=state):
                rc = p.wait()
                st["exit_code"] = rc
                st["status"] = "completed" if rc == 0 else "failed"
                st["pid"] = None
                st["updated_at"] = self._now_iso()
                self._save_state()
                self._emit_event(
                    "task.completed" if rc == 0 else "task.failed",
                    sid, f"exit={rc}",
                    level="info" if rc == 0 else "error",
                )
            threading.Thread(target=_watch, args=(proc,), daemon=False).start()

        return self.service_status(service_id)

    def run_task(
        self,
        service_id: str,
        options: Optional[Dict[str, str]] = None,
        timeout: Optional[int] = None,
    ) -> Dict:
        spec = self._spec(service_id)
        if spec.service_type != "task":
            raise KernelCoreError(f"{spec.label} is not a task service")

        state = self.state["services"][service_id]
        command = spec.build_command(options or {})
        log_file = spec.log_file or (self.home_dir / "logs" / f"{service_id}.log")
        state["status"] = "running"
        state["started_at"] = self._now_iso()
        state["updated_at"] = self._now_iso()
        state["run_count"] = int(state.get("run_count", 0)) + 1
        state["exit_code"] = None
        state["last_error"] = None
        self._save_state()
        self._emit_event("task.started", service_id, " ".join(command[:4]))

        with open(log_file, "a") as fh:
            result = subprocess.run(
                command,
                cwd=str(spec.cwd or self.home_dir),
                env={**os.environ, **(spec.env or {})},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout,
            )
            output = (result.stdout or "") + (result.stderr or "")
            if output:
                fh.write(output)
                if not output.endswith("\n"):
                    fh.write("\n")

        state["exit_code"] = result.returncode
        state["updated_at"] = self._now_iso()
        state["status"] = "completed" if result.returncode == 0 else "failed"
        state["last_error"] = None if result.returncode == 0 else output[-500:]
        self._save_state()
        self._emit_event(
            "task.completed" if result.returncode == 0 else "task.failed",
            service_id,
            f"exit={result.returncode}",
            level="info" if result.returncode == 0 else "error",
        )

        return {
            **self.service_status(service_id),
            "output": output,
            "returncode": result.returncode,
        }

    def stop_service(self, service_id: str) -> Dict:
        spec = self._spec(service_id)
        state = self.state["services"][service_id]

        pid = None
        if spec.pid_file and spec.pid_file.exists():
            try:
                pid = int(spec.pid_file.read_text().strip())
            except Exception:
                pass
        if pid is None:
            pid = state.get("pid")

        if pid is None:
            raise KernelCoreError(f"No running PID found for {spec.label}")

        if not self._is_alive(pid):
            state["status"] = "stopped"
            state["pid"] = None
            state["updated_at"] = self._now_iso()
            self._save_state()
            return self.service_status(service_id)

        try:
            os.kill(pid, signal.SIGTERM)
            time.sleep(0.5)
        except OSError as exc:
            raise KernelCoreError(f"Failed to stop {spec.label}: {exc}")

        if spec.pid_file and spec.pid_file.exists():
            spec.pid_file.unlink(missing_ok=True)

        state["status"] = "stopped"
        state["pid"] = None
        state["updated_at"] = self._now_iso()
        self._save_state()
        self._emit_event("service.stopped", service_id, f"pid={pid}")
        return self.service_status(service_id)

    def restart_service(self, service_id: str, options: Optional[Dict[str, str]] = None) -> Dict:
        try:
            self.stop_service(service_id)
        except KernelCoreError:
            pass
        time.sleep(0.5)
        return self.start_service(service_id, options=options or {})

    def tail_log(self, service_id: str, lines: int = 200) -> str:
        spec = self._spec(service_id)
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
