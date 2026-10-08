"""Portable run metadata; generated folder names are labels, never identities."""

import copy
from contextlib import contextmanager
import fcntl
from datetime import datetime, timezone
import json
import os
import tempfile
from pathlib import Path
from uuid import uuid4

from vivado_build_hash import hash_source


CONFIG = Path('manifest.json')
LEGACY_CONFIG = Path('snapshot/scripts/run.json')
IDENTITY = Path('snapshot/scripts/_run_id')
PATH_FIELDS = {'project_file', 'snapshot_root', 'script', 'output', 'output_root', 'project_root', 'input_dcp',
               'bitstream_source', 'logs_dir', 'artifacts_dir', 'work_dir'}
PATH_LISTS = {'input_files', 'bitstream_probes'}


def map_paths(config: dict, base: Path, *, relative: bool) -> dict:
    """Convert only schema path fields, leaving literal Vivado values intact."""
    result = copy.deepcopy(config)
    def convert(value: str) -> str:
        if not value:
            return value
        return os.path.relpath(value, base) if relative else str((base / value).resolve())
    for key in PATH_FIELDS & result.keys():
        result[key] = convert(result[key])
    for key in PATH_LISTS & result.keys():
        result[key] = [convert(value) for value in result[key]]
    if 'implementation_scripts' in result:
        result['implementation_scripts'] = {
            name: convert(path) for name, path in result['implementation_scripts'].items()
        }
    if 'impl_json' in result:
        result['impl_json'] = {name: convert(path) for name, path in result['impl_json'].items()}
    for key in ('sources', 'ips', 'constraints'):
        for entry in result.get(key, []):
            entry['path'] = convert(entry['path'])
    for name, child in result.get('implementation_configs', {}).items():
        result['implementation_configs'][name] = map_paths(child, base, relative=relative)
    for name, child in result.get('attempts', {}).items():
        result['attempts'][name] = map_paths(child, base, relative=relative)
    return result


def metadata_path(folder: Path) -> Path:
    if (folder / CONFIG).is_file():
        return folder / CONFIG
    # Historical attempts remain readable; new launches never write this layout.
    for parent in (folder, *folder.parents):
        if (parent / LEGACY_CONFIG).is_file():
            return parent / LEGACY_CONFIG
    raise ValueError(f'No run manifest in {folder}')


def read_run(folder: Path) -> dict:
    path = metadata_path(folder)
    document = json.loads(path.read_text())
    if not isinstance(document, dict):
        raise ValueError(f'Invalid run manifest: {path}')
    if path.name == 'manifest.json':
        return map_paths(document, folder, relative=False)
    if (folder / IDENTITY).is_file():
        identity = (folder / IDENTITY).read_text().strip()
        result = map_paths(document['attempts'][identity], path.parent, relative=False)
        old = Path(result['output'])
        rebased = map_paths(map_paths(result, old, relative=True), folder, relative=False)
        for key in ('input_dcp', 'output_root'):
            if key in result:
                rebased[key] = result[key]
        result = rebased
    else:
        result = map_paths(document, path.parent, relative=False)
        result.pop('attempts', None)
    for key, filename in {'status': 'status', 'exit_code': 'exit_code',
                          'last_routed_checkpoint': 'last_routed_checkpoint.txt'}.items():
        source = folder / 'logs' / filename
        if source.is_file():
            value = source.read_text().strip()
            result[key] = int(value) if key == 'exit_code' else value
    return result


@contextmanager
def edit_run(folder: Path):
    """Lock one attempt across reading, editing and atomically publishing it."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / CONFIG
    with (folder / '.manifest.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        document = json.loads(path.read_text()) if path.exists() else {}
        document = map_paths(document, folder, relative=False)
        yield document
        document = map_paths(document, folder, relative=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(mode='w', dir=folder, prefix='.manifest-', delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(json.dumps(document, indent=2) + '\n')
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()


def write_run(folder: Path, config: dict) -> None:
    """Merge and atomically publish one attempt; never mutate a parent record."""
    with edit_run(folder) as document:
        document.update(config)


def new_identity() -> dict:
    now = datetime.now(timezone.utc)
    return dict(format_version=3, run_id=uuid4().hex, created_at=now.isoformat(),
                launch_timestamp=now.isoformat(), launch_epoch=int(now.timestamp()))


def new_label() -> str:
    return '_' + datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S.%fZ')


def run_directories(root: Path, selector: str | None = None) -> list[Path]:
    """Discover direct children from their metadata, even after renaming."""
    if not root.is_dir():
        return []
    found = []
    for folder in root.iterdir():
        if folder.is_symlink() or not folder.is_dir() or not any((folder / name).is_file() for name in (CONFIG, LEGACY_CONFIG, IDENTITY)):
            continue
        try:
            config = read_run(folder)
            if not all(config.get(key) for key in ('run_id', 'created_at', 'selector', 'stage')):
                continue
        except (OSError, ValueError, KeyError, TypeError):
            continue
        if config.get('format_version') not in {2, 3}:
            continue
        if selector is None or config['selector'] == selector:
            found.append((config['created_at'], config['run_id'], folder))
    return [folder for _, _, folder in sorted(found)]


def find_run(root: Path, selection: str, selector: str | None = None) -> Path:
    runs = run_directories(root, selector)
    if selection == 'latest':
        if not runs:
            raise ValueError(f'No recorded runs in {root}')
        return runs[-1]
    matches = [folder for folder in runs if selection in
               (folder.name, read_run(folder)['run_id'], read_run(folder)['created_at'])]
    if len(matches) != 1:
        raise ValueError(f'Expected one recorded run for {selection!r} in {root}; found {len(matches)}')
    return matches[0]


def descendant_runs(folder: Path) -> list[Path]:
    """Visit run containers only; never scan large input/work trees for metadata."""
    result = [folder]
    implementations = folder / 'impl_runs'
    if implementations.is_dir():
        for group in implementations.iterdir():
            for child in run_directories(group):
                result.extend(descendant_runs(child))
    for container in ('impl', 'bitstream_runs'):
        for child in run_directories(folder / container):
            result.extend(descendant_runs(child))
    return result


def verify_checkpoint(config: dict) -> None:
    """Require the exact checkpoint recorded when this attempt was selected."""
    if config.get('stage') not in {'impl', 'bitstream'}:
        return
    checkpoint = Path(config['input_dcp'])
    if not checkpoint.is_file() or hash_source(checkpoint) != config.get('input_dcp_sha256'):
        raise ValueError(f'Parent checkpoint missing or changed: {checkpoint}; create a new implementation run')
    if config.get('stage') == 'impl':
        parent = read_run(checkpoint.parent.parent)
        if parent['run_id'] != config['parent_run_id']:
            raise ValueError('Parent synthesis identity changed; create a new implementation run')


def run_lock_path(folder: Path, run_id: str) -> Path:
    """Keep new locks inside attempts; honor locks owned by older workers."""
    legacy = folder.parent / f'_{run_id}.run.lock'
    return legacy if legacy.exists() else folder / '.run.lock'
