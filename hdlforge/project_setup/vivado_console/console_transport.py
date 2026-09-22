"""Persistent tmux Vivado Tcl transport; no separate build process launcher."""
import base64
from contextlib import contextmanager
import fcntl
import hashlib
import os
import re
from pathlib import Path
import shlex
import subprocess
import tempfile
import time

from .tcl_arguments import tcl_word
from .project_paths import ensure_xpr_is_available
from .terminal_output import log as log_message

HELPER_TCL = Path(__file__).with_name("live_project_helpers.tcl")
RUN_TCL = Path(__file__).with_name("run_commands.tcl")

class ConsoleUnavailable(RuntimeError):
    """The console transport failed, rather than the requested Tcl command."""


class ProjectConsole:
    def __init__(self, xpr: Path, timeout: float = 180, project_file: Path | None = None):
        self.xpr = xpr.resolve()
        self.project_file = project_file
        self.logs_directory = self.xpr.parent.parent / "project_console" / self.xpr.stem
        self.timeout = timeout
        self.force_recovery = False
        identity = hashlib.sha1(str(self.xpr).encode()).hexdigest()[:10]
        self.session = f"agent_tmux_{os.environ.get('USER', '').replace('.', '_')}_vivado_xpr_{self.xpr.stem}_{identity}_1"
        self.directory = Path(tempfile.gettempdir()) / f"vivado-project-console-{os.getuid()}-{identity}"
        self.directory.mkdir(mode=0o700, exist_ok=True)
        self.terminal = self.directory / "terminal.log"

    @contextmanager
    def locked(self, filename: str = "command.lock"):
        with (self.directory / filename).open("a") as lock:
            deadline = time.monotonic() + self.timeout
            while True:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except BlockingIOError:
                    if time.monotonic() >= deadline:
                        raise RuntimeError("Timed out waiting for another console command")
                    time.sleep(0.1)
            yield

    def exists(self) -> bool:
        return subprocess.run(["tmux", "has-session", "-t", self.session], capture_output=True).returncode == 0

    def helper(self, command: str) -> None:
        if command == "open":
            startup = self.directory / "startup.tcl"
            startup.write_text(f"source {tcl_word(HELPER_TCL)}\nsource {tcl_word(RUN_TCL)}\n")
            logs = self.logs_directory
            logs.mkdir(parents=True, exist_ok=True)
            invocation = shlex.join(["vivado", "-mode", "tcl", "-log", str(logs / "vivado.log"),
                                     "-journal", str(logs / "vivado.jou"), "-source", str(startup)])
            subprocess.run(["tmux", "new-session", "-d", "-s", self.session,
                            "-c", str(self.xpr.parent.parent), "exec " + invocation], check=True, capture_output=True)
            subprocess.run(["tmux", "pipe-pane", "-t", self.session, "cat >> " + shlex.quote(str(self.terminal))], check=True, capture_output=True)
            pid = subprocess.run(["tmux", "display-message", "-p", "-t", self.session, "#{pane_pid}"],
                                 check=True, capture_output=True, text=True).stdout.strip()
            log_message(f"Background console process started: {pid}\nLog: {logs / 'vivado.log'}\nTail: tail -f {shlex.quote(str(logs / 'vivado.log'))}", error=True)
        elif command == "close":
            self.request("lvp_close_project")
            subprocess.run(["tmux", "kill-session", "-t", "=" + self.session], check=True, capture_output=True)
        else:
            raise ValueError(f"Unknown console lifecycle action: {command}")

    def open(self) -> None:
        try:
            self._open()
        except ConsoleUnavailable as error:
            if self.exists() and not self.force_recovery:
                raise ConsoleUnavailable(
                    f"{error}\nRestarting may interrupt pending work. "
                    "Confirm by retrying with --append '--force'.") from error
            self.close(force=True)
            self.force_recovery = False
            self._open()

    def _open(self) -> None:
        with self.locked("lifecycle.lock"):
            if not self.exists():
                self.helper("open")
                # Requests from a previous console cannot complete in this one.
                (self.directory / "pending").unlink(missing_ok=True)

    def ensure_project(self) -> None:
        if not self.exists():
            ensure_xpr_is_available(self.xpr)
        self.open()
        self.request(f"lvp_open_project {tcl_word(self.xpr)}")

    def pending_request(self) -> Path | None:
        """Return the unfinished request without contacting Vivado."""
        try:
            previous = Path((self.directory / "pending").read_text())
        except FileNotFoundError:
            return None
        return previous if not (previous / "done").exists() else None

    def request(self, command: str) -> str:
        """Capture native Vivado messages, Tcl output, result and full error details."""
        if not self.exists():
            raise ConsoleUnavailable("Console is not running")
        previous = self.pending_request()
        if previous is not None:
            raise ConsoleUnavailable(f"Previous Tcl command is still pending: {previous}")
        request_dir = Path(tempfile.mkdtemp(prefix="request-", dir=self.directory))
        (self.directory / "pending").write_text(str(request_dir))
        script = request_dir / "command.tcl"
        output, done = request_dir / "output.log", request_dir / "done"
        result_file, data_file = request_dir / "result.txt", request_dir / "records.tsv"
        begin = "__HDLFORGE_BEGIN_" + request_dir.name + "__"
        end = "__HDLFORGE_END_" + request_dir.name + "__"
        offset = self.terminal.stat().st_size if self.terminal.exists() else 0
        script.write_text(
            f"puts {tcl_word(begin)}\n"
            f"set ::lvp_data_channel [open {tcl_word(data_file)} w]\n"
            "set ::lvp_result {}\nset ::lvp_error {}\n"
            "set ::lvp_code [catch {\n"
            f"source {tcl_word(RUN_TCL)}\n"
            f"set ::lvp_result [uplevel #0 {tcl_word(command)}]\n"
            "} ::lvp_message ::lvp_options]\n"
            "if {$::lvp_code} {set ::lvp_error $::lvp_message; if {[dict exists $::lvp_options -errorinfo]} {set ::lvp_error [dict get $::lvp_options -errorinfo]}}\n"
            "close $::lvp_data_channel\nunset ::lvp_data_channel\n"
            f"set ::lvp_handle [open {tcl_word(result_file)} w]\n"
            "puts -nonewline $::lvp_handle [expr {$::lvp_code ? $::lvp_error : $::lvp_result}]\nclose $::lvp_handle\n"
            f"set ::lvp_handle [open {tcl_word(done.with_suffix('.tmp'))} w]\n"
            "puts $::lvp_handle $::lvp_code\nclose $::lvp_handle\n"
            f"file rename -force {tcl_word(done.with_suffix('.tmp'))} {tcl_word(done)}\n"
            f"puts {tcl_word(end)}\n"
        )
        subprocess.run(["tmux", "send-keys", "-t", self.session, "-l", f"source {tcl_word(script)} -notrace"], check=True, capture_output=True)
        subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"], check=True, capture_output=True)
        deadline = time.monotonic() + self.timeout
        while not done.exists():
            if not self.exists():
                raise ConsoleUnavailable(f"Vivado console exited; incomplete request: {request_dir}")
            if time.monotonic() >= deadline:
                raise ConsoleUnavailable(f"Tcl command still pending; not cancelled. Output: {output}")
            time.sleep(0.1)
        code = int(done.read_text().strip())
        # pipe-pane records the complete PTY stream, including native Vivado diagnostics.
        while True:
            with self.terminal.open("rb") as handle:
                handle.seek(offset)
                transcript = handle.read().decode(errors="replace")
            if end in transcript:
                break
            if time.monotonic() >= deadline:
                raise ConsoleUnavailable(f"Response finished but transcript incomplete: {request_dir}")
            time.sleep(0.05)
        captured = transcript.split(begin, 1)[1].split(end, 1)[0]
        captured = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", captured).replace("\r\n", "\n").lstrip("\n")
        output.write_text(captured)
        result = result_file.read_text(errors="replace")
        records = []
        for line in data_file.read_text().splitlines():
            values = [base64.b64decode(v).decode() for v in line.split("\t")]
            records.append(dict(zip(values[::2], values[1::2])))
        response = {"request": request_dir.name, "command": command, "output": captured,
                    "result": result, "code": code, "records": records}
        self.last_response = response
        if getattr(self, "on_response", None):
            self.on_response(response)
        if code:
            raise RuntimeError(result)
        return result

    def close(self, force: bool = False) -> None:
        if force:
            # Recovery must not call Tcl or wait for a blocked request's lock.
            with self.locked("lifecycle.lock"):
                if self.exists():
                    subprocess.run(["tmux", "kill-session", "-t", "=" + self.session], check=True, capture_output=True)
                (self.directory / "pending").unlink(missing_ok=True)
            return
        if self.exists():
            self.helper("close")
