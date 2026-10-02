"""Non-destructive project JSON initialization and strict, offline validation."""

import argparse
import copy
import getpass
import json
import os
from pathlib import Path
import socket
import shlex
import subprocess
import tempfile

from hdlforge_command_tree import parse
from ssh_config_inventory import render as render_ssh, unique_object
from vivado_console.project_console_commands import hdlforge_commands
from vivado_build import file_path


ENV = {"path": [], "path_import": [], "pythonpath": [], "pythonpath_import": [],
       "variables": {}, "variables_import": [], "tools": {"vivado": "", "verilator": ""}}
TARGET = {"top_module": "", "python_file": "", "build_args": [], "lint_args": [],
          "defines": {}, "parameters": {}, "test_name": None, "post_sim_collect": True,
          "env": {"pythonpath": []}}
RUN = {"script": "", "sources": []}
DEFAULTS = json.loads(Path(__file__).with_name("project_json_defaults.json").read_text())


def fill(value, defaults, path, changes):
    """Add missing keys recursively; never replace existing values or types."""
    if not isinstance(value, dict):
        raise ValueError(f"{path or 'root'} must be an object; existing value preserved")
    for key, default in defaults.items():
        location = f"{path}.{key}".strip(".")
        if key not in value:
            value[key] = copy.deepcopy(default)
            changes.append(location)
        elif location == "verilator.config.sim_targets" and isinstance(value[key], list):
            continue
        elif location.endswith(".build_args") and location != "verilator.config.build_args" and isinstance(value[key], (str, list)):
            continue
        elif isinstance(default, dict):
            fill(value[key], default, location, changes)


def objects(value, path):
    if not isinstance(value, dict):
        raise ValueError(f"{path} must be an object")
    return [(key, child) for key, child in value.items() if not key.startswith("#")]


def scope_defaults(scope):
    if scope == "vivado":
        result = {}
        for child in ("vivado.build", "vivado.console", "vivado.monitor"):
            fill(result, scope_defaults(child), "", [])
        return result
    if scope == "vivado.console":
        return {"LLM_orch": {"vivado": hdlforge_commands()}}
    return DEFAULTS[scope]


def normalize(data, scope, host, user):
    """Build the proposed document in memory, including every existing entry."""
    #######################################################################
    # Stage 1: prepare additions in memory; preserve every supplied value.   #
    #######################################################################
    result = copy.deepcopy(data)
    changes = []
    fill(result, scope_defaults(scope), "", changes)
    if scope in {"paths", "remote-ssh"}:
        envs = result["settings"]["env"]
        fill(envs, {host: {user: {}}}, "settings.env", changes)
        for machine, users in objects(envs, "settings.env"):
            for login, env in objects(users, f"settings.env.{machine}"):
                fill(env, ENV if scope == "paths" else {"ssh_config": {}}, f"settings.env.{machine}.{login}", changes)
    if scope in {"vivado", "vivado.build"}:
        for name, run in objects(result["vivado"]["non_project"]["runs"], "vivado.non_project.runs"):
            path = f"vivado.non_project.runs.{name}"
            fill(run, RUN, path, changes)
            if run.get("kind") != "ip":
                fill(run, {"impl_runs": {}}, path, changes)
            for child, impl in objects(run.get("impl_runs", {}), path + ".impl_runs"):
                fill(impl, RUN, path + ".impl_runs." + child, changes)
    if scope in {"vivado", "vivado.monitor"}:
        monitor = result["vivado"]["monitor"]
        for name, target in objects(monitor["execution_targets"], "execution_targets"):
            fill(target, {"ssh": "", "exec_prefix": []}, f"vivado.monitor.execution_targets.{name}", changes)
        for event, tasks in objects(monitor["event_tasks"], "event_tasks"):
            if not isinstance(tasks, list):
                raise ValueError(f"vivado.monitor.event_tasks.{event} must be an array")
            for index, task in enumerate(tasks):
                defaults = {"name": "", "timeout_seconds": 300}
                if not isinstance(task, dict) or "builtin" not in task:
                    defaults["command"] = []
                fill(task, defaults, f"vivado.monitor.event_tasks.{event}.{index}", changes)
        slack = monitor["notify"]["outputs"]["slack"]
        for login, credentials in objects(slack["user_settings"], "slack.user_settings"):
            fill(credentials, {"token": "", "app_token": ""}, f"vivado.monitor.notify.outputs.slack.user_settings.{login}", changes)
    if scope == "sim-verilator":
        targets = result["verilator"]["config"]["sim_targets"]
        entries = list(enumerate(targets)) if isinstance(targets, list) else objects(targets, "verilator.config.sim_targets")
        for name, target in entries:
            fill(target, TARGET, f"verilator.config.sim_targets.{name}", changes)
    return result, changes


