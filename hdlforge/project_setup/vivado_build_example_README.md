# HDLForge {{STAGE}} build example

For implementation builds, the shared runtime sets `BITSTREAM.CONFIG.USERID`
before `write_bitstream` from the current launch's UTC Unix timestamp. The value
is logged and saved in `info/bitstream_timestamp.json`. Each new launch or rerun
gets a new value; do not put a fixed timestamp in source XDC or run scripts.

To regenerate only the bitstream from a completed implementation:

```bash
hdlforge --project {{PROJECT_ARG}} --tool vivado --build synth_example.latest.impl_example.bitstream.<impl_timestamp>
```

Use a synthesis timestamp instead of `latest` to select a dated parent. Tab
completion lists completed implementation folders after `.bitstream.`; `latest`
is offered only when the newest dated implementation is complete.
This opens the final routed checkpoint and writes a new bitstream, preserving
the selected implementation's USERID timestamp and original paired LTX files.
It does not rerun implementation or read current RTL, IP or XDC. Results go under
the selected implementation's `bitstream_runs/<new_timestamp>/`, with frozen
inputs, `bitstream/`, `runme.log` and `info/`. Normal background logging, Ctrl-C
detach, `--build_status` and `--build_stop_all` apply. Original outputs remain intact.
New implementations record `info/last_routed_checkpoint.txt`; older examples use
`<top>_postroute_physopt.dcp`, falling back to `<top>_routed.dcp`.

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
newest synthesis timestamp (which must be complete); add `--synth_timestamp TIMESTAMP` to select another.
Repeated `--auto_impl` values are deduplicated and implementations run sequentially.

## Files and outputs

The configured output root is `{{OUTPUT_ROOT}}`, relative to the project JSON.

```text
<output_root>/
  ip_example/run.tcl
  ip_example/README.md
  ip_example/artifacts/<timestamp>/
  synth_example/run.tcl
  synth_example/ip_keep_hierarchy.xdc
  synth_example/README.md
  synth_example/artifacts/<timestamp>/inputs/
  synth_example/artifacts/<timestamp>/impl_runs/impl_example/
  synth_example/impl_example/run.tcl
  synth_example/impl_example/README.md
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
`{{OUTPUT_ROOT}}/ip_example/artifacts/latest/work/ip_sources/0/example.xcix`.
Each input glob must match exactly one file. HDLForge resolves latest to a dated producer before opening the XCIX. Missing inputs fail clearly;
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
edits or newer IP runs. Changing implementation inputs requires a new
synthesis. Older synthesis artifacts without a snapshot cannot use this flow.

## Timestamp selection and resources

`latest` is a logical operation: select the newest timestamp folder by its name.
No `latest/` directory is created, copied, cleared, or used as a fallback.
The selected timestamp is pinned before launching or copying consumer inputs.
Failed or incomplete producer inputs are rejected; use an explicit older date if
needed. Rerun selectors may select failed attempts. IP consumers retain their own
frozen copies and hash metadata, so later producer runs cannot change those inputs.

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
do not untrack files already in Git. Cleanup selects timestamped run folders;
old input snapshot subdirectories have no special protection.

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
hdlforge --project {{PROJECT_ARG}} --tool vivado --build_status_all
```

Help describes every field and parameter/property map, process discovery and
stopping, and the artifact ignore/cleanup flags. Lint checks configuration and
paths offline. These commands are examples; none run during injection.
Both `--build_create syth_imp_example` and `--init_build_example` inject all three
examples and these READMEs. Existing example entries or folders are never overwritten.

Failed timestamped runs retain `info/status` and `info/exit_code`. Continue-all
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
This metadata stays in the dated producer folder. Before copying its
XCI/XCIX, consumers compare the recorded producer JSON run and source hashes with
the current producer files. Changed or missing inputs, or missing hash metadata,
produce warnings while allowing the consumer to continue. Warnings are printed
and saved in the consumer artifact `info/warnings.log`. Regenerating older IP
runs creates the metadata. No automatic regeneration is performed. Implementation
continues to use its parent synthesis snapshot.

Before implementation starts, HDLForge copies the selected synthesis DCP into
`inputs/synthesis_checkpoint/` and copies its frozen IP, XDC, Tcl and supporting
inputs into the implementation input tree. Runtime paths use these local copies,
not current sources or newly generated IP outputs. `info/input_manifest.json` maps
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
implementations. `latest` selects the newest timestamp; using it as an input requires success. Timestamp fractions are
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
for the newest implementation attempt under the newest synthesis timestamp, which must be complete.
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

Outputs exist only in dated run folders. `latest` is resolved by HDLForge to
the newest timestamp at the selected level; no latest folder, symlink, publication
copy, or publication lock is created. Existing historical copies are not consulted
or modified. Input readiness checks apply to the selected date without fallback.
IP paths containing `artifacts/latest/` are logical references: HDLForge replaces
that component with a date before copying inputs into the consumer snapshot.

`--build_status` shows active/unavailable registered builds; `--build_status_all`
also shows completed, failed, stopped, and dead runs, as a table without tail
commands or per-run log messages. Both refresh in place in the controlling terminal, without
scrolling repeated tables. Ctrl-C exits the viewer and leaves builds running.
Without a controlling terminal it prints one status snapshot.
