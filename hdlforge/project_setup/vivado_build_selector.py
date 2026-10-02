"""Select runs by stable IDs or opaque directory labels."""

import json
import re
from pathlib import Path

from vivado_build_layout import find_run, read_run, run_directories

STAMP = r"_?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}(?:\.[0-9]{6})?Z"
LABEL = rf"(?:{STAMP}|[A-Za-z0-9_-]+)"


def bitstream_ready(folder: Path) -> bool:
    try:
        config = read_run(folder)
        marker = folder / 'logs/last_routed_checkpoint.txt'
        name = marker.read_text().strip()
        return (config['stage'] == 'impl' and Path(name).name == name
                and (folder / 'artifacts' / name).is_file()
                and (folder / 'logs/status').read_text().strip() == 'complete'
                and (folder / 'logs/exit_code').read_text().strip() == '0')
    except (OSError, ValueError, KeyError, TypeError):
        return False


def parse_selector(value: str) -> dict | None:
    for operation in ('bitstream', 'rerun'):
        match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.({LABEL})\.([A-Za-z0-9_-]+)\.{operation}\.({LABEL})", value)
        if match:
            return dict(run=match[1], synth=match[2], impl=match[3], attempt=match[4], **{operation: True})
    match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.rerun\.({LABEL})", value)
    if match:
        return dict(run=match[1], synth=match[2], impl=None, attempt=None, rerun=True)
    match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.({LABEL})\.([A-Za-z0-9_-]+)\.({LABEL})", value)
    if match:
        if match[2] == 'new':
            raise ValueError('Implementation requires an existing synthesis')
        return dict(run=match[1], synth=match[2], impl=match[3], attempt=match[4])
    match = re.fullmatch(r"([A-Za-z0-9_-]+)\.new", value)
    if match:
        return dict(run=match[1], synth='new', impl=None, attempt=None)
    return None


def selector_choices(project: Path, data: dict, prefix: str) -> list[str]:
    settings = data.get('vivado', {}).get('non_project', {})
    choices = []
    for name, definition in settings.get('runs', {}).items():
        choices.append(name + '.new')
        root = project.parent / settings['output_root'] / name
        parents = run_directories(root)
        for parent in parents:
            # IDs remain usable even when a folder has punctuation or is renamed.
            identity = read_run(parent)['run_id']
            choices.append(f'{name}.rerun.{identity}')
            for impl in definition.get('impl_runs', {}):
                stem = f'{name}.{identity}.{impl}.'
                choices.append(stem + 'new')
                choices.append(f'{name}.latest.{impl}.new')
                for attempt in run_directories(parent / 'impl_runs' / impl, f'{name}.{impl}'):
                    attempt_id = read_run(attempt)['run_id']
                    choices.append(stem + 'rerun.' + attempt_id)
                    if bitstream_ready(attempt):
                        choices.append(stem + 'bitstream.' + attempt_id)
    return sorted(set(choices))


def resolve_rerun(project: Path, selector: str) -> str:
    """Resolve latest to stable IDs exactly once before launch."""
    parsed = parse_selector(selector)
    if parsed is None or parsed['synth'] == 'new':
        return selector
    settings = json.loads(project.read_text())['vivado']['non_project']
    parent = find_run(project.parent / settings['output_root'] / parsed['run'], parsed['synth'])
    identity = read_run(parent)['run_id']
    if not parsed['impl']:
        return f"{parsed['run']}.rerun.{identity}"
    attempt = parsed['attempt']
    if attempt != 'new':
        attempt = read_run(find_run(parent / 'impl_runs' / parsed['impl'], attempt, f"{parsed['run']}.{parsed['impl']}"))['run_id']
    operation = 'bitstream.' if parsed.get('bitstream') else 'rerun.' if parsed.get('rerun') else ''
    return f"{parsed['run']}.{identity}.{parsed['impl']}.{operation}{attempt}"


def relocate_snapshot(value: object, original: str, output: str) -> object:
    """Compatibility utility for consumers of older provenance records."""
    if isinstance(value, dict):
        return {key: relocate_snapshot(item, original, output) for key, item in value.items()}
    if isinstance(value, list):
        return [relocate_snapshot(item, original, output) for item in value]
    if isinstance(value, str) and (value == original or value.startswith(original + '/')):
        return output + value[len(original):]
    return value
