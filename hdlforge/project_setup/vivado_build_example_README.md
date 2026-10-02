# HDLForge {{STAGE}} build example

Generated for `{{PROJECT}}`; run HDLForge from the project JSON directory.
Replace placeholder sources, IP, XDC, part and top before building.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.ip_example.run
hdlforge --project {{PROJECT_ARG}} vivado.build.synth_example.run --auto_impl impl_example
hdlforge --project {{PROJECT_ARG}} vivado.build.synth_example.latest.impl.impl_example.run
```

The project JSON points to maintained scripts: `synth_example/run.tcl`,
`synth_example/impl_run_example.tcl`, and `ip_example/run.tcl`.
HDLForge copies the selected script unchanged; it generates data, not run code.

```text
{{OUTPUT_ROOT}}/synth_example/
  run.tcl                     maintained synthesis Tcl
  impl_run_example.tcl        initial implementation Tcl
  _<attempt>/
    snapshot/<project-path>/{{PROJECT}}.hdlforge.json  full project copy with original filename
    manifest.json             resolved paths, inputs/hashes, status/result
    build.log                 launcher, runner and Vivado console output
    snapshot/
    artifacts/                checkpoints, reports, BIT/LTX/MMI
    work/                     temporary Vivado files
    impl_runs/<implementation>/
      snapshot/  prepared inputs copied from synthesis snapshot
      _<attempt>/             own manifest, log, snapshot, artifacts and work
```

Each attempt has its own atomic `manifest.json`; schema paths are relative to
that attempt. Tcl emits events to the Python runner, which records design
identity, stage times, tool version, status and exit code in the manifest.
`build.log` is the single human-readable build log. Vivado auxiliary files stay
in `work/`. `.manifest.lock` and the run lock are internal synchronization files.
The global registry indexes attempts; it does not duplicate new run records.

Each script declares part/top with `::hdlforge::design $top $part` and owns
defines, parameters (including threads), file-read commands and properties.
JSON is a launcher manifest: `script`, `sources` and `impl_runs`. IP producers add `kind: "ip"` for private working copies
and freshness checks. Synthesis/implementation need no stage declaration.

List every input and helper in one `sources` array. Tcl obtains its saved
location with `::hdlforge::source_path <declared-path>`. HDLForge preserves
repository-relative input paths in snapshot and does not infer dynamic Tcl/Python
dependencies. Source properties and language options belong beside the Tcl
read command.

Implementations use the selected synthesis checkpoint and verify its SHA-256.
Synthesis saves the full project JSON and the implementation Tcl/XDC it declares.
Before Vivado starts, every implementation gets its own prepared `snapshot/`.
Only actual attempts get `work/` and `artifacts/` folders.
Edit the prepared Tcl/XDC to try timing changes.
Every `.run` creates a fresh implementation attempt and
freezes the current Tcl and declared XDC inputs; previous attempt inputs and results stay intact.
The synthesis checkpoint is shared and is never rebuilt by implementation.

Rename completed attempt folders to useful labels, such as `baseline` or
`timing_closed`; keep configured names such as `synth_example` unchanged.
Completion shows actual attempt folder names. Stable identity and creation time
remain in the manifest; `latest` uses creation time, not folder spelling.
Discovery skips folders without valid run metadata. Implementation commands
are available before synthesis finishes; launching without the checkpoint fails
with its missing path. The saved synthesis project JSON defines implementations.

```bash
hdlforge vivado.build.synth_example.baseline.impl.impl_example.run
hdlforge vivado.build.synth_example.baseline.status
hdlforge vivado.build.synth_example.baseline.impl.impl_example.timing_closed.status
hdlforge vivado.build.synth_example.baseline.impl.impl_example.<attempt>.stop
hdlforge vivado.build.synth_example.baseline.impl.impl_example.bitstream.timing_closed
```

There is no in-place rerun: use `.run` again for each timing experiment, including
parallel attempts. Never edit an attempt's frozen snapshot to prepare the next
one. Bitstream-only launches create a child attempt under `bitstream_runs/`,
using the selected routed checkpoint and original USERID timestamp.

Add `_*` once in the repository root `.gitignore`. HDLForge never creates
per-run ignore files. Use `git add -f <run-directory>` to save a generated run;
`--save_this_run` is retired. Recursive cleanup refuses an entire selected tree
if any descendant is tracked or not ignored, inspection fails, a nested Git
repository exists, or a run lock is held.

```bash
hdlforge --project {{PROJECT_ARG}} vivado.build.clean_ignore_artifacts --dry-run
hdlforge --project {{PROJECT_ARG}} vivado.build.status
```

Historical run folders are left intact and remain readable. Create a fresh
synthesis to capture the original project JSON and the consolidated layout.

To preserve a timing result in Git, rename the completed synthesis and selected
implementation attempt folders, then add the synthesis folder (which contains
its checkpoint and the selected child) with `git add -f <synthesis-attempt>`.
Review the staged files before committing; add only the attempts you intend to
keep. A saved implementation needs its producing synthesis checkpoint.

Each synthesis snapshot contains a full, unchanged copy of the selected
`*.hdlforge.json`, preserving its filename. Source → synthesis copies the files
declared by synthesis and its implementations. Synthesis → implementation uses
only the selected implementation's `script` and `sources` from that saved JSON.
The manifest records resolved paths and execution metadata; it does not choose
the file list. Implementation never refreshes inputs from the live project.
Synthesis prepares each `impl_runs/<impl>/snapshot/` with its own declared
files. For timing experiments, edit that implementation's prepared Tcl/XDC;
every `.run` copies those inputs into a fresh attempt. Source selection remains
in the synthesis snapshot's project JSON and must reference that implementation's
prepared inputs. Earlier attempts remain unchanged. Constraints stay in snapshots.

Snapshot copies preserve repository-relative directories and filenames directly
beneath `snapshot/`, including the run Tcl. There are no added `source/` or
`scripts/` input containers. The repository root is the top of every snapshot. The saved JSON stays at
its repository-relative project path; its script paths resolve relative to that
project folder inside the snapshot. Only the attempt copy is executed. Inputs
outside the repository are rejected; no `_external` directory is created.
