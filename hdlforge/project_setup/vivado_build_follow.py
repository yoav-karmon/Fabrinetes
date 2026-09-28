"""Detach interactive build workers and follow their persistent launch logs."""

import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
import time


def background_follow(project: Path, output_root: Path, argv: list[str]) -> int:
    """Ctrl-C detaches the viewer; the worker retains its lock and children."""
    directory = output_root / 'launch_logs'
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', prefix='build-', suffix='.log', dir=directory, delete=False) as stream:
        path = Path(stream.name)
        command = [sys.executable, '-u', str(Path(__file__).with_name('vivado_build.py')),
                   *argv, '--background_worker']
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=stream,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    print(f'Background launcher PID: {process.pid}\nLaunch log: {path}', flush=True)
    print('Ctrl-C stops log following only; the build and automatic implementations continue.', flush=True)
    try:
        with path.open() as reader:
            while True:
                text = reader.read()
                if text:
                    print(text, end='', flush=True)
                result = process.poll()
                if result is not None:
                    print(reader.read(), end='', flush=True)
                    return result
                time.sleep(0.2)
    except KeyboardInterrupt:
        print(f'\nDetached. Build continues with launcher PID {process.pid}.\nLog: {path}', flush=True)
        print(f'Resume log following:\n  {shlex.join(["tail", "-n", "50", "-f", "--", str(path.resolve())])}', flush=True)
        print('Use hdlforge --tool vivado --build_status to inspect it; --stop_run stops a selected attempt.', flush=True)
        return 0
