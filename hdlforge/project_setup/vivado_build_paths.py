"""Resolve producer selectors using JSON identities and timestamps."""

import os
from pathlib import Path

from vivado_build_layout import find_run, run_directories


def dated_runs(folder: Path) -> list[Path]:
    return run_directories(folder)


def latest_run(folder: Path) -> Path:
    return find_run(folder, 'latest')


def resolve_latest_path(path: Path, selections: dict[Path, Path] | None = None) -> Path:
    """Expand logical latest once without embedding physical directory labels."""
    cache = selections if selections is not None else {}
    path = Path(os.path.abspath(path))
    result = Path(path.anchor)
    for part in path.parts[1:]:
        if part == 'latest' and (not (result / part).exists() or run_directories(result)):
            if result not in cache:
                cache[result] = latest_run(result)
            result = cache[result]
        else:
            result /= part
    return result


def require_complete(folder: Path) -> None:
    try:
        complete = ((folder / 'logs/status').read_text().strip() == 'complete'
                    and (folder / 'logs/exit_code').read_text().strip() == '0')
    except OSError:
        complete = False
    if not complete:
        raise ValueError(f'Selected run is incomplete or unsuccessful: {folder}')
