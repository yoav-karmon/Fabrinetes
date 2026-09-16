#!/usr/bin/env python3
"""Synchronous commands through the repository's persistent Vivado console."""

from contextlib import contextmanager
import fcntl
import hashlib
import json
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import tempfile
import time

if __package__:
    from .run_enable import export_markers, tcl_word
    from .project_console_commands import COMMANDS, hdlforge_commands, install_commands, locate_own_key
    from .terminal_output import log as log_message
    from .terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, table
    from .get_runs_from_live_xpr import discover_project_json, ensure_xpr_is_available, find_vivado_owners, load_xpr_path
else:
    from run_enable import export_markers, tcl_word
    from project_console_commands import COMMANDS, hdlforge_commands, install_commands, locate_own_key
    from terminal_output import log as log_message
    from terminal_output import operation, TableArgumentParser, machine_output, show_console_status, show_text, table
    from get_runs_from_live_xpr import discover_project_json, ensure_xpr_is_available, find_vivado_owners, load_xpr_path


HELPER_TCL = Path(__file__).resolve().with_name("live_project_helpers.tcl")


class ProjectConsole:
    def __init__(self, xpr: Path, timeout: float = 180, project_file: Path | None = None):
        self.xpr = xpr.resolve()
        self.project_file = project_file
        self.logs_directory = self.xpr.parent.parent / "project_console" / self.xpr.stem
        self.timeout = timeout
        identity = hashlib.sha1(str(self.xpr).encode()).hexdigest()[:10]
        self.session = f"agent_tmux_{os.environ.get('USER', '').replace('.', '_')}_vivado_xpr_{self.xpr.stem}_{identity}_1"
        self.directory = Path(tempfile.gettempdir()) / f"vivado-project-console-{os.getuid()}-{identity}"
        self.directory.mkdir(mode=0o700, exist_ok=True)

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
            startup.write_text(f"source {tcl_word(HELPER_TCL)}\nlvp_open_project {tcl_word(self.xpr)}\n")
            logs = self.logs_directory
            logs.mkdir(parents=True, exist_ok=True)
            invocation = shlex.join(["vivado", "-mode", "tcl", "-log", str(logs / "vivado.log"),
                                     "-journal", str(logs / "vivado.jou"), "-source", str(startup)])
            subprocess.run(["tmux", "new-session", "-d", "-s", self.session,
                            "-c", str(self.xpr.parent), "exec " + invocation], check=True, capture_output=True)
            pid = subprocess.run(["tmux", "display-message", "-p", "-t", self.session, "#{pane_pid}"],
                                 check=True, capture_output=True, text=True).stdout.strip()
            log_message(f"Background console process started: {pid}\nLog: {logs / 'vivado.log'}\nTail: tail -f {shlex.quote(str(logs / 'vivado.log'))}", error=True)
        elif command == "close":
            self.request("close_project")
            subprocess.run(["tmux", "kill-session", "-t", "=" + self.session], check=True, capture_output=True)
        else:
            raise ValueError(f"Unknown console lifecycle action: {command}")

    def open(self) -> None:
        with self.locked("lifecycle.lock"):
            if not self.exists():
                ensure_xpr_is_available(self.xpr)
                self.helper("open")
                # Requests from a previous console cannot complete in this one.
                (self.directory / "pending").unlink(missing_ok=True)
        self.request(f"if {{[_lvp_project_path] ne {tcl_word(self.xpr)}}} {{error {{Wrong project open}}}}")

    def pending_request(self) -> Path | None:
        """Return the unfinished request without contacting Vivado."""
        try:
            previous = Path((self.directory / "pending").read_text())
        except FileNotFoundError:
            return None
        return previous if not (previous / "done").exists() else None

    def request(self, command: str) -> str:
        """Wait for a unique response file; Tcl errors propagate to the CLI."""
        if not self.exists():
            raise RuntimeError("Console is not running")
        pending = self.directory / "pending"
        previous = self.pending_request()
        if previous is not None:
            raise RuntimeError(f"Previous Tcl command is still pending: {previous}")
        request_dir = Path(tempfile.mkdtemp(prefix="request-", dir=self.directory))
        pending.write_text(str(request_dir))
        script, output, done = (request_dir / name for name in ("command.tcl", "output.log", "done"))
        script.write_text(
            "namespace eval ::project_console_request {\n"
            f"set capture [open {tcl_word(output)} w]\n"
            "rename ::puts ::project_console_request::original_puts\n"
            "proc ::puts {args} {\n"
            "set index [expr {[lindex $args 0] eq \"-nonewline\" ? 1 : 0}]\n"
            "if {[llength $args] == $index + 1} {set args [linsert $args $index $::project_console_request::capture]}\n"
            "if {[lindex $args $index] eq \"stdout\"} {lset args $index $::project_console_request::capture}\n"
            "uplevel 1 [list ::project_console_request::original_puts {*}$args]\n}\n"
            "set code [catch {\n"
            f"set result [uplevel #0 {tcl_word(command)}]\n"
            'if {$result ne ""} {puts $result}\n'
            "} message]\n"
            "rename ::puts {}; rename ::project_console_request::original_puts ::puts\n"
            "close $capture\n"
            f"set handle [open {tcl_word(done.with_suffix('.tmp'))} w]\n"
            'puts $handle $code\nputs $handle $message\nclose $handle\n'
            f"file rename -force {tcl_word(done.with_suffix('.tmp'))} {tcl_word(done)}\n}}\n"
        )
        subprocess.run(["tmux", "send-keys", "-t", self.session, "-l", f"source {tcl_word(script)}"], check=True, capture_output=True)
        subprocess.run(["tmux", "send-keys", "-t", self.session, "Enter"], check=True, capture_output=True)
        deadline = time.monotonic() + self.timeout
        while not done.exists():
            if not self.exists():
                raise RuntimeError(f"Vivado console exited; request: {request_dir}")
            if time.monotonic() >= deadline:
                raise RuntimeError(f"Tcl command still pending; not cancelled. Request: {request_dir}")
            time.sleep(0.1)
        response = done.read_text().split("\n", 1)
        captured = output.read_text() if output.exists() else ""
        if response[0] != "0":
            raise RuntimeError(captured + response[1])
        return captured

    def close(self, force: bool = False) -> None:
        if force:
            # Recovery must not call Tcl or wait for a blocked request's lock.
            with self.locked("lifecycle.lock"):
                if self.exists():
                    subprocess.run(["tmux", "kill-session", "-t", "=" + self.session], check=True, capture_output=True)
                (self.directory / "pending").unlink(missing_ok=True)
            return
        if self.exists():
            self.request('foreach run [get_runs] {if {[regexp -nocase {running|queued} [get_property STATUS $run]]} {error "Run is active: $run"}}')
            self.helper("close")


