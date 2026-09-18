"""Unconditional batch submission; Vivado decides whether runs can launch."""

from pathlib import Path
import shlex
import subprocess
import time

from .terminal_output import log


def start(xpr, target, kind="run", jobs=1, reset=False, reset_only=False, bitstream=True):
    xpr = Path(xpr).resolve()
    attempt = str(time.time_ns())
    directory = xpr.parent.parent / "project_console" / xpr.stem / ("batch-" + attempt)
    directory.mkdir(parents=True)
    output = directory / "build.log"
    script = Path(__file__).with_name("batch_build.tcl")
    command = ["vivado", "-mode", "batch", "-source", str(script),
               "-log", str(directory / "vivado.log"), "-journal", str(directory / "vivado.jou"),
               "-tclargs", str(xpr), target, kind, str(jobs),
               str(int(reset)), str(int(reset_only)), str(int(bitstream))]
    with output.open("w") as handle:
        process = subprocess.Popen(command, cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    # Observe immediate launch errors without keeping a process registry.
    try:
        exit_code = process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        exit_code = None
    log(f"Log: {output}\nTail: tail -f {shlex.quote(str(output))}")
    if exit_code is not None:
        log(f"Immediate exit: {exit_code}")
        print("\n".join(output.read_text(errors="replace").splitlines()[-8:]), flush=True)
    return {"log": str(output), "exit_code": exit_code}
