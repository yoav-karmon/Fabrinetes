"""Select runs by stable IDs or opaque directory labels."""

import json
import re
from pathlib import Path

from vivado_build_config import synthesis_folder
from vivado_build_layout import find_run, read_run, run_directories
from vivado_run_tree import discover_runs, run_definition, run_tree, selected_run

STAMP = r"_?[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}(?:\.[0-9]{6})?Z"
LABEL = rf"(?:{STAMP}|[A-Za-z0-9_ -]+)"


def first_path_component(value: str) -> str:
    """A timestamp's fractional seconds belong to its folder, not a CLI level."""
    match = re.match(STAMP + r"(?=\.|$)", value)
    return match[0] if match else value.split('.', 1)[0]


def bitstream_ready(folder: Path) -> bool:
    try:
        config = read_run(folder)
        name = config.get('last_routed_checkpoint', '')
        return (config['stage'] == 'impl' and bool(name) and Path(name).name == name
                and (folder / 'artifacts' / name).is_file()
                and config.get('status') == 'complete' and config.get('exit_code') == 0)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def parse_selector(value: str, runs: dict | None = None) -> dict | None:
    # Match a marked JSON path first; group names may look like action names.
    if runs is not None:
        name = selected_run(value, runs)
        if name is None:
            return None
        parsed = parse_selector('RUN' + value[len(name):])
        if parsed:
            parsed['run'] = name
        return parsed
    match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.({LABEL})\.([A-Za-z0-9_-]+)\.bitstream\.({LABEL})", value)
    if match:
        return dict(run=match[1], synth=match[2], impl=match[3], attempt=match[4], bitstream=True, action='run')
    match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.({LABEL})(?:\.([A-Za-z0-9_-]+)\.({LABEL}))?\.(status|stop)", value)
    if match:
        return dict(run=match[1], synth=match[2], impl=match[3], attempt=match[4], action=match[5])
    match = re.fullmatch(rf"([A-Za-z0-9_-]+)\.({LABEL})\.([A-Za-z0-9_-]+)\.run", value)
    if match:
        return dict(run=match[1], synth=match[2], impl=match[3], attempt='new', action='run')
    match = re.fullmatch(r"([A-Za-z0-9_-]+)\.run", value)
    if match:
        return dict(run=match[1], synth='new', impl=None, attempt=None, action='run')
    return None


def selector_choices(project: Path, data: dict, prefix: str) -> list[str]:
    # A configured script folder owns its attempts even after JSON regrouping.
    settings = data.get('vivado', {}).get('non_project', {})
    choices = []
    for name, definition in discover_runs(settings.get('runs', {})).items():
        choices.append(name + '.run')
        # The marker alone discovers the command, even during JSON authoring.
        # A script is needed only to look for saved attempts (and to build).
        if not isinstance(definition.get('script'), str) or not definition['script']:
            continue
        root = synthesis_folder(project, settings, name)
        for parent in run_directories(root):
            # Show the folder users inspect; identity remains in the manifest.
            label = parent.name
            choices.extend(f'{name}.{label}.{action}' for action in ('status', 'stop'))
            saved = read_run(parent)
            project_copy = Path(saved.get('project_file', ''))
            if not project_copy.is_file():
                continue
            definitions = run_definition(run_tree(json.loads(project_copy.read_text())), saved['selector']).get('impl_runs', {})
            for impl in definitions:
                stem = f'{name}.{label}.{impl}.'
                choices.append(stem + 'run')
                if parent == find_run(root, 'latest'):
                    choices.append(f'{name}.latest.{impl}.run')
                for attempt in run_directories(parent / 'impl_runs' / impl):
                    choices.extend(stem + attempt.name + '.' + action for action in ('status', 'stop'))
                    if bitstream_ready(attempt):
                        choices.append(stem + 'bitstream.' + attempt.name)
    return sorted(set(choices))


def selected_run_folder(project: Path, parsed: dict) -> Path:
    settings = json.loads(project.read_text())['vivado']['non_project']
    parent = find_run(synthesis_folder(project, settings, parsed['run']), parsed['synth'])
    if parsed['impl'] and parsed['attempt'] != 'new':
        return find_run(parent / 'impl_runs' / parsed['impl'], parsed['attempt'])
    return parent


def resolve_selector(project: Path, selector: str) -> str:
    """Pin latest to stable identity before the detached worker starts."""
    parsed = parse_selector(selector, discover_runs(run_tree(json.loads(project.read_text()))))
    if parsed is None or parsed['synth'] == 'new':
        return selector
    settings = json.loads(project.read_text())['vivado']['non_project']
    parent = find_run(synthesis_folder(project, settings, parsed['run']), parsed['synth'])
    stem = f"{parsed['run']}.{read_run(parent)['run_id']}"
    if not parsed['impl']:
        return stem + '.' + parsed['action']
    stem += '.' + parsed['impl']
    if parsed['attempt'] == 'new':
        return stem + '.run'
    attempt = find_run(parent / 'impl_runs' / parsed['impl'], parsed['attempt'])
    identity = read_run(attempt)['run_id']
    return stem + ('.bitstream.' + identity if parsed.get('bitstream') else '.' + identity + '.' + parsed['action'])
