"""Read-only discovery of JSON non-project runs and their synthesis artifacts."""

import json
import re
from pathlib import Path


RUN_NAME = re.compile(r"[A-Za-z0-9_][A-Za-z0-9_-]*\Z")
TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{6}(?:\.\d{6})?Z\Z")
ARTIFACT_FLAGS = ["--save_this_run", "--clean_ignore_artifacts"]
PROCESS_FLAGS = ["--stopall", "--find_all_user_runs"]

BUILD_HELP = """
Bitstream regeneration from a completed implementation (no synthesis/place/route):
  --build SYNTH.<timestamp|latest>.IMPL.bitstream.<impl_timestamp|latest>
  Copies the final routed checkpoint and original paired LTX into a new
  implementation/bitstream_runs/TIMESTAMP/inputs/ snapshot. Outputs, logs and status
  are separate from the original implementation; its USERID launch timestamp is
  retained. Uses normal background execution, --build_status and --build_stop_all.
  Completion offers existing completed implementation folders. No JSON field needed.
  Refreshing XDC requires a new implementation, not bitstream regeneration.
Non-project JSON: vivado.non_project
  vivado_version: optional exact Vivado version; output_root: artifact/script root.
  runs: named independent synthesis or IP builds; impl_runs: nested implementations.
Run fields:
  stage: synth (RTL synthesis), impl (parent DCP implementation), ip (IP regeneration).
  enabled_on_all: optional boolean, default true. Set false to exclude a run
       from the project's build-all and continue-all shortcuts. Explicit --build
       selection and explicit --auto_impl selection remain allowed.
  script: run.tcl; part: FPGA part; top: required for synth/impl, unnecessary for ip.
  publish_latest: optional boolean, default false; supported for all run types.
       IP publications include info/source_hashes.json. Consumers warn about changed
       producer sources/settings or missing hashes and continue; info/warnings.log records warnings.
       At run startup, remove the previous latest contents and recreate it empty.
       Successful and failed runs publish artifacts with their status and exit code; cancelled runs leave latest empty.
       After success or failure, copy the entire artifact tree to output_root/RUN/latest/.
       For implementation use output_root/SYNTH/IMPL/latest/. Relative paths
       inside the artifact tree are preserved, including work/, info/ and logs.
       Atomic directory replacement and locking prevent older launches replacing
       newer ones. Real copies, no links; timestamped originals remain intact.
  sources: RTL paths or {path, language, library, properties}; language: vhdl2008.
  ips: XCI/XCIX paths or {path, properties, file_properties}.
       Implementation inherits its synthesis list when ips is omitted.
       An explicit implementation ips list overrides it; [] selects none.
       file_properties maps IP-relative member paths to property overrides.
       Consumer example: OUTPUT_ROOT/ip_example/latest/work/ip_sources/**/example.xcix
       The producer uses sources/ip/example.xcix. Build the producer first;
       no published file means an error, not fallback to checked-in IP products.
       Injection rebases this example path when output_root is customized.
  constraints: XDC paths or {path, properties}; defines: synthesis macro list.
       Injection creates synth_example/ip_keep_hierarchy.xdc and lists it in
       synthesis constraints. It warns to replace the placeholder reference and
       uncomment KEEP_HIERARCHY SOFT only for IP hierarchy that needs preserving.
       Verify cell matches; the supplied assignment is commented out.
  input_files: extra supporting file paths (headers, memory/data files, helpers).
       Snapshot declared dependencies here; dynamic Tcl/Python dependencies are
       not inferred. Literal RTL includes are copied recursively.
       Input paths may use globs, but each must match exactly one existing file.
       Synthesis freezes inputs and all declared implementation configurations
       under artifacts/TIMESTAMP/inputs/. Implementations reuse that snapshot
       and parent DCP, never current latest IPs. Old runs without snapshots must
       be rebuilt. info/input_manifest.json records original-to-copy mappings.
  parameters: set_param before project creation.
       general.maxThreads: per-run thread limit, 1 through 8; examples use 8.
       Applies to IP, synthesis and implementation; actual usage depends on
       the operation and available CPUs. This is a limit, not reserved CPUs.
       general.usePosixSpawnForFork: child-process launch mechanism, not a
       thread/job count; examples use 1.
       Example: "parameters": {"general.usePosixSpawnForFork": 1,
                               "general.maxThreads": 8}
       Jobs are independent concurrent runs, not threads within one run.
       This runner has no concurrent-job scheduler or --jobs option;
       automatic implementation continuations are sequential. The Vivado
       runs.launchOptions parameter does not schedule HDLForge builds.
  project_properties / fileset_properties: set_property on project / fileset.
  post_load_parameters: set_param after reading inputs.
  checkpoint_properties / constraint_properties: imported-file defaults;
       explicit per-file constraint properties override defaults.
  Parameter/property maps accept scalar values or lists; omitted maps are empty.
  Source/script/output_root paths are relative to the JSON directory.
  Property values are literal Vivado values; relative ip_output_repo is under work/.
  Commands, directives, reports and checkpoints belong in run.tcl, not JSON hooks.
Create all examples without running Vivado:
  --init_build all: fill missing optional settings in all existing runs.
  --init_build synth_production.impl_production: fill one existing run.
  Full JSON paths such as vivado.non_project.runs.synth_production are accepted.
  Existing values, including false flags, are preserved. Required part/top/script
  must already be supplied; example input filenames are never injected into runs.
  --build_create syth_imp_example (also accepts synth_impl_example)
  --init_build_example is an alias. Creates synth_example/run.tcl,
  synth_example/impl_example/run.tcl and ip_example/run.tcl under output_root,
  plus a README.md in each folder with project-specific commands, input snapshots,
  latest publication and settings. Injects matching JSON. Refuses existing
  entries/folders. Replace placeholder
  inputs and choose the correct part before building. --build_lint checks offline.
Build examples:
  First replace placeholder inputs, then run in dependency order:
  --build ip_example
  --build synth_example
  --build synth_example.impl_example [--synth_timestamp TIMESTAMP]
  --build synth_example --auto_impl impl_example
  Repeat --auto_impl for distinct implementations; duplicates are removed.
  Continuations require success and carry the exact synthesis timestamp.
  Implementation defaults to the latest completed synthesis with a checkpoint.
  IP builds use private copies, generate_target and synth_ip; no top-level bitstream,
  parent synthesis timestamp or auto_impl. Checked-in IP sources are not overwritten.
Selectors:
  SYNTH.new or SYNTH.rerun.TIMESTAMP (or rerun.latest): new synthesis or rerun frozen synthesis.
  SYNTH.latest.IMPL.new or SYNTH.TIMESTAMP.IMPL.new: new implementation.
  SYNTH.TIMESTAMP.IMPL.rerun.IMPL_TIMESTAMP (or rerun.latest): rerun that attempt from frozen inputs.
  Reruns preserve inputs and child implementations; generated outputs are cleared.
Folders:
  One managed .gitignore at each synthesis/IP run root controls all timestamps
  and nested implementations. Examples inject it with explanatory comments.
  !/artifacts/ permits traversal; /artifacts/** ignores all artifact files;
  !/artifacts/**/ permits directory traversal so saved exceptions can work.
  Saved synthesis exceptions come next, followed by implementation ignore rules
  and then saved implementation exceptions. Saving synthesis does not save its
  implementations. --save_this_run adds a saved-path exception;
  Edit .gitignore manually to remove exceptions. Saving implementation also saves synthesis.
  output_root/RUN/artifacts/TIMESTAMP/{info,work,checkpoints,reports,bitstream}
  Implementation: SYNTH/artifacts/TIMESTAMP/impl_runs/IMPL/IMPL_TIMESTAMP/ with the same subfolders.
  IMPL/inputs is shared across attempts; earlier outputs and inputs are retained.
  Full regenerated IP products remain under work/ip_sources/.
  runme.log, vivado.log and vivado.jou are retained per run; run_registry.json
  under output_root records launch identities, PID state, status and log paths.
Management (does not launch builds):
  --build_clean_ignore_artifacts: clean eligible explicitly ignored artifacts
       across all configured runs, regardless of enabled_on_all. Never deletes
       live latest publications (outside timestamp selection). No status, PID, or tracked-file checks.
  --build_status: registered non-dead/unavailable processes.
  --build_status_all: all registered runs, including completed, failed, stopped, and dead runs.
  --build_stop_all: stop verified registered launches and cancel continuations.
  --build_find_all_user_runs: report visible current-user Vivado processes,
       including unregistered processes; does not stop unregistered processes.
  --build RUN --save_this_run / --clean_ignore_artifacts:
       Save selects the newest matching run unless --synth_timestamp is supplied.
       Cleanup covers all matching timestamps unless narrowed by --synth_timestamp.
       Cleanup evaluates actual file ignore rules using Git check-ignore --no-index.
       Any nonignored file protects its run folder; empty folders are eligible.
       No status, PID or tracked-file checks. Snapshot folders named latest have
       no special protection; live publications are outside timestamp selection.
Optional create_msg_db/close_msg_db pairs retain structured GUI messages;
text logs remain available without them. Templates explain these commands.
"""


def timestamp_key(value: str) -> tuple[str, str]:
    seconds, _, fraction = value.removesuffix("Z").partition(".")
    return seconds, fraction or "000000"


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
    """List timestamp directories without querying Vivado or changing artifacts."""
    if selector not in build_names(data):
        return []
    config = data["vivado"]["non_project"]
    root = config.get("output_root")
    if not isinstance(root, str) or not root:
        return []
    artifacts = project_file.parent / root / selector.split(".")[0] / "artifacts"
    try:
        candidates = sorted(artifacts.iterdir(), key=lambda path: path.name)
        result = []
        for path in candidates:
            if not TIMESTAMP.fullmatch(path.name) or not path.is_dir():
                continue
            if completed_only:
                status = path / "info" / "status"
                if not status.is_file() or status.read_text().strip() != "complete":
                    continue
                resolved = path / "info/resolved.json"
                top = config["runs"][selector.split(".")[0]].get("top", "top")
                if resolved.is_file():
                    top = json.loads(resolved.read_text()).get("top", top)
                if not (path / "checkpoints" / f"{top}.dcp").is_file():
                    continue
            result.append(path.name)
        return sorted(result, key=timestamp_key)
    except OSError:
        return []
