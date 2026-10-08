"""Launch a non-project Vivado run described by the selected project JSON."""

from contextlib import redirect_stdout, redirect_stderr
import argparse
import copy
import glob
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import signal
import subprocess
import sys

from vivado_build_config import BUILD_HELP, ARTIFACT_FLAGS, build_names, synthesis_folder
from vivado_build_artifacts import manage_artifacts
from vivado_build_registry import BuildRegistry, BuildStopped, utc_now
from vivado_build_paths import resolve_latest_path
from vivado_build_follow import background_follow
from vivado_build_selector import parse_selector, resolve_selector, selected_run_folder
from vivado_build_snapshot import implementation_definition, snapshot_inputs
from vivado_build_hash import record_source_hashes, hash_source
from vivado_build_layout import run_lock_path, CONFIG, find_run, read_run, write_run, new_identity, new_label, verify_checkpoint, metadata_path
from vivado_build_bitstream import select_bitstream, lock_implementation, snapshot_bitstream
from vivado_build_processes import group_members, local_identity, process_info, signal_process


def file_path(root: Path, value: str, selections: dict | None = None) -> str:
    resolved = resolve_latest_path(root / value, selections)
    if glob.has_magic(value) and not resolved.is_file():
        matches = [Path(path) for path in glob.glob(str(resolved), recursive=True) if Path(path).is_file()]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one input matching {value}; found {len(matches)}. Build the producer first if its latest output is missing.")
        return str(matches[0].resolve())
    path = resolved.resolve()
    if not path.is_file():
        raise ValueError(f"Missing input file: {path}")
    return str(path)


def normalize_run(project: Path, run: dict, stage: str, selections: dict | None = None) -> dict:
    ###########################################################################
    # Resolve input file paths before claiming the output directory.           #
    ###########################################################################
    config = copy.deepcopy(run)
    selections = selections if selections is not None else {}
    unknown = set(config) - {"script", "sources", "impl_runs", "kind"}
    if unknown:
        raise ValueError(f"Unknown run settings: {sorted(unknown)}; design settings belong in run.tcl")
    config.pop("impl_runs", None)
    if config.get("kind", "synth") not in {"synth", "ip"}:
        raise ValueError("kind must be synth or ip")
    if stage == "ip" and run.get("impl_runs"):
        raise ValueError("IP builds cannot have implementation runs")
    config["script_name"] = config["script"]
    config["stage"] = stage
    config.pop("kind", None)
    root = project.parent
    config["script"] = file_path(root, config["script"], selections)
    if not isinstance(config.get("sources", []), list):
        raise ValueError("sources must be an array of snapshot file paths")
    entries = []
    for source in config.get("sources", []):
        if not isinstance(source, str) or not source:
            raise ValueError("sources entries must be nonempty file paths; read options belong in run.tcl")
        entries.append({"name": source, "path": file_path(root, source, selections)})
    config["sources"] = entries
    return config


