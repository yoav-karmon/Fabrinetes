"""One client for persistent Vivado Tcl commands, native output and live summaries."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .console_transport import ConsoleUnavailable, ProjectConsole
from .project_paths import discover_project_json, load_xpr_path
from .project_console_commands import COMMANDS, shortcut_path, hdlforge_commands, install_commands, locate_own_key
from .tcl_arguments import tcl_word
from .terminal_output import table
from .run_output import run_tables
from .run_configuration import configuration_tables
from .log_analysis import enrich
from .follow import follow


def display_response(response: dict, raw: bool = False, machine: bool = False) -> None:
    """Never omit native warnings/errors; summaries are outside the transcript."""
    if machine:
        print(json.dumps(response), flush=True)
        return
    state = "ERROR" if response["code"] else "OK"
    print(f"=== VIVADO OUTPUT BEGIN | {response['request']} ===", flush=True)
    print("Command: " + response["command"], flush=True)
    print(response["output"], end="" if response["output"].endswith("\n") else "\n", flush=True)
    if response["result"]:
        print(response["result"], flush=True)
    print(f"=== VIVADO OUTPUT END | {response['request']} | result={state} ===", flush=True)
    if response.get('analysis_error'):
        print('Log analysis unavailable: ' + response['analysis_error'])
    records = response.get("records", [])
    if records and not raw:
        if configuration_tables(records):
            return
        if run_tables(records):
            return
        if len(records) == 1:
            table(["Property", "Value"], list(records[0].items()))
        else:
            keys = list(dict.fromkeys(k for record in records for k in record))
            labels = {"NAME": "Run", "PARENT": "Parent", "STATUS": "Status", "PROGRESS": "Progress", "CURRENT_STEP": "Step", "STATS.ELAPSED": "Elapsed", "NEEDS_REFRESH": "Refresh", "ENABLED": "Enabled"}
            table([labels.get(k, k.removeprefix("STATS.")) for k in keys], [[record.get(k, "") for k in keys] for record in records])


def run_command(args: argparse.Namespace) -> str:
    """Map arguments to prefabricated procedures; all run semantics live in Tcl."""
    action = args.action
    target = args.group if "group" in action else args.run
    if action in {"get_runs", "get_groups"}:
        return "lvp_" + action
    if not target:
        return "lvp_get_groups" if "group" in action else "lvp_get_runs"
    target = tcl_word(target)
    if action == "set_run_property":
        if not args.property:
            return f"lvp_run_properties {target}"
        if args.value is None:
            raise ValueError("set_run_property requires --value (use an empty string to clear)")
        return f"lvp_edit_run_property {target} {tcl_word(args.property)} {tcl_word(args.value)}"
    if action in {"incremental_on", "incremental_off"}:
        return f"lvp_incremental {target} {int(action == 'incremental_on')}"
    if action.startswith(("enable_", "disable_")):
        return f"lvp_set_enabled {target} {int(action.startswith('enable_'))} {int('group' in action)}"
    command = f"lvp_{action} {target}"
    if action in {"build_run", "build_group"}:
        command += f" {args.jobs} {int(not args.no_bitstream)} {int(args.reset)}"
    elif action == "build_bitstream":
        command += f" {args.jobs}"
    elif action in {"run_info", "group_info"}:
        command += f" {int(args.verbose)}"
    return command


def confirm_close(console: ProjectConsole, args: argparse.Namespace, export_path: Path) -> None:
    """A forced close skips export/confirmation, never implicitly stops active runs."""
    console.request("lvp_status")
    records = console.last_response.get("records", [])
    if not records or not records[0].get("PROJECT"):
        return
    opened = records[0].get("XPR")
    if not opened or Path(opened).resolve() != console.xpr.resolve():
        raise RuntimeError(f"HDLForge JSON targets {console.xpr}, but the console has {opened or 'an unidentified project'} open. Nothing was closed.")
    if not args.force:
        if not sys.stdin.isatty():
            raise RuntimeError("Project is open. Export/close it first, or pass --force to close without exporting Tcl; active runs are still protected.")
        answer = input("Export current project to Tcl before closing? [y/N/cancel] ").strip().lower()
        if answer in {"c", "cancel"}:
            raise RuntimeError("Cancelled; project remains open")
        if answer not in {"", "n", "no", "y", "yes"}:
            raise ValueError("Enter yes, no, or cancel; project remains open")
        if answer in {"y", "yes"}:
            # Never overwrite the Tcl about to be sourced during regeneration.
            destination = export_path.with_name(export_path.stem + ".before-close.tcl")
            console.request(f"lvp_export {tcl_word(destination)}")
    console.request("lvp_close_project")


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    result.add_argument("action", nargs="?", default="help", choices=sorted(COMMANDS))
    result.add_argument("--project-json", type=Path)
    selection = result.add_mutually_exclusive_group()
    selection.add_argument("--run")
    selection.add_argument("--group")
    result.add_argument("--cmd")
    result.add_argument("--property")
    result.add_argument("--value")
    result.add_argument("--file", type=Path)
    result.add_argument("--output", type=Path)
    result.add_argument("--jobs", type=int, default=1)
    result.add_argument("--reset", action="store_true")
    result.add_argument("--no-bitstream", action="store_true")
    result.add_argument("--force", action="store_true")
    result.add_argument("--raw", action="store_true")
    result.add_argument("--json", action="store_true", help="JSON response envelopes include the full transcript, Tcl result and records")
    result.add_argument("--verbose", action="store_true")
    result.add_argument("--timeout", type=float, default=180)
    result.add_argument("--interval", type=float, default=5)
    result.add_argument("--once", action="store_true")
    result.add_argument("--json-file", type=Path)
    result.add_argument("--key")
    result.add_argument("--overwrite", action="store_true")
    return result


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        if args.jobs < 1:
            raise ValueError("jobs must be positive")
        if args.action == "help":
            table(["Command", "Description"], sorted([[shortcut_path(name), value[1]] for name, value in COMMANDS.items()]))
            return 0
        if args.action == "print-json":
            print(json.dumps(hdlforge_commands(), indent=2))
            return 0
        if args.action == "install-json":
            if not args.json_file or not args.key:
                raise ValueError("install-json requires --json-file and --key")
            install_commands(args.json_file, args.key, args.overwrite)
            return 0
        if args.action == "list_consoles":
            result = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True)
            table(["Console"], [[v] for v in result.stdout.splitlines() if "_vivado_xpr_" in v])
            return 0
        project = (args.project_json or discover_project_json(Path.cwd())).resolve()
        if args.action == "update-json":
            install_commands(project, locate_own_key(project, os.environ.get("HDLFORGE_JSON_COMMAND_PATH")), True)
            return 0
        config = json.loads(project.read_text())
        export_path = (project.parent / config["vivado"]["external_config"]["filename"]).resolve()
        console = ProjectConsole(load_xpr_path(project), args.timeout, project)
        console.on_response = lambda response: display_response(enrich(response), args.raw, args.json)
        if args.action == "follow":
            if args.run:
                raise ValueError('follow accepts --group SYNTH; omit it to follow all active groups')
            return follow(console, args.group or '', args.interval, args.once, args.json,
                          config.get('vivado', {}).get('monitor', {}).get('execution_targets', {}))
        if args.action == "stop":
            console.close(force=True)
            print(f"Console terminated: {console.session}")
            return 0
        if args.action == "interactive":
            with console.locked():
                console.open()
            return subprocess.run(["tmux", "attach-session", "-t", console.session]).returncode
        with console.locked():
            if args.action == "status":
                if console.exists():
                    if console.pending_request():
                        display_response({"request": "transport", "command": "status", "output": "Console alive; Tcl request pending.\n", "result": str(console.pending_request()), "code": 0, "records": []}, args.raw, args.json)
                    else:
                        console.request("lvp_status")
                else:
                    display_response({"request": "transport", "command": "status", "output": "Console stopped.\n", "result": "", "code": 0, "records": [{"CONSOLE": "stopped", "CONFIGURED_XPR": str(console.xpr)}]}, args.raw, args.json)
                return 0
            if args.action == "restart":
                if console.exists():
                    confirm_close(console, args, export_path)
                    console.close()
                console.open()
                if console.xpr.exists():
                    console.request(f"lvp_open_project {tcl_word(console.xpr)}")
                console.request("lvp_status")
                return 0
            if args.action == "console_output":
                return subprocess.run(["tmux", "capture-pane", "-p", "-t", console.session, "-S", "-"]).returncode
            if args.action == "close_project":
                console.open()
                confirm_close(console, args, export_path)
                console.request("lvp_status")
                return 0
            if args.action in {"generate_project_from_tcl", "regenerate_project"}:
                console.open()
                confirm_close(console, args, export_path)
                console.request(f"lvp_generate {tcl_word(export_path)} {tcl_word(console.xpr.parent)} {tcl_word(project.parent)}")
                if args.action == "regenerate_project":
                    console.request(f"lvp_open_project {tcl_word(console.xpr)}\nlvp_status")
                return 0
            if args.action in {"start", "send", "source"}:
                console.open()
                if args.action == "start":
                    if console.xpr.exists():
                        console.request(f"lvp_open_project {tcl_word(console.xpr)}")
                    console.request("lvp_status")
                elif args.action == "send":
                    if not args.cmd:
                        raise ValueError("send requires --cmd")
                    console.request(args.cmd)
                else:
                    if not args.file:
                        raise ValueError("source requires --file")
                    console.request(f"source {tcl_word(args.file.resolve())}")
                return 0
            console.open()
            prefix = f"lvp_open_project {tcl_word(console.xpr)}\n"
            if args.action == "export_open_project_to_tcl":
                console.request(prefix + f"lvp_export {tcl_word((args.output or export_path).resolve())}")
            else:
                console.request(prefix + run_command(args))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        if args.json:
            print(json.dumps({"error": str(error), "code": 1}))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1
