"""Parse and complete dated build selectors without splitting timestamp fractions."""

import json
import re
from pathlib import Path

from vivado_build_config import synthesis_timestamps
from vivado_build_paths import dated_runs, latest_run

STAMP = r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{6}(?:\.[0-9]{6})?Z"
PATTERN = re.compile(rf"(?P<run>[A-Za-z0-9_-]+)\.(?P<synth>new|latest|{STAMP})(?:\.(?P<impl>[A-Za-z0-9_-]+)\.(?P<attempt>new|{STAMP}))?")


def bitstream_ready(folder: Path) -> bool:
    """Keep incomplete or concurrently changing attempts out of completion."""
    try:
        if ((folder / 'info/status').read_text().strip() != 'complete'
                or (folder / 'info/exit_code').read_text().strip() != '0'):
            return False
        config = json.loads((folder / 'info/resolved.json').read_text())
        marker = folder / 'info/last_routed_checkpoint.txt'
        names = ([marker.read_text().strip()] if marker.is_file() else
                 [f"{config['top']}_postroute_physopt.dcp", f"{config['top']}_routed.dcp"])
        return config['stage'] == 'impl' and any(
            Path(name).name == name and (folder / 'checkpoints' / name).is_file()
            for name in names)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def parse_selector(value: str) -> dict | None:
    bitstream = re.fullmatch(rf"([A-Za-z0-9_-]+)\.(latest|{STAMP})\.([A-Za-z0-9_-]+)\.bitstream\.(latest|{STAMP})", value)
    if bitstream:
        return dict(run=bitstream[1], synth=bitstream[2], impl=bitstream[3], attempt=bitstream[4], bitstream=True)
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
        root = settings.get('output_root')
        if not isinstance(root, str) or not root:
            continue
        artifacts = project.parent / root / name / 'artifacts'
        stamps = synthesis_timestamps(project, data, name)
        parents = (['latest'] if stamps else []) + stamps
        if parents:
            choices.append(name + '.rerun.')
        if parents and prefix.startswith(name + '.rerun.'):
            choices.extend(name + '.rerun.' + stamp for stamp in parents)
        for stamp in parents:
            base = name + '.' + stamp + '.'
            if not prefix.startswith(base):
                if run.get('impl_runs'):
                    choices.append(base)
                continue
            for impl in run.get('impl_runs', {}):
                stem = base + impl + '.'
                choices.append(stem + 'new')
                parent = latest_run(artifacts) if stamp == 'latest' else artifacts / stamp
                folder = parent / 'impl_runs' / impl
                dates = dated_runs(folder)
                attempts = (['latest'] if dates else []) + [path.name for path in dates]
                if attempts:
                    choices.append(stem + 'rerun.')
                    if prefix.startswith(stem + 'rerun.'):
                        choices.extend(stem + 'rerun.' + attempt for attempt in attempts)
                    completed = [attempt for attempt in attempts
                                 if bitstream_ready(dates[-1] if attempt == 'latest' else folder / attempt)]
                    if completed:
                        choices.append(stem + 'bitstream.')
                        if prefix.startswith(stem + 'bitstream.'):
                            choices.extend(stem + 'bitstream.' + attempt for attempt in completed)
    return sorted(set(choices))


def resolve_rerun(project: Path, selector: str) -> str:
    """Pin every latest component once, including reruns and bitstream selections."""
    parsed = parse_selector(selector)
    if parsed is None:
        return selector
    data = json.loads(project.read_text())
    folder = project.parent / data['vivado']['non_project']['output_root'] / parsed['run'] / 'artifacts'
    synth = latest_run(folder).name if parsed['synth'] == 'latest' else parsed['synth']
    if not parsed['impl']:
        if '.rerun.' in selector and not (folder / synth).is_dir():
            raise ValueError(f'No synthesis/IP attempt to rerun: {folder / synth}')
        return f"{parsed['run']}.rerun.{synth}" if '.rerun.' in selector else f"{parsed['run']}.{synth}"
    folder = folder / synth / 'impl_runs' / parsed['impl']
    attempt = latest_run(folder).name if parsed['attempt'] == 'latest' else parsed['attempt']
    if '.rerun.' in selector and not (folder / attempt).is_dir():
        raise ValueError(f'No implementation attempt to rerun: {folder / attempt}')
    operation = 'bitstream.' if parsed.get('bitstream') else 'rerun.' if '.rerun.' in selector else ''
    return f"{parsed['run']}.{synth}.{parsed['impl']}.{operation}{attempt}"


def relocate_snapshot(value: object, original: str, output: str) -> object:
    """Rebase saved paths when a historical snapshot was relocated."""
    if isinstance(value, dict):
        return {key: relocate_snapshot(item, original, output) for key, item in value.items()}
    if isinstance(value, list):
        return [relocate_snapshot(item, original, output) for item in value]
    if isinstance(value, str) and (value == original or value.startswith(original + '/')):
        return output + value[len(original):]
    return value
