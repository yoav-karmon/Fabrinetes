HDLForge

## Project selection and working directory

Startup selects the project once in `hdlforge_environment.bash`. It searches
from the launch directory upward for the nearest `.hdlforge.json` or
`.hdlforge.toml`, stopping at a Git checkout boundary. Multiple candidates in
one directory require an explicit selection. `--project FILE` and
`--project=FILE` override discovery; relative filenames resolve against the
original launch directory. Symlinks resolve to the actual project file.

Commands execute from the selected file's containing directory. The launcher
passes its absolute filename to native tools and exports it as
`HDLFORGE_PROJECT_FILE`, with the working directory in `ROOT_FOLDER`.
Environment leaf lookup and JSON shortcuts consume that same selection.
Relative VCD capture paths and externally invoked Verilator source lists keep
their original launch-directory base. Source-file arguments do not select a
different project; use `--project` for an external source's project.

Nested commands retain an explicit project choice when searching that same
directory, including directories with multiple project files. Changing to a
different project selects the nearest project there. Fresh launches ignore an
inherited project filename. A raw `--cmd` with no selected project retains its
launch directory when the repository environment is otherwise available.

## SSH configuration inventory

Run these from the repository root to use its `*.hdlforge.json`, or select
`--json PATH` explicitly. These commands need only Python's standard library;
they do not connect to hosts or execute SSH `Match exec` commands.

```bash
hdlforge --sshconfig_import --json fpga.hdlforge.json --ssh-config ~/.ssh/config --dry-run
hdlforge --sshconfig_import --json fpga.hdlforge.json
hdlforge --sshconfig_verify --json fpga.hdlforge.json
hdlforge --sshconfig_export --json fpga.hdlforge.json --dry-run
hdlforge --sshconfig_merge --json fpga.hdlforge.json --input laptop.json --input lab.json --dry-run
hdlforge --sshconfig_merge --json fpga.hdlforge.json --input lab.json --on-collision incoming
hdlforge --sshconfig_export --help
```

`--sshcofnig_import`, `--sshcofnig_export`, `--sshcofnig_verify`, and
`--sshcofnig_merge` are accepted spelling aliases. Every action supports
`--help` / `-h`, `--dry-run`, and `--force` / `-f`.

The inventory belongs to the **local** hostname and local user:
`settings.env.<local-host>.<local-user>.ssh_config`. Defaults come from the
current machine and login user; select another environment with
`--local-host NAME --local-user NAME`. These select inventory ownership, not
remote login credentials. Each input to merge uses this same explicit scope;
other hosts, users, and repository settings are preserved.

```json
{
  "settings": {
    "env": {
      "fpga-dev-1": {
        "ykarmon": {
          "ssh_config": {
            "ch4dev-03": {
              "HostName": "ch4dev-03",
              "User": "yoav.karmon",
              "Port": 22
            },
            "ch4fpgadev-01": {
              "HostName": "ch4fpgadev-01",
              "User": "yoav.karmon",
              "Port": 22
            }
          }
        }
      }
    }
  }
}
```

There is no version, preamble, host list or multiline configuration blob.
The destination host is the dictionary key; its value is an SSH option
dictionary. Repeated directives such as `IdentityFile` use arrays of values.
Import discards standalone comments and whitespace; export generates consistent
SSH syntax. Values retain SSH quoting, and numeric ports are stored as integers.
Global settings, `Include`, `Match`, wildcard/negated patterns, multi-alias
blocks and repeated Host blocks are rejected before import writes anything:
this scoped host dictionary cannot preserve their precedence. SSH directives
are never executed during import or verification.

Import replaces only the selected environment's inventory. Export replaces the
selected SSH file, so review its diff before applying. Verification compares
host options rather than whitespace or comments and reports host collisions;
it does not certify SSH syntax or reachability.

The connection **Host alias**, compared case-insensitively, is the merge key.
Different aliases sharing one `HostName` remain separate. Duplicate JSON object
keys are rejected. Merge reads the destination's selected inventory first,
followed by each `--input` in order. Identical settings are reported as
`DUPLICATE` and deduplicated; differing settings for the same host are reported
as `COLLISION` with source filenames. Default collision policy is `error`
(no write). Explicit `--on-collision keep` keeps the first entry; `incoming`
uses the last. `--force` skips approval but never chooses a collision policy.

