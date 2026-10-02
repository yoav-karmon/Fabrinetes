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
from vivado_build_log import enrich
from vivado_build_artifacts import cleanable
from vivado_build_layout import descendant_runs, read_run, run_directories, write_run
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
    """Identify both selected attempts using the resolved timestamps."""
    if row.get('build_selection'):
        return row['build_selection']
    synthesis, _, implementation = row['selector'].partition('.')
    stamp = row.get('synth_timestamp') or '-'
    selection = f'{synthesis}.{stamp}'
    if row.get('stage') == 'impl':
        attempt = row.get('run_id', '-')
        selection += f'.{implementation}.{attempt}'
    return selection


def unobserved_run(row: dict) -> bool:
    """Keep uncertain workers visible without resurrecting completed launches."""
    finished = row.get('finished_at') or row.get('status') in {'complete', 'failed', 'stopped'}
    return row['pid_state'] == 'unavailable' and (not finished or row.get('continuation_pending', False))


def artifact_protection(output: str) -> str:
    """Report cleanup protection using the cleanup command's own Git rules."""
    folder = Path(output)
    try:
        folder.stat()
        allowed, _ = cleanable(folder)
        return 'No' if allowed else 'Yes'
    except FileNotFoundError:
        return 'Missing'
    except (OSError, ValueError):
        return 'Unknown'


