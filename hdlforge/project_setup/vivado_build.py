"""Launch a non-project Vivado run described by the selected project JSON."""

import argparse
import copy
import glob
import fcntl
from datetime import datetime, timezone
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

from vivado_build_config import BUILD_HELP, ARTIFACT_FLAGS, build_names, synthesis_timestamps, TIMESTAMP
from vivado_build_artifacts import initialize_visibility, manage_artifacts
from vivado_build_registry import BuildRegistry, BuildStopped, utc_now
from vivado_build_publish import clear_latest, publish_latest
from vivado_build_follow import background_follow
from vivado_build_selector import parse_selector, resolve_rerun
from vivado_build_snapshot import implementation_inputs, snapshot_inputs
from vivado_build_hash import record_source_hashes
from vivado_build_processes import group_members, local_identity, process_info, signal_process


def tcl_value(value: object) -> str:
    """Encode data as a Tcl expression without allowing Tcl substitution."""
    if isinstance(value, dict):
        return "[dict create " + " ".join(tcl_value(item) for pair in value.items() for item in pair) + "]"
    if isinstance(value, list):
        return "[list " + " ".join(tcl_value(item) for item in value) + "]"
    if isinstance(value, bool):
        return "1" if value else "0"
    text = str(value)
    for old, new in (("\\", "\\\\"), ('"', '\\"'), ("$", "\\$"), ("[", "\\["),
                     ("]", "\\]"), ("\n", "\\n"), ("\r", "\\r")):
        text = text.replace(old, new)
    return '"' + text + '"'


def file_path(root: Path, value: str) -> str:
    if glob.has_magic(value):
        matches = [Path(path) for path in glob.glob(str(root / value), recursive=True) if Path(path).is_file()]
        if len(matches) != 1:
            raise ValueError(f"Expected exactly one input matching {value}; found {len(matches)}. Build the producer first if its latest output is missing.")
        return str(matches[0].resolve())
    path = (root / value).resolve()
    if not path.is_file():
        raise ValueError(f"Missing input file: {path}")
    return str(path)


def normalize_run(project: Path, run: dict, stage: str) -> dict:
    ###########################################################################
    # Resolve input file paths before claiming the output directory.           #
    ###########################################################################
    config = copy.deepcopy(run)
    unknown = set(config) - {"stage", "script", "part", "top", "sources", "ips", "constraints",
                             "defines", "impl_runs", "parameters", "post_load_parameters", "publish_latest", "input_files", "enabled_on_all",
                             "project_properties", "fileset_properties", "checkpoint_properties", "constraint_properties"}
    if unknown:
        raise ValueError(f"Unknown run settings: {sorted(unknown)}")
    config.pop("impl_runs", None)
    if not isinstance(config.get("enabled_on_all", True), bool):
        raise ValueError("enabled_on_all must be a boolean")
    if not isinstance(config.get("publish_latest", False), bool):
        raise ValueError("publish_latest must be a boolean")
    for field in ("parameters", "post_load_parameters", "project_properties", "fileset_properties",
                  "checkpoint_properties", "constraint_properties"):
        settings = config.setdefault(field, {})
        if not isinstance(settings, dict):
            raise ValueError(f"{field} must be an object mapping names to values")
        for name, value in settings.items():
            if not isinstance(name, str) or not name or not (
                isinstance(value, (str, int, float, bool))
                or isinstance(value, list) and all(isinstance(item, (str, int, float, bool)) for item in value)
            ):
                raise ValueError(f"Invalid {field} entry: {name}")
    root = project.parent
    if stage not in {"synth", "impl", "ip"} or config.get("stage") != stage:
        raise ValueError(f"Expected stage={stage}")
    if stage == "ip" and (not config.get("ips") or config.get("impl_runs") or run.get("impl_runs")):
        raise ValueError("IP builds require IP inputs and cannot have implementation runs")
    for field in (("part",) if stage == "ip" else ("part", "top")):
        if not isinstance(config.get(field), str) or not re.fullmatch(r"[A-Za-z0-9_-]+", config[field]):
            raise ValueError(f"Missing or invalid {field}")
    config["script"] = file_path(root, config["script"])
    config["input_files"] = [file_path(root, path) for path in config.get("input_files", [])]
    for field in ("sources", "ips", "constraints"):
        entries = []
        for entry in config.get(field, []):
            item = {"path": entry} if isinstance(entry, str) else dict(entry)
            allowed = {"path", "properties"}
            if field == "sources":
                allowed.update({"language", "library"})
            if field == "ips":
                allowed.add("file_properties")
            if set(item) - allowed:
                raise ValueError(f"Unknown {field} settings: {sorted(set(item) - allowed)}")
            item["path"] = file_path(root, item["path"])
            extensions = {"sources": {".sv", ".v", ".vhd", ".vhdl"}, "ips": {".xci", ".xcix"}, "constraints": {".xdc"}}
            if Path(item["path"]).suffix.lower() not in extensions[field]:
                raise ValueError(f"Unsupported {field} file: {item['path']}")
            entries.append(item)
        config[field] = entries
    config.setdefault("defines", [])
    return config


