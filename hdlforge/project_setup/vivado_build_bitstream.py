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
    if (config.get('status') != 'complete'
            or config.get('exit_code') != 0):
        raise ValueError(f'Implementation must be complete before regenerating its bitstream: {source}')
    epoch = config['launch_epoch']
    if isinstance(epoch, bool) or not isinstance(epoch, int) or not 0 <= epoch <= 0xffffffff:
        raise ValueError('Implementation launch_epoch must fit the 32-bit USERID')
    names = [config.get('last_routed_checkpoint', '')]
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
                  auto_impl=[], sources=[])
    for key in ('parent_launch_id', 'execution', 'status', 'exit_code', 'stages', 'inputs', 'source_hashes', 'failure'):
        config.pop(key, None)
    config.update(new_identity())
    config['timestamp'] = config['created_at']
    config['input_dcp_sha256'] = hash_source(checkpoint)
    return config


@contextmanager
def lock_implementation(config: dict):
    """Protect the selected DCP against cleanup while it is in use."""
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
                or current.get('status') != 'complete'):
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
    project = Path(config['project_file'])
    saved_project = output / 'snapshot' / project.name
    shutil.copyfile(project, saved_project)
    runtime['project_file'] = str(saved_project)
    runtime['bitstream_probes'] = []
    for probes in sorted((source / 'artifacts').glob('*.ltx')):
        target = inputs / probes.name
        shutil.copy2(probes, target)
        runtime['bitstream_probes'].append(str(target))
    runtime['inputs'] = [{'original': str(source / 'artifacts' / Path(path).name),
                          'snapshot': str(Path(path).relative_to(output)),
                          'sha256': hash_source(Path(path))} for path in runtime['bitstream_probes']]
    return runtime
