"""Reusable HDLForge command definitions for the persistent project console."""

import json
import os
from pathlib import Path
import tempfile


CATALOG = json.loads((Path(__file__).resolve().parents[1] / "native_command_help.json").read_text())
COMMANDS = {name: (action, CATALOG["project_console"]["#" + name])
            for name, action in CATALOG["project_console"].items() if not name.startswith("#")}

GROUPS = {'aux': ('Execute Tcl commands or source Tcl files.', 'send source'),
 'management': ('Console lifecycle and terminal access.',
                'status start stop restart interactive list_consoles console_output'),
 'help': ('Command help and JSON installation.', 'help install-json print-json')}

DISPLAY_NAMES = {
 'send': 'execute_tcl',
 'source': 'source_tcl',
 'status': 'inspect_console',
 'start': 'open_console',
 'stop': 'terminate_console',
 'restart': 'restart_console',
 'interactive': 'attach_console',
 'list_consoles': 'list_consoles',
 'console_output': 'capture_output',
 'help': 'commands',
 'install-json': 'install-json',
 'print-json': 'print-json'}

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
                target["#" + part] = part.capitalize() + " commands."
                target[part] = {}
            target = target[part]
        leaf = path[-1]
        target["#" + leaf] = description
        target[leaf] = 'hdlforge vivado.console.' + ('help' if action == '--help' else action) + ' --project "$HDLFORGE_PROJECT_FILE"'
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
