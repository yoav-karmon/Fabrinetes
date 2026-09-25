HDLForge

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
