"""Explicit live discovery and serial builds for synthesis/implementation families."""

import argparse
import base64
from contextlib import nullcontext
import json
import os
from pathlib import Path
import re
import time

from . import build_jobs
from .build_options import OPERATIONS, available_options, print_options
from .get_runs_from_live_xpr import load_xpr_path
from .project_console import ProjectConsole, tcl_word
from .run_group_menu import ACTIONS, choices, run_key, selected_runs
from .run_enable import blocked, is_enabled, set_enabled
from .terminal_output import log, show_runs, table


FIELDS = ["NAME", "PARENT", "IS_SYNTHESIS", "IS_IMPLEMENTATION", "STATUS", "PROGRESS", "NEEDS_REFRESH", "FLOW", "DIRECTORY", "DESCRIPTION", "CURRENT_STEP", "HDLFORGE_IS_IP", "STRATEGY"]
HELPERS = Path(__file__).resolve().parents[1] / "project_management_helpers.tcl"


def snapshot(console: ProjectConsole, locked: bool = False) -> list:
    """Read live run metadata; never open a closed console or launch a run."""
    if not console.exists():
        raise RuntimeError("Console is closed. Run --project_mng restart before listing or controlling runs.")
    script = f"source {tcl_word(HELPERS)}\n" + r'''
apply {{} {
    foreach run [lsort [get_runs]] {
        set values {}
        foreach field {NAME PARENT IS_SYNTHESIS IS_IMPLEMENTATION STATUS PROGRESS NEEDS_REFRESH FLOW DIRECTORY DESCRIPTION CURRENT_STEP HDLFORGE_IS_IP STRATEGY} {
            set value ""
            if {$field eq "HDLFORGE_IS_IP"} {
                set value 0
                set owner $run
                if {[get_property IS_IMPLEMENTATION $run]} {set owner [get_runs [get_property PARENT $run]]}
                catch {set value [expr {[get_property FILESET_TYPE [get_filesets [get_property SRCSET $owner]]] eq "BlockSrcs"}]}
            } else {
                catch {set value [get_property $field $run]}
            }
            lappend values [binary encode base64 -maxlen 0 [encoding convertto utf-8 $value]]
        }
        lappend values [binary encode base64 -maxlen 0 [hdlforge::project::idr_owner $run]]
        puts [join $values "\t"]
    }
}}
'''
    with nullcontext() if locked else console.locked():
        output = console.request(script)
    disabled = set(re.split(r"[\s,]+", os.environ.get("HDLFORGE_DISABLED_IMPL_RUNS", "")))
    # Keep existing profile exclusions effective during migration to native groups.
    if console.project_file and console.project_file.suffix == ".json":
        config = json.loads(console.project_file.read_text())
        profiles = config.get("vivado", {}).get("config", {}).get("build_profiles", {})
        for profile in profiles.values():
            for entry in profile.get("env", []):
                disabled.update(re.split(r"[\s,]+", entry.get("HDLFORGE_DISABLED_IMPL_RUNS", "")))
    rows = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != len(FIELDS) + 1:
            continue
        values = [base64.b64decode(part).decode() for part in parts]
        properties = dict(zip(FIELDS, values))
        rows.append({"name": properties["NAME"], "parent_run": properties["PARENT"] or None,
                     "properties": properties,
                     "enabled": is_enabled(properties["DESCRIPTION"], properties["NAME"] in disabled),
                     "eligible": not values[-1] and "IDR Flow" not in properties["FLOW"]})
    return rows


def active(run: dict) -> bool:
    return bool(re.search(r"running|queued|launching", run["properties"].get("STATUS", ""), re.I))


def complete(run: dict) -> bool:
    properties = run["properties"]
    status = properties.get("STATUS", "").lower()
    return (properties.get("PROGRESS") == "100%" and properties.get("NEEDS_REFRESH", "0").lower() in {"0", "false"}
            and ("complete" in status or status == "using cached ip results"))


def final_step(run: dict) -> str | None:
    if run["properties"].get("IS_IMPLEMENTATION") not in {"1", "true"}:
        return None
    return "route_design" if run["properties"].get("HDLFORGE_IS_IP", "0").lower() in {"1", "true"} else "write_bitstream"


def finished(run: dict) -> bool:
    step = final_step(run)
    return complete(run) and (step is None or step in run["properties"]["STATUS"].lower())


def relay_log(filename: Path | None, offset: int) -> int:
    """Copy newly emitted Vivado run output into the background worker log."""
    if filename is None or not filename.exists():
        return offset
    with filename.open("rb") as handle:
        handle.seek(0 if filename.stat().st_size < offset else offset)
        output = handle.read()
        if output:
            print(output.decode(errors="replace"), end="", flush=True)
        return handle.tell()


