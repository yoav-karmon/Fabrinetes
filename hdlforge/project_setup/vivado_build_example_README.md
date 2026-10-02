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
The maintained Tcl bootstrap loads this JSON and resolves paths before executing
the script body. `::hdlforge::initialize_design` reads the selected inputs.
Commands, directives, reports and checkpoint writes stay in Tcl; the JSON holds
inputs, defines, parameters and property maps. Declare extra dependencies in
`input_files`; HDLForge does not infer dynamic Tcl/Python dependencies.

Implementation snapshots contain only the implementation's declared files.
If `ips` is omitted, the selected synthesis's frozen IP list is inherited;
an explicit empty list means no IPs. The DCP remains in the parent synthesis's
`artifacts/`. Its relative path, SHA-256 and parent run ID are recorded in JSON.
A missing or changed DCP refuses launch/rerun; a new implementation gets a new
configuration. New implementation attempts copy declared Tcl/XDC
and support files from the synthesis snapshot; reruns use only their frozen snapshots.

Directory labels start with `_` and carry no identity/time meaning.
`run_id`, `created_at`, `timestamp`, and `launch_epoch` are authoritative JSON
metadata. Rename generated synthesis/implementation folders freely, retaining
the relative tree. Discovery and `latest` use metadata; completion offers stable
IDs. A failed newest synthesis is not silently replaced with an older success.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.synth_example.rerun.<run-id>
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.synth_example.<synth-id>.impl_example.rerun.<impl-id>
hdlforge --project {{PROJECT_ARG}} vivado.build.synth.synth_example.<synth-id>.impl_example.bitstream.<impl-id>
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