def select_run(project: Path, selector: str, timestamp: str | None = None) -> dict:
    ###########################################################################
    # Both implicit and explicit implementation inputs must be complete.      #
    ###########################################################################
    project = project.resolve()
    selector = resolve_rerun(project, selector)
    parsed = parse_selector(selector)
    if parsed:
        if timestamp is not None:
            raise ValueError('Use the timestamp in the build selector, not --synth_timestamp')
        canonical = parsed['run'] + ('.' + parsed['impl'] if parsed['impl'] else '')
        if parsed['impl']:
            config = select_run(project, canonical, parsed['synth'])
            if parsed['attempt'] != 'new':
                output = Path(config['output']).parent / parsed['attempt']
                config.update(output=str(output), rerun=True)
        elif parsed['synth'] == 'new':
            config = select_run(project, canonical)
        else:
            data = json.loads(project.read_text())
            root = project.parent / data['vivado']['non_project']['output_root'] / canonical / 'artifacts' / parsed['synth']
            config = json.loads((root / 'info/resolved.json').read_text())
            config.update(output=str(root), rerun=True)
        if config.get('rerun'):
            output = Path(config['output'])
            if not (output / 'info/runtime.json').is_file():
                raise ValueError(f'No frozen run configuration to rerun: {output}')
        return config
    data = json.loads(project.read_text())
    if selector not in build_names(data):
        raise ValueError(f"Unknown build {selector!r}; choices: {', '.join(build_names(data))}")
    settings = data["vivado"]["non_project"]
    synth_name, _, impl_name = selector.partition(".")
    synthesis = settings["runs"][synth_name]
    stage = "impl" if impl_name else synthesis.get("stage", "synth")
    config = None
    artifacts = project.parent / settings["output_root"] / synth_name / "artifacts"
    input_dcp = ""
    if impl_name:
        available = synthesis_timestamps(project, data, selector, completed_only=True)
        if timestamp is None:
            if not available:
                raise ValueError(f"No completed synthesis artifacts in {artifacts}")
            timestamp = available[-1]
        if timestamp != 'latest' and (not TIMESTAMP.fullmatch(timestamp) or timestamp not in available):
            raise ValueError(f"Synthesis timestamp is missing, incomplete, or has no checkpoint: {timestamp}")
        parent = artifacts / timestamp
        if timestamp == 'latest':
            if not (parent / 'info/status').is_file() or (parent / 'info/status').read_text().strip() != 'complete' or (parent / 'info/exit_code').read_text().strip() != '0':
                raise ValueError(f'Published synthesis is missing or unsuccessful: {parent}')
        saved = parent / "info/implementations.json"
        if not saved.is_file():
            raise ValueError(f"Synthesis has no frozen implementation inputs: {parent}; create a new synthesis run")
        frozen_runs = json.loads(saved.read_text())
        if impl_name not in frozen_runs:
            raise ValueError(f"Implementation {impl_name} was not captured by this synthesis")
        config = frozen_runs[impl_name]
        if timestamp == 'latest':
            published = json.loads((parent / 'info/resolved.json').read_text())
            original = published['output']
            def relocate(value):
                if isinstance(value, dict):
                    return {key: relocate(item) for key, item in value.items()}
                if isinstance(value, list):
                    return [relocate(item) for item in value]
                if isinstance(value, str) and value.startswith(original + '/'):
                    return str(parent) + value[len(original):]
                return value
            config = relocate(config)
            config['publication_origin_timestamp'] = published['timestamp']
        input_dcp = str((parent / "checkpoints" / f"{config['top']}.dcp").resolve())
        output = parent / "impl_runs" / impl_name / datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")
    else:
        config = normalize_run(project, synthesis, stage)
        if stage == "synth":
            config["implementation_configs"] = {
                name: normalize_run(project, {"ips": synthesis.get("ips", []), **child}, "impl")
                for name, child in synthesis.get("impl_runs", {}).items()
            }
        if timestamp is not None:
            raise ValueError("--synth_timestamp applies only to an implementation build")
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%S.%fZ")
        output = artifacts / timestamp
    config.update(project_root=config.get("project_root", str(project.parent)), output=str(output.resolve()),
                  output_root=str((project.parent / settings["output_root"]).resolve()),
                  input_dcp=input_dcp, selector=selector, timestamp=timestamp,
                  vivado_version=config.get("vivado_version", settings.get("vivado_version", "")))
    return config


