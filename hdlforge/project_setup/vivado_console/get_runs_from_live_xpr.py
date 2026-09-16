#!/usr/bin/env python3
"""Export every Vivado run and run property from a live XPR as JSON."""

from __future__ import annotations

import base64
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any, Iterable


if __package__:
    from .terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, show_properties, show_runs, table
else:
    from terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, show_properties, show_runs, table


SCHEMA_VERSION = 1


def discover_project_json(project_dir: Path) -> Path:
    """Find the one HDLForge project JSON owned by the current directory."""
    candidates = sorted(project_dir.glob("*.hdlforge.json"))
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one *.hdlforge.json in {project_dir}, "
            f"found {len(candidates)}"
        )
    return candidates[0].resolve()


def load_xpr_path(project_json: Path) -> Path:
    """Resolve the XPR owned by an HDLForge project JSON file."""
    result = subprocess.run(
        ["hdlforge", "--no-print", "--project", str(project_json.resolve()), "--tool", "vivado", "--get_xpr_path"],
        capture_output=True, text=True,
    )
    if result.returncode:
        raise ValueError(result.stderr.strip() or result.stdout.strip())
    value = result.stdout.strip()
    if not value or "\n" in value or not Path(value).is_absolute():
        raise ValueError(f"HDLForge returned an invalid XPR path: {value!r}")
    return Path(value).resolve()


def _resolve_xpr_argument(argument: str, cwd: Path) -> Path | None:
    if not argument.lower().endswith(".xpr"):
        return None
    candidate = Path(argument)
    if not candidate.is_absolute():
        candidate = cwd / candidate
    return candidate.resolve(strict=False)


def _is_vivado_process(arguments: list[str]) -> bool:
    executable_names = {Path(argument).name.lower() for argument in arguments}
    return "vivado" in executable_names or (
        "loader" in executable_names
        and any(
            argument.lower() == "vivado"
            for index, argument in enumerate(arguments)
            if index > 0 and arguments[index - 1] == "-exec"
        )
    )


def find_vivado_owners(
    xpr_path: Path,
    proc_root: Path = Path("/proc"),
) -> list[dict[str, Any]]:
    """Return Vivado processes whose command line explicitly opens this XPR."""
    owners: list[dict[str, Any]] = []
    target = xpr_path.resolve()

    for process_dir in proc_root.iterdir():
        if not process_dir.name.isdigit():
            continue
        try:
            raw_command = (process_dir / "cmdline").read_bytes()
            arguments = [
                item.decode(errors="replace")
                for item in raw_command.split(b"\0")
                if item
            ]
            if not arguments or not _is_vivado_process(arguments):
                continue
            cwd = (process_dir / "cwd").resolve()
        except (FileNotFoundError, PermissionError, ProcessLookupError):
            continue

        if any(_resolve_xpr_argument(item, cwd) == target for item in arguments):
            owners.append(
                {
                    "pid": int(process_dir.name),
                    "command": " ".join(arguments),
                }
            )

    return sorted(owners, key=lambda owner: owner["pid"])


def ensure_xpr_is_available(xpr_path: Path) -> None:
    """Reject missing projects and projects already owned by Vivado."""
    if not xpr_path.is_file():
        raise FileNotFoundError(f"XPR does not exist: {xpr_path}")

    owners = find_vivado_owners(xpr_path)
    if owners:
        owner_list = ", ".join(str(owner["pid"]) for owner in owners)
        raise RuntimeError(
            f"XPR is already open by Vivado process(es) {owner_list}; "
            "refusing to start a second project owner"
        )


def _decode(value: str) -> str:
    return base64.b64decode(value).decode("utf-8")


