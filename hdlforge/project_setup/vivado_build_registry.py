"""Locked JSON launch registry under the configured non-project output root."""

from contextlib import contextmanager, redirect_stdout
from datetime import datetime, timezone
import fcntl
import json
import io
import sys
import os
from pathlib import Path
import shlex
import signal
import tempfile
import time
from uuid import uuid4

from table_formatter import create_matrix_table_from_data
from vivado_console.log_analysis import enrich
from vivado_build_config import TIMESTAMP
from vivado_build_processes import alive, find_user_vivado, group_members, local_identity, probe_process, process_info, signal_process, vivado_engine


class BuildStopped(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class BuildRegistry:
    def __init__(self, output_root: Path):
        self.root = output_root.resolve()
        self.path = self.root / "run_registry.json"

    @contextmanager
    def locked(self):
        #######################################################################
        # Lock a separate inode; atomically replace JSON while holding it.     #
        #######################################################################
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".run_registry.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text()) if self.path.exists() else {"version": 1, "runs": {}}
            yield data
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode="w", dir=self.root, delete=False) as handle:
                    temporary = Path(handle.name)
                    json.dump(data, handle, indent=2)
                    handle.write("\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temporary, self.path)
            finally:
                if temporary and temporary.exists():
                    temporary.unlink()

    def register(self, project: Path, config: dict) -> str:
        launch_id = uuid4().hex
        with self.locked() as data:
            parent = config.get("parent_launch_id")
            if parent and data["runs"][parent].get("stop_requested"):
                raise BuildStopped("Continuation cancelled by --stopall")
            output = Path(config["output"])
            data["runs"][launch_id] = {
                "launch_id": launch_id, "project": str(project.resolve()), "selector": config["selector"],
                "stage": config["stage"], "synth_timestamp": config["timestamp"],
                "output": str(output), "run_log": str(output / "runme.log"),
                "vivado_log": str(output / "vivado.log"), "status_file": str(output / "info/status"),
                "host": local_identity(), "launcher": process_info(os.getpid()), "process": None,
                "pid": None, "pid_state": "not_started", "status": "starting", "exit_code": None,
                "started_at": utc_now(), "finished_at": None, "stop_requested": False,
                "auto_impl": config.get("auto_impl"), "parent_launch_id": parent,
            }
            if parent:
                data["runs"][parent].setdefault("next_launch_ids", []).append(launch_id)
        return launch_id

    def update(self, launch_id: str, **values) -> None:
        with self.locked() as data:
            data["runs"][launch_id].update(values)

    def attach(self, launch_id: str, pid: int) -> None:
        with self.locked() as data:
            row = data["runs"][launch_id]
            row.update(pid=pid, process=process_info(pid), pid_state="running", status="running")
            stop = row["stop_requested"]
        if stop:
            raise BuildStopped("Launch cancelled by --stopall")

    def refresh(self) -> list[dict]:
        if not self.path.exists():
            return []
        with self.locked() as data:
            rows = list(data["runs"].values())
            for row in rows:
                row["pid_state"] = probe_process(row.get("process"), row["host"])
                engine = row.get('engine')
                if not engine or not alive(probe_process(engine, row['host'])):
                    engine = vivado_engine(row.get('process'), row['host'])
                row['engine'] = engine
                row['engine_pid'] = engine.get('pid') if engine else None
                row['engine_state'] = probe_process(engine, row['host'])
                row["launcher_state"] = probe_process(row.get("launcher"), row["host"])
                if row["host"] == local_identity():
                    status = Path(row["status_file"])
                    if status.is_file():
                        row["status"] = status.read_text().strip()
                active = alive(row["pid_state"]) or (alive(row["launcher_state"]) and
                         (not row.get("finished_at") or row.get("continuation_pending")))
                row["active"] = active
                if not active and row["pid_state"] != "unavailable" and row["status"] not in {"complete", "failed", "stopped"}:
                    row["status"] = "dead"
                row["probed_at"] = utc_now()
        return rows

    def watch_status(self) -> None:
        """Refresh one terminal viewport; detaching never signals build workers."""
        # The HDLForge wrapper may pipe stdout even in an interactive terminal.
        # Use the controlling terminal directly so redraw sequences reach it.
        try:
            terminal = open('/dev/tty', 'w', buffering=1)
        except OSError:
            self.status()
            return
        with terminal:
            terminal.write('\x1b[?1049h\x1b[?25l')
            try:
                while True:
                    buffer = io.StringIO()
                    with redirect_stdout(buffer):
                        self.status()
                    terminal.write('\x1b[H\x1b[2J' + buffer.getvalue()
                                   + '\nUpdates every 2 seconds after collection. Ctrl-C exits; builds continue.\n')
                    terminal.flush()
                    time.sleep(2)
            except KeyboardInterrupt:
                pass
            finally:
                terminal.write('\x1b[?25h\x1b[?1049l')
                terminal.flush()

    def status(self) -> None:
        rows = self.refresh()
        active = [row for row in rows if row["active"] or row["pid_state"] == "unavailable"]
        if not active:
            print("No active builds")
            return
        analysis = enrich({'records': [
            {'STATUS': 'Running', 'DIRECTORY': row['output'], 'WORKER_RECORD': {
                'pid': row.get('engine_pid'), 'origin': {
                    'host': row['host'].get('host'), 'boot': row['host'].get('boot_id'),
                    'pidns': str(row['host'].get('pid_namespace', '')),
                    'start': (row.get('engine') or {}).get('start_ticks'),
                },
            }} for row in active
        ]})
        details = analysis.get('records', [])
        table = []
        for index, row in enumerate(active):
            detail = details[index] if index < len(details) else {}
            worker = detail.get('WORKER_STATS', {})
            output = Path(row['output'])
            table.append([
                row['selector'], output.name if TIMESTAMP.fullmatch(output.name) else row.get('synth_timestamp', '-'),
                (row.get('launcher') or {}).get('pid', '-'), row.get('pid') or '-', row.get('engine_pid') or '-',
                row.get('stage', '-'), row.get('status', '-'),
                {'S': 'Sleeping', 'R': 'Running', 'D': 'I/O wait', 'T': 'Stopped',
                 't': 'Tracing stop', 'Z': 'Zombie', 'I': 'Idle', 'X': 'Dead'}.get(
                     row.get('engine_state'), row.get('engine_state', '-')),
                '/'.join(str(detail.get(key, '-')) for key in ('WARNINGS', 'CRITICAL_WARNINGS', 'ERRORS')),
                *[detail.get('LOG_' + key, '-') for key in ('WNS', 'TNS', 'WHS', 'THS')],
                detail.get('LOG_PHASE', '-') or '-',
                *[worker.get(key, '-') for key in ('elapsed', 'cpu', 'rss', 'peak', 'threads', 'source')],
                detail.get('LOG_AGE_SECONDS', '-'),
            ])
        print(f"Build status | {utc_now()}")
        print(create_matrix_table_from_data(
            ['Run', 'Timestamp', 'Launcher PID', 'Wrapper PID', 'Vivado PID', 'Stage', 'Status', 'Vivado state', 'W/CW/E', 'WNS(ns)', 'TNS(ns)', 'WHS(ns)', 'THS(ns)', 'Log phase', 'Elapsed', 'CPU time', 'RSS(MB)', 'Peak(MB)', 'Threads', 'Stats source', 'Log idle(s)'],
            table,
        ))
        print("W/CW/E = warnings / critical warnings / errors. Timing = latest log estimates, not timing closure.")
        print("Log idle = seconds without a log update, not CPU inactivity. Log-timer fallback is command-scoped.")
        if analysis.get('analysis_error'):
            print(f"Log analysis unavailable: {analysis['analysis_error']}")
        for detail in details:
            if str(detail.get('LOG_STAGE', '')).startswith('Log unavailable:'):
                print(f"{detail.get('LOG_PATH', '-')}: {detail['LOG_STAGE']}")
        print(f"Follow logs (paths relative to {Path.cwd()}):")
        for row in active:
            log = Path(row.get('run_log', str(Path(row['output']) / 'runme.log')))
            command = shlex.join(['tail', '-n', '50', '-f', '--', os.path.relpath(log, Path.cwd())])
            print(f"  {row['selector']}:\n    {command}")


    def discover(self) -> None:
        rows = self.refresh()
        known = {row["pid"]: row["launch_id"] for row in rows if alive(row["pid_state"])}
        processes = find_user_vivado()
        for process in processes:
            process["launch_id"] = known.get(process["pid"])
            process["registered"] = process["pid"] in known
        print(json.dumps({"registry": str(self.path), "processes": processes}, indent=2))

    def stop_all(self, output: str | None = None) -> None:
        #######################################################################
        # Mark cancellation before signals so exact-timestamp chains stop too. #
        #######################################################################
        if not self.path.exists():
            print("No registered launches")
            self.discover()
            return
        with self.locked() as data:
            rows = []
            for row in data["runs"].values():
                if output is not None and row.get("output") != output:
                    continue
                live_process = alive(probe_process(row.get("process"), row["host"]))
                live_owner = alive(probe_process(row.get("launcher"), row["host"]))
                if live_process or (live_owner and (not row.get("finished_at") or row.get("continuation_pending"))):
                    row["stop_requested"] = True
                    row["status"] = "stopping"
                    rows.append(dict(row))
        owners = set()
        for row in rows:
            row["group_members"] = group_members(row.get("process"), row["host"])
            signal_process(row.get("process"), row["host"], signal.SIGTERM, group=True)
            owner = row.get("launcher")
            if owner and owner["pid"] not in owners:
                signal_process(owner, row["host"], signal.SIGTERM)
                owners.add(owner["pid"])
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            if not any(alive(probe_process(row.get(key), row["host"])) for row in rows for key in ("process", "launcher")):
                break
            time.sleep(0.1)
        for row in rows:
            signal_process(row.get("process"), row["host"], signal.SIGKILL, group=True)
            for member in row.get("group_members", []):
                signal_process(member, row["host"], signal.SIGKILL)
            signal_process(row.get("launcher"), row["host"], signal.SIGKILL)
            self.update(row["launch_id"], status="stopped", finished_at=utc_now(), continuation_pending=False)
            path = Path(row["status_file"])
            if path.parent.is_dir():
                path.write_text("stopped\n")
        print(f"Stop requested for {len(rows)} registered launches")
        self.discover()  # Also report any remaining unregistered Vivado processes.
