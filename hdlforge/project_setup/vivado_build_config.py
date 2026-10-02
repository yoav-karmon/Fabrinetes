"""Read-only discovery of JSON non-project runs and their synthesis artifacts."""

import re
from pathlib import Path

from vivado_build_layout import read_run, run_directories


RUN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*\Z")
ARTIFACT_FLAGS = ["--save_this_run", "--clean_ignore_artifacts"]
PROCESS_FLAGS = ["--stopall", "--find_all_user_runs"]

BUILD_HELP = """
Non-project builds: vivado.non_project in the selected project JSON.
  output_root: maintained run root (normally compilation).
  vivado_version: optional exact installed Vivado version.
  runs.NAME: script, sources, enabled_on_all, optional kind: ip, impl_runs.
  impl_runs.NAME: script, sources and optional enabled_on_all.
  sources is one list of snapshot file paths: RTL, XDC, IP, Tcl and helpers.
  Each run.tcl owns part/top, defines, threads, properties and Vivado commands.
  Call ::hdlforge::design TOP PART to record the design identity.
  Resolve declared inputs with ::hdlforge::source_path LOGICAL_PATH.
  Implementation Tcl reads the hash-checked input_dcp from runtime metadata.

Run layout:
  compilation/RUN/run.tcl
  compilation/RUN/_TIMESTAMP/{snapshot/source,snapshot/scripts,logs,artifacts,work}
  compilation/RUN/_TIMESTAMP/impl_runs/IMPL/_TIMESTAMP/{snapshot,logs,artifacts,work}
  HDLForge copies maintained scripts unchanged into snapshot/scripts.
  All runtime JSON paths are relative to snapshot/scripts; Vivado runs in work/.
  Labels begin with _; run_id and created_at remain authoritative after renaming.
  latest uses JSON metadata, never folder names or filesystem mtime.
  New synthesis snapshots implementation definitions and their declared sources.
  New implementations use these frozen inputs unless --refresh_impl_inputs is set.
  Reruns use frozen Tcl and sources; changed parent checkpoints refuse execution.

Commands:
  hdlforge vivado.build.synth.RUN.new
  hdlforge vivado.build.impl.RUN.latest.IMPL.new
  hdlforge vivado.build.synth.RUN.rerun.RUN_ID
  hdlforge vivado.build.impl.RUN.RUN_ID.IMPL.rerun.IMPL_ID
  hdlforge vivado.build.impl.RUN.RUN_ID.IMPL.bitstream.IMPL_ID
  --auto_impl NAME can be repeated and pins the exact synthesis run ID.
  hdlforge vivado.build.status
  hdlforge vivado.build.stop_all
  hdlforge vivado.build.clean_ignore_artifacts --dry-run

Cleanup:
  Keep maintained scripts outside underscore-prefixed folders.
  A single _* rule in the root .gitignore excludes generated attempts.
  Save a generated attempt explicitly with git add -f <run-directory>.
  Cleanup refuses tracked/non-ignored descendants, nested repositories and locks.
  Historical output directories are neither migrated nor deleted.
"""


def build_names(data: dict) -> list[str]:
    """Return synthesis names and synthesis.implementation selectors."""
    runs = data.get("vivado", {}).get("non_project", {}).get("runs", {})
    names = []
    if not isinstance(runs, dict):
        return names
    for name, run in runs.items():
        if not RUN_NAME.fullmatch(name) or not isinstance(run, dict):
            continue
        names.append(name)
        implementations = run.get("impl_runs", {})
        if isinstance(implementations, dict):
            names.extend(f"{name}.{child}" for child, config in implementations.items()
                         if RUN_NAME.fullmatch(child) and isinstance(config, dict))
    return sorted(names)


def synthesis_timestamps(project_file: Path, data: dict, selector: str,
                         *, completed_only: bool = False) -> list[str]:
    """List stable synthesis IDs ordered by JSON creation time."""
    if selector not in build_names(data):
        return []
    config = data["vivado"]["non_project"]
    root = config.get("output_root")
    if not isinstance(root, str) or not root:
        return []
    root = project_file.parent / root / selector.split(".")[0]
    result = []
    for folder in run_directories(root):
        config = read_run(folder)
        if completed_only:
            try:
                if ((folder / 'logs/status').read_text().strip() != 'complete'
                        or (folder / 'logs/exit_code').read_text().strip() != '0'
                        or not (folder / 'artifacts' / f"{config['top']}.dcp").is_file()):
                    continue
            except OSError:
                continue
        result.append(config['run_id'])
    return result
