"""Read-only discovery of JSON non-project runs and their synthesis artifacts."""

import json
import re
from pathlib import Path

from vivado_build_layout import read_run, run_directories


RUN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*\Z")
ARTIFACT_FLAGS = ["--save_this_run", "--clean_ignore_artifacts"]
PROCESS_FLAGS = ["--stopall", "--find_all_user_runs"]

BUILD_HELP = """
Non-project builds: vivado.non_project in the selected project JSON.
  output_root: run-definition root; vivado_version: optional exact version.
  runs.NAME: stage (synth/ip), script, part, top, sources, ips, constraints,
    defines, input_files, parameters, post_load_parameters, project_properties,
    fileset_properties, checkpoint_properties, constraint_properties.
  impl_runs.NAME: implementation definition with its own script and inputs.
    Omitted ips inherits the selected synthesis's frozen IP inputs; [] selects none.
  HDLForge copies the maintained script unchanged as snapshot/scripts/run.tcl.
  Implementation scripts conventionally live beside the synthesis script as
    impl_run_NAME.tcl; script paths always come from the project JSON.
  Commands, directives, reports and checkpoints belong in Tcl, not JSON hooks.
  Use the example scripts' bootstrap to load the shared runtime and generated JSON.

Run layout:
  RUN/_LABEL/{snapshot/source,snapshot/scripts,logs,artifacts,work}
  RUN/_LABEL/impl_runs/IMPL/_LABEL/{snapshot/source,snapshot/scripts,logs,artifacts,work}
  All run.json paths are relative to snapshot/scripts. Vivado runs from work/.
  The JSON stores the stable run_id, created_at and launch_epoch; folder names
    carry no time/identity semantics. Renaming generated run folders is supported.
  Implementations reference the parent DCP directly and freeze its SHA-256.
    A changed or missing parent checkpoint refuses execution/rerun.
  Existing old-format directories are not migrated or deleted by these commands.

Selectors:
  --build SYNTH / SYNTH.new
  --build SYNTH.IMPL --synth_timestamp ID
  --build SYNTH.latest.IMPL.new
  --build SYNTH.rerun.ID
  --build SYNTH.SYNTH_ID.IMPL.rerun.IMPL_ID
  --build SYNTH.SYNTH_ID.IMPL.bitstream.IMPL_ID
  IDs are stable JSON run IDs; existing folder labels are also accepted.
  latest uses JSON created_at, never folder names or filesystem mtime.
  --auto_impl NAME may be repeated; continuations pin their parent by run ID.
  A new implementation snapshots current declared Tcl/XDC/support files.
    --refresh_impl_inputs is retained as a compatibility spelling for this behavior.
  Reruns use frozen run.json and scripts; their recorded time does not change.

Cleanup:
  Add a single _* rule to the repository root .gitignore.
  Generated labels and housekeeping files start with _; no per-run ignore files.
  Save explicitly with git add -f <run-directory>; --save_this_run is retired.
  --build_clean_ignore_artifacts [--dry-run], or --build RUN --clean_ignore_artifacts:
    refuse the entire selected tree if ANY descendant is tracked or not ignored,
    a nested repository exists, inspection fails, or a run lock is held.
  --build_status / --build_status_all / --build_stop_all manage launch workers.
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
