"""Resolve logical latest selectors to real timestamped run directories."""

import os
from pathlib import Path

from vivado_build_config import TIMESTAMP, timestamp_key


def dated_runs(folder: Path) -> list[Path]:
    """List real dated attempts in timestamp order, never filesystem mtime order."""
    try:
        return sorted((path for path in folder.iterdir()
                       if TIMESTAMP.fullmatch(path.name) and path.is_dir() and not path.is_symlink()),
                      key=lambda path: timestamp_key(path.name))
    except FileNotFoundError:
        return []


def latest_run(folder: Path) -> Path:
    """Select the newest attempt; callers validate readiness without fallback."""
    runs = dated_runs(folder)
    if not runs:
        raise ValueError(f'No timestamped runs in {folder}; build the producer first')
    return runs[-1]


def resolve_latest_path(path: Path, selections: dict[Path, Path] | None = None) -> Path:
    """Expand artifacts/latest and impl_runs/NAME/latest before accessing files."""
    cache = selections if selections is not None else {}
    path = Path(os.path.abspath(path))
    result = Path(path.anchor)
    for part in path.parts[1:]:
        if part == 'latest' and (result.name == 'artifacts' or result.parent.name == 'impl_runs'):
            if result not in cache:
                cache[result] = latest_run(result)
            result = cache[result]
        else:
            result /= part
    return result


def require_complete(folder: Path) -> None:
    """Require success for an input-producing attempt, not just an existing file."""
    try:
        complete = ((folder / 'info/status').read_text().strip() == 'complete'
                    and (folder / 'info/exit_code').read_text().strip() == '0')
    except OSError:
        complete = False
    if not complete:
        raise ValueError(f'Selected run is incomplete or unsuccessful: {folder}; select an older timestamp explicitly or rebuild')
