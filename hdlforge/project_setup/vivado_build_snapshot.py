"""Freeze declared build inputs and implementation configurations before launch."""

import copy
import fcntl
import json
from pathlib import Path
import re
import shutil

from vivado_build_hash import hash_source, verify_source_hashes
from vivado_build_layout import CONFIG, LEGACY_CONFIG, IDENTITY, read_run
from vivado_build_paths import require_complete


def snapshot_inputs(config: dict) -> dict:
    """Return a runtime configuration whose inputs point only at saved copies."""
    output = Path(config['output'])
    root = Path(config['project_root'])
    destination = Path(config.get('input_destination', output / 'snapshot/source'))
    copied = {}
    # Prepared implementation inputs retain their paths beneath snapshot/source.
    frozen_root = (next(parent for parent in Path(config['script']).parents if parent.name == 'snapshot') / 'source'
                   if config.get('stage') == 'impl' else None)

    def save(path: Path) -> Path:
        path = path.absolute()
        if str(path) in copied:
            return Path(copied[str(path)])
        # Strip the parent snapshot prefix instead of nesting its artifacts tree.
        if frozen_root is not None and path.is_relative_to(frozen_root):
            relative = path.relative_to(frozen_root)
        else:
            try:
                relative = path.relative_to(root.parent)
            except ValueError:
                relative = Path('_external') / path.relative_to(path.anchor)
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
            with (producer.parent / f'_{read_run(producer)["run_id"]}.run.lock').open('a') as lock:
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

    def freeze(run: dict, name: str = '') -> dict:
        frozen = copy.deepcopy(run)
        script = Path(run['script'])
        scripts = output / 'snapshot/scripts'
        if name:
            scripts /= 'impl/' + name
        scripts.mkdir(parents=True, exist_ok=True)
        for entry in frozen.get('sources', []):
            source = Path(entry['path'])
            if config.get('stage') != 'impl' and source.suffix.lower() == '.xci':
                for sibling in source.parent.rglob('*'):
                    if sibling.is_file():
                        save(sibling)
            entry['path'] = str(save(source))
        target_script = scripts / 'run.tcl'
        if target_script.exists() and copied.get(str(script)) != str(target_script):
            raise ValueError(f'Script snapshot collision: {script} -> {target_script}')
        shutil.copy2(script, target_script)
        frozen['script'] = str(target_script)
        copied[str(script)] = str(target_script)
        frozen['project_root'] = str(destination / root.name)
        frozen['vivado_version'] = config.get('vivado_version', '')
        return frozen

    selected_project = Path(config['project_file'])
    saved_project = output / 'snapshot' / selected_project.name
    saved_project.parent.mkdir(parents=True, exist_ok=True)
    if hash_source(selected_project) != config['project_sha256']:
        raise ValueError('Selected project JSON changed before snapshot creation; select the run again')
    shutil.copyfile(selected_project, saved_project)
    runtime = freeze(config)
    runtime['project_file'] = str(saved_project)
    runtime['implementation_configs'] = {
        name: freeze(child, name) for name, child in config.get('implementation_configs', {}).items()
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
        # This first copy originates in the synthesis snapshot/source tree.
        child['input_destination'] = str(prepared / 'snapshot/source')
        prepared_config = snapshot_inputs(child)
        prepared_config.pop('input_destination', None)
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
    scripts = {prepared.get('script_name'): prepared['script']} if 'script' in prepared else {}
    selected = dict(definition)
    try:
        selected['script'] = scripts[definition['script']]
        selected['sources'] = [available[name] for name in definition.get('sources', [])]
    except KeyError as error:
        raise ValueError(f'Declared implementation input is absent from its prepared snapshot: {error.args[0]}') from None
    return project, selected