Writes show a unified diff and prompt `Apply changes? [y/N]`; EOF or declining
leaves files untouched. `--force` retains the diff and backup but skips the
prompt. Every changed existing destination gets a sibling backup named
`<filename>.<YYYYMMDDTHHMMSS.microsecondsZ>.bak`, with private permissions.
New files have no previous content to back up and are created with mode 0600.
Existing destination permissions are retained. Writes use atomic replacement;
symlink destinations are refused (select the resolved path explicitly).
Changes detected during approval abort the write.

Dry-run, verification, cancellation, and unchanged files create no backups or
other writes. Exit codes: 0 for success/clean verification, 1 for cancellation
or verification differences/collisions, 2 for invalid input/unresolved merge
collisions. Inventories and diffs can contain sensitive SSH options; review
their contents before committing or sharing.

Bitstream-only regeneration uses the normal Vivado build selector:

```bash
hdlforge --tool vivado --build synth_production.latest.impl_production.bitstream.<impl_timestamp>
```

Select a dated synthesis in place of `latest` when needed. Completion lists
existing completed implementation attempts after `.bitstream.`; a literal
newest timestamped implementation must be complete to select `latest`.
HDLForge snapshots the final routed checkpoint and original paired LTX files,
then writes a new bitstream in the implementation's `bitstream_runs/<timestamp>/`.
The original implementation's USERID timestamp is retained. No synthesis,
placement, routing, physical optimization or current-source/XDC reload occurs.
Original implementation outputs remain intact. Regeneration uses the normal
background launcher, `runme.log`, `--build_status`, Ctrl-C detach and
`--build_stop_all`. No extra JSON setting or project Tcl helper is required.
New runs record the final checkpoint in `info/last_routed_checkpoint.txt`.
Legacy examples use `<top>_postroute_physopt.dcp` or `<top>_routed.dcp`.

Non-project implementation bitstream identity:
  The shared runtime sets BITSTREAM.CONFIG.USERID immediately before write_bitstream
  from launch_epoch (UTC Unix seconds), fixed for that implementation launch.
  New launches and reruns get new values. The run log and info/bitstream_timestamp.json
  record the value. Source XDC files are not rewritten; USR_ACCESS/version remains
  design-controlled. Existing bitstreams and saved runtime snapshots are unchanged.

Project file:
  <project>.hdlforge.json

Project root:
  folder containing the project file

Auto-detect project:
  cd <project root>
  hdlforge --tool <tool> <args>

Explicit project:
  hdlforge --project <project>.hdlforge.json --tool <tool> <args>

Tools:
  Verilator
  vivado
  tsharkWrapper
  hw_server
  toolbox

Verilator:
  hdlforge --tool Verilator --step build --SimTargetName <target>
  hdlforge --tool Verilator --step sim --SimTargetName <target>
  hdlforge --tool Verilator --step lint --SimTargetName <target>
  hdlforge --tool Verilator --file <source.sv> --flags -Wno-fatal --flags -Werror-UNUSEDSIGNAL
  hdlforge --tool Verilator --lint-file <source.sv> --flags -Wno-fatal
  --file lints selected project files with package sources and source-dir lookup
  --lint-file lints only the selected file path without dependency sources
  --file and --lint-file imply --step lint when no step is supplied
  targetless file lint scopes -Werror-<CODE> failures to selected files

