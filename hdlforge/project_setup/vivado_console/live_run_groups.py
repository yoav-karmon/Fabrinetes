"""Live project queries and console-free batch command dispatch."""

import argparse
import base64
from contextlib import nullcontext
import json
from pathlib import Path

from . import batch_build, build_jobs
from .build_options import available_options, print_options
from .get_runs_from_live_xpr import load_xpr_path
from .project_console import ConsoleUnavailable, ProjectConsole, tcl_word
from .run_enable import blocked, is_enabled, set_enabled
from .terminal_output import log, show_runs, table


FIELDS = ["NAME", "PARENT", "IS_SYNTHESIS", "IS_IMPLEMENTATION", "STATUS", "PROGRESS", "NEEDS_REFRESH", "FLOW", "DIRECTORY", "DESCRIPTION", "CURRENT_STEP", "HDLFORGE_IS_IP", "STRATEGY"]
HELPERS = Path(__file__).resolve().parents[1] / "project_management_helpers.tcl"


def snapshot(console: ProjectConsole, locked: bool = False) -> list:
    """Ensure the project console is available, then read live run metadata."""
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
        console.open()
        try:
            output = console.request(script)
        except ConsoleUnavailable:
            # open() enforces confirmation for a still-running, stuck console.
            console.open()
            output = console.request(script)
        except RuntimeError:
            if console.exists():
                raise
            # Retry this read once if Vivado exited after the readiness check.
            console.open()
            output = console.request(script)
    rows = []
    for line in output.splitlines():
        parts = line.split("\t")
        if len(parts) != len(FIELDS) + 1:
            continue
        values = [base64.b64decode(part).decode() for part in parts]
        properties = dict(zip(FIELDS, values))
        rows.append({"name": properties["NAME"], "parent_run": properties["PARENT"] or None,
                     "properties": properties,
                     "enabled": is_enabled(properties["DESCRIPTION"]),
                     "eligible": not values[-1] and "IDR Flow" not in properties["FLOW"]})
    return rows



def main(project: Path, action: str, argv: list[str]) -> int:
    if action in {"build_run", "build_group"} and not argv:
        action = "get_build_options"
    parser = argparse.ArgumentParser(description="Submit batches; inspect PID and logs on request.")
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--run")
    selectors.add_argument("--group")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--no-bitstream", action="store_true")
    parser.add_argument("--follow", action="store_true")
    parser.add_argument("--submission", help="Submission ID; status defaults to all submissions")
    parser.add_argument("--quiet-seconds", type=float, default=60)
    parser.add_argument("--lines", type=int, default=8)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1 or args.lines < 1 or args.quiet_seconds < 0:
        parser.error("jobs/lines must be positive; quiet-seconds must be nonnegative")
    console = ProjectConsole(load_xpr_path(project), project_file=project)
    console.force_recovery = args.force
    try:
        if action == "build-status":
            build_jobs.monitor(console, args.follow, args.submission, args.quiet_seconds, args.lines, args.json)
            return 0
        if action == "build-stop":
            if not args.submission:
                parser.error("Pass --submission ID to stop one batch and its children")
            build_jobs.stop(console, args.submission)
            return 0
        if action in {"build_run", "build_group", "reset_run", "reset_group"}:
            kind = action.split("_")[1]
            target = getattr(args, kind)
            if not target:
                parser.error(f"Pass --{kind} NAME")
            batch_build.start(console, target, kind, args.jobs, args.reset,
                              action.startswith("reset_"), not args.no_bitstream)
            return 0
        if action in {"build", "build.", "run_groups", "run_groups."}:
            parser.error("Use build_run --run NAME or build_group --group NAME")
        if args.force and console.pending_request() is not None:
            console.close(force=True)
        if action in {"enable_run", "enable_group", "disable_run", "disable_group"}:
            kind = action.split("_")[1]
            target = getattr(args, kind)
            if not target:
                parser.error(f"Pass --{kind} NAME")
            with console.locked():
                console.open()
            set_enabled(console, [target], action.startswith("enable"))
        elif action == "get_build_options":
            options = available_options(project, snapshot(console))
            print(json.dumps({"options": options}, indent=2)) if args.json else print_options(options)
        elif action in {"get_runs", "get_groups"}:
            runs = snapshot(console)
            for run in runs:
                run["availability"] = "excluded (IDR)" if not run["eligible"] else "disabled" if blocked(run, runs) else "enabled"
            if action == "get_groups":
                groups = [run for run in runs if run["properties"].get("IS_SYNTHESIS") in {"1", "true"}]
                if args.json:
                    print(json.dumps({"groups": groups}, indent=2))
                else:
                    table(["Group", "Status", "Availability", "Implementations"],
                          [[run["name"], run["properties"]["STATUS"], run["availability"],
                            ", ".join(child["name"] for child in runs if child.get("parent_run") == run["name"])] for run in groups])
            elif args.json:
                print(json.dumps({"runs": runs}, indent=2))
            else:
                show_runs(runs)
        else:
            parser.error(f"Unknown action: {action}")
        return 0
    except (RuntimeError, ValueError, OSError) as error:
        log(str(error), error=True)
        return 1
