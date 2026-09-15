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