Vivado non-project:
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example --auto_impl impl_example
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.latest.impl_example.new
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.rerun.<run-id>
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.<synth-id>.impl_example.rerun.<impl-id>
    Definitions live in vivado.non_project.runs; implementation definitions are
    nested in impl_runs. Project-definition paths are relative to the project JSON.
    The script field explicitly selects maintained Tcl code. HDLForge copies it,
    generates snapshot/scripts/run.json, and launches the copied run.tcl directly
    with -tclargs <run.json>. The current working directory is the run's work/.
    New synthesis snapshots also freeze each implementation's declared inputs and
    store each definition in run.json implementation_configs. Each launched
    implementation adds an entry to that same JSON under attempts, keyed by run ID,
    with identity and checkpoint hash. Child scripts receive the shared JSON path
    and run ID. Updates use file locking and atomic replacement.
    The maintained script's bootstrap loads the frozen runtime and Tcllib JSON parser.

    Layout: <output_root>/<synth>/_<label>/{snapshot,logs,artifacts,work}.
    snapshot contains source/ and scripts/{run.tcl,run.json,_hdlforge/}.
    Implementation: <synth-run>/impl_runs/<implementation-name>/_<label>/ with exactly the same layout.
    Maintained implementation scripts live beside the synthesis script, conventionally
    impl_run_NAME.tcl. Only declared files and literal RTL includes are snapshotted;
    declare dynamic dependencies in input_files. Implementations inherit the parent's
    frozen IP list only when ips is omitted; they do not copy synthesis RTL or DCP.
    Their JSON references the parent DCP relatively and stores SHA-256/parent run ID.
    A missing or changed checkpoint refuses execution or rerun.

    Generated JSON paths are relative to its own directory, not the working directory.
    Run labels are opaque and start with _. Identity and time come from run_id,
    created_at, timestamp and launch_epoch in JSON. Renaming generated run folders
    preserves execution, discovery, latest selection and reruns. Use stable IDs
    from completion when labels contain punctuation. New implementations snapshot
    the parent synthesis's frozen declared Tcl/XDC/support files; reruns preserve the original JSON,
    scripts, inputs and bitstream USERID timestamp. --refresh_impl_inputs remains
    accepted for a new implementation but is redundant with that default behavior.
    Latest selects by JSON creation time and requires success; no fallback to an
    older success. Auto-implementation pins the successful parent's stable ID.
    Commands, directives and stages belong to Tcl. Parameter/property maps remain
    literal Vivado values. initialize_design loads JSON inputs into an in-memory project.

  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.latest.impl_example.bitstream.<impl-id>
    Open the selected routed checkpoint without synthesis/place/route. Save a
    hash-checked reference and paired probes in a new bitstream_runs/_<label> run.
    Preserve the implementation's original bitstream USERID timestamp.
  hdlforge --project example.hdlforge.json --tool vivado --build ip_example
    Regenerate private work/ip_sources copies; the input snapshot stays immutable.
  hdlforge --project example.hdlforge.json --tool vivado --build_status
  hdlforge --project example.hdlforge.json --tool vivado --build_status_all
  hdlforge --project example.hdlforge.json --tool vivado --build_stop_all
  hdlforge --project example.hdlforge.json --tool vivado --build_find_all_user_runs
    _run_registry.json records launches; run IDs relocate renamed folders.
    logs/ holds status, exit code, stage events, runme.log, vivado.log and journal.
    Ctrl-C detaches log following; it does not stop the background worker.
    Process identity and run locks protect active runs.
  hdlforge --project example.hdlforge.json --tool vivado --build_clean_ignore_artifacts --dry-run
    Cleanup without a selector checks whole synthesis trees, including every nested
    implementation. Any tracked or non-ignored descendant prevents deletion of
    the entire tree; unreadable paths, nested repositories and held locks also block.
    Remove --dry-run to delete eligible trees. --build RUN --clean_ignore_artifacts
    narrows selection. Add _* once to the repository root .gitignore; HDLForge does
    not generate per-run ignore files. Save explicitly with git add -f <run-folder>.
    --save_this_run is retired. Old-format folders remain intact and are not selected.
  hdlforge --project example.hdlforge.json --tool vivado --build_create syth_imp_example
  hdlforge --project example.hdlforge.json --tool vivado --init_build all
  hdlforge --project example.hdlforge.json --tool vivado --build_lint
    Create examples, fill missing defaults without overriding values, or validate
    definitions and script/input paths without launching Vivado. Scripts belong
    directly in the synthesis/IP definition directory. Existing examples are not
    overwritten. enabled_on_all controls project-defined batch selection.
    See hdlforge/project_setup/vivado_build_example_README.md for the full example.

