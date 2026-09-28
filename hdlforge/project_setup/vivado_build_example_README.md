# HDLForge {{STAGE}} build example

Generated for `{{PROJECT}}`. Run the commands below from the project JSON's
directory. Example creation writes configuration and scripts only; it does not
start Vivado. Replace placeholder sources, constraints, IP and supporting files,
and select the correct FPGA part before building.

## Build order

```bash
hdlforge --project {{PROJECT_ARG}} --tool vivado --build ip_example
hdlforge --project {{PROJECT_ARG}} --tool vivado --build synth_example
hdlforge --project {{PROJECT_ARG}} --tool vivado --build synth_example.impl_example
```

Alternatively, after generating the IP, run synthesis with
`--build synth_example --auto_impl impl_example`. Automatic continuation uses the
exact successful synthesis timestamp. A direct implementation command chooses the
latest completed synthesis; add `--synth_timestamp TIMESTAMP` to select another.
Repeated `--auto_impl` values are deduplicated and implementations run sequentially.

## Files and outputs

The configured output root is `{{OUTPUT_ROOT}}`, relative to the project JSON.

```text
<output_root>/
  ip_example/run.tcl
  ip_example/README.md
  ip_example/artifacts/<timestamp>/
  ip_example/latest/
  synth_example/run.tcl
  synth_example/ip_keep_hierarchy.xdc
  synth_example/README.md
  synth_example/artifacts/<timestamp>/inputs/
  synth_example/artifacts/<timestamp>/impl_runs/impl_example/
  synth_example/impl_example/run.tcl
  synth_example/impl_example/README.md
  synth_example/impl_example/latest/
  synth_example/latest/
```

`stage` selects `ip`, `synth`, or `impl`. JSON declares input paths, part, top
(for synthesis/implementation), and parameter/property maps. Tcl owns native
Vivado commands, directives and reports. `initialize_design` loads the selected
inputs; `ACTIVE_STEP` labels progress without executing a command.

Each run includes `"enabled_on_all": true`. Set it to `false` to exclude a run
from project build-all and continue-all shortcuts. Omission means true. Direct
`--build` and explicit `--auto_impl` selections still work. This option filters
bulk selection; it does not create a build-all shortcut in the injected project.

Synthesis consumes the example IP from
`{{OUTPUT_ROOT}}/ip_example/latest/work/ip_sources/**/example.xcix`.
Each input glob must match exactly one file. Missing IP publications fail clearly;
there is no fallback to the original IP. The IP producer itself reads the authored
`sources/ip/example.xcix` and regenerates a private copy.

## Reproducible inputs

Injection also creates `synth_example/ip_keep_hierarchy.xdc` and adds it to the
synthesis constraint list. **Customize it before building:** replace the placeholder
IP reference and uncomment `set_property KEEP_HIERARCHY SOFT ...` where needed.
Add explicit assignments for the intended IP references and verify the cell query
matches the right instances. The template is commented out and applies no hierarchy
constraints until edited. This is a synthesis choice, not mandatory for every IP.

Before synthesis, HDLForge copies declared RTL, IP, XDC, Tcl scripts and
`input_files` into the timestamped `inputs/` tree. Literal RTL includes are also
copied. Declare supporting headers, memory/data files and script dependencies in
`input_files`; arbitrary dynamic Tcl/Python dependencies are not inferred.
`info/input_manifest.json` records original-to-copy mappings.

Synthesis also freezes all declared implementation configurations and inputs.
Implementation uses that parent snapshot and checkpoint, not later working-tree
edits or newer IP publications. Changing implementation inputs requires a new
synthesis. Older synthesis artifacts without a snapshot cannot use this flow.

## Publishing and resources

`publish_latest: true` enables publishing for any run type. At run startup,
HDLForge removes the previous latest contents and recreates the directory empty.
After a run succeeds or fails,
HDLForge copies the entire artifact tree, including inputs, work, reports and logs,
to the run's `latest/` folder. Files retain their relative layout: XCIX files are
under `latest/work/ip_sources/`, not directly under `latest/`. Atomic replacement
publishes only the complete copied tree. A lock prevents older launches from
replacing the empty directory or published result belonging to a newer run. Copies are real files, not links;
timestamped originals remain intact. Publishing duplicates disk usage.

