"""Plain operational logs and structured report tables for Vivado commands."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import shutil
import sys

if __package__:
    from .run_groups import changed_runs, group_runs
else:
    from run_groups import changed_runs, group_runs


RENDERER = runpy.run_path(str(Path(__file__).resolve().parents[1] / "table_formatter.py"))


def log(message: str, error: bool = False) -> None:
    """Print an operational message without table formatting."""
    print(message, file=sys.stderr if error else sys.stdout, flush=True)


@contextmanager
def operation(action: str, source: str, machine: bool = False):
    """Report the actual data source before work and its outcome afterward."""
    state = {"status": "Done"}
    log(f"[Working] {action}: {source}", error=machine)
    try:
        yield state
    except BaseException:
        state["status"] = "Failed"
        raise
    finally:
        log(f"[{state['status']}] {action}: {source}", error=machine)


class TableArgumentParser(argparse.ArgumentParser):
    """Render CLI help as tables and argument errors as plain messages."""

    def print_help(self, file=None) -> None:
        with operation("Reading built-in command help", self.prog):
            table(["Command", "Purpose"], [[self.prog, self.description or ""]])
            rows = [[", ".join(action.option_strings) or action.dest,
                     action.help or ("Choices: " + ", ".join(action.choices) if action.choices else "")]
                    for action in self._actions if action.help != argparse.SUPPRESS]
            table(["Argument", "Description"], rows)

    def error(self, message: str) -> None:
        log(f"[Error] {message}", error=True)
        raise SystemExit(2)


def machine_output(value: str) -> None:
    """Central output path for explicitly requested raw or JSON payloads."""
    sys.stdout.write(value)


def table(headers: list, rows: list, error: bool = False) -> None:
    """Print a bordered table wrapped to the terminal width."""
    width = max(60, shutil.get_terminal_size((140, 24)).columns)
    widths = [max(len(line) for row in [headers, *rows] for line in (str(row[index]).splitlines() or [""])) for index in range(len(headers))]
    while sum(widths) + 3 * len(headers) + 1 > width and max(widths) > 12:
        index = widths.index(max(widths))
        widths[index] -= 1
    rendered = RENDERER["create_matrix_table_from_data"](headers, rows, col_wrapped_limits=dict(enumerate(widths)))
    print(rendered, file=sys.stderr if error else sys.stdout, flush=True)


def show_console_status(output: str) -> None:
    """Separate project fields and run names instead of boxing a console dump."""
    fields = [["Console", "Open"]]
    runs = []
    for line in output.splitlines():
        key, separator, value = line.partition(":")
        if key.strip() == "runs" and separator:
            runs = value.split()
            fields.append(["Run count", str(len(runs))])
        elif separator:
            fields.append([key.strip().capitalize(), value.strip()])
        elif line.strip():
            fields.append(["Information", line.strip()])
    table(["Field", "Value"], fields)
    table(["Run"], [[run] for run in runs] or [["No runs found"]])


def show_text(output: str, label: str = "Result", error: bool = False) -> None:
    """Print console output and log excerpts as plain text."""
    log(f"{label}:\n{output}" if output else f"{label}: Completed", error=error)


def properties(value: object, prefix: str = "") -> list:
    """Flatten records without dropping nested values or empty containers."""
    if isinstance(value, dict) and value:
        return [row for key, child in value.items() for row in properties(child, f"{prefix}.{key}" if prefix else key)]
    if isinstance(value, list) and value:
        return [row for index, child in enumerate(value) for row in properties(child, f"{prefix}[{index}]")]
    return [[prefix, value if isinstance(value, str) else json.dumps(value)]]


def show_properties(value: object) -> None:
    table(["Property", "Value"], properties(value))


def show_runs(runs: list) -> None:
    """Display each parent and its descendants together in a separate table."""
    headers = ["Run", "Status", "Parent", "Strategy"]
    availability = any("availability" in run for run in runs)
    if availability:
        headers.append("Availability")
    if not runs:
        table(headers, [["No runs found", "-", "-", "-"]])
        return
    for title, family in group_runs(runs):
        rows = [[run["name"], run["properties"].get("STATUS", "-"),
                 run.get("parent_run") or "-", run["properties"].get("STRATEGY", "-")]
                + ([run.get("availability", "-")] if availability else [])
                for run in family]
        log(f"\nParent run: {title}")
        table(headers, rows)


def show_run_changes(previous: dict, current: dict) -> None:
    """Print one row per changed run in separate parent-family tables."""
    changes = changed_runs(previous, current)
    if not changes:
        table(["Database update"], [["No run changes."]])
        return
    # Retain deleted runs and parents so removals still appear in a family.
    combined = {run["name"]: run for run in previous.get("runs", [])}
    combined.update((run["name"], run) for run in current["runs"])
    for title, family in group_runs(list(combined.values())):
        rows = [[run["name"], *changes[run["name"]],
                 "-" if changes[run["name"]][0] == "Removed" else run["properties"].get("STATUS", "-")]
                for run in family if run["name"] in changes]
        if rows:
            log(f"\nParent run: {title}")
            table(["Run", "Update", "Changed fields", "Status"], rows)


def main() -> None:
    parser = TableArgumentParser(description="Display project configuration as a table")
    parser.add_argument("field", choices=["filename", "project_name", "syth_list", "impl_list"])
    parser.add_argument("--raw", action="store_true", help="Print only the value for shell scripts")
    args = parser.parse_args()
    paths = list(Path.cwd().glob("*.hdlforge.json"))
    if len(paths) != 1:
        parser.error("Expected exactly one project JSON in the current directory")
    with operation("Reading project configuration JSON", str(paths[0].resolve()), machine=args.raw):
        value = paths[0].name if args.field == "filename" else json.loads(paths[0].read_text())["vivado"]["config"][args.field]
        if args.raw:
            machine_output((",".join(value) if isinstance(value, list) else value) + "\n")
        else:
            label = {"filename": "Configuration file", "project_name": "Project name", "syth_list": "Synthesis run", "impl_list": "Implementation run"}[args.field]
            table([label], [[entry] for entry in value] if isinstance(value, list) and value else [[value]])


if __name__ == "__main__":
    main()
