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
  hdlforge --tool vivado --build_project

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
