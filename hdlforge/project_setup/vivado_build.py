"""Launch a non-project Vivado run described by the selected project JSON."""

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
import time

from vivado_build_config import BUILD_HELP, ARTIFACT_FLAGS, build_names
from vivado_build_artifacts import cleanable, manage_artifacts
from vivado_build_registry import BuildRegistry, BuildStopped, utc_now
from vivado_build_paths import require_complete, resolve_latest_path
from vivado_build_follow import background_follow
from vivado_build_selector import parse_selector, resolve_rerun
from vivado_build_snapshot import implementation_inputs, snapshot_inputs
from vivado_build_hash import record_source_hashes, hash_source
from vivado_build_layout import CONFIG, find_run, read_run, write_run, new_identity, new_label, verify_checkpoint, map_paths, metadata_path
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
    unknown = set(config) - {"script", "sources", "impl_runs", "enabled_on_all", "kind"}
    if unknown:
        raise ValueError(f"Unknown run settings: {sorted(unknown)}; design settings belong in run.tcl")
    config.pop("impl_runs", None)
    if not isinstance(config.get("enabled_on_all", True), bool):
        raise ValueError("enabled_on_all must be a boolean")
    if config.get("kind", "synth") not in {"synth", "ip"}:
        raise ValueError("kind must be synth or ip")
    if stage == "ip" and run.get("impl_runs"):
        raise ValueError("IP builds cannot have implementation runs")
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


def select_run(project: Path, selector: str, timestamp: str | None = None, *, refresh_impl_inputs: bool = False) -> dict:
    """Select immutable metadata independently of physical directory names."""
    project = project.resolve()
    selector = resolve_rerun(project, selector)
    parsed = parse_selector(selector)
    if parsed and timestamp is not None:
        raise ValueError('Use the parent selection in the build selector, not --synth_timestamp as well')
    if parsed and parsed.get('bitstream'):
        return select_bitstream(project, parsed)
    data = json.loads(project.read_text())
    settings = data['vivado']['non_project']
    root = (project.parent / settings['output_root']).resolve()
    synthesis, _, implementation = selector.partition('.')
    if parsed:
        synthesis, implementation = parsed['run'], parsed['impl']
        timestamp = parsed['synth']
    if synthesis not in settings['runs']:
        raise ValueError(f'Unknown synthesis/IP run: {synthesis}')
    definition = settings['runs'][synthesis]
    if parsed and parsed['synth'] != 'new' and (not implementation or parsed['attempt'] != 'new'):
        parent = find_run(root / synthesis, parsed['synth'])
        output = find_run(parent / 'impl_runs' / implementation, parsed['attempt'], f'{synthesis}.{implementation}') if implementation else parent
        config = read_run(output)
        config.update(output=str(output), output_root=str(root), rerun=True)
        verify_checkpoint(config)
        return config
    if implementation:
        if implementation not in definition.get('impl_runs', {}):
            raise ValueError(f'Unknown implementation: {implementation}')
        parent = find_run(root / synthesis, timestamp or 'latest')
        require_complete(parent)
        parent_config = read_run(parent)
        # Freeze only the implementation's declared files, never all parent RTL.
        child = definition['impl_runs'][implementation]
        if not refresh_impl_inputs and implementation in parent_config.get('impl_json', {}):
            path = Path(parent_config['impl_json'][implementation])
            config = map_paths(json.loads(path.read_text()), path.parent, relative=False)
        elif not refresh_impl_inputs and implementation in parent_config.get('implementation_configs', {}):
            config = copy.deepcopy(parent_config['implementation_configs'][implementation])
        else:
            config = normalize_run(project, child, 'impl')
        config.update(parent_top=parent_config['top'], parent_part=parent_config['part'])
        checkpoint = parent / 'artifacts' / f"{parent_config['top']}.dcp"
        config.update(input_dcp=str(checkpoint), input_dcp_sha256=hash_source(checkpoint),
                      parent_run_id=parent_config['run_id'], synthesis_run_id=parent_config['run_id'])
        output = parent / 'impl_runs' / implementation / new_label()
    else:
        if timestamp not in (None, 'new'):
            raise ValueError('Use RUN.rerun.ID to rerun a synthesis')
        config = normalize_run(project, definition, definition.get('kind', 'synth'))
        config['implementation_configs'] = {
            name: normalize_run(project, child, 'impl')
            for name, child in definition.get('impl_runs', {}).items()
        }
        output = root / synthesis / new_label()
        config.update(input_dcp='')
    config.update(new_identity())
    config.setdefault('synthesis_run_id', config['run_id'])
    config['timestamp'] = config['created_at']
    config.update(project_root=str(project.parent), output=str(output), output_root=str(root),
                  selector=synthesis + ('.' + implementation if implementation else ''),
                  vivado_version=settings.get('vivado_version', ''))
    return config


