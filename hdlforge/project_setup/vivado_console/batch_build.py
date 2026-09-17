"""Unconditional batch submission; Vivado decides whether runs can launch."""

from pathlib import Path
import shlex
import subprocess
import time

from . import build_jobs
from .terminal_output import log


def start(console, target, kind="run", jobs=1, reset=False, reset_only=False, bitstream=True):
    attempt = str(time.time_ns())
    directory = console.logs_directory / ("batch-" + attempt)
    directory.mkdir(parents=True)
    output = directory / "build.log"
    script = Path(__file__).with_name("batch_build.tcl")
    command = ["vivado", "-mode", "batch", "-source", str(script),
               "-log", str(directory / "vivado.log"), "-journal", str(directory / "vivado.jou"),
               "-tclargs", str(console.xpr), target, kind, str(jobs),
               str(int(reset)), str(int(reset_only)), str(int(bitstream))]
    submitted = time.time()
    with output.open("w") as handle:
        process = subprocess.Popen(command, cwd=directory, stdin=subprocess.DEVNULL,
                                   stdout=handle, stderr=subprocess.STDOUT, start_new_session=True)
    entry = {"id": attempt, "target": target, "kind": kind, "jobs": jobs,
             "reset": reset, "reset_only": reset_only, "bitstream": bitstream,
             "pid": process.pid, "process": build_jobs.identity(process.pid),
             "command": command, "project": str(console.xpr), "submitted_at": submitted,
             "log": str(output)}
    # This is only an early-exit observation, never a pre-launch acceptance check.
    try:
        entry["exit_code"] = process.wait(timeout=0.5)
    except subprocess.TimeoutExpired:
        entry["exit_code"] = None
    entry["last_status"] = build_jobs.observe(entry)
    with console.locked("history.lock"):
        history = build_jobs.read_history(console)
        history["submissions"].append(entry)
        build_jobs.write_history(console, history)
    log(f"Submitted: {attempt}\nPID: {process.pid}\nLog: {output}\nTail: tail -f {shlex.quote(str(output))}")
    if entry["exit_code"] is not None:
        log(f"Immediate exit: {entry['exit_code']}")
    print("\n".join(entry["last_status"]["tail"]), flush=True)
    return entry
