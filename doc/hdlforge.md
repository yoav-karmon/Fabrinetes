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
  hdlforge --tool vivado --project_console print-hdlforge-json-commends
    Print the reusable project_console group as JSON.
  hdlforge --tool vivado --project_console print-hdlforge-json-commends --json-file example.hdlforge.json --key LLM_orch.vivado --overwrite
    Install under this dotted parent key. Replace project_console and its
    description entirely; preserve siblings. Create missing parent objects.
    Installation requires an existing JSON object, not an XPR or Vivado process.
    Generated commands use native HDLForge and retain the selected project via
    HDLFORGE_PROJECT_FILE. An arbitrary .json filename requires --project.
    Running project actions requires the usual vivado configuration in that JSON.
    The implementation lives in hdlforge/project_setup/vivado_console, with no
    dependency on an FPGA repository's tools or .codex directories.

Native project management:
  hdlforge --tool vivado --project_mng help
  hdlforge --tool vivado --project_mng restart
  hdlforge --tool vivado --project_mng live-runs
  hdlforge --tool vivado --project_mng refresh-runs
  hdlforge --tool vivado --project_mng saved-runs --summary
  hdlforge --tool vivado --project_mng saved-runs --run synth_1 --property STATUS
  --project_console remains an alias of --project_mng.

  hdlforge --tool vivado --project_mng install-json --json-file project.json --key LLM_orch.vivado
    Insert a self-contained project_console group under the given parent key.
    Existing groups produce a warning and remain unchanged unless --overwrite
    is supplied. Overwrite replaces the whole group, removing obsolete keys.
  hdlforge vivado.project_console.management.update-json
    Detect the selected JSON and invoking key through HDLForge's invocation
    context, then replace that project_console group by default. Siblings stay intact.
    Direct native update-json can locate a single installed group; with multiple
    groups, invoke the desired group's shortcut. No other JSON commands are used.

Explicit live discovery and background builds:
  hdlforge vivado.project_console.runs.get_groups
  hdlforge vivado.project_console.runs.get_runs
    Query the open console only when these commands execute. get_groups shows
    synthesis groups and their implementation children; get_runs shows separate
    parent/child status tables with availability. Append '--json' for metadata.
    Saved-run commands are absent from installed groups.
  hdlforge vivado.project_console.build.get_build_options
    Query the open project and print one table row per synthesis group, with
    aligned Command, Arguments, and Explanation columns. Each command appears once
    per group with argument variations below it; combine it with an Arguments cell.
    Commands omit --project and use correctly quoted --append arguments; run them
    from the selected project directory. Output includes
    continue/full build, reset-and-full-build, reset, disable, and enable as
    applicable. Disabled entries offer enable/reset; build stays blocked.
    Append '--json' for structured options. Tab-Tab completes static names only;
    it never queries Vivado. Build actions live under build; run discovery and availability live under runs.
  hdlforge vivado.project_console.build.build_group --append '--group synth_1 --reset'
  hdlforge vivado.project_console.build.build_run --append '--run synth_1'
  hdlforge vivado.project_console.build.build_run --append '--run impl_1'
    Choose --group SYNTH for synthesis and its enabled implementation children,
    or --run NAME for exactly one synthesis/implementation run. build_run and
    build_group continue without resetting; add --reset for reset-and-full-build.
    reset_run/reset_group reset without launch. A single implementation
    needs current, completed synthesis. Names are validated against live Vivado.
    Full implementations run through write_bitstream; IP implementations stop at
    route_design. Continue reuses completed results and resumes partial runs.
    Stale/failed runs require reset_and_build. Failure stops the remaining sequence.
    Builds return a worker PID, project log path, and tail command immediately.
    Resetting synthesis invalidates ALL its children, including disabled runs.
    Resetting one implementation leaves synthesis and sibling runs intact.
  hdlforge vivado.project_console.runs.disable_group --append '--group synth_1'
  hdlforge vivado.project_console.runs.enable_run --append '--run impl_1'
    Disabled runs remain visible in listings. Disabling synthesis blocks the entire
    group, including direct child continue/build commands. Enabling the group
    preserves individual child exclusions. Disable does not stop an active run;
    the worker rechecks availability before every subsequent launch.
    Vivado has no run-wide enabled property. HDLForge preserves description text
    and stores [HDLForge:enabled] or [HDLForge:disabled] marker lines in the native
    run DESCRIPTION property. State survives XPR restart and HDLForge's project
    Tcl export/recreation; raw Vivado write_project_tcl omits run descriptions.
    This controls HDLForge launches; launching directly in Vivado bypasses it.
    IDR owners/children remain excluded. Existing HDLFORGE_DISABLED_IMPL_RUNS
    exclusions are honored until an explicit native enable overrides them.
    --jobs defaults to 1. --run-timeout defaults to 86400 seconds per run; timeout
    does not stop an already-running Vivado process.
    Native equivalent: hdlforge --tool vivado --project_mng build_group --group synth_1
    Reset only: hdlforge vivado.project_console.build.reset_run --append '--run impl_1'
  hdlforge --tool vivado --project_mng build-status
  hdlforge --tool vivado --project_mng build-status --follow
    Inspect the worker state or follow its combined progress and runme.log output.
    Logs and state live under <build_dir>/project_console/<project_name>/. The Vivado console
    also writes vivado.log and vivado.jou there and survives caller-shell exit.

Native autocomplete descriptions:
  native_command_help.json supplies #name descriptions for HDLForge's own flags,
  tool choices, and project-management actions. Double-Tab displays descriptions;
  ordinary completion inserts plain tokens. Run discovery requires explicit get_groups/get_runs.

Native Vivado build commands:
  hdlforge --tool vivado --generate_prj_with_external_tcl
  hdlforge --tool vivado --syn synth_1
  hdlforge --tool vivado --syn synth_1 --more_options '["-generic DEBUG=1"]'
  hdlforge --tool vivado --impl synth_1
  hdlforge --tool vivado --impl_and_bitstream synth_1
  hdlforge --tool vivado --bit synth_1
  hdlforge --tool vivado --continue synth_1
  hdlforge --tool vivado --reset_synth synth_1
  hdlforge --tool vivado --reset_run synth_1  # compatibility alias for --reset_synth
  hdlforge --tool vivado --reset_impl synth_1
  hdlforge --tool vivado --reset_bitstream synth_1
  --more_options accepts a JSON array of raw Vivado MORE OPTIONS entries
  repeat --more_options to append additional arrays in command-line order

Interactive Vivado project helpers:
  source <Fabrinetes>/hdlforge/project_setup/project_management_helpers.tcl
  hdlforge::project::help
  hdlforge::project::print_runs
  hdlforge::project::reset_synth {synth_1}
  hdlforge::project::reset_impl {synth_1}
  hdlforge::project::reset_bitstream {synth_1}

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