def execute(project: Path, config: dict, executable: str = "vivado") -> int:
    if config['stage'] == 'bitstream':
        with lock_implementation(config):
            return execute_attempt(project, config, executable)
    if config['stage'] == 'impl':
        parent = Path(config['input_dcp']).parent.parent
        with (parent.parent / f'_{read_run(parent)["run_id"]}.run.lock').open('a') as lock:
            # The chosen date stays fixed; block parent reruns while using it.
            fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
            require_complete(parent)
            return execute_attempt(project, config, executable)
    return execute_attempt(project, config, executable)


def execute_attempt(project: Path, config: dict, executable: str = "vivado") -> int:
    """Lock an attempt before clearing only its generated outputs."""
    output = Path(config['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / f'_{config["run_id"]}.run.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            if config.get('lock_action') in {'stop', 'force'}:
                BuildRegistry(Path(config['output_root'])).stop_all(str(output))
                deadline = time.monotonic() + 5
                while True:
                    try:
                        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                        break
                    except BlockingIOError:
                        if time.monotonic() >= deadline:
                            raise ValueError(f'Run lock still held: {lock.name}; owner could not be stopped') from None
                        time.sleep(0.1)
            else:
                lock.seek(0)
                raw_owner = lock.read().strip()
                try:
                    owner = json.loads(raw_owner)
                except (ValueError, TypeError):
                    owner = {}
                pid = (owner.get('launcher') or {}).get('pid', 'unknown')
                synthesis, _, implementation = config['selector'].partition('.')
                selector = f"{synthesis}.rerun.{config['synthesis_run_id']}"
                if implementation:
                    selector = f"{synthesis}.{config['synthesis_run_id']}.{implementation}.rerun.{output.name}"
                stage = 'impl' if implementation else 'synth'
                command = shlex.join(['hdlforge', '--project', str(project), f'vivado.build.{stage}.' + selector])
                raise ValueError(
                    f"Run blocked: another launcher holds this run's lock.\n"
                    f"Launcher PID: {pid}\nLock: {lock.name}\nLog: {output / 'logs/runme.log'}\n\n"
                    f"Stop this run without rebuilding:\n  {command} --stop_run\n\n"
                    f"Stop this run, then clear its outputs and rerun frozen inputs:\n  {command} --force_run\n\n"
                    f"Clear stale metadata only after the run has stopped (no build):\n  {command} --remove_lock\n\n"
                    "--remove_lock cannot release an active lock. A stopped process releases "
                    "its lock automatically. The empty lock file stays in place to prevent races; "
                    "do not delete it manually."
                ) from None
        if config.get('lock_action') in {'remove', 'stop'}:
            lock.seek(0)
            lock.truncate()
            print(f'Run stopped / lock metadata cleared: {lock.name}; no build launched')
            return 0
        if config.get('rerun') and config['stage'] == 'synth':
            implementations = output / 'impl_runs'
            history = implementations.exists() and any(
                not child.is_dir() or any(child.iterdir()) for child in implementations.iterdir()
            )
            recorded = json.loads(metadata_path(output).read_text()).get('attempts', {})
            history = history or any(entry.get('stage') == 'impl' for entry in recorded.values())
            legacy = output / 'impl'
            if history or (legacy.exists() and any(legacy.iterdir())):
                raise ValueError('Cannot rerun synthesis with implementation history; create a new synthesis run')
        lock.seek(0)
        lock.truncate()
        json.dump({'launcher': process_info(os.getpid()), 'host': local_identity(),
                   'output': str(output), 'log': str(output / 'logs/runme.log')}, lock)
        lock.flush()
        if config.get('rerun'):
            if not shutil.which(executable):
                raise ValueError(f'Vivado executable not found: {executable}')
            if output.is_symlink():
                raise ValueError(f'Refusing symlink run: {output}')
            verify_checkpoint(config)
            # Reruns preserve the immutable snapshot and JSON. Refuse to overwrite
            # tracked or non-ignored outputs, using the same recursive cleanup gate.
            allowed, reason = cleanable(output)
            if not allowed:
                raise ValueError(f'Refusing to overwrite {output}: {reason}')
            config['_rerun_runtime'] = read_run(output)
            for name in ('work', 'artifacts'):
                directory = output / name
                if directory.exists():
                    shutil.rmtree(directory)
        return execute_locked(project, config, executable)


def execute_locked(project: Path, config: dict, executable: str = "vivado") -> int:
    ###########################################################################
    # Claim once, snapshot settings/scripts, and preserve every completed step. #
    ###########################################################################
    program = shutil.which(executable)
    if not program:
        raise ValueError(f"Vivado executable not found: {executable}")
    output = Path(config["output"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.mkdir(exist_ok=bool(config.get("rerun")))
    # Initialize once; explicit user visibility changes on existing runs persist.
    info = output / "logs"
    info.mkdir(exist_ok=True)
    status = info / "status"
    status.write_text("starting\n")
    registry = BuildRegistry(Path(config["output_root"]))
    launch_id = None
    exit_code = 1
    stopped = False
    try:
        launch_id = registry.register(project, config)
        config["launch_id"] = launch_id
        for folder in ("work", "artifacts"):
            (output / folder).mkdir(exist_ok=True)
        saved_project = project
        if config['stage'] == 'bitstream':
            saved_project = Path(config['bitstream_source']) / 'logs/project.json'
        if not config.get("rerun"):
            shutil.copyfile(saved_project, info / "project.json")
        if config.get("refresh_impl_inputs"):
            shutil.copyfile(project, info / "implementation_project.json")
        rerun_runtime = config.pop("_rerun_runtime", None)
        (info / "launch.json").write_text(json.dumps({"launch_id": launch_id, "started_at": utc_now()}, indent=2) + "\n")
        if rerun_runtime is not None:
            runtime_config = rerun_runtime
        elif config['stage'] == 'bitstream':
            runtime_config = snapshot_bitstream(config)
        else:
            runtime_config = implementation_inputs(config) if config["stage"] == "impl" else snapshot_inputs(config)
        if config["stage"] == "ip" and not config.get('rerun'):
            record_source_hashes(project, config)
        scripts = output / 'snapshot/scripts'
        scripts.mkdir(parents=True, exist_ok=True)
        if not config.get('rerun'):
            helper = scripts / '_hdlforge'
            helper.mkdir()
            shutil.copyfile(Path(__file__).with_name('vivado_build_runtime.tcl'), helper / 'runtime.tcl')
            shutil.copytree(Path(__file__).with_name('tcllib_json'), helper / 'json')
            runtime_config.update(logs_dir=str(info), artifacts_dir=str(output / 'artifacts'),
                                  work_dir=str(output / 'work'))
            write_run(output, runtime_config)
        elif config['stage'] in {'impl', 'bitstream'}:
            write_run(output, runtime_config)
        if config['stage'] == 'synth':
            for name in runtime_config.get('implementation_configs', {}):
                (output / 'impl_runs' / name).mkdir(parents=True, exist_ok=True)
        verify_checkpoint(runtime_config)
        command = [program, "-m64", "-product", "Vivado", "-mode", "batch", "-notrace",
                   "-messageDb", str(info / "vivado.pb"), "-log", str(info / "vivado.log"),
                   "-journal", str(info / "vivado.jou"), "-source", runtime_config['script'],
                   "-tclargs", str(metadata_path(output)), runtime_config['run_id']]
        (info / "invocation.txt").write_text(shlex.join(command) + "\n")
        print(f"Build: {config['selector']}\nSynthesis run ID: {config['synthesis_run_id']}\nArtifacts: {output}", flush=True)
        snapshot_root = Path(runtime_config["project_root"]).parent
        if config['stage'] == 'bitstream':
            snapshot_root = Path(runtime_config['project_root'])
        source_metadata = (
            f"Source mode: frozen input snapshot (not live project sources)\n"
            f"Input snapshot: {snapshot_root}\n"
            f"Snapshot project sources: {runtime_config['project_root']}\n"
            f"Input manifest: {info / 'input_manifest.json'}\n"
        )
        if config["stage"] == "impl":
            source_metadata += f"Synthesis checkpoint input: {runtime_config['input_dcp']}\n"
        elif config['stage'] == 'bitstream':
            source_metadata += (f"Bitstream selection: {config['build_selection']}\n"
                                f"Routed implementation checkpoint input: {runtime_config['input_dcp']}\n"
                                f"Original implementation timestamp (USERID epoch): {config['bitstream_epoch']}\n")
        elif config["stage"] == "ip":
            source_metadata += f"IP regeneration work copies (from snapshot): {output / 'work' / 'ip_sources'}\n"
        with (output / "logs/runme.log").open("w") as log:
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
                            f"Run log: {output / 'logs/runme.log'}\n" + source_metadata)
                log.write(metadata)
                log.flush()
                print(metadata, end="", flush=True)
                for line in process.stdout:
                    log.write(line)
                    log.flush()
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
                value = (info / ("design_" + key)).read_text().strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
                    raise ValueError(f"Invalid Tcl design {key}: {value!r}")
                runtime_config[key] = value
                config[key] = value
            write_run(output, runtime_config)
            exit_code = 0
        if exit_code == 0 and status.read_text().strip() != "complete":
            exit_code = 1
    except (BuildStopped, KeyboardInterrupt):
        stopped = True
        exit_code = 130
    finally:
        if exit_code != 0:
            status.write_text("stopped\n" if stopped else "failed\n")
        (info / "exit_code").write_text(f"{exit_code}\n")
        if launch_id:
            registry.update(launch_id, status=status.read_text().strip(), exit_code=exit_code,
                            finished_at=utc_now(), continuation_pending=exit_code == 0 and bool(config.get("auto_impl")))
    return exit_code


def log_continuation(parent: dict, child: dict, selector: str, event: str, returncode: int | None = None) -> None:
    """Record exact stage handoff separately from each Vivado worker log."""
    info = Path(parent['output']) / 'logs'
    entry = {
        'time': utc_now(), 'event': event, 'selector': selector,
        'synthesis_timestamp': parent['synthesis_run_id'],
        'synthesis_log': str(Path(parent['output']) / 'logs/runme.log'),
        'implementation_output': child['output'],
        'implementation_log': str(Path(child['output']) / 'logs/runme.log'),
        'returncode': returncode,
    }
    with (info / 'continuation.jsonl').open('a') as stream:
        stream.write(json.dumps(entry) + '\n')
    message = (f"[{entry['time']}] {event}: {selector}"
               f" | synthesis={parent['timestamp']} | log={entry['implementation_log']}"
               + (f" | returncode={returncode}" if returncode is not None else ''))
    with (info / 'continuation.log').open('a') as stream:
        stream.write(message + '\n')
    print(message, flush=True)


def stop_signal(signum: int, frame: object) -> None:
    raise BuildStopped(f"Received signal {signum}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=BUILD_HELP, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    parser.add_argument("--project")
    parser.add_argument("--build", nargs="?", const="", help="synthesis or synthesis.implementation; omit for process actions")
    parser.add_argument("--synth_timestamp", help="synthesis run ID or folder label; default: newest metadata timestamp, which must be complete")
    parser.add_argument("--refresh_impl_inputs", action="store_true", help="New implementation only: snapshot current XDC/Tcl/supporting files; retain synthesis DCP and frozen IPs")
    parser.add_argument("--auto_impl", action="append", default=[], help="After successful synthesis run this implementation; repeat for multiple runs")
    artifacts = parser.add_mutually_exclusive_group()
    artifacts.add_argument("--build_status", action="store_true", help="Probe the launch registry and report all non-dead registered processes")
    artifacts.add_argument("--build_status_all", action="store_true", help="Show all registered builds, including completed, failed, stopped, and dead runs")
    artifacts.add_argument("--stopall", action="store_true", help="Stop all registered live launches and their pending continuations")
    artifacts.add_argument("--find_all_user_runs", action="store_true", help="Discover current-user Vivado processes, including unregistered processes")
    artifacts.add_argument("--save_this_run", action="store_true", help="Save the selected timestamp (newest by default); implementation also saves synthesis; do not build")
    artifacts.add_argument("--clean_ignore_artifacts", action="store_true", help="Delete explicitly ignored artifact folders; add --dry-run to preview")
    parser.add_argument('--dry-run', action='store_true', help='List cleanup candidates and skip reasons without deleting artifacts')
    locks = parser.add_mutually_exclusive_group()
    locks.add_argument('--remove_lock', action='store_true', help='Clear idle lock metadata only; never unlink a held lock')
    locks.add_argument('--stop_run', action='store_true', help='Stop only this timestamped run; do not rebuild')
    locks.add_argument('--force_run', action='store_true', help='Stop this run, acquire its lock, then rerun')
    parser.add_argument("--background_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.dry_run:
            if (not args.clean_ignore_artifacts or args.auto_impl or args.refresh_impl_inputs
                    or args.remove_lock or args.stop_run or args.force_run or args.background_worker):
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
            data = json.loads(project.read_text())
            registry = BuildRegistry(project.parent / data["vivado"]["non_project"]["output_root"])
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
        if (not args.background_worker
                and not args.remove_lock and not args.stop_run):
            data = json.loads(project.read_text())
            return background_follow(project, project.parent / data['vivado']['non_project']['output_root'],
                                     list(argv if argv is not None else sys.argv[1:]))
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
            config = select_run(project, args.build, args.synth_timestamp, refresh_impl_inputs=args.refresh_impl_inputs)
            if args.refresh_impl_inputs:
                if config['stage'] != 'impl' or config.get('rerun'):
                    raise ValueError('--refresh_impl_inputs requires a new implementation attempt')
                config['refresh_impl_inputs'] = True
            action = 'remove' if args.remove_lock else 'stop' if args.stop_run else 'force' if args.force_run else None
            if action and (not config.get('rerun') or implementations):
                raise ValueError('Lock actions require an existing explicit attempt timestamp and no --auto_impl')
            config['lock_action'] = action
            config["auto_impl"] = implementations
            result = execute(project, config)
            if result:
                return result
            for implementation in implementations:
                # Always pin to THIS synthesis; another concurrent run may be newer.
                child_selector = f"{base_build}.{config['synthesis_run_id']}.{implementation}.new"
                child = select_run(project, child_selector)
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
                BuildRegistry(Path(config["output_root"])).update(config["launch_id"], continuation_pending=False)
            for sig, handler in previous.items():
                signal.signal(sig, handler)
    except (BuildStopped, KeyboardInterrupt):
        print("Build continuation stopped", file=sys.stderr)
        return 130
    except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
        print(f"Build error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
