"""Project path discovery and existing Vivado owner checks."""
import json
from pathlib import Path
import subprocess
from typing import Any

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