Vivado project mode:
  hdlforge --tool vivado --get_xpr_path
    Print only the absolute configured XPR path on stdout, without starting Vivado.
    Uses ProjectFile, including --project selection and JSON/TOML discovery.
    The XPR need not exist yet. Configuration diagnostics go to stderr.
  hdlforge --tool vivado --project_console help
    Show persistent-console actions and arguments; requires no project shortcut.
  hdlforge --tool vivado --project_console print-json
    Print the reusable project_console group as JSON.
  hdlforge --tool vivado --project_console install-json --json-file example.hdlforge.json --key LLM_orch.vivado --overwrite
    Install under this dotted parent key. Replace project_console and its
    description entirely; preserve siblings. Create missing parent objects.
    Installation requires an existing JSON object, not an XPR or Vivado process.
    Generated commands use native HDLForge and retain the selected project via
    HDLFORGE_PROJECT_FILE. An arbitrary .json filename requires --project.
    Running project actions requires the usual vivado configuration in that JSON.
    The implementation lives in hdlforge/project_setup/vivado_console, with no
    dependency on an FPGA repository's tools or .codex directories.

Persistent Vivado project console:
  hdlforge --tool vivado --project_console help
  hdlforge --tool vivado --project_console install-json --json-file project.json --key LLM_orch.vivado
  hdlforge vivado.project_console.update-json
    One namespace owns project lifecycle, builds, run queries and run control.
    There is no separate batch launcher, build manager or saved run-status database.
    Existing project shortcuts need update-json; unrelated settings are preserved.

  hdlforge vivado.project_console.management.open_console
  hdlforge vivado.project_console.management.inspect_console
  hdlforge vivado.project_console.runs.list_runs
  hdlforge vivado.project_console.runs.enumerate_groups
  hdlforge vivado.project_console.runs.inspect_run --append '--run impl_1'
    Shows run metadata followed by stage settings in execution order: enable flags,
    directives, arguments, Tcl pre/post hooks and report configurations. Values come
    from the live run, including stage overrides of the named strategy. Only
    properties exposed by Vivado are shown; (empty) means an exposed empty value.
    --verbose adds all remaining run properties. --json retains the flat property
    records, including every exposed STEPS.* setting. Group configuration uses the
    same stage display separately for each run.
  hdlforge vivado.project_console.runs.status_run --append '--run impl_1'
  hdlforge vivado.project_console.runs.group_status --append '--group synth_1'
  hdlforge vivado.project_console.build.build_group --append '--group synth_1 --jobs 2'
  hdlforge vivado.project_console.build.launch_run --append '--run synth_1'
  hdlforge vivado.project_console.build.write_bitstream --append '--run impl_1'
    Launch uses Vivado launch_runs and returns without waiting for completion.
    Vivado manages its own workers and synthesis dependencies. Omitting a target
    lists live choices. --no-bitstream stops at implementation, --reset resets first.
    reset_run/group and stop_run/group are explicit separate commands.

  hdlforge vivado.project_console.runs.reuse_status --append '--run impl_1'
  hdlforge vivado.project_console.settings.clear_refresh --append '--run impl_1'
    clear_refresh clears NEEDS_REFRESH only; it does not validate stale results.

  hdlforge vivado.project_console.settings.edit_run_property --append '--run impl_1 --property STRATEGY --value Performance_Explore'
    Without --property, list the selected run's properties. Edits are read back immediately; active runs are protected.
  hdlforge vivado.project_console.settings.enable_incremental --append '--run synth_1'
  hdlforge vivado.project_console.settings.disable_incremental --append '--run impl_1'
    Both clear a manually selected incremental checkpoint. On enables automatic incremental reuse; off disables it.
  hdlforge vivado.project_console.project.close_project --append '--force'
    Close the project but keep the console alive.
  hdlforge vivado.project_console.project.regenerate_project --append '--force'
    Close, preserve the old directory, regenerate from configured Tcl, and reopen. Without --force, prompt to export before closing. Active runs are protected.
    enable_run/group and disable_run/group persist availability in DESCRIPTION.

  hdlforge vivado.project_console.project.export_open_project_to_tcl
  hdlforge vivado.project_console.project.generate_project_from_tcl
    Generation requires the open project to close first. Interactive mode offers
    export to <project>.before-close.tcl before closing. Noninteractive mode refuses
    unless --force is supplied. Force skips the export/prompt, not active-run checks.
    Old generated project directories are preserved, never implicitly deleted.

  hdlforge vivado.project_console.aux.execute_tcl --append '--cmd "get_projects"'
  hdlforge vivado.project_console.aux.source_tcl --append '--file script.tcl'
  hdlforge vivado.project_console.management.attach_console
    send/source execute on the console as it stands, even with no project open.
    Interactive attaches to tmux; Ctrl-b d detaches without stopping the console.
    Noninteractive clients exit after responses; the console remains alive.
    stop and restart ask before closing an open project; --force skips the prompt.