def parse_records(lines: Iterable[str]) -> dict[str, Any]:
    """Convert the Tcl extractor's base64 record stream to JSON-ready data."""
    result: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "project": {},
        "runs": [],
    }
    current_run: dict[str, Any] | None = None

    for line_number, raw_line in enumerate(lines, start=1):
        fields = raw_line.rstrip("\n").split("\t")
        record_type = fields[0]

        if record_type == "PROJECT" and len(fields) == 3:
            result["project"] = {"name": _decode(fields[1]), "xpr": _decode(fields[2])}
        elif record_type == "RUN" and len(fields) == 2:
            if current_run is not None:
                raise ValueError(f"nested RUN record at line {line_number}")
            current_run = {
                "name": _decode(fields[1]),
                "kind": "unknown",
                "parent_run": None,
                "properties": {},
                "property_errors": {},
            }
        elif record_type in {"PROPERTY", "PROPERTY_ERROR"} and len(fields) == 3:
            if current_run is None:
                raise ValueError(f"{record_type} outside RUN at line {line_number}")
            key = _decode(fields[1])
            value = _decode(fields[2])
            destination = "properties" if record_type == "PROPERTY" else "property_errors"
            current_run[destination][key] = value
        elif record_type == "ENDRUN" and len(fields) == 1:
            if current_run is None:
                raise ValueError(f"ENDRUN outside RUN at line {line_number}")
            properties = current_run["properties"]
            if properties.get("IS_SYNTHESIS", "").lower() in {"1", "true"}:
                current_run["kind"] = "synthesis"
            elif properties.get("IS_IMPLEMENTATION", "").lower() in {"1", "true"}:
                current_run["kind"] = "implementation"
            current_run["parent_run"] = (
                properties.get("PARENT") or properties.get("PARENT_RUN") or None
            )
            if not current_run["property_errors"]:
                del current_run["property_errors"]
            result["runs"].append(current_run)
            current_run = None
        else:
            raise ValueError(f"invalid record at line {line_number}: {raw_line.rstrip()}")

    if current_run is not None:
        raise ValueError("unterminated RUN record")
    if not result["project"]:
        raise ValueError("PROJECT record is missing")
    return result


def extract_runs(xpr_path: Path, vivado: str = "vivado", console: bool = False) -> dict[str, Any]:
    """Open an unowned XPR read-only and return every run property."""
    if not console:
        ensure_xpr_is_available(xpr_path)

    script_path = Path(__file__).with_suffix(".tcl")
    with tempfile.TemporaryDirectory(prefix="vivado-runs-") as temp_dir:
        records_path = Path(temp_dir) / "runs.records"
        command = [
            vivado,
            "-mode",
            "batch",
            "-nolog",
            "-nojournal",
            "-notrace",
            "-source",
            str(script_path),
            "-tclargs",
            str(xpr_path),
            str(records_path),
        ]
        if console:
            encoded = [base64.b64encode(str(path).encode()).decode() for path in (xpr_path, records_path, script_path)]
            words = [f"[encoding convertfrom utf-8 [binary decode base64 {value}]]" for value in encoded]
            tcl = "apply {{} {set argc 3; set argv [list " + words[0] + " " + words[1] + " reuse]; source " + words[2] + "}}"
            # Local import breaks the console/inventory module dependency cycle.
            if __package__:
                from .project_console import ProjectConsole
            else:
                from project_console import ProjectConsole
            session = ProjectConsole(xpr_path)
            with session.locked():
                session.open()
                session.request(tcl)
        else:
            completed = subprocess.run(command, check=False, capture_output=True, text=True)
            if completed.returncode != 0:
                detail = completed.stderr.strip() or completed.stdout.strip()
                raise RuntimeError(f"Vivado run extraction failed: {detail}")
        with records_path.open(encoding="utf-8") as handle:
            return parse_records(handle)


