"""Discover build workers from attempt manifests in configured run folders."""

from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timezone
import json
import io
import sys
import os
from pathlib import Path
import shlex
import signal
import time
from uuid import uuid4

from table_formatter import create_matrix_table_from_data
from vivado_build_log import enrich
from vivado_build_artifacts import cleanable
from vivado_build_config import project_attempts, synthesis_folder
from vivado_build_layout import edit_run, read_run, write_run
from vivado_build_processes import alive, find_user_vivado, group_members, local_identity, probe_process, process_info, signal_process, thread_activity, vivado_engine
from vivado_run_tree import discover_runs, run_tree


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
    """Use the current JSON hierarchy with the attempts' saved identities."""
    synthesis, implementation = row['selector'], ''
    if row.get('stage') in {'impl', 'bitstream'}:
        synthesis, _, implementation = row['selector'].rpartition('.')
    current = row.get('current_synthesis', synthesis)
    if row.get('build_selection'):
        selection = row['build_selection']
        return current + selection[len(synthesis):] if selection.startswith(synthesis + '.') else selection
    stamp = row.get('synth_timestamp') or '-'
    selection = f'{current}.{stamp}'
    if row.get('stage') == 'impl':
        attempt = row.get('run_id', '-')
        selection += f'.{implementation}.{attempt}'
    return selection


def unobserved_run(row: dict) -> bool:
    """Keep uncertain workers visible without resurrecting completed launches."""
    finished = row.get('finished_at') or row.get('status') in {'complete', 'failed', 'stopped'}
    return row['pid_state'] == 'unavailable' and (not finished or row.get('continuation_pending', False))


