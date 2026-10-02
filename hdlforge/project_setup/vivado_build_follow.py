"""Detach interactive build workers and follow their persistent launch logs."""

from contextlib import ExitStack
from pathlib import Path
import shlex
import subprocess
import sys
import time

from vivado_build_layout import read_run, write_run


def background_follow(project: Path, config: dict, argv: list[str]) -> int:
    """Ctrl-C detaches the viewer; the worker retains its lock and children."""
    directory = Path(config['output'])
    directory.mkdir(parents=True, exist_ok=False)
    write_run(directory, dict(config, status='queued'))
    path = directory / 'build.log'
    path.touch()
    command = [sys.executable, '-u', str(Path(__file__).with_name('vivado_build.py')),
               *argv, '--background_worker', '--prepared_run', str(directory)]
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                               stderr=subprocess.DEVNULL, start_new_session=True)
    print(f'Background launcher PID: {process.pid}\nLaunch log: {path}', flush=True)
    print('Ctrl-C stops log following only; the build and automatic implementations continue.', flush=True)
    try:
        with ExitStack() as stack:
            readers = {path: stack.enter_context(path.open())}
            while True:
                # Follow each child's own log without creating another combined file.
                for child in read_run(directory).get('continuations', []):
                    child_log = Path(child['output']) / 'build.log'
                    if child_log not in readers and child_log.is_file():
                        readers[child_log] = stack.enter_context(child_log.open())
                for reader in readers.values():
                    text = reader.read()
                    if text:
                        print(text, end='', flush=True)
                result = process.poll()
                if result is not None:
                    for reader in readers.values():
                        print(reader.read(), end='', flush=True)
                    return result
                time.sleep(0.2)
    except KeyboardInterrupt:
        print(f'\nDetached. Build continues with launcher PID {process.pid}.\nLog: {path}', flush=True)
        print(f'Resume log following:\n  {shlex.join(["tail", "-n", "50", "-f", "--", str(path.resolve())])}', flush=True)
        print('Use hdlforge vivado.build.status to inspect it; use the attempt’s .stop command to stop it.', flush=True)
        return 0
