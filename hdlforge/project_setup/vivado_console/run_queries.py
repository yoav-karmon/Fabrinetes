#!/usr/bin/env python3
"""Refresh a run inventory and build HDLForge property completion shortcuts."""

import fcntl
import json
from pathlib import Path
import re
import shlex
import sys

if __package__:
    from .command_help import add_group_help
    from .terminal_output import operation, TableArgumentParser, machine_output, show_run_changes, show_text, show_properties, show_runs, table
    from .get_runs_from_live_xpr import discover_project_json, extract_runs, get_run_info, load_xpr_path
else:
    from command_help import add_group_help
    from terminal_output import operation, TableArgumentParser, machine_output, show_run_changes, show_text, show_properties, show_runs, table
    from get_runs_from_live_xpr import discover_project_json, extract_runs, get_run_info, load_xpr_path


def cache_path(project_json: Path) -> Path:
    return project_json.parent / "_proejct_manger.db.json"


def completion_tree(inventory: dict) -> dict:
    """Generate ordinary LLM_orch leaves for native HDLForge tab completion."""
    base = 'hdlforge --project "$HDLFORGE_PROJECT_FILE" --tool vivado --project_mng saved-runs'
    tree = {"all": base}
    for run in inventory["runs"]:
        run_key = re.sub(r"[^A-Za-z0-9_-]", "_", run["name"])
        if run_key in tree:
            raise ValueError(f"Run completion key collision: {run_key}")
        command = base + " --run " + shlex.quote(run["name"])
        node = {"all": command}
        tree[run_key] = node
        for name in sorted(run["properties"]):
            branch = node
            parts = [re.sub(r"[^A-Za-z0-9_-]", "_", part) for part in name.split(".")]
            for part in parts[:-1]:
                if part in branch and not isinstance(branch[part], dict):
                    branch[part] = {"_value": branch[part]}
                branch = branch.setdefault(part, {})
            leaf = command + " --property " + shlex.quote(name)
            key = parts[-1]
            if key in branch:
                if isinstance(branch[key], dict):
                    branch[key]["_value"] = leaf
                else:
                    raise ValueError(f"Property completion key collision: {run_key}.{name}")
            else:
                branch[key] = leaf
    return add_group_help(tree, "saved_runs.get")


def write_json(path: Path, value: dict) -> None:
    content = json.dumps(value, indent=2) + "\n"
    if path.exists() and path.read_text() == content:
        return
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content)
    temporary.replace(path)


def retain_descriptions(previous: dict, current: dict) -> None:
    """Keep inline descriptions for commands that survive a run refresh."""
    for name, value in previous.items():
        if name.startswith("#") and name[1:] in current:
            current[name] = value
        elif isinstance(value, dict) and isinstance(current.get(name), dict):
            retain_descriptions(value, current[name])


def update(project_json: Path) -> None:
    path = cache_path(project_json)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.with_suffix(".lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        previous = json.loads(path.read_text()) if path.exists() else {}
        inventory = extract_runs(load_xpr_path(project_json), console=True)
        # Read after the live query so unrelated edits made during it survive.
        config = json.loads(project_json.read_text())
        saved = config.get("LLM_orch", {}).get("vivado", {}).get("project_mng", {}).get("saved_runs", {})
        if "get" in saved:
            tree = completion_tree(inventory)
            retain_descriptions(saved["get"], tree)
            saved["get"] = tree
        write_json(path, inventory)
        write_json(project_json, config)
    show_run_changes(previous, inventory)


def main(argv: list[str] | None = None) -> int:
    parser = TableArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["update", "get"])
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--summary", action="store_true", help="Show saved run status without contacting Vivado")
    parser.add_argument("--run")
    parser.add_argument("--property")
    parser.add_argument("--project-json", type=Path)
    args = parser.parse_args(argv)
    try:
        project_json = args.project_json or discover_project_json(Path.cwd())
        if args.action == "update":
            with operation("Accessing live console and updating JSON", str(load_xpr_path(project_json)) + " -> " + str(cache_path(project_json)), machine=args.json):
                update(project_json)
            return 0
        path = cache_path(project_json)
        with operation("Reading saved run JSON", str(path), machine=args.json):
            if not path.exists():
                raise ValueError("No inventory: run hdlforge vivado.project_mng.saved_runs.refresh_from_open_project")
            inventory = json.loads(path.read_text())
            value = get_run_info(inventory, args.run)["run"] if args.run else inventory
            if args.property:
                if not args.run:
                    raise ValueError("--property requires --run")
                value = value["properties"][args.property]
            if args.json:
                machine_output(json.dumps(value, indent=2) + "\n")
            elif args.summary:
                show_runs([value] if args.run else inventory["runs"])
            elif args.property:
                table(["Run", "Property", "Value"], [[args.run, args.property, value]])
            else:
                show_properties(value)
        return 0
    except (OSError, RuntimeError, ValueError, KeyError) as error:
        show_text(str(error), "Error", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
