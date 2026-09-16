"""Detached serial-build workers and local status/log monitoring."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from .terminal_output import log, table


def state_path(console) -> Path:
    return console.logs_directory / "build.json"


def readable_state_path(console) -> Path:
    path = state_path(console)
    legacy = console.xpr.parent.parent / "project_console/build.json"
    if not path.exists() and legacy.exists():
        if json.loads(legacy.read_text()).get("project") == str(console.xpr):
            return legacy
    return path


def alive(pid: int | None) -> bool:
    if not pid:
        return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def write_state(path: Path, state: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(state, indent=2) + "\n")
    temporary.replace(path)


def start(console, project: Path, action: str, jobs: int, timeout: float) -> None:
    """Start one detached worker and report its PID and durable project log."""
    path = state_path(console)
    path.parent.mkdir(parents=True, exist_ok=True)
    with console.locked("launcher.lock"):
        previous_path = readable_state_path(console)
        previous = json.loads(previous_path.read_text()) if previous_path.exists() else {}
        if previous.get("status") in {"starting", "running"} and alive(previous.get("pid")):
            raise RuntimeError(f"Build worker {previous['pid']} is already active; log: {previous['log']}")
        output = path.parent / f"build-{time.time_ns()}.log"
        command = [sys.executable, str(Path(__file__).resolve().parents[1] / "tasks.py"),
                   "--project", str(project.resolve()), "--tool", "vivado", "--project_mng", action,
                   "--foreground", "--jobs", str(jobs), "--run-timeout", str(timeout)]
        with output.open("w") as handle:
            process = subprocess.Popen(command, cwd=project.parent, stdin=subprocess.DEVNULL,
                                       stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
        write_state(path, {"pid": process.pid, "status": "starting", "action": action,
                           "project": str(console.xpr), "log": str(output)})
    log(f"Process started: {process.pid}\nLog: {output}\nTail: tail -f {shlex.quote(str(output))}")


def monitor(console, follow: bool = False) -> None:
    path = readable_state_path(console)
    if not path.exists():
        log("No managed build has been started for this project.")
        return
    state = json.loads(path.read_text())
    if state.get("status") in {"starting", "running"} and not alive(state.get("pid")):
        state["status"] = "worker exited without a final result; inspect log"
    table(["Field", "Value"], list(state.items()))
    if follow:
        with Path(state["log"]).open() as handle:
            while True:
                text = handle.read()
                if text:
                    print(text, end="", flush=True)
                current = json.loads(path.read_text())
                if current.get("status") not in {"starting", "running"} or not alive(current.get("pid")):
                    print(handle.read(), end="", flush=True)
                    break
                time.sleep(1)
