"""Detached serial-build workers and local status/log monitoring."""

import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time

from .terminal_output import log, table
from .build_progress import plan_entry, show_plan, show_summary, update_entry
from .run_group_menu import selected_runs
from .run_enable import blocked


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
    except PermissionError:
        return True


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
                           "project": str(console.xpr), "log": str(output), "started_at": time.time()})
    log(f"Process started: {process.pid}\nLog: {output}\nTail: tail -f {shlex.quote(str(output))}")


def monitor(console, follow: bool = False, read_runs=None) -> None:
    path = readable_state_path(console)
    if not path.exists():
        log("No managed build has been started for this project.")
        return
    state = json.loads(path.read_text())
    if state.get("status") in {"starting", "running"} and not alive(state.get("pid")):
        state["status"] = "worker exited without a final result; inspect log"
    if read_runs and state.get("status") in {"starting", "running"}:
        try:
            live = read_runs()
            if not state.get("runs"):
                sequence, _ = selected_runs(state["action"], live)
                state["runs"] = [plan_entry(run) for run in sequence]
            for item in state.get("runs", []):
                run = next((run for run in live if run["name"] == item["name"]), None)
                if run is None:
                    continue
                properties = run["properties"]
                status = properties.get("STATUS", "").lower()
                result = item["state"]
                if blocked(run, live):
                    result = "skipped: disabled"
                elif any(word in status for word in ("running", "queued", "launching")):
                    result = "running"
                elif any(word in status for word in ("error", "fail", "cancel", "abort")):
                    result = "failed"
                elif properties.get("PROGRESS") == "100%" and properties.get("NEEDS_REFRESH", "0").lower() in {"0", "false"}:
                    target = item["stages"][-1]
                    if target in status or "using cached ip results" in status:
                        result = "current results" if result == "pending" else result
                # Do not infer completion from an intermediate implementation step.
                update_entry(item, run, result)
            state["observation"] = "Live Vivado run status"
            running = next((item for item in state.get("runs", []) if item["state"] == "running"), None)
            if running:
                state["phase"] = f"Building {running['name']}: {running.get('status', '')}"
            state["next_run"] = next((item["name"] for item in state.get("runs", []) if item["state"] == "pending"), "None pending")
        except (RuntimeError, ValueError, OSError) as error:
            state["observation"] = f"Saved worker report; live query unavailable: {error}"
    fields = {key: value for key, value in state.items() if key != "runs"}
    for key in ("started_at", "updated_at", "finished_at"):
        if key in fields:
            fields[key] = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime(fields[key]))
    show_summary(fields, state)
    show_plan(state)
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
