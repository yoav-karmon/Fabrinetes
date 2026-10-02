# HDLForge {{STAGE}} build example

Generated for `{{PROJECT}}`; run HDLForge from the project JSON directory.
Replace placeholder sources, IP, XDC, part and top before building.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.ip_example.continue
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.synth_example.continue --auto_impl impl_example
hdlforge --project {{PROJECT_ARG}} vivado.build.impl.synth_example.latest.impl_example.new
```

The project JSON points to maintained scripts: `synth_example/run.tcl`,
`synth_example/impl_run_example.tcl`, and `ip_example/run.tcl`.
HDLForge copies the selected script unchanged; it generates data, not run code.

```text
{{OUTPUT_ROOT}}/synth_example/
  run.tcl
  impl_run_example.tcl
  _<label>/
    snapshot/
      source/                 only declared inputs and literal RTL includes
      scripts/
        run.tcl               copy of the selected maintained script
        run.json              shared synthesis configuration and attempt records
        _hdlforge/            frozen runtime and vendored Tcllib JSON reader
    logs/                     stdout, Vivado logs, status, stage events, provenance
    artifacts/                checkpoints, reports, BIT/LTX/MMI
    work/                     Vivado working directory
    impl_runs/<implementation-name>/
      _<label>/               same snapshot/logs/artifacts/work layout
```

All schema paths in generated `run.json` are relative to that JSON's directory.
The maintained Tcl bootstrap resolves runtime paths before executing the body.
Each script declares part/top with `::hdlforge::design $top $part` and owns
defines, parameters (including threads), file-read commands and properties.
JSON is a launcher manifest: `script`, `sources`, `impl_runs` and
`enabled_on_all`. IP producers add `kind: "ip"` for private working copies
and freshness checks. Synthesis/implementation need no stage declaration.

List every input and helper in one `sources` array. Tcl obtains its saved
location with `::hdlforge::source_path <declared-path>`. HDLForge preserves
input subdirectories in snapshot/source and does not infer dynamic Tcl/Python
dependencies. Source properties and language options belong beside the Tcl
read command.

Implementations explicitly declare their own sources. Their parent DCP remains
in the synthesis artifacts directory; Tcl uses
`[dict get $::hdlforge_config input_dcp]`. HDLForge verifies its SHA-256 and
checks the Tcl design identity against the selected synthesis. New attempts
use the synthesis-frozen implementation definitions and inputs; use
`--refresh_impl_inputs` to snapshot the current maintained files.

Directory labels start with `_` and carry no identity/time meaning.
`run_id`, `created_at`, `timestamp`, and `launch_epoch` are authoritative JSON
metadata. Rename generated synthesis/implementation folders freely, retaining
the relative tree. Discovery and `latest` use metadata; completion offers stable
IDs. A failed newest synthesis is not silently replaced with an older success.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.synth_example.rerun.<run-id>
hdlforge --project {{PROJECT_ARG}} vivado.build.impl.synth_example.<synth-id>.impl_example.rerun.<impl-id>
hdlforge --project {{PROJECT_ARG}} vivado.build.impl.synth_example.<synth-id>.impl_example.bitstream.<impl-id>
```

Bitstream-only runs reference the selected implementation's routed checkpoint,
freeze its hash, copy its paired probes, and preserve its USERID timestamp.
They live under `bitstream_runs/_<label>/` with the same run layout.
A rerun preserves its frozen configuration and timestamp.

Add `_*` once in the repository root `.gitignore`. HDLForge never creates
per-run ignore files. Use `git add -f <run-directory>` to save a generated run;
`--save_this_run` is retired. Recursive cleanup refuses an entire selected tree
if any descendant is tracked or not ignored, inspection fails, a nested Git
repository exists, or a run lock is held.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.clean_ignore_artifacts --dry-run
hdlforge --project {{PROJECT_ARG}} vivado.build.status
```

Historical old-format output folders are left intact and are not selected for
new-format reruns or cleanup. Create a new synthesis to use the new format.

One synthesis run.json contains implementation_configs and attempts keyed by
run ID. Implementations and bitstream runs receive this JSON path and their run
ID as Tcl arguments; they do not get separate JSON files. A child _run_id marker
contains its identity for discovery after renaming. Metadata updates are locked
and atomic. Synthesis reruns are blocked once implementation history exists.
