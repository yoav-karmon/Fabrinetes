"""Submission history and fresh PID/log observations; no Vivado queries."""

import json
import os
from pathlib import Path
import re
import signal
import time

from .terminal_output import log, table


def state_path(console):
    return console.logs_directory / "submissions.json"


def identity(pid):
    try:
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        if fields[0] in {"Z", "X"}:
            return None
        return {"pid": pid, "start_ticks": fields[19],
                "boot_id": Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
                "pgid": int(fields[2])}
    except (FileNotFoundError, ProcessLookupError):
        return None


def alive(entry):
    saved = entry.get("process")
    return bool(saved and identity(saved["pid"]) == saved)


def read_history(console):
    path = state_path(console)
    return json.loads(path.read_text()) if path.exists() else {"submissions": []}


def write_history(console, data):
    path = state_path(console)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def observe(entry, quiet_seconds=60, lines=8):
    path = Path(entry["log"])
    try:
        modified = path.stat().st_mtime
        text = path.read_text(errors="replace")
    except FileNotFoundError:
        modified, text = entry["submitted_at"], ""
    now = time.time()
    live = alive(entry)
    age = max(0, now - modified)
    if live and entry.get("stop_requested_at"):
        status = "Stopping"
    elif live:
        status = "Quiet" if age >= quiet_seconds else "Running"
    elif entry.get("stop_requested_at"):
        status = "Stopped"
    elif entry.get("exit_code") not in {None, 0} or re.search(r"(?m)^ERROR:|^HDLFORGE_BATCH_FAILED|^.*(?:synth_design failed|was cancelled|Interrupt caught)", text):
        status = "Failed / interrupted"
    elif re.search(r"(?m)^HDLFORGE_BATCH_COMPLETED$", text):
        status = "Completed"
    else:
        status = "Exited; result unknown"
    return {"status": status, "alive": live, "checked_at": now,
            "last_log_update": modified, "quiet_seconds": round(age, 1),
            "tail": text.splitlines()[-lines:]}


def refresh(console, submission=None, quiet_seconds=60, lines=8):
    with console.locked("history.lock"):
        history = read_history(console)
        entries = history["submissions"]
        if submission:
            entries = [entry for entry in entries if entry["id"] == submission]
            if not entries:
                raise ValueError(f"Unknown submission: {submission}")
        for entry in entries:
            entry["last_status"] = observe(entry, quiet_seconds, lines)
        write_history(console, history)
    return entries


def monitor(console, follow=False, submission=None, quiet_seconds=60, lines=8, as_json=False):
    while True:
        entries = refresh(console, submission, quiet_seconds, lines)
        if as_json:
            print(json.dumps(entries, indent=2))
        else:
            table(["Submission", "Requested", "PID", "Status", "Log quiet (s)"],
                  [[e["id"], e["target"], e["pid"], e["last_status"]["status"],
                    e["last_status"]["quiet_seconds"]] for e in entries])
            for entry in entries:
                log(f"{entry['id']} — {entry['log']}")
                print("\n".join(entry["last_status"]["tail"]), flush=True)
        if not follow or not any(e["last_status"]["alive"] for e in entries):
            return
        time.sleep(2)


def stop(console, submission):
    with console.locked("history.lock"):
        history = read_history(console)
        entry = next((e for e in history["submissions"] if e["id"] == submission), None)
        if entry is None:
            raise ValueError(f"Unknown submission: {submission}")
        if not alive(entry):
            log("Process already exited or identity changed; no signal sent")
            return
        if entry["process"]["pgid"] != entry["pid"]:
            raise RuntimeError("Process group does not match this submission")
        entry["stop_requested_at"] = time.time()
        os.killpg(entry["pid"], signal.SIGTERM)
        write_history(console, history)
    log(f"Stop requested for submission {submission} and its process group")