class BuildRegistry:
    def __init__(self, output_root: Path):
        self.root = output_root.resolve()
        self.path = self.root / "_run_registry.json"

    @contextmanager
    def locked(self):
        #######################################################################
        # Lock a separate inode; atomically replace JSON while holding it.     #
        #######################################################################
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / "_run_registry.lock").open("a") as lock:
            fcntl.flock(lock, fcntl.LOCK_EX)
            data = json.loads(self.path.read_text()) if self.path.exists() else {"version": 1, "runs": {}}
            # The global file is an index; execution records live in manifests.
            if data.get('version') == 2:
                locations = {}
                for definition in self.root.iterdir():
                    if definition.is_dir() and not definition.is_symlink():
                        for parent in run_directories(definition):
                            for folder in descendant_runs(parent):
                                record = read_run(folder)
                                if record.get('launch_id'):
                                    locations[record['launch_id']] = folder
                records = {}
                for launch_id, location in data['runs'].items():
                    if isinstance(location, dict):
                        records[launch_id] = location
                        continue
                    folder = locations.get(launch_id, self.root / location)
                    try:
                        record = read_run(folder)
                        row = record['execution']
                    except (OSError, ValueError, KeyError):
                        continue
                    row.update(output=str(folder), run_log=str(folder / 'build.log'),
                               vivado_log=str(folder / 'build.log'), status_file=str(folder / 'manifest.json'))
                    row['status'] = record.get('status', row.get('status'))
                    row['exit_code'] = record.get('exit_code', row.get('exit_code'))
                    row['finished_at'] = record.get('finished_at')
                    records[launch_id] = row
                data = {'version': 1, 'runs': records}
            previous = json.loads(json.dumps(data['runs']))
            yield data
            index = {}
            for launch_id, row in data['runs'].items():
                folder = Path(row['output'])
                manifest = folder / 'manifest.json'
                if not manifest.is_file():
                    index[launch_id] = row  # Preserve read-only historical/unobservable launches.
                    continue
                if row != previous.get(launch_id):
                    execution = {key: value for key, value in row.items()
                                 if key not in {'status', 'exit_code', 'finished_at'}}
                    values = {'execution': execution}
                    for key in ('status', 'exit_code', 'finished_at'):
                        if row.get(key) != previous.get(launch_id, {}).get(key):
                            values[key] = row.get(key)
                    write_run(folder, values)
                index[launch_id] = os.path.relpath(folder, self.root)
            data = {'version': 2, 'runs': index}
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
                "launch_id": launch_id, "run_id": config["run_id"], "project": str(project.resolve()), "selector": config["selector"],
                "stage": config["stage"], "synth_timestamp": config["synthesis_run_id"],
                "build_selection": config.get('build_selection'),
                "output": str(output), "run_log": str(output / "build.log"),
                "vivado_log": str(output / "build.log"), "status_file": str(output / "manifest.json"),
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
            locations = {}
            for definition in self.root.iterdir():
                if not definition.is_dir() or definition.is_symlink():
                    continue
                for parent in run_directories(definition):
                    for folder in descendant_runs(parent):
                        config = read_run(folder)
                        locations[config['run_id']] = folder
            for row in rows:
                if row.get('run_id') in locations:
                    current = locations[row['run_id']]
                    config = read_run(current)
                    modern = config.get('format_version') == 3
                    row.update(output=str(current),
                               run_log=str(current / ('build.log' if modern else 'logs/runme.log')),
                               vivado_log=str(current / ('build.log' if modern else 'logs/vivado.log')),
                               status_file=str(current / ('manifest.json' if modern else 'logs/status')))
                    if not modern and row['host'] == local_identity():
                        row['status'] = config.get('status', row['status'])
                        row['exit_code'] = config.get('exit_code', row.get('exit_code'))
                row["pid_state"] = probe_process(row.get("process"), row["host"])
                engine = row.get('engine')
                if not engine or not alive(probe_process(engine, row['host'])):
                    engine = vivado_engine(row.get('process'), row['host'])
                row['engine'] = engine
                row['engine_pid'] = engine.get('pid') if engine else None
                row['engine_state'] = probe_process(engine, row['host'])
                row["launcher_state"] = probe_process(row.get("launcher"), row["host"])
                active = alive(row["pid_state"]) or (alive(row["launcher_state"]) and
                         (not row.get("finished_at") or row.get("continuation_pending")))
                row["active"] = active
                if not active and row["pid_state"] != "unavailable" and row["status"] not in {"complete", "failed", "stopped"}:
                    row["status"] = "dead"
                row["probed_at"] = utc_now()
            # Keep launch chains while workers can still update their registry rows.
            retained = {row['launch_id'] for row in rows if row['active'] or alive(row['engine_state'])}
            for launch_id in list(retained):
                parent = data['runs'][launch_id].get('parent_launch_id')
                while parent and parent not in retained and parent in data['runs']:
                    retained.add(parent)
                    parent = data['runs'][parent].get('parent_launch_id')
            local = local_identity()
            for row in rows:
                host = row['host']
                previous_boot = host.get('host') == local['host'] and host.get('boot_id') and host['boot_id'] != local['boot_id']
                known_inactive = previous_boot or (host == local and all(row[key] != 'unavailable' for key in ('pid_state', 'launcher_state', 'engine_state')))
                output = Path(row['output'])
                if row['launch_id'] in retained or not known_inactive or not output.is_relative_to(self.root):
                    continue
                try:
                    output.stat()
                except FileNotFoundError:
                    del data['runs'][row['launch_id']]
                except OSError:
                    pass  # Inaccessible storage is not evidence of deletion.
            rows = list(data['runs'].values())
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
            rows = [row for row in rows if row['active'] or unobserved_run(row)]
        if not rows:
            print("No registered builds" if all_runs else "No active builds")
            return
        rows.sort(key=lambda row: (not row['active'], row.get('started_at', '')))
        analysis = enrich({'records': [
            # Running enables log enrichment; the registry status stays authoritative.
            {'STATUS': 'Running', 'DIRECTORY': str(Path(row['output']) / 'logs'), 'WORKER_RECORD': {
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
                thread_activity(row.get('engine'), row['host']) if row['active'] else ('Unavailable' if unobserved_run(row) else 'Exited'),
                '/'.join(str(detail.get(key, '-')) for key in ('WARNINGS', 'CRITICAL_WARNINGS', 'ERRORS')),
                *[detail.get('LOG_' + key, '-') for key in ('WNS', 'TNS', 'WHS', 'THS')],
                detail.get('LOG_PHASE', '-') or '-',
                launch_elapsed(row),
                *[worker.get(key, '-') for key in ('rss', 'peak', 'threads')],
                detail.get('LOG_AGE_SECONDS', '-') if row['active'] else '-',
                artifact_protection(row['output']),
            ])
        print(f"Build status | {utc_now()}")
        print(create_matrix_table_from_data(
            ['Run', 'Vivado PID', 'Stage', 'Status', 'Vivado state', 'W/CW/E', 'WNS(ns)', 'TNS(ns)', 'WHS(ns)', 'THS(ns)', 'Log phase', 'Elapsed', 'RAM used(MB)', 'Peak RAM(MB)', 'Threads', 'Log idle(s)', 'Protected'],
            table,
        ))
        print('Protected = tracked files or Git-ignore cleanup exceptions (Yes/No); Missing/Unknown means protection could not be evaluated.')
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
            log = Path(row.get('run_log', str(Path(row['output']) / 'build.log')))
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
            path = Path(row['output'])
            if (path / 'manifest.json').is_file():
                write_run(path, {'status': 'stopped', 'exit_code': 130, 'finished_at': utc_now()})
            elif (path / 'logs').is_dir():
                (path / 'logs/status').write_text('stopped\n')
        print(f"Stop requested for {len(rows)} registered launches")
        self.discover()  # Also report any remaining unregistered Vivado processes.