def build_runs_list(inventory: dict[str, Any]) -> dict[str, Any]:
    """Group each synthesis run with implementation runs that name it as parent."""
    synthesis_runs = sorted(
        (run for run in inventory["runs"] if run["kind"] == "synthesis"),
        key=lambda run: run["name"],
    )
    implementation_runs = [
        run for run in inventory["runs"] if run["kind"] == "implementation"
    ]
    synthesis_names = {run["name"] for run in synthesis_runs}

    return {
        "schema_version": SCHEMA_VERSION,
        "project": inventory["project"],
        "run_groups": [
            {
                "synthesis_run": synthesis_run["name"],
                "implementation_runs": sorted(
                    run["name"]
                    for run in implementation_runs
                    if run["parent_run"] == synthesis_run["name"]
                ),
            }
            for synthesis_run in synthesis_runs
        ],
        "ungrouped_runs": sorted(
            run["name"]
            for run in inventory["runs"]
            if run["kind"] == "unknown"
            or (
                run["kind"] == "implementation"
                and run["parent_run"] not in synthesis_names
            )
        ),
    }


def get_run_info(inventory: dict[str, Any], run_name: str) -> dict[str, Any]:
    """Return one run record without inventing properties Vivado did not expose."""
    for run in inventory["runs"]:
        if run["name"] == run_name:
            return {
                "schema_version": SCHEMA_VERSION,
                "project": inventory["project"],
                "run": run,
            }
    raise ValueError(f"run not found: {run_name}")


def get_all_run_info(inventory: dict[str, Any]) -> dict[str, Any]:
    """Build all-run output through the same one-run projection."""
    return {
        "schema_version": SCHEMA_VERSION,
        "project": inventory["project"],
        "runs": [
            get_run_info(inventory, run["name"])["run"]
            for run in inventory["runs"]
        ],
    }


def build_parser() -> TableArgumentParser:
    parser = TableArgumentParser(
        description="Print all runs and run properties from a live Vivado XPR as JSON."
    )
    parser.add_argument(
        "--project-json",
        type=Path,
        help="HDLForge project JSON (default: the one *.hdlforge.json in cwd)",
    )
    parser.add_argument("--xpr", type=Path, help="override the XPR path")
    parser.add_argument("--console", action="store_true", help="Reuse the persistent project Tcl console")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON instead of a table")
    parser.add_argument("--all", action="store_true", help="Print every property of every run")
    parser.add_argument("--run", help="Print every property of one run")
    parser.add_argument(
        "--output",
        type=Path,
        help="JSON output path (default: <project>.runs.json beside the XPR)",
    )
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser(
        "get_runs_list",
        help="group synthesis runs with their implementation children",
    )

    run_info_parser = subparsers.add_parser("get_run_info")
    run_info_parser.add_argument("run_name")

    subparsers.add_parser(
        "get_all_run_info",
        help="return every run through the get_run_info projection",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        project_json = (
            args.project_json.resolve()
            if args.project_json
            else discover_project_json(Path.cwd())
        )
        with operation("Reading project configuration JSON", str(project_json), machine=bool(args.json or args.command)):
            xpr_path = args.xpr.resolve() if args.xpr else load_xpr_path(project_json)
        with operation("Accessing live console" if args.console else "Reading XPR with Vivado", str(xpr_path), machine=bool(args.json or args.command)):
            inventory = extract_runs(xpr_path, console=args.console)
            if args.run:
                result = get_run_info(inventory, args.run)
            elif args.command == "get_runs_list":
                result = build_runs_list(inventory)
            elif args.command == "get_run_info":
                result = get_run_info(inventory, args.run_name)
            else:
                result = get_all_run_info(inventory)

            rendered = json.dumps(result, indent=2, sort_keys=True) + "\n"
            output_path = args.output.resolve() if args.output else None
            if output_path is None and args.command in {None, "get_all_run_info"}:
                output_path = xpr_path.with_suffix(".runs.json")
            if output_path is not None:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                saved = rendered if args.output else json.dumps(inventory, indent=2, sort_keys=True) + "\n"
                output_path.write_text(saved, encoding="utf-8")
            if args.json or args.command:
                machine_output(rendered)
            elif args.all or args.run:
                show_properties(result)
            else:
                show_runs(inventory["runs"])
        return 0
    except (FileNotFoundError, KeyError, OSError, RuntimeError, ValueError) as error:
        show_text(str(error), "Error", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