def types(value, defaults, path, errors):
    for key, default in defaults.items():
        location = f"{path}.{key}".strip(".")
        if key not in value:
            errors.append(f"Missing key: {location}")
            continue
        supplied = value[key]
        if location == "verilator.config.sim_targets" and isinstance(supplied, list):
            continue
        if location.endswith((".build_args", ".lint_args")) and location != "verilator.config.build_args" and isinstance(supplied, (str, list)):
            continue
        if default is None:
            if supplied is not None and not isinstance(supplied, str):
                errors.append(f"{location} must be a string or null")
        elif isinstance(default, dict) and isinstance(supplied, dict):
            types(supplied, default, location, errors)
        elif type(supplied) is not type(default):
            if not (isinstance(default, float) and type(supplied) is int):
                errors.append(f"{location} must be {type(default).__name__}")


def check_file(project, value, location, errors, directory=False):
    if not isinstance(value, str):
        errors.append(f"{location} must be a path string")
        return
    if not value:
        return  # Explicit empty placeholders are valid JSON, not runnable inputs.
    expanded = os.path.expandvars(os.path.expanduser(value))
    try:
        if directory:
            if not (project.parent / expanded).is_dir():
                raise ValueError(f"Missing directory: {expanded}")
        else:
            file_path(project.parent, expanded)
    except (OSError, ValueError) as error:
        errors.append(f"{location}: {error}")


def lint(data, scope, project, host, user):
    #######################################################################
    # Stage 2: validate structure and inputs without starting any tool.     #
    #######################################################################
    errors = []
    try:
        proposed, missing = normalize(data, scope, host, user)
    except (KeyError, TypeError, ValueError) as error:
        return [str(error)]
    errors.extend("Missing key: " + path for path in missing)
    types(data, scope_defaults(scope), "", errors)
    if scope in {"vivado", "vivado.build"}:
        for key in ("config", "external_config"):
            if key in data.get("vivado", {}):
                errors.append(f"vivado.{key} is retired; use vivado.non_project")
        retired = {"stage", "part", "top", "ips", "constraints", "input_files", "defines",
                   "parameters", "project_properties", "fileset_properties", "post_load_parameters",
                   "checkpoint_properties", "constraint_properties"}
        for name, run in objects(proposed["vivado"]["non_project"]["runs"], "runs"):
            for label, entry in [(name, run), *[(name + "." + k, v) for k, v in objects(run.get("impl_runs", {}), "impl_runs")]]:
                types(entry, RUN, label, errors)
                for key in entry.keys() - {"script", "sources", "impl_runs", "kind"} - retired:
                    errors.append(f"{label}.{key} is not a supported build key")
                if entry.get("kind", "ip") != "ip":
                    errors.append(f"{label}.kind must be ip when provided")
                for key in retired & entry.keys():
                    errors.append(f"{label}.{key} is retired; put design settings in Tcl")
                check_file(project, entry["script"], label + ".script", errors)
                if isinstance(entry["sources"], list):
                    for source in entry["sources"]:
                        check_file(project, source, label + ".sources", errors)
    if scope == "sim-verilator":
        config = proposed["verilator"]["config"]
        for key in ("sources", "includes_paths"):
            if isinstance(config[key], list):
                for value in config[key]:
                    check_file(project, value, "verilator.config." + key, errors, key == "includes_paths")
        targets = config["sim_targets"]
        for name, target in (enumerate(targets) if isinstance(targets, list) else objects(targets, "sim_targets")):
            types(target, TARGET, str(name), errors)
            check_file(project, target["python_file"], str(name) + ".python_file", errors)
            if isinstance(target["env"]["pythonpath"], list):
                for path in target["env"]["pythonpath"]:
                    check_file(project, path, str(name) + ".env.pythonpath", errors, True)
    if scope == "aliases":
        def visit(node, path):
            for name, value in objects(node, path):
                if isinstance(value, dict):
                    visit(value, path + "." + name)
                elif isinstance(value, str) and value.startswith("hdlforge "):
                    try:
                        # Shell payloads remain quoted words; inspect native invocations only.
                        lexer = shlex.shlex(value, posix=True, punctuation_chars=";&|")
                        lexer.whitespace_split = True
                        tokens = list(lexer)
                        commands = [[]]
                        for token in tokens:
                            if token in {";", "&&", "||", "|"}:
                                commands.append([])
                            else:
                                commands[-1].append(token)
                        for command in commands:
                            if not command or command[0] != "hdlforge":
                                continue
                            arguments = command[1:]
                            if "--project" in arguments:
                                arguments[arguments.index("--project") + 1] = str(project)
                            else:
                                arguments += ["--project", str(project)]
                            parse(arguments, project.parent)
                    except (ValueError, IndexError) as error:
                        errors.append(f"{path}.{name}: {error}")
        visit(proposed["LLM_orch"], "LLM_orch")
    if scope == "remote-ssh":
        for machine, users in objects(proposed["settings"]["env"], "settings.env"):
            for login, env in objects(users, machine):
                try:
                    render_ssh(env["ssh_config"])
                except ValueError as error:
                    errors.append(f"settings.env.{machine}.{login}.ssh_config: {error}")
    if scope in {"vivado", "vivado.monitor"}:
        monitor = proposed["vivado"]["monitor"]
        for name, target in objects(monitor["execution_targets"], "execution_targets"):
            types(target, {"ssh": "", "exec_prefix": []}, f"vivado.monitor.execution_targets.{name}", errors)
        for login, credentials in objects(monitor["notify"]["outputs"]["slack"]["user_settings"], "slack.user_settings"):
            types(credentials, {"token": "", "app_token": ""}, f"slack.user_settings.{login}", errors)
        for event, tasks in objects(monitor["event_tasks"], "event_tasks"):
            if not isinstance(tasks, list):
                continue  # The schema type check already reports this.
            for index, task in enumerate(tasks):
                location = f"vivado.monitor.event_tasks.{event}.{index}"
                if not isinstance(task, dict):
                    errors.append(location + " must be an object")
                    continue
                types(task, {"name": "", "timeout_seconds": 300}, location, errors)
                if "builtin" in task and task["builtin"] != "collect":
                    errors.append(location + ".builtin must be collect")
                command = task.get("command", [])
                if not isinstance(command, list) or any(not isinstance(part, str) for part in command):
                    errors.append(location + ".command must be a string array")
                elif command and "/" in command[0] and "{" not in command[0]:
                    check_file(project, command[0], location + ".command", errors)
    if scope == "paths":
        for machine, users in objects(proposed["settings"]["env"], "settings.env"):
            for login, env in objects(users, machine):
                types(env, ENV, f"settings.env.{machine}.{login}", errors)
        # Use the startup resolver for identical import/cycle/type semantics.
        environment = Path(__file__).with_name("hdlforge_environment.bash")
        command = 'source "$1"; HDLFORGE_JQ="$(command -v jq)"; hdlforge_read_repository_environment "$2" "$3" "$4"'
        result = subprocess.run(["bash", "-c", command, "bash", str(environment), str(project), host, user], capture_output=True, text=True)
        if result.returncode:
            errors.append(result.stderr.strip())
        else:
            for layer in json.loads(result.stdout):
                for key in ("path", "pythonpath"):
                    for value in layer.get(key, []):
                        check_file(project, value, "settings.env." + key, errors, True)
                for value in layer.get("tools", {}).values():
                    check_file(project, value, "settings.env.tools", errors)
    return list(dict.fromkeys(errors))