def prepare_run_config(project: Path, selector: str, timestamp: str | None = None) -> dict:
    """Resolve the requested build inputs and calculate attempt paths without creating files."""
    project = project.resolve()
    selector = resolve_selector(project, selector)
    parsed = parse_selector(selector)
    if not parsed or parsed['action'] != 'run':
        raise ValueError('Select a fresh .run action; attempts cannot be rerun')
    if parsed and timestamp is not None:
        raise ValueError('Use the parent selection in the build selector, not --synth_timestamp as well')
    if parsed and parsed.get('bitstream'):
        return select_bitstream(project, parsed)
    data = json.loads(project.read_text())
    settings = data['vivado']['non_project']
    synthesis, _, implementation = selector.partition('.')
    if parsed:
        synthesis, implementation = parsed['run'], parsed['impl']
        timestamp = parsed['synth']
    if synthesis not in settings['runs']:
        raise ValueError(f'Unknown synthesis/IP run: {synthesis}')
    definition = settings['runs'][synthesis]
    if implementation:
        parent = find_run(synthesis_folder(project, settings, synthesis), timestamp or 'latest', synthesis)
        parent_config = read_run(parent)
        checkpoint = parent / 'artifacts' / f"{parent_config.get('top', 'top')}.dcp"
        if not checkpoint.is_file():
            raise ValueError(f'Missing synthesis checkpoint: {checkpoint}')
        saved_project, selected = implementation_definition(parent, parent_config, synthesis, implementation)
        config = normalize_run(saved_project, selected, 'impl')
        prepared_snapshot = parent / 'impl_runs' / implementation / 'snapshot'
        config['snapshot_root'] = str(prepared_snapshot)
        config['project_root'] = str(prepared_snapshot / saved_project.parent.relative_to(parent / 'snapshot'))
        saved_data = json.loads(saved_project.read_text())
        declared = saved_data['vivado']['non_project']['runs'][synthesis]['impl_runs'][implementation]
        config['script_name'] = declared['script']
        for entry, name in zip(config['sources'], declared.get('sources', [])):
            entry['name'] = name
        config.update(project_file=str(saved_project), project_sha256=hash_source(saved_project))
        config.update(parent_top=parent_config['top'], parent_part=parent_config['part'])
        checkpoint = parent / 'artifacts' / f"{parent_config['top']}.dcp"
        config.update(input_dcp=str(checkpoint), input_dcp_sha256=hash_source(checkpoint),
                      parent_run_id=parent_config['run_id'], synthesis_run_id=parent_config['run_id'])
        output = parent / 'impl_runs' / implementation / new_label()
    else:
        if timestamp not in (None, 'new'):
            raise ValueError('Use RUN.run to create a synthesis attempt')
        config = normalize_run(project, definition, definition.get('kind', 'synth'))
        config['implementation_configs'] = {
            name: normalize_run(project, child, 'impl')
            for name, child in definition.get('impl_runs', {}).items()
        }
        output = synthesis_folder(project, settings, synthesis) / new_label()
        config.update(input_dcp='', project_file=str(project), project_sha256=hash_source(project))
    config.update(new_identity())
    config.setdefault('synthesis_run_id', config['run_id'])
    config['timestamp'] = config['created_at']
    config.setdefault('project_root', str(project.parent))
    config.update(output=str(output),
                  selector=synthesis + ('.' + implementation if implementation else ''),
                  vivado_version=(saved_data['vivado']['non_project'] if implementation else settings).get('vivado_version', ''))
    return config


def execute(project: Path, config: dict, executable: str = "vivado") -> int:
    if config['stage'] == 'bitstream':
        with lock_implementation(config):
            return execute_attempt(project, config, executable)
    if config['stage'] == 'impl':
        parent = Path(config['input_dcp']).parent.parent
        with run_lock_path(parent, read_run(parent)["run_id"]).open('a') as lock:
            # Keep the parent checkpoint protected from cleanup during use.
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            return execute_attempt(project, config, executable)
    return execute_attempt(project, config, executable)


class BuildLog:
    """Tee launcher messages and tool output into one persistent attempt log."""
    def __init__(self, stream, terminal):
        self.stream, self.terminal = stream, terminal

    def write(self, text):
        self.stream.write(text)
        self.stream.flush()
        self.terminal.write(text)
        return len(text)

    def flush(self):
        self.stream.flush()
        self.terminal.flush()


