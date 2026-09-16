"""Table help for project-manager groups, including saved property groups."""

import json
from pathlib import Path
import shlex

if __package__:
    from .project_console_commands import COMMANDS
    from .terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, table
else:
    from project_console_commands import COMMANDS
    from terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, table


GROUPS = {
    "": "Manage the background console, project files, and saved run database.",
    "background_console": "Control the live Vivado Tcl console that owns the open XPR.",
    "project_files": "Generate, export, or delete project files on disk.",
    "live_runs": "Query current run status directly from the open Vivado project.",
    "saved_runs": "Refresh the database from Vivado, then query saved values without contacting Vivado.",
    "saved_runs.get": "Read saved run properties. Use all for the full database, or select a run.",
}


def add_group_help(tree: dict, path: str = "") -> dict:
    """Add help at every command branch; also used when completion is refreshed."""
    for name, value in list(tree.items()):
        if not name.startswith("#") and isinstance(value, dict):
            add_group_help(value, f"{path}.{name}" if path else name)
    command = 'hdlforge --project "$HDLFORGE_PROJECT_FILE" --tool vivado --project_mng saved-help'
    if path:
        command += " --group " + shlex.quote(path)
    if "help" in tree and not tree["help"].startswith(command.split(" --group")[0]):
        raise ValueError(f"Reserved help command conflicts with saved property: {path}.help")
    tree["help"] = command
    tree["#help"] = "Describe commands and saved properties in this group."
    for name, value in list(tree.items()):
        if not name.startswith("#"):
            tree.setdefault("#" + name, "Saved property group." if isinstance(value, dict) else "Read saved run properties; no live Vivado query.")
    return tree


def main(argv: list[str] | None = None) -> None:
    parser = TableArgumentParser(description=__doc__)
    parser.add_argument("--group", default="")
    parser.add_argument("--project-json", type=Path)
    args = parser.parse_args(argv)
    paths = [args.project_json] if args.project_json else list(Path.cwd().glob("*.hdlforge.json"))
    if len(paths) != 1:
        parser.error("Expected exactly one project JSON in the current directory")
    with operation("Reading help from JSON", str(paths[0].resolve())):
        tree = json.loads(paths[0].read_text()).get("LLM_orch", {}).get("vivado", {}).get("project_mng")
        if tree is None:
            table(["Native action", "Description"], [[action, description] for action, description in COMMANDS.values()])
            return
        for name in args.group.split(".") if args.group else []:
            tree = tree[name]
        prefix = "hdlforge vivado.project_mng" + ("." + args.group if args.group else "")
        table(["Group", "Purpose"], [[prefix, GROUPS.get(args.group, "Read saved properties in this group; no live Vivado query.")]])
        known = {}
        rows = []
        for name, command in tree.items():
            if name.startswith("#"):
                continue
            path = f"{args.group}.{name}" if args.group else name
            description = tree.get("#" + name) or known.get(path) or GROUPS.get(path)
            if name == "help":
                description = "Explain this group and its commands."
            elif not description and isinstance(command, dict):
                description = "Saved run or property group; use .help to see its commands."
            elif not description:
                words = shlex.split(command)
                if "--property" in words:
                    description = "Read saved property: " + words[words.index("--property") + 1]
                else:
                    description = "Print all saved properties for this run." if "--run" in words else "Print the entire saved inventory."
            rows.append([name + ("." if isinstance(command, dict) else ""), description])
        table(["Command suffix", "What it does"], rows)


if __name__ == "__main__":
    main()
