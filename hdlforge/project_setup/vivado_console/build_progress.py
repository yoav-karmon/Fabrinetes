"""Build plans and artifact discovery owned by the project console."""

from pathlib import Path
import time

from .terminal_output import log, table


def plan_entry(run: dict) -> dict:
    properties = run["properties"]
    implementation = properties.get("IS_IMPLEMENTATION") in {"1", "true"}
    ip = properties.get("HDLFORGE_IS_IP", "0").lower() in {"1", "true"}
    stages = ["synth_design"] if not implementation else ["opt_design", "place_design", "phys_opt_design (if enabled)", "route_design"]
    if implementation and not ip:
        stages += ["post-route phys_opt_design (if enabled)", "write_bitstream"]
    return {"name": run["name"], "directory": properties.get("DIRECTORY", ""),
            "stages": stages, "state": "pending", "status": properties.get("STATUS", ""),
            "step": properties.get("CURRENT_STEP", ""), "progress": properties.get("PROGRESS", ""),
            "outputs": "*.dcp, *.rpt" + (", *.bit, *.ltx (if debug enabled)" if implementation and not ip else "")}


def update_entry(entry: dict, run: dict, state: str) -> None:
    properties = run["properties"]
    entry.update(state=state, status=properties.get("STATUS", ""),
                 step=properties.get("CURRENT_STEP", ""), progress=properties.get("PROGRESS", ""))


def show_plan(state: dict) -> None:
    entries = [item for item in state.get("runs", []) if not item["state"].startswith("skipped")]
    if not entries:
        return
    log("\nRun status")
    table(["Order", "Run", "State", "Vivado stage/status", "Progress"],
          [[index, item["name"], item["state"], item.get("step") or item.get("status", ""), item.get("progress", "")]
           for index, item in enumerate(entries, 1)])
    rows = []
    for index, item in enumerate(entries, 1):
        directory = Path(item["directory"]) if item.get("directory") else None
        details = ["Plan: " + " → ".join(item["stages"]),
                   "Directory: " + (short_path(str(directory), state) if directory else "Not available"),
                   "Log: runme.log | Expected: " + item["outputs"]]
        if directory and directory.exists():
            artifacts = sorted(path for path in directory.iterdir() if path.suffix in {".dcp", ".rpt", ".bit", ".ltx"})
            details.append("On disk: " + (", ".join(path.name for path in artifacts) or "None yet"))
            logfile = directory / "runme.log"
            if logfile.exists():
                with logfile.open("rb") as handle:
                    handle.seek(max(0, logfile.stat().st_size - 8192))
                    lines = handle.read().decode(errors="replace").splitlines()
                updated = time.strftime("%H:%M:%S UTC", time.gmtime(logfile.stat().st_mtime))
                details.append(f"Latest ({updated}): " + next((line for line in reversed(lines) if line.strip()), "")[:240])
        rows.append([item['name'], "\n".join(details)])
    log("\nFiles and artifacts")
    log("Directories are relative to the XPR directory. DCP: checkpoint; RPT: report; BIT: bitstream; LTX: debug probes.")
    table(["Run", "Expected locations and available files"], rows)
    log("File names are relative to each run directory; files on disk may predate this build.")


def short_path(value: str, state: dict) -> str:
    project = state.get("project")
    if not project:
        return value
    try:
        return str(Path(value).relative_to(Path(project).parent))
    except ValueError:
        return value


def show_summary(fields: dict, state: dict) -> None:
    log("Worker status")
    table(["Field", "Value"], list(fields.items()))
