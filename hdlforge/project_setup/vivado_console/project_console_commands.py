"""Reusable HDLForge command definitions for the persistent project console."""

import json
import os
from pathlib import Path
import tempfile


CATALOG = json.loads((Path(__file__).resolve().parents[1] / "native_command_help.json").read_text())
COMMANDS = {name: (action, CATALOG["project_console"]["#" + name])
            for name, action in CATALOG["project_console"].items() if not name.startswith("#")}


def shortcut_path(name: str) -> str:
    """Return the public shortcut location for a native console command."""
    management_names = {"name": "project_info", "list": "list_consoles", "capture": "console_output"}
    if name in management_names:
        return "management." + management_names[name]
    if name in {"restart", "close", "status", "list", "name", "capture", "clean", "install-json", "update-json", "print-hdlforge-json-commends"}:
        return "management." + name
    if name in {"build_run", "build_group", "reset_run", "reset_group", "get_build_options", "clean_logs"}:
        return "build." + name
    if name in {"get_runs", "get_groups", "enable_run", "enable_group", "disable_run", "disable_group"}:
        return "runs." + name
    if name == "runs":
        return "runs.list"
    return name


def hdlforge_commands() -> dict:
    """Return console keys without imposing the caller's parent JSON path."""
    root = {
        "#management": "Manage console sessions, clean the generated project, and print, install, or update JSON shortcuts.",
        "management": {},
        "#build": "Inspect build options, launch or reset builds, monitor workers, and clean logs.",
        "build": {},
        "#runs": "List live runs and synthesis groups and control their availability.",
        "runs": {},
    }
    for name, (action, description) in COMMANDS.items():
        path = shortcut_path(name).split(".")
        target = root[path[0]] if len(path) == 2 else root
        name = path[-1]
        target["#" + name] = description
        target[name] = 'hdlforge --project "$HDLFORGE_PROJECT_FILE" --tool vivado --project_mng ' + ("help" if action == "--help" else action)
    return {
        "#project_console": "Manage the persistent Vivado project console. Pass extra options with --append; --timeout sets the wait limit and --raw removes table formatting.",
        "project_console": root,
    }


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
        own = management.get("update-json") if isinstance(management, dict) else None
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
