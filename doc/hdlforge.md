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
  hdlforge sources ~/.bashrc
  hdlforge runs update_repo_path
  hdlforge captures PATH, PYTHONPATH, REPO_TOP
  hdlforge accepts native --env-python / --env-path / --env-var handoff
  hdlforge --cmd uses the same env handoff and project-root execution path
  hdlforge --cmd prints command-mode/executing lines by default; use --no-print for quiet stdout
  raw hdlforge --cmd can run without a project JSON; project-leaf env values still need one

More:
  hdlforge_project_file.md
  how_hdlforge_keeps_paths_clean.md

Bash completion descriptions:
  Double-Tab displays command candidates one per row, with a description when
  provided by the selected project's JSON. Normal Tab and menu completion
  insert only the command token. File-path completion keeps native Bash behavior.
  Long labels and descriptions are shortened to fit the terminal; group help provides
  the full text. Existing shells pick up runtime changes on their next completion.

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
