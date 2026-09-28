"""Freeze declared build inputs and implementation configurations before launch."""

import copy
import fcntl
import json
from pathlib import Path
import re
import shutil

from vivado_build_hash import hash_source, verify_source_hashes


def snapshot_inputs(config: dict) -> dict:
    """Return a runtime configuration whose inputs point only at saved copies."""
    output = Path(config['output'])
    root = Path(config['project_root'])
    destination = Path(config.get('input_destination', output / 'inputs'))
    copied = {}
    # Implementation paths may mix live refreshed XDC/Tcl with frozen IPs.
    # Resolve frozen inputs against their snapshot root before the live project.
    frozen_root = (Path(config['input_dcp']).parent.parent / 'inputs'
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
        # Hold the producer's publication lock while copying a latest input.
        latest = next((parent for parent in path.parents if parent.name == 'latest'), None)
        if latest is not None and config.get('stage') != 'impl':
            with ((latest.parent.parent if latest.parent.name == 'artifacts' else latest.parent) / '.publish.lock').open('a') as lock:
                fcntl.flock(lock, fcntl.LOCK_SH)
                if ((latest / 'info/status').read_text().strip() != 'complete'
                        or (latest / 'info/exit_code').read_text().strip() != '0'):
                    raise ValueError(f'Cannot use inputs from unsuccessful latest run: {latest}')
                if path.suffix.lower() in {".xcix", ".xci"}:
                    try:
                        verify_source_hashes(latest)
                    except (OSError, ValueError, KeyError, TypeError) as error:
                        warning = f"WARNING: IP freshness could not be verified: {error}. Continuing with {path}"
                        print(warning, flush=True)
                        with (output / 'info/warnings.log').open('a') as warnings:
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
        for field in ('sources', 'ips', 'constraints'):
            for entry in frozen.get(field, []):
                source = Path(entry['path'])
                if source.suffix.lower() == '.xci':
                    for sibling in source.parent.rglob('*'):
                        if sibling.is_file():
                            save(sibling)
                entry['path'] = str(save(source))
        for path in frozen.get('input_files', []):
            save(Path(path))
        frozen['input_files'] = [copied[path] for path in frozen.get('input_files', [])]
        script = Path(run['script'])
        for sibling in script.parent.glob('*.tcl'):
            save(sibling)
        frozen['script'] = str(save(script))
        frozen['project_root'] = str(destination / root.name)
        frozen['vivado_version'] = config.get('vivado_version', '')
        return frozen

    runtime = freeze(config)
    if config.get('stage') == 'impl':
        # Copy the selected parent checkpoint; all other paths above already
        # refer to the parent's frozen inputs, never live producer publications.
        checkpoint = Path(config['input_dcp'])
        target = destination / 'synthesis_checkpoint' / checkpoint.name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(checkpoint, target)
        copied[str(checkpoint)] = str(target)
        runtime['input_dcp'] = str(target)
        (output / 'info/input_hashes.json').write_text(json.dumps({
            source: {'copy': saved, 'sha256': hash_source(Path(saved))}
            for source, saved in copied.items()
        }, indent=2) + '\n')
    children = {name: freeze(child) for name, child in config.get('implementation_configs', {}).items()}
    runtime.pop('implementation_configs', None)
    (output / 'info/implementations.json').write_text(json.dumps(children, indent=2) + '\n')
    (output / 'info/input_manifest.json').write_text(json.dumps(copied, indent=2) + '\n')
    return runtime


def implementation_inputs(config: dict) -> dict:
    """Create one shared frozen input tree, then reuse it for dated attempts."""
    output = Path(config['output'])
    if config.get('refresh_impl_inputs'):
        runtime = snapshot_inputs(config)
        previous = config.get('refresh_previous_inputs', {})
        old_root = Path(previous['project_root'])
        old_manifest = Path(config['input_dcp']).parent.parent / 'info/input_manifest.json'
        originals = json.loads(old_manifest.read_text()) if old_manifest.is_file() else {}
        manifest = json.loads((output / 'info/input_manifest.json').read_text())
        changes = []
        frozen_sources = set(originals.values()) | {config['input_dcp']}
        for source, saved in manifest.items():
            path = Path(source)
            frozen = source in frozen_sources
            try:
                relative = path.relative_to(Path(config['project_root']))
            except ValueError:
                relative = path
            baseline = path if frozen else Path(originals.get(source, str(old_root / relative)))
            current_hash = hash_source(Path(saved))
            old_hash = hash_source(baseline) if baseline.is_file() else None
            state = 'ADDED' if old_hash is None else 'UNCHANGED' if old_hash == current_hash else 'CHANGED'
            changes.append({'path': str(relative), 'source': source, 'destination': saved,
                            'baseline': str(baseline), 'status': state, 'frozen': frozen,
                            'previous_sha256': old_hash, 'sha256': current_hash,
                            'changed': old_hash != current_hash})
        (output / 'info/refreshed_inputs.json').write_text(json.dumps(changes, indent=2) + '\n')
        with (output / 'info/refreshed_inputs.log').open('w') as log:
            for item in changes:
                message = (
                    f"[{item['status']}] Copied {'frozen' if item['frozen'] else 'current'} input\n"
                    f"  Source: {item['source']}\n"
                    f"  Destination: {item['destination']}\n"
                    f"  Compared with: {item['baseline']}\n"
                    f"  Previous SHA-256: {item['previous_sha256'] or '(no previous snapshot file)'}\n"
                    f"  Copied SHA-256:   {item['sha256']}"
                )
                print(message, flush=True)
                log.write(message + '\n')
            summary = 'Input copy summary: ' + ', '.join(
                f"{sum(item['status'] == state for item in changes)} {state.lower()}"
                for state in ('CHANGED', 'ADDED', 'UNCHANGED'))
            print(summary, flush=True)
            log.write(summary + '\n')
        return runtime
    shared = output.parent
    cache = shared / 'input_config.json'
    with (shared / '.inputs.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if not cache.exists():
            inputs = shared / 'inputs'
            # A missing completion marker means a prior snapshot was interrupted.
            if inputs.exists():
                shutil.rmtree(inputs)
            preparation = copy.deepcopy(config)
            preparation['input_destination'] = str(inputs)
            frozen = snapshot_inputs(preparation)
            fields = ('sources', 'ips', 'constraints', 'input_files', 'script', 'project_root', 'input_dcp')
            for name in ('input_manifest.json', 'input_hashes.json'):
                shutil.copy2(output / 'info' / name, shared / name)
            temporary = shared / '.input_config.tmp'
            temporary.write_text(json.dumps({key: frozen[key] for key in fields if key in frozen}, indent=2) + '\n')
            temporary.replace(cache)
        runtime = copy.deepcopy(config)
        runtime.update(json.loads(cache.read_text()))
        for name in ('input_manifest.json', 'input_hashes.json'):
            shutil.copy2(shared / name, output / 'info' / name)
        return runtime
