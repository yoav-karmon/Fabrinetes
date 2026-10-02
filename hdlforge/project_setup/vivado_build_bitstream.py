"""Select and snapshot bitstream-only launches from completed implementations."""

from contextlib import contextmanager, ExitStack
import fcntl
import json
from pathlib import Path
import shutil

from vivado_build_hash import hash_source
from vivado_build_layout import find_run, read_run, new_identity, new_label


def select_bitstream(project: Path, parsed: dict) -> dict:
    """Keep the source implementation intact and create a separate child launch."""
    settings = json.loads(project.read_text())['vivado']['non_project']
    definition = settings['runs'][parsed['run']]
    if parsed['impl'] not in definition.get('impl_runs', {}):
        raise ValueError(f"Unknown implementation: {parsed['impl']}")
    root = (project.parent / settings['output_root']).resolve()
    parent = find_run(root / parsed['run'], parsed['synth'])
    source = find_run(parent / 'impl_runs' / parsed['impl'], parsed['attempt'], f"{parsed['run']}.{parsed['impl']}")
    config = read_run(source)
    if config['stage'] != 'impl':
        raise ValueError(f'Expected an implementation: {source}')
    if ((source / 'logs/status').read_text().strip() != 'complete'
            or (source / 'logs/exit_code').read_text().strip() != '0'):
        raise ValueError(f'Implementation must be complete before regenerating its bitstream: {source}')
    epoch = config['launch_epoch']
    if isinstance(epoch, bool) or not isinstance(epoch, int) or not 0 <= epoch <= 0xffffffff:
        raise ValueError('Implementation launch_epoch must fit the 32-bit USERID')
    marker = source / 'logs/last_routed_checkpoint.txt'
    if marker.is_file():
        names = [marker.read_text().strip()]
    else:
        # Earlier runtimes did not record checkpoints. Their example scripts
        # saved these names, with post-route optimization optional.
        names = [f"{config['top']}_postroute_physopt.dcp", f"{config['top']}_routed.dcp"]
    checkpoint = next((source / 'artifacts' / name for name in names
                       if Path(name).name == name and (source / 'artifacts' / name).is_file()), None)
    if checkpoint is None:
        raise ValueError(f'No recorded routed checkpoint found in {source / "artifacts"}')
    selector = f"{parsed['run']}.{parsed['impl']}"
    selection = f"{parsed['run']}.{parsed['synth']}.{parsed['impl']}.bitstream.{parsed['attempt']}"
    config.update(stage='bitstream', output=str(source / 'bitstream_runs' / new_label()),
                  output_root=str(root), selector=selector, synthesis_run_id=parsed['synth'],
                  input_dcp=str(checkpoint), bitstream_source=str(source),
                  bitstream_source_launch_id=config.get('launch_id'),
                  bitstream_epoch=epoch, build_selection=selection,
                  script=str(Path(__file__).with_name('vivado_build_bitstream.tcl')),
                  auto_impl=[], sources=[], ips=[], constraints=[],
                  input_files=[], rerun=False)
    for key in ('refresh_impl_inputs', '_rerun_runtime', '_rerun_original_output', 'parent_launch_id'):
        config.pop(key, None)
    config.update(new_identity())
    config['timestamp'] = config['created_at']
    config['input_dcp_sha256'] = hash_source(checkpoint)
    return config


@contextmanager
def lock_implementation(config: dict):
    """Block source reruns/publication while copying and using the selected DCP."""
    source = Path(config['bitstream_source'])
    paths = [source.parent / f'_{read_run(source)["run_id"]}.run.lock']
    with ExitStack() as stack:
        for path in paths:
            handle = stack.enter_context(path.open('a'))
            try:
                fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            except BlockingIOError:
                raise ValueError(f'Implementation is running or being published; retry after it finishes: {source}') from None
        current = read_run(source)
        if (current.get('launch_id') != config['bitstream_source_launch_id']
                or current['launch_epoch'] != config['bitstream_epoch']
                or (source / 'logs/status').read_text().strip() != 'complete'):
            raise ValueError('Selected implementation changed during selection; select it again')
        yield


def snapshot_bitstream(config: dict) -> dict:
    """Freeze paired probes and retain a hash-checked reference to the routed DCP."""
    runtime = dict(config)
    source = Path(config['bitstream_source'])
    output = Path(config['output'])
    inputs = output / 'snapshot/source'
    inputs.mkdir(parents=True)
    scripts = output / 'snapshot/scripts'
    scripts.mkdir(parents=True)
    shutil.copy2(config['script'], scripts / 'run.tcl')
    runtime['script'] = str(scripts / 'run.tcl')
    runtime['project_root'] = str(inputs)
    runtime['bitstream_probes'] = []
    for probes in sorted((source / 'artifacts').glob('*.ltx')):
        target = inputs / probes.name
        shutil.copy2(probes, target)
        runtime['bitstream_probes'].append(str(target))
    (output / 'logs/input_manifest.json').write_text('{}\n')
    return runtime