def execute_attempt(project: Path, config: dict, executable: str = "vivado") -> int:
    """Claim a fresh attempt exactly once, preserving all previous attempts."""
    output = Path(config['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    try:
        output.mkdir()
        created = True
    except FileExistsError:
        created = False
    with run_lock_path(output, config["run_id"]).open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise ValueError(f'Attempt already active: {output}') from None
        if not created:
            saved = read_run(output)
            if saved.get('status') != 'queued' or saved['run_id'] != config['run_id']:
                raise ValueError(f'Attempt already exists; use .run for a fresh attempt: {output}')
        write_run(output, dict(config, status='starting'))
        with (output / 'build.log').open('a', buffering=1) as stream:
            with redirect_stdout(BuildLog(stream, sys.stdout)), redirect_stderr(BuildLog(stream, sys.stderr)):
                try:
                    return execute_locked(project, config, executable)
                except BaseException as error:
                    write_run(output, {'status': 'failed', 'exit_code': 1, 'failure': str(error)})
                    print(f'Build failed: {error}', flush=True)
                    raise


def runtime_event(line: str, config: dict) -> bool:
    """Consume Tcl events; only this runner publishes tool metadata."""
    if not line.startswith('HDLFORGE_EVENT\t'):
        return False
    _, kind, *fields = line.rstrip('\n').split('\t')
    values = [bytes.fromhex(field).decode('utf-8') for field in fields]
    if kind == 'stage':
        time, event, stage, elapsed, command = values
        config.setdefault('stages', []).append(dict(time=time, event=event, stage=stage,
                                                    elapsed_seconds=float(elapsed) if elapsed else None, command=command))
    elif kind == 'bitstream_timestamp':
        config[kind] = dict(launch_epoch=int(values[0]), userid=values[1])
    elif kind in {'status', 'top', 'part', 'last_routed_checkpoint', 'tool_version', 'failure'}:
        config[kind] = values[0]
    else:
        raise ValueError(f'Unknown Tcl event: {kind}')
    write_run(Path(config['output']), {key: config[key] for key in
              ('status', 'top', 'part', 'last_routed_checkpoint', 'tool_version', 'failure', 'stages', 'bitstream_timestamp') if key in config})
    return True


def execute_locked(project: Path, config: dict, executable: str = "vivado") -> int:
    ###########################################################################
    # Claim once, snapshot settings/scripts, and preserve every completed step. #
    ###########################################################################
    program = shutil.which(executable)
    if not program:
        raise ValueError(f"Vivado executable not found: {executable}")
    output = Path(config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=True)
    registry = BuildRegistry(project)
    launch_id = None
    exit_code = 1
    stopped = False
    try:
        launch_id = registry.register(project, config)
        config["launch_id"] = launch_id
        for folder in ("work", "artifacts"):
            (output / folder).mkdir(exist_ok=True)
        runtime_config = (snapshot_bitstream(config) if config['stage'] == 'bitstream'
                          else snapshot_inputs(config))
        if config['stage'] == 'ip':
            record_source_hashes(project, runtime_config)
        scripts = Path(runtime_config['script']).parent
        helper = scripts / '_hdlforge'
        helper.mkdir()
        shutil.copyfile(Path(__file__).with_name('vivado_build_runtime.tcl'), helper / 'runtime.tcl')
        shutil.copytree(Path(__file__).with_name('tcllib_json'), helper / 'json')
        runtime_config.update(artifacts_dir=str(output / 'artifacts'), work_dir=str(output / 'work'))
        write_run(output, runtime_config)
        verify_checkpoint(runtime_config)
        command = [program, "-m64", "-product", "Vivado", "-mode", "batch", "-notrace",
                   "-messageDb", str(output / "work/vivado.pb"), "-nolog", "-nojournal", "-source", runtime_config['script'],
                   "-tclargs", str(metadata_path(output)), runtime_config['run_id']]
        write_run(output, {'command': command})
        print(f"Build: {config['selector']}\nSynthesis run ID: {config['synthesis_run_id']}\nArtifacts: {output}", flush=True)
        snapshot_root = Path(runtime_config["project_root"])
        if config['stage'] == 'bitstream':
            snapshot_root = Path(runtime_config['project_root'])
        source_metadata = (
            f"Source mode: frozen input snapshot (not live project sources)\n"
            f"Input snapshot: {snapshot_root}\n"
            f"Snapshot project sources: {runtime_config['project_root']}\n"
            f"Manifest: {output / 'manifest.json'}\n"
        )
        if config["stage"] == "impl":
            source_metadata += f"Synthesis checkpoint input: {runtime_config['input_dcp']}\n"
        elif config['stage'] == 'bitstream':
            source_metadata += (f"Bitstream selection: {config['build_selection']}\n"
                                f"Routed implementation checkpoint input: {runtime_config['input_dcp']}\n"
                                f"Original implementation timestamp (USERID epoch): {config['bitstream_epoch']}\n")
        elif config["stage"] == "ip":
            source_metadata += f"IP regeneration work copies (from snapshot): {output / 'work' / 'ip_sources'}\n"
        process = subprocess.Popen(command, cwd=output / "work", stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
        try:
            registry.attach(launch_id, process.pid)
            metadata = (f"VIVADO_RUN_PID={process.pid}\n"
                        f"VIVADO_RUN_ORIGIN={json.dumps(local_identity(), sort_keys=True)}\n"
                        f"Build: {config['selector']}\n"
                        f"Launch timestamp: {config['launch_timestamp']}\n"
                        f"Synthesis timestamp: {config['synthesis_run_id']}\n"
                        f"Artifacts: {output}\n"
                        f"Working directory: {output / 'work'}\n"
                        f"Run log: {output / 'build.log'}\n" + source_metadata)
            print(metadata, end="", flush=True)
            for line in process.stdout:
                if not runtime_event(line, runtime_config):
                    print(line, end="", flush=True)
            exit_code = process.wait()
        except BaseException:
            # Terminate the entire session, including Vivado's worker children.
            previous = {sig: signal.signal(sig, signal.SIG_IGN) for sig in (signal.SIGTERM, signal.SIGINT)}
            try:
                host = local_identity()
                members = group_members(process_info(process.pid), host)
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                for member in members:
                    signal_process(member, host, signal.SIGKILL)
            finally:
                for sig, handler in previous.items():
                    signal.signal(sig, handler)
            raise
        finally:
            process.stdout.close()
        # Tcl owns the design identity. Persist its validated result for DCP
        # selection, implementations and later bitstream-only launches.
        if exit_code == 0 and config["stage"] != "bitstream":
            exit_code = 1  # Missing/invalid Tcl metadata is a failed run.
            for key in ("top", "part"):
                value = runtime_config.get(key, '')
                if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                    raise ValueError(f"Invalid Tcl design {key}: {value!r}")
                runtime_config[key] = value
                config[key] = value
            write_run(output, runtime_config)
            exit_code = 0
        if exit_code == 0 and runtime_config.get("status") != "complete":
            exit_code = 1
    except (BuildStopped, KeyboardInterrupt):
        stopped = True
        exit_code = 130
    finally:
        status = 'complete' if exit_code == 0 else 'stopped' if stopped else 'failed'
        write_run(output, {'status': status, 'exit_code': exit_code, 'finished_at': utc_now()})
        if launch_id:
            registry.update(launch_id, status=status, exit_code=exit_code,
                            finished_at=utc_now(), continuation_pending=exit_code == 0 and bool(config.get("auto_impl")))
    return exit_code


def log_continuation(parent: dict, child: dict, selector: str, event: str, returncode: int | None = None) -> None:
    """Keep automatic implementation handoffs in the synthesis log/manifest."""
    output = Path(parent['output'])
    record = read_run(output)
    entry = dict(time=utc_now(), event=event, selector=selector,
                 output=child['output'], returncode=returncode)
    write_run(output, {'continuations': [*record.get('continuations', []), entry]})
    message = f"[{entry['time']}] {event}: {selector} | log={Path(child['output']) / 'build.log'}"
    with (output / 'build.log').open('a') as stream:
        stream.write(message + '\n')
    print(message, flush=True)


def stop_signal(signum: int, frame: object) -> None:
    raise BuildStopped(f"Received signal {signum}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=BUILD_HELP, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    parser.add_argument("--project")
    parser.add_argument("--build", nargs="?", const="", help="synthesis or synthesis.implementation; omit for process actions")
    parser.add_argument("--synth_timestamp", help="synthesis run ID or folder label; default: newest metadata timestamp, which must be complete")
    parser.add_argument("--auto_impl", action="append", default=[], help="After successful synthesis run this implementation; repeat for multiple runs")
    artifacts = parser.add_mutually_exclusive_group()
    artifacts.add_argument("--build_status", action="store_true", help="Probe the launch registry and report all non-dead registered processes")
    artifacts.add_argument("--build_status_all", action="store_true", help="Show all registered builds, including completed, failed, stopped, and dead runs")
    artifacts.add_argument("--stopall", action="store_true", help="Stop all registered live launches and their pending continuations")
    artifacts.add_argument("--find_all_user_runs", action="store_true", help="Discover current-user Vivado processes, including unregistered processes")
    artifacts.add_argument("--save_this_run", action="store_true", help="Save the selected timestamp (newest by default); implementation also saves synthesis; do not build")
    artifacts.add_argument("--clean_ignore_artifacts", action="store_true", help="Delete explicitly ignored artifact folders; add --dry-run to preview")
    parser.add_argument('--dry-run', action='store_true', help='List cleanup candidates and skip reasons without deleting artifacts')
    parser.add_argument("--background_worker", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--prepared_run", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            if (not args.clean_ignore_artifacts or args.auto_impl
                    or args.background_worker):
                raise ValueError('--dry-run requires artifact cleanup without build or lock actions')
            print('Artifact cleanup dry-run: no files or folders will be deleted')
        if args.project:
            project = Path(args.project).resolve()
        else:
            candidates = list(Path.cwd().glob("*.hdlforge.json"))
            if len(candidates) != 1:
                raise ValueError("Select a project with --project <file.hdlforge.json>")
            project = candidates[0].resolve()
        if args.build_status or args.build_status_all or args.stopall or args.find_all_user_runs:
            if args.build or args.auto_impl or args.synth_timestamp:
                raise ValueError("Process actions use --build without a run name or continuation options")
            registry = BuildRegistry(project)
            if args.build_status or args.build_status_all:
                registry.watch_status(all_runs=args.build_status_all)
            elif args.stopall:
                registry.stop_all()
            else:
                registry.discover()
            return 0
        if not args.build and args.clean_ignore_artifacts:
            if args.auto_impl:
                raise ValueError("Cleanup cannot be combined with --auto_impl")
            data = json.loads(project.read_text())
            selectors = [name for name in build_names(data) if '.' not in name]
            for selector in selectors:
                manage_artifacts(project, selector, "--clean_ignore_artifacts", args.synth_timestamp, dry_run=args.dry_run)
            return 0
        if not args.build:
            raise ValueError("--build requires a run name or --stopall/--find_all_user_runs; use --build_status for status")
        for flag in ARTIFACT_FLAGS:
            if getattr(args, flag.removeprefix("--")):
                selected = parse_selector(args.build)
                if selected and selected.get('bitstream'):
                    raise ValueError('Artifact actions require the parent implementation selector, without .bitstream')
                if args.auto_impl:
                    raise ValueError("Artifact actions cannot be combined with --auto_impl")
                return manage_artifacts(project, args.build, flag, args.synth_timestamp, dry_run=args.dry_run)
        parsed_build = parse_selector(args.build)
        base_build = parsed_build["run"] if parsed_build else args.build
        if parsed_build and parsed_build['action'] in {'status', 'stop'}:
            if args.auto_impl:
                raise ValueError('Status/stop do not accept build modifiers')
            folder = selected_run_folder(project, parsed_build)
            config = read_run(folder)
            registry = BuildRegistry(project)
            observed = next((row for row in registry.refresh() if row['output'] == str(folder)), config)
            if parsed_build['action'] == 'stop':
                registry.stop_all(str(folder))
            else:
                print(json.dumps(dict(attempt=folder.name, status=observed.get('status'),
                                      exit_code=observed.get('exit_code'), manifest=str(folder / CONFIG),
                                      log=str(folder / 'build.log')), indent=2))
            return 0
        if not args.background_worker:
            config = prepare_run_config(project, args.build, args.synth_timestamp)
            return background_follow(project, config, list(argv if argv is not None else sys.argv[1:]))
        implementations = list(dict.fromkeys(args.auto_impl))
        if implementations:
            if (parsed_build and parsed_build["impl"]) or (not parsed_build and "." in args.build):
                raise ValueError("--auto_impl applies to synthesis builds only")
            data = json.loads(project.read_text())
            if data["vivado"]["non_project"]["runs"].get(base_build, {}).get("kind", "synth") != "synth":
                raise ValueError("--auto_impl applies to synthesis builds only")
            names = build_names(data)
            for implementation in implementations:
                selector = f"{base_build}.{implementation}"
                if selector not in names:
                    raise ValueError(f"Unknown automatic implementation: {selector}")
        previous = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
        config = None
        try:
            config = (read_run(Path(args.prepared_run)) if args.prepared_run else
                      prepare_run_config(project, args.build, args.synth_timestamp))
            config.pop('execution', None)
            config["auto_impl"] = implementations
            result = execute(project, config)
            if result:
                return result
            for implementation in implementations:
                # Always pin to THIS synthesis; another concurrent run may be newer.
                child_selector = f"{base_build}.{config['synthesis_run_id']}.{implementation}.run"
                child = prepare_run_config(project, child_selector)
                child["parent_launch_id"] = config["launch_id"]
                log_continuation(config, child, child_selector, 'synthesis passed; implementation starting')
                try:
                    result = execute(project, child)
                except BaseException:
                    log_continuation(config, child, child_selector, 'implementation interrupted or launch failed')
                    raise
                log_continuation(config, child, child_selector,
                                 'implementation passed' if result == 0 else 'implementation failed', result)
                if result:
                    return result
            return 0
        finally:
            if config and config.get("launch_id"):
                BuildRegistry(project).update(config["launch_id"], continuation_pending=False)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    except (BuildStopped, KeyboardInterrupt):
        print("Build continuation stopped", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        if args.prepared_run:
            folder = Path(args.prepared_run)
            write_run(folder, {'status': 'failed', 'exit_code': 1, 'failure': str(error)})
            with (folder / 'build.log').open('a') as stream:
                stream.write(f'Build error: {error}\n')
        print(f"Build error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
