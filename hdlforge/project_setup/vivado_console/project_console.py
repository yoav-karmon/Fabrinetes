"""One client for persistent Vivado Tcl commands, native output and live summaries."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

from .console_transport import ConsoleUnavailable, ProjectConsole
from .project_paths import discover_project_json
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
    command = f"lvp_{action} {target}"
    if action in {"run_info", "group_info"}:
        command += f" {int(args.verbose)}"
    return command


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
            table(["Console"], [[v] for v in result.stdout.splitlines() if "_vivado_console_" in v])
            return 0
        project = (args.project_json or discover_project_json(Path.cwd())).resolve()
        if args.action == "update-json":
            install_commands(project, locate_own_key(project, os.environ.get("HDLFORGE_JSON_COMMAND_PATH")), True)
            return 0
        config = json.loads(project.read_text())
        console = ProjectConsole(project, args.timeout)
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
                    display_response({"request": "transport", "command": "status", "output": "Console stopped.\n", "result": "", "code": 0, "records": [{"CONSOLE": "stopped", "PROJECT_JSON": str(project)}]}, args.raw, args.json)
                return 0
            if args.action == "restart":
                if console.exists():
                    console.close(force=True)
                console.open()
                console.request("lvp_status")
                return 0
            if args.action == "console_output":
                return subprocess.run(["tmux", "capture-pane", "-p", "-t", console.session, "-S", "-"]).returncode
            if args.action == "close_project":
                console.open()
                console.request("lvp_close_project")
                console.request("lvp_status")
                return 0
            if args.action in {"start", "send", "source"}:
                console.open()
                if args.action == "start":
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
            console.request(run_command(args))
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        if args.json:
            print(json.dumps({"error": str(error), "code": 1}))
        else:
            print(f"Error: {error}", file=sys.stderr)
        return 1
