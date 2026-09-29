HDLForge

Bitstream-only regeneration uses the normal Vivado build selector:

```bash
hdlforge --tool vivado --build synth_production.latest.impl_production.bitstream.<impl_timestamp>
```

Select a dated synthesis in place of `latest` when needed. Completion lists
existing completed implementation attempts after `.bitstream.`; a literal
`latest` implementation folder must exist and be complete to select it.
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

Vivado:
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.impl_example
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.impl_example --synth_timestamp 2026-09-28T120000Z
    Native non-project builds read vivado.non_project.runs from the selected JSON.
    Implementation definitions live under the synthesis run's impl_runs object.
    All paths are relative to the JSON directory, except IP file_properties member
    names, which are relative to the imported IP root. Stages share one process.
    Without --synth_timestamp, implementation uses the latest completed synthesis
    with its checkpoint present. Explicit timestamps must also be complete.
    Output: <output_root>/<synth>/artifacts/<UTC timestamp>/impl_runs/<impl>.
    Implementation attempts create new timestamped output folders; new synthesis/IP folders must be unique. Logs, checkpoints, reports and bitstreams
    are retained as regular files. Declared RTL, IP, XDC, Tcl, supporting input_files
    and literal RTL includes are copied into artifacts/TIMESTAMP/inputs/ before launch.
    info/input_manifest.json records the copies. Synthesis freezes implementation
    configurations and inputs too; implementations reuse those snapshots and the
    parent checkpoint. Older synthesis runs without snapshots require regeneration.
    Declare dynamic script dependencies and memory files explicitly in input_files.
    The configured script owns native Vivado commands, directives, checkpoints and
    reports, e.g. route_design -directive AggressiveExplore. It calls
    ::hdlforge::initialize_design to create the project and load the JSON file lists.
    Common input-loading defaults live in vivado_build_runtime.tcl. JSON contains inputs and run identity;
    it has no JSON stage sequence or hook configuration. Edit run.tcl to change the sequence
    or directives. Passive Tcl execution traces record status and timing without
    wrapping or changing the native commands. Artifact traces copy completed outputs.
    Completion offers run names, then --synth_timestamp only for an implementation,
    then timestamp directories found on disk (including incomplete folders).
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example --auto_impl impl_example --auto_impl impl_other
    Repeated --auto_impl values are deduplicated in order. Names are validated before
    synthesis starts. After synthesis succeeds, implementations run sequentially,
    each pinned to that synthesis's exact timestamp, never an implicit latest run.
    A failed/stopped run stops the chain. Each implementation runs its configured
    Tcl stages through write_bitstream when included. The Python launcher monitors
    the process and schedules continuation; no per-project run.sh is needed.
    New timestamps include six fractional digits to distinguish same-second launches;
    old second-resolution timestamps remain selectable.
  hdlforge --project example.hdlforge.json --tool vivado --build_status
  hdlforge --project example.hdlforge.json --tool vivado --build_stop_all
  hdlforge --project example.hdlforge.json --tool vivado --build_find_all_user_runs
    Launch records are stored in <output_root>/run_registry.json using a lock and
    atomic replacement. Rows include project, selector, synthesis timestamp,
    launcher/Vivado PID identities, process state, run status, exit code, timestamps,
    output folder, runme.log/vivado.log locations and parent/continuation links.
    --build_status shows active/unavailable registered builds.
    --build_status_all also includes completed, failed, stopped, and dead runs.
    Stage status comes from each run's info/status. Dead history stays in the registry.
    --stopall cancels queued continuation and sends TERM to registered local-user
    launchers and Vivado process groups, escalating after ten seconds. PID start time,
    boot identity and PID namespace prevent acting on reused or foreign PIDs.
    --find_all_user_runs scans the visible Linux /proc tree for current-user Vivado
    processes, including those absent from this output root's registry. It reports
    PID/state, command, working directory and log argument when available. Stop-all
    also reports remaining processes; it does not kill unregistered processes.
    All these options and --auto_impl implementation values support completion.
  hdlforge --project example.hdlforge.json --tool vivado --build ip_example
    stage: ip regenerates a private IP copy using the configured run.tcl.
    The supplied example uses generate_target, synth_ip and convert_ips; generated
    output products and XCIX remain under work/ip_sources/. No persistent XPR is needed.
    Parameters and project/fileset properties are JSON maps. Set general.maxThreads
    in parameters per run. enabled_on_all defaults true for batch selection; false
    does not prevent explicitly selecting the run. Batch shortcuts are project-defined.
    publish_latest defaults false. When true, startup clears and recreates the run's
    latest/ folder. Completion copies the entire artifact tree on success or failure;
    cancelled runs leave it empty. Publication is locked and newer launches take
    precedence. Copies are regular files, not links. Consumers snapshot only successful
    publications (complete status and zero exit code). A failed latest retains logs
    for diagnosis but cannot supply a consumer build.
  hdlforge --project example.hdlforge.json --tool vivado --build_create syth_imp_example
  hdlforge --project example.hdlforge.json --tool vivado --init_build_example
    Inject synth_example, nested impl_example and ip_example JSON entries, their
    run.tcl scripts, README files, and synthesis/IP root .gitignore files.
    Existing example entries or folders are rejected; other settings are preserved.
    Replace placeholder inputs before building. No Vivado process starts.
    The generated ip_keep_hierarchy.xdc contains a commented KEEP_HIERARCHY SOFT
    example. Injection warns to customize its cell query before enabling it.
    create_msg_db/close_msg_db are optional, commented examples for structured GUI
    messages; normal text logging works without them. Custom actions belong in Tcl.
  hdlforge --project example.hdlforge.json --tool vivado --init_build all
  hdlforge --project example.hdlforge.json --tool vivado --init_build synth_example.impl_example
    Fill missing optional settings in existing run definitions, preserving existing
    values. Also accepts vivado.non_project.runs.<run> JSON paths. Required identity
    and input paths must already be supplied; initialization does not launch builds.
  hdlforge --project example.hdlforge.json --tool vivado --build synth_example.impl_example --save_this_run
  hdlforge --project example.hdlforge.json --tool vivado --build_clean_ignore_artifacts
    Management replaces building. A selected run covers all matching timestamps;
    --synth_timestamp narrows selection. Cleanup without a selector covers all runs.
    One .gitignore at each synthesis/IP run root controls all timestamps and nested
    implementations. Artifact files are ignored by default; directories remain
    traversable for exceptions. --save_this_run adds a saved-path exception;
    so saving synthesis does not automatically save its implementations.
    /latest/ and /*/latest/ are ignored by default. Live publication folders are
    outside cleanup's timestamp selection. A snapshot directory named latest inside
    an artifact tree has no special protection.
    Cleanup asks Git to evaluate actual file ignore rules with check-ignore --no-index.
    A folder containing any nonignored file is skipped. Empty folders are eligible.
    No PID, run-status or tracked-file protection is applied. These commands do not
    stage, commit, or untrack files. User-authored ignore exceptions also apply.
  hdlforge --project example.hdlforge.json --tool vivado --build_lint
    Check all run definitions, file paths and scoped IP files/archive members.
    Require existing output_root and named script folders: <output_root>/<synth>/
    and <output_root>/<synth>/<impl>/. Each run's script must be directly in its
    folder. Resolved paths
    are checked, so '..' or symlink escapes do not bypass the layout rules.
    Prints defects together and exits nonzero on failure; never launches Vivado
    or creates build artifacts. This is structural lint, not HDL/timing analysis.
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

Completion groups retries under `rerun.`. `SYNTH.rerun.latest` reruns the actual
`artifacts/latest` snapshot in place, even if failed; it never scans for a newer
dated folder. Frozen paths are rebased to that copy. The publication is locked
across the rerun and automatic implementations and is not cleared or copied onto
itself. `SYNTH.latest.IMPL.rerun.latest` requires an actual `latest` attempt folder
under that implementation, not just dated attempts.
`new` remains a separate choice. Explicit dates follow `rerun.` as well.
Completion discovers dates from existing artifact directories. It offers `.latest.`
only when `artifacts/latest/` exists. It offers `rerun.` when a `latest` folder
or dated attempts exist at that level; `rerun.latest` requires the `latest` folder.
An empty implementation container
does not offer reruns. Folder discovery does not certify a successful build;
launch-time validation still checks the selected inputs.

`--auto_impl IMPL` works with `SYNTH.new`, `SYNTH.rerun.TIMESTAMP`, and
`SYNTH.rerun.latest`. After synthesis succeeds it creates new implementation
attempts through their configured bitstream stage. Dated reruns retain the exact
parent timestamp; latest reruns use the locked physical publication throughout
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

Published output lives at `<output_root>/<run>/artifacts/latest/` (nested
implementation run definitions use `<synth>/<impl>/artifacts/latest/`).
The selector `.latest` resolves to a successful timestamp; it does not execute
inside the mutable published copy. Timestamp cleanup excludes the latest directory.

`--build_status` and `--build_status_all` refresh in place in the controlling terminal, without
scrolling repeated tables. Ctrl-C exits the viewer and leaves builds running.
Without a controlling terminal it prints one status snapshot.
`--build_status` shows active/unavailable builds only. `--build_status_all` includes
all registered launches, with active builds first. Completed runs
retain their final status and elapsed duration; runs with an unknown exit time
show `-` for elapsed time. Log idle is shown only for active runs.
The `Run` column identifies the selected synthesis and implementation attempts:
`<synth>.<synth timestamp or latest>[.<impl>.<impl timestamp or latest>]`.
For `.new`, it shows the allocated timestamp; a literal `.latest` selection
stays `latest`. In `--build_status`, the same label identifies each tail command
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
