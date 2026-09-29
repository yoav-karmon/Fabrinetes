"""Select and snapshot bitstream-only launches from completed implementations."""

from contextlib import contextmanager, ExitStack
from datetime import datetime, timezone
import fcntl
import json
from pathlib import Path
import shutil

from vivado_build_hash import hash_source


def select_bitstream(project: Path, parsed: dict) -> dict:
    """Keep the source implementation intact and create a separate child launch."""
    settings = json.loads(project.read_text())['vivado']['non_project']
    definition = settings['runs'][parsed['run']]
    if parsed['impl'] not in definition.get('impl_runs', {}):
        raise ValueError(f"Unknown implementation: {parsed['impl']}")
    root = (project.parent / settings['output_root']).resolve()
    source = root / parsed['run'] / 'artifacts' / parsed['synth'] / 'impl_runs' / parsed['impl'] / parsed['attempt']
    config = json.loads((source / 'info/resolved.json').read_text())
    if config['stage'] != 'impl':
        raise ValueError(f'Expected an implementation: {source}')
    if ((source / 'info/status').read_text().strip() != 'complete'
            or (source / 'info/exit_code').read_text().strip() != '0'):
        raise ValueError(f'Implementation must be complete before regenerating its bitstream: {source}')
    epoch = config['launch_epoch']
    if isinstance(epoch, bool) or not isinstance(epoch, int) or not 0 <= epoch <= 0xffffffff:
        raise ValueError('Implementation launch_epoch must fit the 32-bit USERID')
    marker = source / 'info/last_routed_checkpoint.txt'
    if marker.is_file():
        names = [marker.read_text().strip()]
    else:
        # Earlier runtimes did not record checkpoints. Their example scripts
        # saved these names, with post-route optimization optional.
        names = [f"{config['top']}_postroute_physopt.dcp", f"{config['top']}_routed.dcp"]
    checkpoint = next((source / 'checkpoints' / name for name in names
                       if Path(name).name == name and (source / 'checkpoints' / name).is_file()), None)
    if checkpoint is None:
        raise ValueError(f'No recorded routed checkpoint found in {source / "checkpoints"}')
    stamp = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H%M%S.%fZ')
    selector = f"{parsed['run']}.{parsed['impl']}"
    selection = f"{parsed['run']}.{parsed['synth']}.{parsed['impl']}.bitstream.{parsed['attempt']}"
    config.update(stage='bitstream', output=str(source / 'bitstream_runs' / stamp),
                  output_root=str(root), selector=selector, timestamp=parsed['synth'],
                  input_dcp=str(checkpoint), bitstream_source=str(source),
                  bitstream_source_launch_id=config.get('launch_id'),
                  bitstream_epoch=epoch, build_selection=selection,
                  script=str(Path(__file__).with_name('vivado_build_bitstream.tcl')),
                  auto_impl=[], sources=[], ips=[], constraints=[],
                  input_files=[], rerun=False)
    for key in ('refresh_impl_inputs', '_rerun_runtime', '_rerun_original_output', 'parent_launch_id'):
        config.pop(key, None)
    return config


@contextmanager
def lock_implementation(config: dict):
    """Block source reruns/publication while copying and using the selected DCP."""
    source = Path(config['bitstream_source'])
    paths = [source.parent / f'.{source.name}.run.lock']
    with ExitStack() as stack:
        for path in paths:
            handle = stack.enter_context(path.open('a'))
            try:
                fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(f'Implementation is running or being published; retry after it finishes: {source}') from None
        current = json.loads((source / 'info/resolved.json').read_text())
        if (current.get('launch_id') != config['bitstream_source_launch_id']
                or current['launch_epoch'] != config['bitstream_epoch']
                or (source / 'info/status').read_text().strip() != 'complete'):
            raise ValueError('Selected implementation changed during selection; select it again')
        yield


def snapshot_bitstream(config: dict) -> dict:
    """Freeze the routed DCP and paired probes without rereading RTL/IP/XDC."""
    runtime = dict(config)
    source = Path(config['bitstream_source'])
    output = Path(config['output'])
    inputs = output / 'inputs'
    inputs.mkdir()
    copied = {}
    checkpoint = Path(config['input_dcp'])
    target = inputs / checkpoint.name
    shutil.copy2(checkpoint, target)
    copied[str(checkpoint)] = str(target)
    runtime['input_dcp'] = str(target)
    runtime['project_root'] = str(inputs)
    runtime['bitstream_probes'] = []
    for probes in sorted((source / 'bitstream').glob('*.ltx')):
        target = inputs / 'probes' / probes.name
        target.parent.mkdir(exist_ok=True)
        shutil.copy2(probes, target)
        copied[str(probes)] = str(target)
        runtime['bitstream_probes'].append(str(target))
    for name in ('resolved.json', 'runtime.json'):
        shutil.copy2(source / 'info' / name, output / 'info' / f'implementation_{name}')
    (output / 'info/input_manifest.json').write_text(json.dumps(copied, indent=2) + '\n')
    (output / 'info/input_hashes.json').write_text(json.dumps({
        original: {'copy': saved, 'sha256': hash_source(Path(saved))}
        for original, saved in copied.items()
    }, indent=2) + '\n')
    return runtime