def status_hierarchy(rows: list[dict]) -> list[tuple[dict, str]]:
    ###########################################################################
    # Keep each synthesis attempt directly above its implementations, including
    # manually launched children without parent_launch_id. Active groups lead.
    ###########################################################################
    groups = {}
    for row in rows:
        synthesis = row['selector']
        if row.get('stage') in {'impl', 'bitstream'}:
            synthesis = synthesis.rpartition('.')[0]
        key = (row.get('current_synthesis', synthesis), row.get('synth_timestamp') or row.get('run_id', '-'))
        groups.setdefault(key, []).append(row)
    ordered = sorted(groups.values(), key=lambda group: (
        not any(row.get('active') for row in group),
        min(row.get('started_at', '') for row in group),
        run_selection(group[0]),
    ))
    result = []
    for group in ordered:
        group.sort(key=lambda row: (row.get('stage') != 'synth', row.get('started_at', ''), run_selection(row)))
        parent = next((row for row in group if row.get('stage') == 'synth'), None)
        prefix = run_selection(parent) + '.' if parent else ''
        for row in group:
            label = run_selection(row)
            if row is not parent and prefix and label.startswith(prefix):
                # Expand one indentation level to spaces so table columns align.
                label = '    ' + label[len(prefix):]
            result.append((row, label))
    return result


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
    def __init__(self, project: Path):
        self.project = project.resolve()
        self.locations = {}

    def records(self) -> list[dict]:
        """Read attempt-local execution state; status never rewrites manifests."""
        data = json.loads(self.project.read_text())
        settings = data.get('vivado', {}).get('non_project', {})
        roots = {synthesis_folder(self.project, settings, name): name for name in discover_runs(run_tree(data))}
        rows = []
        for folder in project_attempts(self.project, data):
            try:
                config = read_run(folder)
                row = dict(config['execution'])
            except (FileNotFoundError, KeyError):
                continue  # A queued or historical attempt may have no worker yet.
            # The configured script folder owns historical attempts after JSON regrouping.
            current = next((roots[parent] for parent in folder.parents if parent in roots), None)
            if current is not None:
                row['current_synthesis'] = current
            modern = config.get('format_version') == 3
            row.update(output=str(folder),
                       run_log=str(folder / ('build.log' if modern else 'logs/runme.log')),
                       vivado_log=str(folder / ('build.log' if modern else 'logs/vivado.log')),
                       status_file=str(folder / 'manifest.json'))
            for key in ('status', 'exit_code', 'finished_at'):
                row[key] = config.get(key, row.get(key))
            self.locations[row['launch_id']] = folder
            rows.append(row)
        return rows

    def folder(self, launch_id: str) -> Path:
        """Workers cache their own location; discovery also handles renamed attempts."""
        folder = self.locations.get(launch_id)
        if folder is None or not folder.is_dir():
            self.records()
            folder = self.locations.get(launch_id)
        if folder is None or not folder.is_dir():
            raise ValueError(f'Attempt for launch {launch_id} is no longer discoverable')
        return folder

    def register(self, project: Path, config: dict) -> str:
        launch_id = uuid4().hex
        output = Path(config['output'])
        parent = config.get('parent_launch_id')
        # Lock parent before child: registration and cancellation cannot cross.
        guard = edit_run(self.folder(parent)) if parent else nullcontext(None)
        with guard as parent_record:
            if parent_record and parent_record['execution'].get('stop_requested'):
                raise BuildStopped('Continuation cancelled by --stopall')
            row = {
                'launch_id': launch_id, 'run_id': config['run_id'], 'project': str(project.resolve()),
                'selector': config['selector'], 'stage': config['stage'],
                'synth_timestamp': config['synthesis_run_id'], 'build_selection': config.get('build_selection'),
                'output': str(output), 'run_log': str(output / 'build.log'),
                'host': local_identity(), 'launcher': process_info(os.getpid()), 'process': None,
                'pid': None, 'pid_state': 'not_started', 'started_at': utc_now(), 'stop_requested': False,
                'auto_impl': config.get('auto_impl'), 'parent_launch_id': parent,
            }
            write_run(output, dict(config, launch_id=launch_id, execution=row,
                                   status='starting', exit_code=None, finished_at=None))
            if parent_record is not None:
                parent_record['execution'].setdefault('next_launch_ids', []).append(launch_id)
        self.locations[launch_id] = output
        return launch_id

    def update(self, launch_id: str, **values) -> None:
        with edit_run(self.folder(launch_id)) as config:
            config['execution'].update({key: value for key, value in values.items()
                                        if key not in {'status', 'exit_code', 'finished_at'}})
            config.update({key: value for key, value in values.items()
                           if key in {'status', 'exit_code', 'finished_at'}})

    def attach(self, launch_id: str, pid: int) -> None:
        folder = self.folder(launch_id)
        parent = read_run(folder)['execution'].get('parent_launch_id')
        guard = edit_run(self.folder(parent)) if parent else nullcontext(None)
        with guard as parent_record:
            with edit_run(folder) as config:
                row = config['execution']
                row.update(pid=pid, process=process_info(pid), pid_state='running')
                stop = row['stop_requested'] or bool(parent_record and parent_record['execution'].get('stop_requested'))
                row['stop_requested'] = stop
                config['status'] = 'stopping' if stop else 'running'
        if stop:
            raise BuildStopped('Launch cancelled by --stopall')

    def refresh(self) -> list[dict]:
        rows = self.records()
        for row in rows:
            row['pid_state'] = probe_process(row.get('process'), row['host'])
            engine = row.get('engine')
            if not engine or not alive(probe_process(engine, row['host'])):
                engine = vivado_engine(row.get('process'), row['host'])
            row['engine'] = engine
            row['engine_pid'] = engine.get('pid') if engine else None
            row['engine_state'] = probe_process(engine, row['host'])
            row['launcher_state'] = probe_process(row.get('launcher'), row['host'])
            active = alive(row['pid_state']) or (alive(row['launcher_state']) and
                     (not row.get('finished_at') or row.get('continuation_pending')))
            row['active'] = active
            if not active and row['pid_state'] != 'unavailable' and row['status'] not in {'complete', 'failed', 'stopped'}:
                row['status'] = 'dead'
            row['probed_at'] = utc_now()
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
        displayed = status_hierarchy(rows) if all_runs else [(row, run_selection(row)) for row in rows]
        rows = [row for row, _ in displayed]
        analysis = enrich({'records': [
            # Running enables log enrichment; the registry status stays authoritative.
            {'STATUS': 'Running', 'DIRECTORY': str(Path(row.get('run_log', str(Path(row['output']) / 'build.log'))).parent), 'WORKER_RECORD': {
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
                displayed[index][1],
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
        if analysis.get('analysis_error'):
            print(f"Log analysis unavailable: {analysis['analysis_error']}")
        for detail in details:
            if str(detail.get('LOG_STAGE', '')).startswith('Log unavailable:'):
                print(f"{detail.get('LOG_PATH', '-')}: {detail['LOG_STAGE']}")
        if all_runs:
            return
        print("W/CW/E = warnings / critical warnings / errors. Timing = latest log estimates, not timing closure.")
        print("Elapsed = wall time since launch. RAM used = Vivado resident memory (RSS).")
        print("Vivado state samples all engine threads; Waiting means none was runnable at that instant.")
        print("Log idle = seconds without a log update, not CPU inactivity.")
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
        print(json.dumps({"project": str(self.project), "processes": processes}, indent=2))

    def stop_all(self, output: str | None = None) -> None:
        #######################################################################
        # Mark cancellation before signals so exact-timestamp chains stop too. #
        #######################################################################
        rows = []
        for observed in self.records():
            if output is not None and observed['output'] != output:
                continue
            folder = Path(observed['output'])
            with edit_run(folder) as config:
                row = config['execution']
                live_process = alive(probe_process(row.get('process'), row['host']))
                live_owner = alive(probe_process(row.get('launcher'), row['host']))
                if live_process or (live_owner and (not config.get('finished_at') or row.get('continuation_pending'))):
                    row['stop_requested'] = True
                    config['status'] = 'stopping'
                    rows.append(dict(row, output=str(folder)))
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