def build(console: ProjectConsole, path: str, jobs: int, run_timeout: float) -> None:
    """Serialize the group while releasing the Tcl lock between status polls."""
    with console.locked("build.lock"):
        runs = snapshot(console)
        sequence, action = selected_runs(path, runs)
        if action in {"enable", "disable"}:
            set_enabled(console, [sequence[0]["name"]], action == "enable")
            log(f"{sequence[0]['name']}: {'enabled' if action == 'enable' else 'disabled'} in the XPR")
            return
        if action != "reset":
            for run in sequence:
                if blocked(run, runs):
                    log(f"[Skipped: disabled] {run['name']}")
            sequence = [run for run in sequence if not blocked(run, runs)]
            if not sequence:
                return
        if any(active(run) for run in runs):
            raise RuntimeError("A run is already active; wait before resetting or building another group")
        table(["Order", "Run"], [[index, run["name"]] for index, run in enumerate(sequence, 1)])
        if action in {"reset", "reset_and_build"}:
            if not sequence[0].get("parent_run"):
                log("Resetting synthesis invalidates all its implementation children, including disabled or unselected ones.")
            with console.locked():
                console.request("reset_runs " + tcl_word(sequence[0]["name"]))
        if action == "reset":
            return
        for item in sequence:
            name = item["name"]
            current = snapshot(console)
            run = next(run for run in current if run["name"] == name)
            if blocked(run, current):
                log(f"[Skipped: disabled] {name}")
                continue
            if finished(run):
                log(f"[Current] {name}")
                continue
            status = run["properties"]["STATUS"]
            if run["properties"].get("NEEDS_REFRESH", "0").lower() not in {"0", "false"} or re.search(r"error|fail|cancel|abort", status, re.I):
                raise RuntimeError(f"{name}: {status}. Choose reset_and_build to rebuild this group.")
            parent = next((row for row in current if row["name"] == run.get("parent_run")), None)
            if parent is not None and not complete(parent):
                raise RuntimeError(f"{name}: synthesis {parent['name']} is not current and complete; continue or reset_and_build the group first")
            log(f"[Building] {name}")
            directory = run["properties"].get("DIRECTORY")
            output = Path(directory) / "runme.log" if directory else None
            offset = 0
            if output:
                log(f"Run log: {output}")
            with console.locked():
                # Recheck availability under the same lock as launch so disable cannot race a queued run.
                latest = snapshot(console, locked=True)
                latest_run = next(row for row in latest if row["name"] == name)
                if blocked(latest_run, latest):
                    log(f"[Skipped: disabled] {name}")
                    continue
                step = final_step(latest_run)
                target = f" -to_step {step}" if step else ""
                console.request(f"launch_runs {tcl_word(name)} -jobs {jobs}{target}")
            deadline = time.monotonic() + run_timeout
            while True:
                run = next(run for run in snapshot(console) if run["name"] == name)
                offset = relay_log(output, offset)
                if finished(run):
                    log(f"[Done] {name}")
                    break
                status = run["properties"]["STATUS"]
                if re.search(r"error|fail|cancel|abort", status, re.I):
                    raise RuntimeError(f"{name}: {status}; remaining runs were not launched")
                if time.monotonic() >= deadline:
                    raise RuntimeError(f"Timed out waiting for {name}; run may still be active. Remaining runs were not launched.")
                time.sleep(2)