`parameters.general.maxThreads: 8` is a thread limit per Vivado process; actual
usage depends on the operation and CPUs. `general.usePosixSpawnForFork: 1` selects
a child-process mechanism, not a thread count. Concurrent jobs are separate;
HDLForge has no `--jobs` scheduler for this flow.

`create_msg_db` and its matching `close_msg_db` are commented out by default.
Uncomment both only when needed: they retain structured
messages for Vivado GUI filtering. Text logs remain available without them.

## Help and management

Injection creates one commented `.gitignore` at each synthesis/IP run root.
It controls every timestamp and nested implementation; implementations have no
separate `.gitignore`. Git reads rules top to bottom, and `!` means do not ignore.

- `!/artifacts/` allows Git to enter the artifact directory.
- `/artifacts/**` ignores every artifact file by default.
- `!/artifacts/**/` permits directory traversal so later exceptions can work.
- Saved synthesis/IP exceptions follow these defaults.
- `/artifacts/*/impl_runs/**` keeps implementation files ignored even when
  their parent synthesis is saved; its directory exception permits traversal.
- Saved implementation exceptions appear last and override that rule.

`--build RUN --save_this_run` adds a saved-path exception. These rules
do not untrack files already in Git. Live publication folders are outside timestamp cleanup selection. The root rules
ignore `/latest/` and `/*/latest/` by default. Copies named `latest` inside input
snapshots have no special protection.

`--build_clean_ignore_artifacts` covers every configured run; add a run selector
to narrow it. Cleanup evaluates actual file ignore rules with Git, including manual
exceptions. Any nonignored file protects its containing run folder. Empty folders
are eligible. No PID, run-status or tracked-file checks are performed.

`--init_build all` fills missing optional settings in existing JSON runs while
preserving current values; a run selector limits the update to one definition.

```bash
hdlforge --project {{PROJECT_ARG}} --tool vivado --build --help
hdlforge --project {{PROJECT_ARG}} --tool vivado --build_lint
hdlforge --project {{PROJECT_ARG}} --tool vivado --build_status
```

Help describes every field and parameter/property map, process discovery and
stopping, and the artifact ignore/cleanup flags. Lint checks configuration and
paths offline. These commands are examples; none run during injection.
Both `--build_create syth_imp_example` and `--init_build_example` inject all three
examples and these READMEs. Existing example entries or folders are never overwritten.

Failed latest publications retain `info/status` and `info/exit_code`. Continue-all
retries them, and input snapshotting rejects them as consumer inputs.

Implementation IP inputs inherit the parent synthesis `ips` list when omitted.
Examples keep one shared list on synthesis; an explicit implementation list
overrides inheritance. The resolved list is frozen with the synthesis inputs.
In input paths, `**` matches generated subdirectories recursively; each IP pattern
must resolve to exactly one file.

`--build RUN --save_this_run` saves the newest matching existing timestamp by
adding exceptions to the run-root `.gitignore`. Use `--synth_timestamp TIMESTAMP`
to select an exact run. Saving an implementation also saves its parent synthesis,
but not sibling implementations. This management action does not start a build.
Edit `.gitignore` manually to change or remove saved exceptions.

IP runs record SHA-256 hashes of frozen source inputs in `info/source_hashes.json`.
Full publication copies this metadata into `latest/info/`. Before copying a published
XCI/XCIX, consumers compare the recorded producer JSON run and source hashes with
the current producer files. Changed or missing inputs, or missing hash metadata,
produce warnings while allowing the consumer to continue. Warnings are printed
and saved in the consumer artifact `info/warnings.log`. Regenerating older IP
publications creates the metadata. No automatic regeneration is performed. Implementation
continues to use its parent synthesis snapshot.