def main(argv: list[str] | None = None) -> int:
    parser = TableArgumentParser(description=__doc__)
    parser.add_argument("action", choices=sorted({action for action, _ in COMMANDS.values() if action != "--help"} | {"print-hdlforge-json-commands"}))
    parser.add_argument("--cmd", help="Tcl command to execute with the send action")
    parser.add_argument("--raw", action="store_true", help="Print Tcl output without table formatting")
    parser.add_argument("--output", type=Path, help="Override the write_tcl destination; default is the project's configured Tcl")
    parser.add_argument("--timeout", type=float, default=180, help="Maximum seconds to wait for the console or command lock (default: 180)")
    parser.add_argument("--json-file", type=Path, help="Existing JSON file for install-json; update-json detects its own selected file")
    parser.add_argument("--key", help="Dotted parent key for installation, e.g. LLM_orch.vivado; replace its project_console group entirely")
    parser.add_argument("--project-json", type=Path, help="HDLForge project selected by the native --project option")
    parser.add_argument("--overwrite", action="store_true", help="Allow install-json to replace an existing project_console group; update-json always replaces it")
    args = parser.parse_args(argv)
    printing = args.action in {"print-hdlforge-json-commends", "print-hdlforge-json-commands"}
    if (args.json_file is not None) != (args.key is not None):
        parser.error("--json-file and --key must be supplied together")
    if args.json_file is not None and not (printing or args.action == "install-json"):
        parser.error("--json-file and --key require install-json")
    if args.action == "install-json" and args.json_file is None:
        parser.error("install-json requires --json-file FILE --key PARENT")
    if printing or args.action in {"install-json", "update-json"}:
        if printing and args.json_file is None:
            machine_output(json.dumps(hdlforge_commands(), indent=2) + "\n")
        else:
            try:
                if args.action == "update-json":
                    args.json_file = args.project_json or discover_project_json(Path.cwd())
                    args.key = locate_own_key(args.json_file, os.environ.get("HDLFORGE_JSON_COMMAND_PATH"))
                install_commands(args.json_file, args.key, overwrite=args.overwrite or args.action == "update-json")
            except (OSError, ValueError) as error:
                show_text(str(error), "Error", error=True)
                return 1
            log_message(f"[Done] Installed {args.key}.project_console in {args.json_file.resolve()}; replaced any previous group")
        return 0
    if args.action == "list":
        result = subprocess.run(["tmux", "list-sessions", "-F", "#{session_name}"], capture_output=True, text=True)
        sessions = [name for name in result.stdout.splitlines() if name.startswith("agent_tmux_") and "_vivado_xpr_" in name]
        table(["Console"], [[name] for name in sessions] or [["No managed consoles"]])
        return 0
    if args.action == "clean_logs":
        return subprocess.run(["hdlforge", "--tool", "vivado", "--clean_logs", "-f"]).returncode
    try:
        project_json = args.project_json.resolve() if args.project_json else discover_project_json(Path.cwd())
        with operation("Reading project configuration JSON", str(project_json), machine=args.raw):
            console = ProjectConsole(load_xpr_path(project_json), args.timeout, project_json)
        if args.action == "name":
            table(["Project", "Console"], [[str(console.xpr), console.session]])
            return 0
        action = {"clean": "Closing console and deleting project folder", "generate": "Closing console and generating project from Tcl", "write_tcl": "Accessing live console and exporting project Tcl", "status": "Checking background console; reading live status if open", "close": "Closing background console", "restart": "Restarting background console and reopening XPR"}.get(args.action, "Accessing live console")
        if args.action in {"close", "restart"}:
            with operation(action, str(console.xpr), machine=args.raw):
                console.close(force=True)
                if args.action == "restart":
                    with console.locked():
                        console.open()
                    log_path = console.logs_directory / "vivado.log"
                    show_text(f"Session: {console.session}; project: {console.xpr}\nLog: {log_path}\nTail: tail -f {shlex.quote(str(log_path))}", "Background console ready")
                else:
                    log_message("[Done] Console closed")
            return 0
        if args.action == "status" and console.exists() and console.pending_request() is not None:
            table(["Field", "Value"], [["Console", "Open; Tcl request pending"], ["Project", str(console.xpr)], ["Session", console.session], ["Pending request", str(console.pending_request())], ["Recovery", "Use close or restart to interrupt the console"]])
            return 0
        with operation(action, str(console.xpr), machine=args.raw) as progress, console.locked():
            if args.action == "capture":
                if not console.exists():
                    raise RuntimeError("Console is not running")
                return subprocess.run(["tmux", "capture-pane", "-p", "-t", console.session, "-S", "-120"]).returncode
            if args.action == "status":
                if not console.exists():
                    table(["Console", "Project"], [["Closed", str(console.xpr)]])
                else:
                    show_console_status(console.request("lvp_info"))
                return 0
            if args.action in {"clean", "generate"}:
                console.close()
            if args.action in {"clean", "generate"}:
                if find_vivado_owners(console.xpr):
                    raise RuntimeError("Another Vivado process owns this project")
                if args.action == "clean":
                    project_dir = console.xpr.parent
                    source_dir = project_json.parent.resolve()
                    if source_dir not in project_dir.parents:
                        raise RuntimeError("Refusing to delete outside the project's generated subdirectories")
                    if project_dir.exists():
                        shutil.rmtree(project_dir)
                    log_message(f"[Done] Cleaned generated project folder: {project_dir}")
                    return 0
                flags = ["--generate_prj_with_external_tcl", "--force"]
                log_dir = console.xpr.parent.parent
                log_dir.mkdir(parents=True, exist_ok=True)
                with tempfile.NamedTemporaryFile(mode="w", prefix=f"{args.action}-", suffix=".log", dir=log_dir, delete=False) as log:
                    log_message(f"[Running] {args.action}; log: {log.name}")
                    result = subprocess.run(["hdlforge", "--project", str(project_json), "--tool", "vivado", *flags], cwd=project_json.parent, stdout=log, stderr=subprocess.STDOUT)
                log_message(f"[{('Done' if result.returncode == 0 else 'Failed')}] {args.action}: exit code {result.returncode}; log: {log.name}", error=bool(result.returncode))
                if result.returncode:
                    show_text("\n".join(Path(log.name).read_text(errors="replace").splitlines()[-20:]), "Log excerpt", error=True)
                if result.returncode:
                    progress["status"] = "Failed"
                return result.returncode
            console.open()
            if args.action == "send":
                if not args.cmd:
                    raise ValueError("send requires --cmd")
                output = console.request(args.cmd)
                if args.raw:
                    machine_output(output)
                else:
                    show_text(output, "Tcl result")
            elif args.action == "runs":
                table(["Run"], [[line] for line in console.request("lvp_runs").splitlines()] or [["No runs found"]])
            elif args.action == "write_tcl":
                config = json.loads(project_json.read_text())
                output = args.output or project_json.parent / config["vivado"]["external_config"]["filename"]
                console.request(f"write_project_tcl -force {tcl_word(output.resolve())}")
                export_markers(console, output.resolve())
                show_text(str(output.resolve()), "Exported project Tcl")
        return 0
    except (OSError, RuntimeError, ValueError, subprocess.SubprocessError) as error:
        show_text(str(error), "Error", error=True)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
