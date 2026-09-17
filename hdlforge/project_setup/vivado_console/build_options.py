"""Explicit run/group commands and copy-paste options from live Vivado metadata."""

import os
import shlex

from table_formatter import create_matrix_table_from_data

from .run_enable import blocked
from .project_console_commands import shortcut_path


OPERATIONS = {
    "build_run": ("run", "continue"), "build_group": ("group", "continue"),
    "reset_run": ("run", "reset"), "reset_group": ("group", "reset"),
    "enable_run": ("run", "enable"), "enable_group": ("group", "enable"),
    "disable_run": ("run", "disable"), "disable_group": ("group", "disable"),
}


def command(project, operation: str, arguments: list[str]) -> str:
    """Quote the entire appended payload so names with spaces remain one argument."""
    invoked = os.environ.get("HDLFORGE_JSON_COMMAND_PATH", "")
    if invoked.endswith(".get_build_options"):
        prefix = invoked.removeprefix("LLM_orch.").rsplit(".", 2)[0]
        return shlex.join(["hdlforge", prefix + "." + shortcut_path(operation), "--append", shlex.join(arguments)])
    return shlex.join(["hdlforge", "--tool", "vivado", "--project_mng", operation, *arguments])


def available_options(project, runs: list) -> list[dict]:
    """Describe enabled actions for each live synthesis group and individual run."""
    result = []
    for kind in ("group", "run"):
        for run in runs:
            if not run["eligible"] or (kind == "group" and run.get("parent_run")):
                continue
            disabled = blocked(run, runs)
            actions = [("reset", "Reset without launching", [])]
            if not disabled:
                actions = [("build", "Submit batch; Vivado resolves dependencies", []),
                           ("build", "Reset and full build", ["--reset"]),
                           *actions, ("disable", "Disable", [])]
            else:
                actions.append(("enable", "Enable (a disabled synthesis parent must also be enabled)", []))
            for operation, description, extra in actions:
                result.append({"kind": kind, "name": run["name"], "availability": "disabled" if disabled else "enabled",
                               "group": run.get("parent_run") or run["name"],
                               "description": description,
                               "command": command(project, operation + "_" + kind, ["--" + kind, run["name"], *extra])})
    return result


def print_options(options: list[dict]) -> None:
    """Keep one row per synthesis family and whole commands on separate cell lines."""
    groups = {}
    for option in options:
        groups.setdefault(option["group"], []).append(option)
    rows = []
    for group, entries in groups.items():
        entries.sort(key=lambda entry: (0 if entry["kind"] == "group" else 1 if entry["name"] == group else 2, entry["name"]))
        commands = {}
        for entry in entries:
            words = shlex.split(entry["command"])
            split = next(index for index, word in enumerate(words) if word in {"--append", "--run", "--group"})
            base = shlex.join(words[:split])
            commands.setdefault(base, []).append((shlex.join(words[split:]), entry["description"]))
        command_lines, argument_lines, explanations = [], [], []
        for base, variants in commands.items():
            command_lines.extend([base, *[""] * (len(variants) - 1)])
            argument_lines.extend(arguments for arguments, _ in variants)
            explanations.extend(description for _, description in variants)
        rows.append([group, "\n".join(command_lines), "\n".join(argument_lines), "\n".join(explanations)])
    # Keep each command and its shell-quoted arguments on one physical line.
    print(create_matrix_table_from_data(["Synthesis group", "Command", "Arguments", "Explanation"], rows or [["No groups found", "-", "-", "-"]]))
