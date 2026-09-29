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
from vivado_build_processes import alive, find_user_vivado, group_members, local_identity, probe_process, process_info, signal_process, thread_activity, vivado_engine


class BuildStopped(Exception):
    pass


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def launch_elapsed(row: dict) -> str:
    """Show wall time since registration, independent of process/log timers."""
    if not row.get('active') and not row.get('finished_at'):
        return '-'  # An unobserved exit has no reliable end time.
    try:
        started = datetime.fromisoformat(row['started_at'])
        finished = datetime.fromisoformat(row['finished_at']) if row.get('finished_at') else datetime.now(timezone.utc)
        seconds = max(0, int((finished - started).total_seconds()))
    except (KeyError, TypeError, ValueError):
        return '-'
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    return f'{hours:02d}:{minutes:02d}:{seconds:02d}'


def run_selection(row: dict) -> str:
    """Identify both selected attempts, retaining literal latest selections."""
    if row.get('build_selection'):
        return row['build_selection']
    synthesis, _, implementation = row['selector'].partition('.')
    stamp = row.get('synth_timestamp') or '-'
    selection = f'{synthesis}.{stamp}'
    if row.get('stage') == 'impl':
        attempt = Path(row['output']).name
        if attempt != 'latest' and not TIMESTAMP.fullmatch(attempt):
            attempt = '-'  # Legacy implementation folders had no attempt date.
        selection += f'.{implementation}.{attempt}'
    return selection


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
                "build_selection": config.get('build_selection'),
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
                if row["host"] == local_identity() and not row.get('finished_at'):
                    # A rerun can replace this path; retain completed launch history.
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

    def watch_status(self, *, all_runs: bool = False) -> None:
        """Refresh one terminal viewport; detaching never signals build workers."""
        # The HDLForge wrapper may pipe stdout even in an interactive terminal.
        # Use the controlling terminal directly so redraw sequences reach it.
        try:
            terminal = open('/dev/tty', 'w', buffering=1)
        except OSError:
            self.status(all_runs=all_runs)
            return
        with terminal:
            terminal.write('\x1b[?1049h\x1b[?25l')
            try:
                while True:
                    buffer = io.StringIO()
                    with redirect_stdout(buffer):
                        self.status(all_runs=all_runs)
                    terminal.write('\x1b[H\x1b[2J' + buffer.getvalue()
                                   + '\nUpdates every 2 seconds after collection. Ctrl-C exits; builds continue.\n')
                    terminal.flush()
                    time.sleep(2)
            except KeyboardInterrupt:
                pass
            finally:
                terminal.write('\x1b[?25h\x1b[?1049l')
                terminal.flush()

    def status(self, *, all_runs: bool = False) -> None:
        rows = self.refresh()
        if not all_runs:
            rows = [row for row in rows if row['active'] or row['pid_state'] == 'unavailable']
        if not rows:
            print("No registered builds" if all_runs else "No active builds")
            return
        rows.sort(key=lambda row: (not row['active'], row.get('started_at', '')))
        analysis = enrich({'records': [
            # Running enables log enrichment; the registry status stays authoritative.
            {'STATUS': 'Running', 'DIRECTORY': row['output'], 'WORKER_RECORD': {
                'pid': row.get('engine_pid'), 'origin': {
                    'host': row['host'].get('host'), 'boot': row['host'].get('boot_id'),
                    'pidns': str(row['host'].get('pid_namespace', '')),
                    'start': (row.get('engine') or {}).get('start_ticks'),
                },
            }} for row in rows
        ]})
        details = analysis.get('records', [])
        table = []
        for index, row in enumerate(rows):
            detail = details[index] if index < len(details) else {}
            worker = detail.get('WORKER_STATS', {})
            table.append([
                run_selection(row),
                row.get('engine_pid') or '-',
                row.get('stage', '-'), row.get('status', '-'),
                thread_activity(row.get('engine'), row['host']) if row['active'] or row['pid_state'] == 'unavailable' else 'Exited',
                '/'.join(str(detail.get(key, '-')) for key in ('WARNINGS', 'CRITICAL_WARNINGS', 'ERRORS')),
                *[detail.get('LOG_' + key, '-') for key in ('WNS', 'TNS', 'WHS', 'THS')],
                detail.get('LOG_PHASE', '-') or '-',
                launch_elapsed(row),
                *[worker.get(key, '-') for key in ('rss', 'peak', 'threads')],
                detail.get('LOG_AGE_SECONDS', '-') if row['active'] else '-',
            ])
        print(f"Build status | {utc_now()}")
        print(create_matrix_table_from_data(
            ['Run', 'Vivado PID', 'Stage', 'Status', 'Vivado state', 'W/CW/E', 'WNS(ns)', 'TNS(ns)', 'WHS(ns)', 'THS(ns)', 'Log phase', 'Elapsed', 'RAM used(MB)', 'Peak RAM(MB)', 'Threads', 'Log idle(s)'],
            table,
        ))
        if all_runs:
            return
        print("W/CW/E = warnings / critical warnings / errors. Timing = latest log estimates, not timing closure.")
        print("Elapsed = wall time since launch. RAM used = Vivado resident memory (RSS).")
        print("Vivado state samples all engine threads; Waiting means none was runnable at that instant.")
        print("Log idle = seconds without a log update, not CPU inactivity.")
        if analysis.get('analysis_error'):
            print(f"Log analysis unavailable: {analysis['analysis_error']}")
        for detail in details:
            if str(detail.get('LOG_STAGE', '')).startswith('Log unavailable:'):
                print(f"{detail.get('LOG_PATH', '-')}: {detail['LOG_STAGE']}")
        print(f"Follow logs (paths relative to {Path.cwd()}):")
        for row in rows:
            log = Path(row.get('run_log', str(Path(row['output']) / 'runme.log')))
            command = shlex.join(['tail', '-n', '50', '-f', '--', os.path.relpath(log, Path.cwd())])
            print(f"  {run_selection(row)}:\n    {command}")


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
