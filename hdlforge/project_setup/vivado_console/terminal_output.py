"""Plain operational logs and structured report tables for Vivado commands."""

import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import runpy
import shutil
import sys

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


def table(headers: list, rows: list, error: bool = False, wrap: bool = True) -> None:
    """Print a bordered table wrapped to the terminal width."""
    width = max(60, shutil.get_terminal_size((140, 24)).columns)
    widths = [max(len(line) for row in [headers, *rows] for line in (str(row[index]).splitlines() or [""])) for index in range(len(headers))]
    while wrap and sum(widths) + 3 * len(headers) + 1 > width and max(widths) > 12:
        index = widths.index(max(widths))
        widths[index] -= 1
    rendered = RENDERER["create_matrix_table_from_data"](headers, rows, col_wrapped_limits=dict(enumerate(widths)))
    print(rendered, file=sys.stderr if error else sys.stdout, flush=True)
