"""Parse and complete dated build selectors without splitting timestamp fractions."""

import json
import re
from pathlib import Path

from vivado_build_config import synthesis_timestamps, timestamp_key, TIMESTAMP

STAMP = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}(?:\.[0-9]{6})?Z"
PATTERN = re.compile(rf"(?P<run>[A-Za-z0-9_-]+)\.(?P<synth>new|latest|{STAMP})(?:\.(?P<impl>[A-Za-z0-9_-]+)\.(?P<attempt>new|{STAMP}))?")


def parse_selector(value: str) -> dict | None:
    synthesis_rerun = re.fullmatch(rf"([A-Za-z0-9_-]+)\.rerun\.(latest|{STAMP})", value)
    if synthesis_rerun:
        return dict(run=synthesis_rerun[1], synth=synthesis_rerun[2], impl=None, attempt=None)
    implementation_rerun = re.fullmatch(rf"([A-Za-z0-9_-]+)\.(latest|{STAMP})\.([A-Za-z0-9_-]+)\.rerun\.(latest|{STAMP})", value)
    if implementation_rerun:
        return dict(run=implementation_rerun[1], synth=implementation_rerun[2], impl=implementation_rerun[3], attempt=implementation_rerun[4])
    match = PATTERN.fullmatch(value)
    if not match:
        return None
    result = match.groupdict()
    if result['impl'] and result['synth'] == 'new':
        raise ValueError('Implementation requires latest or an existing synthesis timestamp')
    if not result['impl'] and result['synth'] == 'latest':
        raise ValueError('Use an explicit timestamp to rerun synthesis')
    return result


def selector_choices(project: Path, data: dict, prefix: str) -> list[str]:
    settings = data.get('vivado', {}).get('non_project', {})
    choices = []
    for name, run in settings.get('runs', {}).items():
        choices.append(name + '.new')
        stamps = synthesis_timestamps(project, data, name)
        choices.append(name + '.rerun.')
        if prefix.startswith(name + '.rerun.'):
            choices.extend(name + '.rerun.' + stamp for stamp in ['latest', *stamps])
        for stamp in ['latest', *stamps]:
            base = name + '.' + stamp + '.'
            if not prefix.startswith(base):
                if run.get('impl_runs'):
                    choices.append(base)
                continue
            for impl in run.get('impl_runs', {}):
                stem = base + impl + '.'
                choices.extend([stem + 'new', stem + 'rerun.'])
                selected = stamp
                folder = project.parent / settings['output_root'] / name / 'artifacts' / selected / 'impl_runs' / impl
                if folder.is_dir():
                    if prefix.startswith(stem + 'rerun.'):
                        choices.append(stem + 'rerun.latest')
                        choices.extend(stem + 'rerun.' + path.name for path in folder.iterdir()
                                       if path.is_dir() and TIMESTAMP.fullmatch(path.name))
    return sorted(set(choices))


def resolve_rerun(project: Path, selector: str) -> str:
    """Convert explicit rerun syntax to an exact internal timestamp selector."""
    if '.rerun.' not in selector:
        return selector
    parsed = parse_selector(selector)
    if parsed is None:
        raise ValueError(f'Invalid rerun selector: {selector}')
    data = json.loads(project.read_text())
    run = parsed['run']
    synth = parsed['synth']
    if not parsed['impl']:
        impl = parsed['impl']
    attempt = parsed['attempt']
    if attempt == 'latest':
        folder = project.parent / data['vivado']['non_project']['output_root'] / run / 'artifacts' / synth / 'impl_runs' / impl
        stamps = sorted((p.name for p in folder.iterdir() if p.is_dir() and TIMESTAMP.fullmatch(p.name)), key=timestamp_key) if folder.is_dir() else []
        if not stamps:
            raise ValueError(f'No dated implementation attempts in {folder}')
        attempt = stamps[-1]
    return f'{run}.{synth}.{impl}.{attempt}'
