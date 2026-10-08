"""Read-only discovery of JSON non-project runs and their synthesis artifacts."""

import re
from pathlib import Path

from vivado_build_layout import descendant_runs, read_run, run_directories
from vivado_run_tree import discover_runs, run_definition, run_tree, selected_run


RUN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*\Z")
ARTIFACT_FLAGS = ["--save_this_run", "--clean_ignore_artifacts"]
PROCESS_FLAGS = ["--stopall", "--find_all_user_runs"]

BUILD_HELP = """
Non-project builds: vivado.non_project in the selected project JSON.
  Attempts and locks live beside each configured script; no output_root required.
  vivado_version: optional exact installed Vivado version.
  runs.<groups>.NAME: is_hdlforge_run: "true", script, sources, optional kind: ip, impl_runs.
  Groups are arbitrary JSON objects; only marked synthesis/IP definitions are runs.
  impl_runs.NAME: script and sources.
  sources is one list of snapshot file paths: RTL, XDC, IP, Tcl and helpers.
  Each run.tcl owns part/top, defines, threads, properties and Vivado commands.
  Call ::hdlforge::design TOP PART to record the design identity.
  Resolve declared inputs with ::hdlforge::source_path LOGICAL_PATH.
  Implementation Tcl reads the hash-checked input_dcp from runtime metadata.

Run layout (RUN_FOLDER is the synthesis/IP script's parent):
  RUN_FOLDER/_TIMESTAMP/ -- attempts beside the script; nested folders allowed.
  Each run uses a distinct folder; implementation scripts live beside synthesis.
  Default example:
  compilation/RUN/run.tcl
  compilation/RUN/_TIMESTAMP/{manifest.json,build.log,snapshot,artifacts,work}
  compilation/RUN/_TIMESTAMP/impl_runs/IMPL/snapshot/
  compilation/RUN/_TIMESTAMP/impl_runs/IMPL/_TIMESTAMP/{manifest.json,build.log,snapshot,artifacts,work}
  Each attempt owns an atomic manifest; schema paths are relative to it.
  snapshot/<repo-relative-project-path> is the full unchanged project JSON copy.
  Snapshots mirror repository-relative paths; inputs outside the repo are rejected.
  Implementations read script/sources from that saved JSON and copy only saved inputs.
  Synthesis prepares every implementation's own snapshot before starting Vivado.
  Edit that prepared implementation Tcl/XDC before the next .run.
  Implementation launch stays visible; a missing synthesis DCP fails at launch.
  Every .run freezes those edits into a fresh attempt using the fixed synthesis DCP.
  Rename completed attempt folders; completion shows folder names, not IDs.
  Save selected attempts in Git together with the producing synthesis checkpoint.

Commands:
  hdlforge vivado.build.runs.RUN.run
  hdlforge vivado.build.runs.RUN.ATTEMPT.status
  hdlforge vivado.build.runs.RUN.ATTEMPT.stop
  hdlforge vivado.build.runs.RUN.ATTEMPT.impl.IMPL.run
  hdlforge vivado.build.runs.RUN.ATTEMPT.impl.IMPL.IMPL_ATTEMPT.status
  hdlforge vivado.build.runs.RUN.ATTEMPT.impl.IMPL.IMPL_ATTEMPT.stop
  hdlforge vivado.build.runs.RUN.ATTEMPT.impl.IMPL.bitstream.IMPL_ATTEMPT
  --auto_impl NAME can be repeated and pins the exact synthesis attempt.
  hdlforge vivado.build.status
  hdlforge vivado.build.stop_all
  hdlforge vivado.build.clean_ignore_artifacts --dry-run

Cleanup:
  Keep maintained scripts outside underscore-prefixed folders.
  A single _* rule in the root .gitignore excludes generated attempts.
  Save a generated attempt explicitly with git add -f <run-directory>.
  Cleanup refuses tracked/non-ignored descendants, nested repositories and locks.
  Orphan run locks are removed only when ignored, untracked and not held.
  Locks for existing attempts are retained. --dry-run also previews orphan locks.
  Historical output directories are neither migrated nor deleted.
"""


def synthesis_folder(project: Path, settings: dict, name: str) -> Path:
    """Place attempts beside the maintained synthesis/IP Tcl script."""
    return (project.parent / run_definition(settings['runs'], name)['script']).resolve().parent


def project_attempts(project: Path, data: dict) -> list[Path]:
    """Visit configured run folders and their children, never snapshot inputs."""
    settings = data.get('vivado', {}).get('non_project', {})
    attempts = []
    for name in sorted(discover_runs(settings.get('runs', {}))):
        for parent in run_directories(synthesis_folder(project, settings, name)):
            attempts.extend(descendant_runs(parent))
    return attempts


def build_names(data: dict) -> list[str]:
    """Return synthesis names and synthesis.implementation selectors."""
    runs = discover_runs(run_tree(data))
    names = []
    if not isinstance(runs, dict):
        return names
    for name, run in runs.items():
        if not isinstance(run, dict):
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
    root = synthesis_folder(project_file, config, selected_run(selector, discover_runs(run_tree(data))))
    result = []
    for folder in run_directories(root):
        config = read_run(folder)
        if completed_only:
            try:
                if (config.get('status') != 'complete'
                        or config.get('exit_code') != 0
                        or not (folder / 'artifacts' / f"{config['top']}.dcp").is_file()):
                    continue
            except OSError:
                continue
        result.append(config['run_id'])
    return result