def main(project: Path, action: str, argv: list[str]) -> int:
    public_operation = OPERATIONS.get(action)
    parser = argparse.ArgumentParser(prog="hdlforge --tool vivado --project_mng " + action,
        description="List groups/runs explicitly, then select a target and action. Tab-Tab never queries Vivado.",
        epilog="Run build.get_build_options for complete copy-paste commands. Examples: build.build_run --append '--run synth_1'; build.build_group --append '--group synth_1 --reset'.",
        formatter_class=argparse.RawDescriptionHelpFormatter)
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--group", help="Synthesis group name from get_groups: synthesis and its enabled implementations")
    selectors.add_argument("--run", help="Individual synthesis/implementation name from get_runs; implementation needs completed synthesis")
    parser.add_argument("--action", choices=list(ACTIONS), help=argparse.SUPPRESS if public_operation else "; ".join(name + ": " + description for name, description in ACTIONS.items()))
    parser.add_argument("--list-options", action="store_true", help="Show available build options and --append examples without querying Vivado")
    parser.add_argument("--reset", action="store_true", help="For build_run/build_group: reset the selected target before its full build")
    parser.add_argument("--jobs", type=int, default=1, help="Jobs within a run; runs are always launched one at a time (default 1)")
    parser.add_argument("--run-timeout", type=float, default=86400, help="Maximum seconds to wait per run; timeout does not stop Vivado (default 86400)")
    parser.add_argument("--foreground", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--follow", action="store_true", help="For build-status: follow the worker log until it exits")
    parser.add_argument("--json", action="store_true", help="For get_runs: print the current live run metadata")
    args = parser.parse_args(argv)
    if args.jobs < 1 or args.run_timeout <= 0:
        parser.error("--jobs and --run-timeout must be positive")
    if public_operation:
        kind, operation = public_operation
        if args.action:
            parser.error("This command already defines the action; do not pass --action")
        if not getattr(args, kind) or getattr(args, "run" if kind == "group" else "group"):
            parser.error(f"Pass --{kind} NAME; get_build_options prints complete commands for this project")
        if args.reset and operation != "continue":
            parser.error("--reset applies only to build_run/build_group")
        args.action = "reset_and_build" if args.reset else operation
        action = "build"
    if args.list_options or (action in {"build", "build."} and not (args.group or args.run or args.action)):
        parser.print_help()
        return 0
    if action in {"build", "build."} and (not args.action or not (args.group or args.run)):
        parser.error("Supply --group NAME or --run NAME together with --action ACTION")
    console = ProjectConsole(load_xpr_path(project), project_file=project)
    try:
        if action in {"build", "build."}:
            current = snapshot(console)
            name = args.group or args.run
            selected = next((run for run in current if run["name"] == name), None)
            if selected is None or not selected["eligible"]:
                raise ValueError(f"Run {name!r} is missing or excluded; use get_groups/get_runs for current choices")
            if args.group:
                if selected["properties"].get("IS_SYNTHESIS") not in {"1", "true"}:
                    raise ValueError("--group must name a synthesis run; use --run for one implementation")
                action = f"build.{run_key(name)}.{args.action}"
            elif selected.get("parent_run"):
                action = f"build.{run_key(selected['parent_run'])}.implementations.{run_key(name)}.{args.action}"
            else:
                action = f"build.{run_key(name)}.synthesis.{args.action}"
        if action == "build-status":
            build_jobs.monitor(console, args.follow)
        elif action == "get_build_options":
            options = available_options(project, snapshot(console))
            if args.json:
                print(json.dumps({"options": options}, indent=2))
            else:
                print_options(options)
        elif action in {"get_runs", "get_groups"}:
            runs = snapshot(console)
            for run in runs:
                run["availability"] = "excluded (IDR)" if not run["eligible"] else "disabled" if blocked(run, runs) else "enabled"
            if action == "get_groups":
                groups = [run for run in runs if run["properties"].get("IS_SYNTHESIS") in {"1", "true"}]
                if args.json:
                    print(json.dumps({"groups": groups}, indent=2))
                else:
                    table(["Group (synthesis)", "Status", "Availability", "Implementations"],
                          [[run["name"], run["properties"]["STATUS"], run["availability"],
                            ", ".join(child["name"] for child in runs if child.get("parent_run") == run["name"])] for run in groups])
            elif args.json:
                print(json.dumps({"runs": runs}, indent=2))
            else:
                show_runs(runs)
        elif action in {"run_groups", "run_groups."}:
            log("Use get_groups/get_runs to list current names, then build --group NAME or --run NAME with --action ACTION.")
        elif args.foreground:
            path = build_jobs.state_path(console)
            with console.locked("launcher.lock"):
                state = json.loads(path.read_text())
                state["status"] = "running"
                build_jobs.write_state(path, state)
            try:
                build(console, action, args.jobs, args.run_timeout)
            except BaseException:
                state["status"] = "failed"
                build_jobs.write_state(path, state)
                raise
            state["status"] = "complete"
            build_jobs.write_state(path, state)
        else:
            # Validate against live state before reporting a started worker.
            current = snapshot(console)
            sequence, operation = selected_runs(action, current)
            if operation in {"enable", "disable"}:
                set_enabled(console, [sequence[0]["name"]], operation == "enable")
                log(f"{sequence[0]['name']}: {operation}d in the XPR; already active runs finish")
            elif operation == "reset":
                build(console, action, args.jobs, args.run_timeout)
            elif all(blocked(run, current) for run in sequence):
                log("Selection is disabled; no runs were reset or launched. Enable the run and its synthesis group first.")
            else:
                build_jobs.start(console, project, action, args.jobs, args.run_timeout)
        return 0
    except (RuntimeError, ValueError, OSError) as error:
        log(str(error), error=True)
        return 1
