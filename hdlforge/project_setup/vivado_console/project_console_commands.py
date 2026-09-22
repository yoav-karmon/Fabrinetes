"""Reusable HDLForge command definitions for the persistent project console."""

import json
import os
from pathlib import Path
import tempfile


CATALOG = json.loads((Path(__file__).resolve().parents[1] / "native_command_help.json").read_text())
COMMANDS = {name: (action, CATALOG["project_console"]["#" + name])
            for name, action in CATALOG["project_console"].items() if not name.startswith("#")}

GROUPS = {
    "aux": ("Execute Tcl commands or source Tcl files in the console.", "send source"),
    "management": ("Console status, start, stop, restart and terminal access.",
                   "status start stop restart interactive list_consoles console_output"),
    "project": ("Close, export, generate or regenerate the project.",
                "close_project export_open_project_to_tcl generate_project_from_tcl regenerate_project"),
    "runs": ("List runs and groups; inspect live status and properties.",
             "get_runs get_groups run_info run_status group_info group_status reuse_status follow"),
    "build": ("Launch, stop or reset runs and groups through Tcl.",
              "build_run build_group build_bitstream stop_run stop_group reset_run reset_group"),
    "settings": ("Edit run properties, incremental compilation and launch enablement.",
                 "set_run_property incremental_on incremental_off clear_refresh enable_run disable_run enable_group disable_group"),
    "help": ("Command help and JSON installation.", "help install-json print-json"),
}

DISPLAY_NAMES = {
    "follow": "follow_active_groups",
    "send": "execute_tcl", "source": "source_tcl",
    "status": "inspect_console", "start": "open_console", "stop": "terminate_console", "restart": "restart_console",
    "interactive": "attach_console", "list_consoles": "list_consoles", "console_output": "capture_output",
    "close_project": "close_project", "export_open_project_to_tcl": "export_open_project_to_tcl",
    "generate_project_from_tcl": "generate_project_from_tcl", "regenerate_project": "regenerate_project",
    "get_runs": "list_runs", "get_groups": "enumerate_groups", "run_info": "inspect_run",
    "run_status": "status_run", "group_info": "configuration_group", "group_status": "group_status",
    "reuse_status": "reuse_status", "build_run": "launch_run", "build_group": "build_group",
    "build_bitstream": "write_bitstream", "stop_run": "terminate_run", "stop_group": "halt_group",
    "reset_run": "reset_run", "reset_group": "clear_group_results",
    "set_run_property": "edit_run_property", "incremental_on": "enable_incremental",
    "incremental_off": "disable_incremental", "clear_refresh": "clear_refresh",
    "enable_run": "activate_run", "enable_group": "permit_group",
    "disable_run": "block_run", "disable_group": "suspend_group",
    "help": "commands", "install-json": "install-json", "print-json": "print-json",
}


def shortcut_path(name: str) -> str:
    for group, (_, actions) in GROUPS.items():
        if name in actions.split():
            return group + "." + DISPLAY_NAMES[name]
    return name


def hdlforge_commands() -> dict:
    """One console namespace, with no separate build manager or batch interface."""
    root = {}
    for group, (description, _) in GROUPS.items():
        root["#" + group] = description
        root[group] = {}
    for name, (action, description) in COMMANDS.items():
        path = shortcut_path(name).split(".")
        target = root
        for part in path[:-1]:
            if part not in target:
                target["#" + part] = part.capitalize() + " a run or group." if part != "incremental" else "Enable or disable automatic incremental compilation."
                target[part] = {}
            target = target[part]
        leaf = path[-1]
        target["#" + leaf] = description
        target[leaf] = 'hdlforge --project "$HDLFORGE_PROJECT_FILE" --tool vivado --project_console ' + action
    return {"#project_console": "Persistent Vivado Tcl console; full command transcripts and live summaries.",
            "project_console": root}


def install_commands(filename: Path, key: str, overwrite: bool = False) -> None:
    """Replace the console group under a dotted parent key, keeping siblings."""
    parts = key.split(".")
    if any(not part.strip() for part in parts):
        raise ValueError("--key must be a nonempty dotted parent path, for example LLM_orch.vivado")
    filename = filename.resolve(strict=True)
    config = json.loads(filename.read_text())
    parent = config
    for part in parts:
        if not isinstance(parent, dict):
            raise ValueError(f"--key {key!r} traverses a value that is not a JSON object")
        parent = parent.setdefault(part, {})
    if not isinstance(parent, dict):
        raise ValueError(f"--key {key!r} must identify a JSON object")
    if not overwrite and ("project_console" in parent or "#project_console" in parent):
        raise ValueError(f"WARNING: {key}.project_console already exists. No changes made. Use --overwrite to replace the entire group.")
    parent.update(hdlforge_commands())
    # Replace the complete file atomically only after validating the target.
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=filename.parent, prefix=f".{filename.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(json.dumps(config, indent=2) + "\n")
        temporary.chmod(filename.stat().st_mode & 0o777)
        os.replace(temporary, filename)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def locate_own_key(filename: Path, invoked_key: str | None = None) -> str:
    """Locate this update shortcut; require a unique match without invocation context."""
    config = json.loads(filename.read_text())
    matches = []

    def visit(value: object, path: list[str]) -> None:
        if not isinstance(value, dict):
            return
        management = value.get("management", {})
        own = value.get("update-json") or (management.get("update-json") if isinstance(management, dict) else None)
        own = own or value.get("update-json")
        if path and path[-1] == "project_console" and isinstance(own, str) and any(flag + " update-json" in own for flag in ("--project_console", "--project_mng")):
            matches.append(".".join(path[:-1]))
        for name, child in value.items():
            if not name.startswith("#"):
                visit(child, [*path, name])

    visit(config, [])
    if invoked_key:
        for suffix in (".project_console.management.update-json", ".project_console.update-json"):
            if invoked_key.endswith(suffix) and invoked_key[:-len(suffix)] in matches:
                return invoked_key[:-len(suffix)]
        raise ValueError("The invoking shortcut does not identify a project_console.management.update-json group in this file")
    if len(matches) != 1:
        raise ValueError(f"Cannot uniquely locate project_console: found {len(matches)} groups. Run the desired group's update-json shortcut.")
    return matches[0]