Before implementation starts, HDLForge copies the selected synthesis DCP into
`inputs/synthesis_checkpoint/` and copies its frozen IP, XDC, Tcl and supporting
inputs into the implementation input tree. Runtime paths use these local copies,
not current sources or live latest publications. `info/input_manifest.json` maps
parent paths to copies; `info/input_hashes.json` records their SHA-256 hashes.
Later attempts reuse the shared input snapshot without clearing it.

Implementation layout:

```text
artifacts/<synth_timestamp>/impl_runs/<impl>/
  inputs/                     shared frozen DCP, IP, XDC, Tcl and supporting files
  input_config.json           completed snapshot and local input paths
  input_manifest.json
  input_hashes.json
  <implementation_timestamp>/
    info/
    work/
    checkpoints/
    reports/
    bitstream/
    runme.log
```

Each launch creates a new UTC implementation timestamp, retains previous attempts,
and uses the shared input tree. The synthesis timestamp still selects the parent.
Input creation is locked; a completed shared snapshot is reused without recopying.
Saving an implementation also preserves its shared inputs and parent synthesis.

Dated selectors (preferred; older selectors remain compatible):

```bash
hdlforge --tool vivado --build synth_production.new
hdlforge --tool vivado --build synth_production.rerun.<synth_timestamp>
hdlforge --tool vivado --build synth_production.latest.impl_production.new
hdlforge --tool vivado --build synth_production.<synth_timestamp>.impl_production.new
hdlforge --tool vivado --build synth_production.<synth_timestamp>.impl_production.rerun.<impl_timestamp>
```

`new` creates an attempt. An explicit attempt timestamp reruns its frozen inputs,
clearing generated outputs while preserving inputs, snapshot metadata, and child
implementations. `latest` selects successful synthesis. Timestamp fractions are
part of the timestamp, not selector separators. Completion discovers timestamps
and implementation names from JSON and artifact directories. No separate timestamp
flag is needed. Existing shorthand and --synth_timestamp remain compatible.

Run locks retain PID identity and log location. A busy attempt reports its lock
and recovery options. With an explicit attempt selector, `--remove_lock` clears
idle metadata without building; `--stop_run` stops only that attempt; `--force_run`
stops it before rerunning. A held lock is never bypassed or unlinked. The empty
lock file remains to avoid races between processes locking different file inodes.

Completion groups retries under `rerun.`. Use `SYNTH.rerun.latest` for the newest
existing synthesis attempt, even if failed; use `SYNTH.latest.IMPL.rerun.latest`
for the newest implementation attempt under the latest successful synthesis.
`new` remains a separate choice. Explicit dates follow `rerun.` as well.

Builds always launch a detached worker and follow its persistent
`output_root/launch_logs/` log. Ctrl-C detaches the viewer without stopping the
build or auto-implementation chain. Use --build_status and a timestamped --stop_run
to inspect or stop it. TTY detection is not used; Ctrl-C detaches log following even through wrappers or pipes. Each run still has its own runme.log.

Use `--build synth_production.latest.impl_production.new --refresh_impl_inputs`
to snapshot current implementation XDC, Tcl and declared supporting files in the
new attempt's own inputs directory. The synthesis DCP and IPs remain frozen.
Previous shared inputs are untouched; reruns reuse this attempt's refreshed snapshot.
Changes are logged in info/refreshed_inputs.log and refreshed_inputs.json.
The flag is rejected for synthesis and reruns. Synthesis-affecting changes require
new synthesis. Other implementation settings remain from the synthesis snapshot.

Published output lives at `<output_root>/<run>/artifacts/latest/` (nested
implementation run definitions use `<synth>/<impl>/artifacts/latest/`).
The selector `.latest` resolves to a successful timestamp; it does not execute
inside the mutable published copy. Timestamp cleanup excludes the latest directory.

`--build_status` refreshes in place in the controlling terminal, without
scrolling repeated tables. Ctrl-C exits the viewer and leaves builds running.
Without a controlling terminal it prints one status snapshot.
