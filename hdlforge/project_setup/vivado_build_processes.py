"""Linux process identity and read-only discovery for native Vivado builds."""

import os
from pathlib import Path
import socket


def local_identity() -> dict:
    return {"host": socket.gethostname(), "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
            "pid_namespace": os.stat("/proc/self/ns/pid").st_ino, "uid": os.getuid()}


def process_info(pid: int) -> dict | None:
    try:
        directory = Path("/proc") / str(pid)
        text = (directory / "stat").read_text()
        fields = text[text.rfind(")") + 2:].split()
        command = (directory / "cmdline").read_bytes().decode(errors="replace").rstrip("\0").split("\0")
        return {"pid": pid, "state": fields[0], "ppid": int(fields[1]), "pgid": int(fields[2]),
                "start_ticks": fields[19], "uid": directory.stat().st_uid, "command": command}
    except FileNotFoundError:
        return None
    except PermissionError:
        return {"pid": pid, "state": "unavailable"}
    except (OSError, IndexError, ValueError):
        return None


def probe_process(identity: dict | None, host: dict) -> str:
    if not identity:
        return "not_started"
    if host != local_identity():
        return "unavailable"
    current = process_info(identity["pid"])
    if current is None:
        return "dead"
    if current["state"] == "unavailable":
        return "unavailable"
    if current["start_ticks"] != identity.get("start_ticks") or current["uid"] != host["uid"]:
        return "pid_reused"
    return "dead" if current["state"] in {"Z", "X"} else current["state"]


def alive(state: str) -> bool:
    return state not in {"not_started", "dead", "pid_reused", "unavailable"}


def thread_activity(identity: dict | None, host: dict) -> str:
    """Sample all engine threads; a waiting main thread does not imply idle work."""
    state = probe_process(identity, host)
    if not alive(state):
        return {'not_started': 'Starting', 'dead': 'Exited',
                'pid_reused': 'PID changed', 'unavailable': 'Unavailable'}.get(state, state)
    states = set()
    try:
        for task in (Path('/proc') / str(identity['pid']) / 'task').iterdir():
            try:
                text = (task / 'stat').read_text()
                states.add(text[text.rfind(')') + 2:].split()[0])
            except FileNotFoundError:
                continue  # Threads may exit during the sample.
    except (OSError, IndexError):
        return 'Unavailable'
    if not alive(probe_process(identity, host)):
        return 'Unavailable'
    if 'R' in states:
        return 'Running'
    if 'D' in states:
        return 'I/O wait'
    if states and states <= {'T', 't'}:
        return 'Stopped'
    if states and states <= {'S', 'I'}:
        return 'Waiting'
    return 'Unknown'


def group_members(identity: dict | None, host: dict) -> list[dict]:
    """Capture identities of current group members before stopping the leader."""
    if not identity or not alive(probe_process(identity, host)):
        return []
    if identity.get("pgid") != identity["pid"]:
        return []
    members = []
    for path in Path("/proc").iterdir():
        if path.name.isdigit():
            info = process_info(int(path.name))
            if info and info.get("pgid") == identity["pgid"] and info.get("uid") == host["uid"]:
                members.append(info)
    return members


def signal_process(identity: dict | None, host: dict, signum: int, *, group: bool = False) -> bool:
    """Never signal a reused PID, another user, or a foreign PID namespace."""
    if not alive(probe_process(identity, host)):
        return False
    pid = identity["pid"]
    try:
        if group and identity.get("pgid") == pid and os.getpgid(pid) == pid:
            os.killpg(pid, signum)
        else:
            os.kill(pid, signum)
        return True
    except ProcessLookupError:
        return False


def find_user_vivado() -> list[dict]:
    """Discover current-user Vivado processes, including unregistered launches."""
    result = []
    for directory in Path("/proc").iterdir():
        if not directory.name.isdigit():
            continue
        info = process_info(int(directory.name))
        if not info or info.get("uid") != os.getuid() or not alive(info["state"]):
            continue
        arguments = info["command"]
        if not arguments:
            continue
        executable = Path(arguments[0]).name.lower()
        vivado = executable in {"vivado", "vivado.bin"}
        if executable in {"loader", "loader.bin"} and "-exec" in arguments:
            position = arguments.index("-exec") + 1
            vivado = position < len(arguments) and Path(arguments[position]).name.lower() in {"vivado", "vivado.bin"}
        if not vivado:
            continue
        try:
            info["cwd"] = str((directory / "cwd").resolve(strict=True))
        except OSError:
            info["cwd"] = None
        info["log"] = None
        if "-log" in arguments and arguments.index("-log") + 1 < len(arguments):
            log = Path(arguments[arguments.index("-log") + 1])
            info["log"] = str(log if log.is_absolute() else Path(info["cwd"] or ".") / log)
        result.append(info)
    return sorted(result, key=lambda item: item["pid"])


def vivado_engine(wrapper: dict | None, host: dict) -> dict | None:
    """Find a verified Vivado executable descendant, excluding shell wrappers."""
    if not wrapper or not alive(probe_process(wrapper, host)):
        return None
    pending = [wrapper['pid']]
    seen = set()
    while pending:
        pid = pending.pop()
        if pid in seen:
            continue
        seen.add(pid)
        info = process_info(pid)
        if not info or info.get('uid') != host.get('uid'):
            continue
        directory = Path('/proc') / str(pid)
        try:
            executable = (directory / 'exe').resolve(strict=True)
            if executable.name == 'vivado' and 'unwrapped' in executable.parts:
                if alive(probe_process(wrapper, host)) and alive(probe_process(info, host)):
                    return info
            for task in (directory / 'task').iterdir():
                pending.extend(int(child) for child in (task / 'children').read_text().split())
        except (OSError, ValueError):
            continue
    return None