Output:
  Every Tcl request has VIVADO OUTPUT BEGIN/END boundaries and OK/ERROR status.
  The full native output includes stdout, stderr, warnings and errors. The Tcl
  result and error stack are retained. A formatted live summary follows the block.
  --raw suppresses summary tables. --json emits response envelopes containing the
  complete transcript, result, return code and structured records. --verbose on
  info commands requests all properties. Subsequent build-worker output stays in
  the run log; it is not misrepresented as part of the launch response.

Implementation:
  hdlforge/project_setup/vivado_console/run_commands.tcl owns run operations.
  console_transport.py carries serialized requests to the persistent console.
  project_console.py selects procedures and prints responses, without inferring status.
  Completion is static; only explicit commands contact Vivado.

LLM_orch:
  hdlforge <shortcut.path>
  hdlforge <shortcut.path> --append '<extra flags>'
  hdlforge --cmd '<shell command>'
  hdlforge --no-print --cmd '<shell command>'
  hdlforge --cmd '<shell command>' --append '<extra flags>'
  hdlforge --env-python '["sources/tests"]' --cmd 'python3 -m package.tool'
  hdlforge --env-path '["tools"]' --cmd 'my_tool' --append '<extra flags>'

Environment:
  hdlforge resolves its installation from its executable, including symlinks
  hdlforge loads its bundled environment helper without sourcing ~/.bashrc
  hdlforge loads /etc/profile.d/init_env.sh when present and configured VIVADO_SETTINGS
  hdlforge restores its own executable path before preparing repository paths
  hdlforge captures PATH, PYTHONPATH, REPO_TOP
  hdlforge accepts native --env-python / --env-path / --env-var handoff
  hdlforge --cmd uses the same env handoff and project-root execution path
  hdlforge --cmd prints command-mode/executing lines by default; use --no-print for quiet stdout
  --no-print propagates to nested commands and suppresses environment summaries;
  command output and errors remain visible
  raw hdlforge --cmd can run without a project JSON; project-leaf env values still need one

More:
  hdlforge_project_file.md
  how_hdlforge_keeps_paths_clean.md

Bash completion descriptions:
  Invoking a command group, such as hdlforge vivado --no-print, lists only
  its immediate children. Invoke a listed subgroup to see the next level;
  group listing does not execute any child commands. Keys beginning with #
  remain hidden.
  Running bare hdlforge prints usage followed by the same top-level choices
  and descriptions as Double-Tab, using the project in the current directory.
  This also works through Fabrinetes.sh --exec and requires no interactive
  terminal. With no project, the table contains global options only.
  Double-Tab displays command candidates in a bordered Command/Description
  table, using descriptions from the selected project's JSON. Normal Tab and menu completion
  insert only the command token. File-path completion keeps native Bash behavior.
  Long command names and descriptions wrap within their table cells. Existing shells pick up runtime changes on their next completion.
  Vivado build-profile menus describe stage actions. The shared command prefix appears once
  above the table, while completion still inserts the full command token.
  Invoking a group (with or without a trailing dot) uses the same table.
  Synthesis shortcuts run synthesis only; implementation shortcuts run all
  enabled implementations and require current synthesis. Combined full-build
  shortcuts cover both stages. Menus do not inspect or list saved XPR runs.
  Explicit JSON descriptions take precedence over standard profile help text.

  Put descriptions beside the command or group they describe. A key beginning
  with # is metadata: it is hidden from command listings and completion and
  cannot be executed, including through an explicit --eval_json path.

