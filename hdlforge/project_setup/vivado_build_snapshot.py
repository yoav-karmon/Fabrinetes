"""Freeze declared build inputs and implementation configurations before launch."""

import copy
import fcntl
import json
from pathlib import Path
import re
import shutil

from vivado_build_hash import verify_source_hashes
from vivado_build_layout import CONFIG, read_run, map_paths
from vivado_build_paths import require_complete


def snapshot_inputs(config: dict) -> dict:
    """Return a runtime configuration whose inputs point only at saved copies."""
    output = Path(config['output'])
    root = Path(config['project_root'])
    destination = Path(config.get('input_destination', output / 'snapshot/source'))
    copied = {}
    # Implementation paths may mix live refreshed XDC/Tcl with frozen IPs.
    # Resolve frozen inputs against their snapshot root before the live project.
    frozen_root = (Path(config['input_dcp']).parent.parent / 'snapshot/source'
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
        # lock so an explicit rerun cannot replace files while they are copied.
        producer = next((parent for parent in path.parents
                         if (parent / CONFIG).is_file()), None)
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
                        with (output / 'logs/warnings.log').open('a') as warnings:
                            warnings.write(warning + '\n')
                shutil.copy2(path, target)
        else:
            shutil.copy2(path, target)
        copied[str(path)] = str(target)
        if path.suffix.lower() in {'.v', '.sv', '.vh', '.svh'}:
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
        scripts = output / 'snapshot/scripts'
        scripts.mkdir(parents=True, exist_ok=True)
        for field in ('sources', 'ips', 'constraints'):
            for entry in frozen.get(field, []):
                source = Path(entry['path'])
                if source.suffix.lower() == '.xci':
                    for sibling in source.parent.rglob('*'):
                        if sibling.is_file():
                            save(sibling)
                entry['path'] = str(save(source))
        for path in frozen.get('input_files', []):
            helper = Path(path)
            if helper.suffix == '.tcl' and helper.is_relative_to(script.parent):
                target = scripts / helper.relative_to(script.parent)
                if target.name == 'run.tcl' or target.is_relative_to(scripts / '_hdlforge'):
                    raise ValueError(f'Declared helper conflicts with reserved runtime paths: {helper}')
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(helper, target)
                copied[str(helper)] = str(target)
            else:
                save(helper)
        frozen['input_files'] = [copied[path] for path in frozen.get('input_files', [])]
        target_script = scripts / ('run.tcl' if run is config else script.name)
        if target_script.exists() and copied.get(str(script)) != str(target_script):
            raise ValueError(f'Script snapshot collision: {script} -> {target_script}')
        shutil.copy2(script, target_script)
        frozen['script'] = str(target_script)
        copied[str(script)] = str(target_script)
        frozen['project_root'] = str(destination / root.name)
        frozen['vivado_version'] = config.get('vivado_version', '')
        return frozen

    runtime = freeze(config)
    runtime['implementation_configs'] = {
        name: freeze(child) for name, child in config.get('implementation_configs', {}).items()
    }
    runtime.pop('implementation_scripts', None)
    runtime.pop('impl_json', None)
    (output / 'logs/input_manifest.json').write_text(json.dumps(copied, indent=2) + '\n')
    return runtime



def implementation_inputs(config: dict) -> dict:
    """Each implementation snapshots only its declared inputs; DCP stays in parent."""
    return snapshot_inputs(config)