def write_update(project, original, proposed):
    """Replace atomically only if the reviewed input is still current."""
    #######################################################################
    # Stage 3: publish a checked replacement only when content is unchanged.#
    #######################################################################
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=project.parent, prefix=".hdlforge-json-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(proposed, indent=2) + "\n")
        temporary.chmod(project.stat().st_mode)
        if project.read_text() != original:
            raise ValueError("Project JSON changed during update; retry")
        os.replace(temporary, project)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scope", choices=[*DEFAULTS, "vivado", "vivado.console"])
    parser.add_argument("action", choices=["update-json", "lint-json"])
    parser.add_argument("--project", required=True, type=Path)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        project = args.project.resolve(strict=True)
        original = project.read_text()
        data = json.loads(original, object_pairs_hook=unique_object)
        host = os.environ.get("HDLFORGE_SELECTED_HOST") or os.environ.get("HOST_MACHINE") or socket.gethostname().split(".")[0]
        user = os.environ.get("HDLFORGE_SELECTED_USER") or os.environ.get("HDLFORGE_HOST_USER") or getpass.getuser()
        if args.action == "lint-json":
            errors = lint(data, args.scope, project, host, user)
            for error in errors:
                print(error)
            if not errors:
                print(f"{args.scope}: JSON valid; configured input paths resolve")
            return int(bool(errors))
        proposed, changes = normalize(data, args.scope, host, user)
        for path in changes:
            print("Add " + path)
        if not changes:
            print("No changes needed")
        elif args.dry_run:
            print("Dry run: no files changed")
        else:
            write_update(project, original, proposed)
        return 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print(f"error: {error}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