```json
{
  "LLM_orch": {
    "#build": "Build commands",
    "build": {
      "#status": "Show the current build status",
      "status": "python3 tools/status.py"
    }
  }
}
```

  #status describes its sibling status; #build describes its sibling build.
  Other # keys can hold notes and are also excluded from command traversal.
  Shorthand and --eval_json completion both use these descriptions. Inline
  descriptions take priority over the older top-level LLM_orch_help map,
  which remains supported for compatibility. Completion only reads JSON;
  it never executes help text. The backend --describe option adds separate
  __DESC__ records; its default output remains plain completion candidates.

Completion table formatting is bundled in hdlforge/project_setup/table_formatter.py.
It uses only the Python standard library and does not load another repository
or a skills directory. The backend --display-table option emits __TABLE__
display records separately from completion tokens; --columns sets table width.

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

Completion groups retries under `rerun.`. `SYNTH.rerun.latest` resolves to
and reruns the newest dated synthesis attempt, even if failed. Likewise,
`SYNTH.latest.IMPL.rerun.latest` selects the newest implementation attempt beneath
the newest synthesis. No physical latest folder is used. The resolved attempt
keeps its own lock and frozen inputs. `new` remains a separate choice.
Completion offers `latest` and `rerun.` only when timestamped folders exist at that
level. Bitstream completion requires the selected implementation to be complete.

`--auto_impl IMPL` works with `SYNTH.new`, `SYNTH.rerun.TIMESTAMP`, and
`SYNTH.rerun.latest`. After synthesis succeeds it creates new implementation
attempts through their configured bitstream stage. Dated reruns retain the exact
parent timestamp; logical latest reruns also pin that date throughout
the chain. A changed parent checkpoint is copied into private implementation
inputs instead of reusing a stale shared checkpoint. Existing attempts keep
their frozen inputs. These paths have not been build-tested during this change.

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

`--build_status` and `--build_status_all` refresh in place in the controlling terminal, without
scrolling repeated tables. Ctrl-C exits the viewer and leaves builds running.
Without a controlling terminal it prints one status snapshot.
`--build_status` shows active/unavailable builds only. `--build_status_all` includes
all registered launches, with active builds first. Completed runs
retain their final status and elapsed duration; runs with an unknown exit time
show `-` for elapsed time. Log idle is shown only for active runs.
The `Run` column identifies the selected synthesis and implementation attempts:
`<synth>.<synth timestamp or latest>[.<impl>.<impl timestamp or latest>]`.
For `.new`, it shows the allocated timestamp; a logical `.latest` selection
shows its resolved timestamp. In `--build_status`, the same label identifies each tail command
below the table. `--build_status_all` displays the table without tail commands
or per-run log messages.
There is no separate, ambiguous timestamp column. Legacy implementation folders
without an attempt timestamp show `-` for that part.
The table shows only the actual Vivado engine PID, omitting launcher/wrapper PIDs,
CPU time, and the statistics source. `Elapsed` is wall time since the recorded
launch (stopping at completion), independent of log command timers. `RAM used(MB)`
is resident memory (RSS); `Peak RAM(MB)` is the peak memory measurement.
`Vivado state` samples all engine threads: `Running` if any is runnable,
`I/O wait` if a thread is in uninterruptible wait and none is runnable, or
`Waiting` when all sampled threads are waiting. A waiting main thread alone
does not imply idle workers; even `Waiting` is an instantaneous observation,
not evidence of a stalled build. `Log idle(s)` measures time without log updates.

Synthesis reruns are refused once the run has implementation history under
impl_runs/<implementation-name>/. Empty implementation folders do not block
reruns. Create a new synthesis run once implementation history exists. Implementation reruns remain available
and validate the parent checkpoint hash before changing outputs.
