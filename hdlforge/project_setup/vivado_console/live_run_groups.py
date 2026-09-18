"""Live project queries and console-free batch command dispatch."""

import argparse
import base64
from contextlib import nullcontext
import json
from pathlib import Path
import xml.etree.ElementTree as ET

from . import batch_build
from .build_options import available_options, print_options
from .get_runs_from_live_xpr import load_xpr_path
from .project_console import ConsoleUnavailable, ProjectConsole, tcl_word
from .run_enable import blocked, is_enabled, set_enabled
from .terminal_output import log, show_runs, table


FIELDS = ["NAME", "PARENT", "IS_SYNTHESIS", "IS_IMPLEMENTATION", "STATUS", "PROGRESS", "NEEDS_REFRESH", "FLOW", "DIRECTORY", "DESCRIPTION", "CURRENT_STEP", "HDLFORGE_IS_IP", "STRATEGY"]
HELPERS = Path(__file__).resolve().parents[1] / "project_management_helpers.tcl"


def saved_run_options(xpr: Path) -> list:
    """Read saved run names and configuration without opening Vivado."""
    rows = []
    for run in ET.parse(xpr).findall("./Runs/Run"):
        strategy = run.find("./Strategy/StratHandle")
        flow = strategy.get("Flow", "") if strategy is not None else ""
        description = run.get("Description", "")
        rows.append({"name": run.attrib["Id"], "parent_run": run.get("SynthRun"),
                     "properties": {"NAME": run.attrib["Id"], "DESCRIPTION": description, "FLOW": flow,
                                    "IS_SYNTHESIS": "1" if run.get("Type") == "Ft3:Synth" else "0",
                                    "IS_IMPLEMENTATION": "0" if run.get("Type") == "Ft3:Synth" else "1",
                                    "STATUS": "See monitor", "STRATEGY": strategy.get("Name", "") if strategy is not None else ""},
                     "enabled": is_enabled(description),
                     "eligible": not run.get("ParentHierarchy") and "Vivado IDR Flow" not in flow})
    return rows


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
    parser = argparse.ArgumentParser(description="Submit batches; use the Vivado monitor for build status.")
    selectors = parser.add_mutually_exclusive_group()
    selectors.add_argument("--run")
    selectors.add_argument("--group")
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--no-bitstream", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args(argv)
    if args.jobs < 1:
        parser.error("jobs must be positive")
    try:
        if action in {"build_run", "build_group", "reset_run", "reset_group"}:
            kind = action.split("_")[1]
            target = getattr(args, kind)
            if not target:
                parser.error(f"Pass --{kind} NAME")
            result = batch_build.start(load_xpr_path(project), target, kind, args.jobs, args.reset,
                                       action.startswith("reset_"), not args.no_bitstream)
            return result["exit_code"] or 0
        console = ProjectConsole(load_xpr_path(project), project_file=project)
        console.force_recovery = args.force
        if action in {"build", "build.", "run_groups", "run_groups."}:
            parser.error("Use build_run --run NAME or build_group --group NAME")
        if action not in {"get_runs", "get_groups", "runs", "get_build_options"} and args.force and console.pending_request() is not None:
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
            options = available_options(project, saved_run_options(console.xpr))
            print(json.dumps({"options": options}, indent=2)) if args.json else print_options(options)
        elif action in {"get_runs", "get_groups", "runs"}:
            runs = saved_run_options(console.xpr)
            for run in runs:
                run["availability"] = "excluded (IDR)" if not run["eligible"] else "disabled" if blocked(run, runs) else "enabled"
            if action == "runs":
                table(["Run"], [[run["name"]] for run in runs])
            elif action == "get_groups":
                groups = [run for run in runs if run["properties"].get("IS_SYNTHESIS") in {"1", "true"}]
                if args.json:
                    print(json.dumps({"groups": groups}, indent=2))
                else:
                    table(["Group", "Availability", "Implementations"],
                          [[run["name"], run["availability"],
                            ", ".join(child["name"] for child in runs if child.get("parent_run") == run["name"])] for run in groups])
            elif args.json:
                print(json.dumps({"runs": runs}, indent=2))
            else:
                show_runs(runs)
        else:
            parser.error(f"Unknown action: {action}")
        return 0
    except (RuntimeError, ValueError, OSError, ET.ParseError) as error:
        log(str(error), error=True)
        return 1
