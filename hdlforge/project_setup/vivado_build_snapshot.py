"""Freeze declared build inputs and implementation configurations before launch."""

import copy
import fcntl
import json
from pathlib import Path
import re
import shutil
import subprocess

from vivado_build_hash import hash_source, verify_source_hashes
from vivado_build_layout import run_lock_path, CONFIG, LEGACY_CONFIG, IDENTITY, read_run
from vivado_build_paths import require_complete


def snapshot_inputs(config: dict) -> dict:
    """Return a runtime configuration whose inputs point only at saved copies."""
    output = Path(config['output'])
    root = Path(config['project_root'])
    snapshot_root = Path(config['snapshot_root']) if config.get('snapshot_root') else Path(
        subprocess.check_output(['git', '-C', str(root), 'rev-parse', '--show-toplevel'], text=True).strip())
    destination = output / 'snapshot'
    copied = {}

    def save(path: Path) -> Path:
        path = path.resolve()
        if str(path) in copied:
            return Path(copied[str(path)])
        try:
            relative = path.relative_to(snapshot_root)
        except ValueError:
            raise ValueError(f'Snapshot input is outside the repository: {path}') from None
        target = destination / relative
        previous_source = next((source for source, saved in copied.items()
                                if saved == str(target) and source != str(path)), None)
        if previous_source is not None:
            raise ValueError(f'Snapshot path collision: {previous_source} and {path} map to {target}')
        target.parent.mkdir(parents=True, exist_ok=True)
        # Inputs already resolve to a fixed producer timestamp. Hold its run
        # lock so cleanup cannot remove files while they are copied.
        producer = next((parent for parent in path.parents
                         if any((parent / marker).is_file() for marker in (CONFIG, LEGACY_CONFIG, IDENTITY))), None)
        if producer is not None and config.get('stage') != 'impl':
            with run_lock_path(producer, read_run(producer)["run_id"]).open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_SH | fcntl.LOCK_NB)
                require_complete(producer)
                if path.suffix.lower() in {".xcix", ".xci"}:
                    try:
                        verify_source_hashes(producer)
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        warning = f"WARNING: IP freshness could not be verified: {error}. Continuing with {path}"
                        print(warning, flush=True)
                shutil.copy2(path, target)
        else:
            shutil.copy2(path, target)
        copied[str(path)] = str(target)
        if config.get('stage') != 'impl' and path.suffix.lower() in {'.v', '.sv', '.vh', '.svh'}:
            for name in re.findall(r'`include\s+"([^"]+)"', path.read_text()):
                included = path.parent / name
                if not included.is_file():
                    included = root / name
                if not included.is_file():
                    raise ValueError(f'Cannot snapshot include {name} referenced by {path}; use an explicit local include path')
                save(included)
        return target

    def freeze(run: dict) -> dict:
        frozen = copy.deepcopy(run)
        script = Path(run['script'])
        for entry in frozen.get('sources', []):
            source = Path(entry['path'])
            if config.get('stage') != 'impl' and source.suffix.lower() == '.xci':
                for sibling in source.parent.rglob('*'):
                    if sibling.is_file():
                        save(sibling)
            entry['path'] = str(save(source))
        frozen['script'] = str(save(script))
        frozen['project_root'] = str(destination / root.relative_to(snapshot_root))
        frozen['snapshot_root'] = str(destination)
        frozen['vivado_version'] = config.get('vivado_version', '')
        return frozen

    selected_project = Path(config['project_file'])
    saved_project = destination / root.relative_to(snapshot_root) / selected_project.name
    saved_project.parent.mkdir(parents=True, exist_ok=True)
    if hash_source(selected_project) != config['project_sha256']:
        raise ValueError('Selected project JSON changed before snapshot creation; select the run again')
    shutil.copyfile(selected_project, saved_project)
    runtime = freeze(config)
    runtime['project_file'] = str(saved_project)
    runtime['implementation_configs'] = {
        name: freeze(child) for name, child in config.get('implementation_configs', {}).items()
    }
    runtime.pop('implementation_scripts', None)
    runtime.pop('impl_json', None)
    runtime['inputs'] = [{'original': source, 'snapshot': str(Path(saved).relative_to(output)),
                          'sha256': hash_source(Path(saved))} for source, saved in copied.items()]
    # Materialize every implementation before synthesis starts. No checkpoint
    # is needed to prepare inputs; launches check that dependency separately.
    for name, child in list(runtime['implementation_configs'].items()):
        prepared = output / 'impl_runs' / name
        child.update(output=str(prepared), project_file=str(saved_project),
                     project_sha256=hash_source(saved_project), stage='impl')
        prepared_config = snapshot_inputs(child)
        runtime['implementation_configs'][name] = prepared_config
    return runtime


def implementation_definition(parent: Path, config: dict, synthesis: str, implementation: str) -> tuple[Path, dict]:
    """Read the project saved by synthesis, then bind only its declared inputs."""
    project = Path(config.get('project_file', ''))
    if not project.is_file() or not project.is_relative_to(parent / 'snapshot'):
        raise ValueError(f'Synthesis snapshot has no saved HDLForge project JSON: {parent}')
    data = json.loads(project.read_text())
    definition = data['vivado']['non_project']['runs'][synthesis].get('impl_runs', {}).get(implementation)
    if definition is None:
        raise ValueError(f'Implementation is not declared in {project.name}: {implementation}')
    # The manifest is a path index; the saved project JSON owns the file list.
    prepared = config.get('implementation_configs', {}).get(implementation, {})
    available = {entry['name']: entry['path'] for entry in prepared.get('sources', [])}
    selected = dict(definition)
    # The synthesis JSON selects the filename; execute only a prepared copy.
    snapshot = parent / 'impl_runs' / implementation / 'snapshot'
    project_relative = project.relative_to(parent / 'snapshot')
    script = (snapshot / project_relative.parent / definition['script']).resolve()
    if not script.is_relative_to(snapshot):
        raise ValueError(f'Implementation script must remain inside its snapshot: {script}')
    if not script.is_file():
        raise ValueError(f'Missing prepared implementation script: {script}')
    selected['script'] = str(script)
    try:
        selected['sources'] = [available[name] for name in definition.get('sources', [])]
    except KeyError as error:
        raise ValueError(f'Declared implementation input is absent from its prepared snapshot: {error.args[0]}') from None
    return project, selected