def execute(project: Path, config: dict, executable: str = "vivado") -> int:
    """Lock an attempt before clearing only its generated outputs."""
    output = Path(config['output'])
    output.parent.mkdir(parents=True, exist_ok=True)
    with (output.parent / f'.{output.name}.run.lock').open('a') as lock:
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
                selector = f"{synthesis}.rerun.{config['timestamp']}"
                if implementation:
                    selector = f"{synthesis}.{config['timestamp']}.{implementation}.rerun.{output.name}"
                command = shlex.join(['hdlforge', '--project', str(project), '--tool', 'vivado', '--build', selector])
                raise ValueError(
                    f"Run blocked: another launcher holds this run's lock.\n"
                    f"Launcher PID: {pid}\nLock: {lock.name}\nLog: {output / 'runme.log'}\n\n"
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
        lock.seek(0)
        lock.truncate()
        json.dump({'launcher': process_info(os.getpid()), 'host': local_identity(),
                   'output': str(output), 'log': str(output / 'runme.log')}, lock)
        lock.flush()
        if config.get('rerun'):
            if not shutil.which(executable):
                raise ValueError(f'Vivado executable not found: {executable}')
            if output.is_symlink():
                raise ValueError(f'Refusing symlink run: {output}')
            config['_rerun_runtime'] = json.loads((output / 'info/runtime.json').read_text())
            for child in output.iterdir():
                if child.name in {'inputs', 'info', 'impl_runs'}:
                    continue
                if child.is_dir() and not child.is_symlink():
                    shutil.rmtree(child)
                else:
                    child.unlink()
            for name in ('status', 'exit_code', 'stages.tsv', 'publication_error.txt'):
                (output / 'info' / name).unlink(missing_ok=True)
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
    initialize_visibility(output)
    info = output / "info"
    info.mkdir(exist_ok=True)
    status = info / "status"
    status.write_text("starting\n")
    registry = BuildRegistry(Path(config["output_root"]))
    launch_id = None
    exit_code = 1
    stopped = False
    try:
        launch_time = datetime.now(timezone.utc)
        config["launch_timestamp"] = launch_time.isoformat()
        config["launch_epoch"] = int(launch_time.timestamp())
        launch_id = registry.register(project, config)
        if config.get("publish_latest"):
            clear_latest(config)
        config["launch_id"] = launch_id
        for folder in ("work", "checkpoints", "reports", "bitstream"):
            (output / folder).mkdir(exist_ok=True)
        saved_project = Path(config["input_dcp"]).parent.parent / "info/project.json" if config["stage"] == "impl" else project
        if not config.get("rerun"):
            shutil.copyfile(saved_project, info / "project.json")
        if config.get("refresh_impl_inputs"):
            shutil.copyfile(project, info / "implementation_project.json")
        rerun_runtime = config.pop("_rerun_runtime", None)
        (info / "resolved.json").write_text(json.dumps(config, indent=2) + "\n")
        if rerun_runtime is not None:
            runtime_config = rerun_runtime
            for key in ('output', 'launch_id', 'launch_timestamp', 'launch_epoch', 'timestamp'):
                if key in config:
                    runtime_config[key] = config[key]
        else:
            runtime_config = implementation_inputs(config) if config["stage"] == "impl" else snapshot_inputs(config)
        if config["stage"] == "ip":
            record_source_hashes(project, config)
            # Regeneration may rewrite IP products: only expose private copies to Vivado.
            for index, entry in enumerate(runtime_config["ips"]):
                source = Path(entry["path"])
                destination = output / "work" / "ip_sources" / str(index)
                if source.suffix.lower() == ".xci":
                    # Vivado names the converted XCIX after the containing
                    # directory. Keep the IP name instead of the numeric slot.
                    destination = destination / source.stem
                    shutil.copytree(source.parent, destination)
                else:
                    destination.mkdir(parents=True)
                    shutil.copy2(source, destination / source.name)
                entry["path"] = str(destination / source.name)
        scripts = info / "scripts"
        scripts.mkdir(exist_ok=True)
        for sibling in Path(runtime_config["script"]).parent.glob("*.tcl"):
            if sibling.resolve() != (scripts / sibling.name).resolve():
                shutil.copyfile(sibling, scripts / sibling.name)
        runtime_config["script"] = str(scripts / Path(config["script"]).name)
        (info / "runtime.json").write_text(json.dumps(runtime_config, indent=2) + "\n")
        for name in ("vivado_build_runtime.tcl",):
            shutil.copyfile(Path(__file__).with_name(name), info / name)
        (info / "config.tcl").write_text("set ::hdlforge_config " + tcl_value(runtime_config) + "\n")
        command = [program, "-m64", "-product", "Vivado", "-mode", "batch", "-notrace",
                   "-messageDb", str(output / "vivado.pb"), "-log", str(output / "vivado.log"),
                   "-journal", str(output / "vivado.jou"), "-source", str(info / "vivado_build_runtime.tcl"),
                   "-tclargs", str(info / "config.tcl")]
        (info / "invocation.txt").write_text(shlex.join(command) + "\n")
        print(f"Build: {config['selector']}\nSynthesis timestamp: {config['timestamp']}\nArtifacts: {output}", flush=True)
        snapshot_root = Path(runtime_config["project_root"]).parent
        source_metadata = (
            f"Source mode: frozen input snapshot (not live project sources)\n"
            f"Input snapshot: {snapshot_root}\n"
            f"Snapshot project sources: {runtime_config['project_root']}\n"
            f"Input manifest: {info / 'input_manifest.json'}\n"
        )
        if config["stage"] == "impl":
            source_metadata += f"Synthesis checkpoint input: {runtime_config['input_dcp']}\n"
        elif config["stage"] == "ip":
            source_metadata += f"IP regeneration work copies (from snapshot): {output / 'work' / 'ip_sources'}\n"
        with (output / "runme.log").open("w") as log:
            process = subprocess.Popen(command, cwd=output / "work", stdout=subprocess.PIPE,
                                       stderr=subprocess.STDOUT, text=True, errors="replace", start_new_session=True)
            try:
                registry.attach(launch_id, process.pid)
                metadata = (f"VIVADO_RUN_PID={process.pid}\n"
                            f"VIVADO_RUN_ORIGIN={json.dumps(local_identity(), sort_keys=True)}\n"
                            f"Build: {config['selector']}\n"
                            f"Launch timestamp: {config['launch_timestamp']}\n"
                            f"Synthesis timestamp: {config['timestamp']}\n"
                            f"Artifacts: {output}\n"
                            f"Working directory: {output / 'work'}\n"
                            f"Run log: {output / 'runme.log'}\n" + source_metadata)
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
        if exit_code == 0 and status.read_text().strip() != "complete":
            exit_code = 1
    except (BuildStopped, KeyboardInterrupt):
        stopped = True
        exit_code = 130
    finally:
        if exit_code != 0:
            status.write_text("stopped\n" if stopped else "failed\n")
        (info / "exit_code").write_text(f"{exit_code}\n")
        if launch_id and config.get("publish_latest") and not stopped:
            try:
                publish_latest(config)
            except (OSError, ValueError, AttributeError) as error:
                print(f"Latest publication failed: {error}", file=sys.stderr)
                (info / "publication_error.txt").write_text(str(error) + "\n")
                exit_code = exit_code or 1
                status.write_text("failed\n")
                (info / "exit_code").write_text(f"{exit_code}\n")
        if launch_id:
            registry.update(launch_id, status=status.read_text().strip(), exit_code=exit_code,
                            finished_at=utc_now(), continuation_pending=exit_code == 0 and bool(config.get("auto_impl")))
    return exit_code


def log_continuation(parent: dict, child: dict, selector: str, event: str, returncode: int | None = None) -> None:
    """Record exact stage handoff separately from each Vivado worker log."""
    info = Path(parent['output']) / 'info'
    entry = {
        'time': utc_now(), 'event': event, 'selector': selector,
        'synthesis_timestamp': parent['timestamp'],
        'synthesis_log': str(Path(parent['output']) / 'runme.log'),
        'implementation_output': child['output'],
        'implementation_log': str(Path(child['output']) / 'runme.log'),
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
    parser.add_argument("--synth_timestamp", help="default: latest successfully completed synthesis")
    parser.add_argument("--refresh_impl_inputs", action="store_true", help="New implementation only: snapshot current XDC/Tcl/supporting files; retain synthesis DCP and frozen IPs")
    parser.add_argument("--auto_impl", action="append", default=[], help="After successful synthesis run this implementation; repeat for multiple runs")
    artifacts = parser.add_mutually_exclusive_group()
    artifacts.add_argument("--build_status", action="store_true", help="Probe the launch registry and report all non-dead registered processes")
    artifacts.add_argument("--stopall", action="store_true", help="Stop all registered live launches and their pending continuations")
    artifacts.add_argument("--find_all_user_runs", action="store_true", help="Discover current-user Vivado processes, including unregistered processes")
    artifacts.add_argument("--save_this_run", action="store_true", help="Save the selected timestamp (newest by default); implementation also saves synthesis; do not build")
    artifacts.add_argument("--clean_ignore_artifacts", action="store_true", help="Delete explicitly ignored inactive artifact folders; do not build")
    locks = parser.add_mutually_exclusive_group()
    locks.add_argument('--remove_lock', action='store_true', help='Clear idle lock metadata only; never unlink a held lock')
    locks.add_argument('--stop_run', action='store_true', help='Stop only this timestamped run; do not rebuild')
    locks.add_argument('--force_run', action='store_true', help='Stop this run, acquire its lock, then rerun')
    parser.add_argument("--background_worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    try:
        if args.project:
            project = Path(args.project).resolve()
        else:
            candidates = list(Path.cwd().glob("*.hdlforge.json"))
            if len(candidates) != 1:
                raise ValueError("Select a project with --project <file.hdlforge.json>")
            project = candidates[0].resolve()
        if args.build_status or args.stopall or args.find_all_user_runs:
            if args.build or args.auto_impl or args.synth_timestamp:
                raise ValueError("Process actions use --build without a run name or continuation options")
            data = json.loads(project.read_text())
            registry = BuildRegistry(project.parent / data["vivado"]["non_project"]["output_root"])
            if args.build_status:
                registry.watch_status()
            elif args.stopall:
                registry.stop_all()
            else:
                registry.discover()
            return 0
        if not args.build and args.clean_ignore_artifacts:
            if args.auto_impl:
                raise ValueError("Cleanup cannot be combined with --auto_impl")
            data = json.loads(project.read_text())
            selectors = sorted(build_names(data), key=lambda name: (-name.count("."), name))
            for selector in selectors:
                manage_artifacts(project, selector, "--clean_ignore_artifacts", args.synth_timestamp)
            return 0
        if not args.build:
            raise ValueError("--build requires a run name or --stopall/--find_all_user_runs; use --build_status for status")
        for flag in ARTIFACT_FLAGS:
            if getattr(args, flag.removeprefix("--")):
                if args.auto_impl:
                    raise ValueError("Artifact actions cannot be combined with --auto_impl")
                return manage_artifacts(project, args.build, flag, args.synth_timestamp)
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
            if data["vivado"]["non_project"]["runs"].get(base_build, {}).get("stage") != "synth":
                raise ValueError("--auto_impl applies to synthesis builds only")
            names = build_names(data)
            for implementation in implementations:
                selector = f"{base_build}.{implementation}"
                if selector not in names:
                    raise ValueError(f"Unknown automatic implementation: {selector}")
        previous = {sig: signal.signal(sig, stop_signal) for sig in (signal.SIGTERM, signal.SIGINT)}
        config = None
        publication_lock = None
        try:
            publication_lock = None
            selection = parse_selector(args.build)
            if selection and selection.get('impl') and selection['synth'] == 'latest':
                settings = json.loads(project.read_text())['vivado']['non_project']
                publication_lock = (project.parent / settings['output_root'] / selection['run'] / '.publish.lock').open('a')
                fcntl.flock(publication_lock, fcntl.LOCK_SH)
            config = select_run(project, args.build, args.synth_timestamp)
            if args.refresh_impl_inputs:
                if config['stage'] != 'impl' or config.get('rerun'):
                    raise ValueError('--refresh_impl_inputs requires a new implementation attempt')
                synthesis, implementation = config['selector'].split('.')
                data = json.loads(project.read_text())
                definition = data['vivado']['non_project']['runs'][synthesis]['impl_runs'][implementation]
                # Do not resolve current IPs or RTL: the selected synthesis owns them.
                current = normalize_run(project, {**definition, 'ips': [], 'sources': []}, 'impl')
                if current['part'] != config['part'] or current['top'] != config['top']:
                    raise ValueError('Refreshing implementation inputs cannot change part or top; create new synthesis')
                config['refresh_previous_inputs'] = {key: config.get(key) for key in ('constraints', 'script', 'input_files', 'project_root')}
                for key in ('constraints', 'script', 'input_files'):
                    config[key] = current[key]
                config['project_root'] = str(project.parent)
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
                child_selector = f"{base_build}.{config['timestamp']}.{implementation}.new"
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
            if publication_lock is not None:
                publication_lock.close()
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
