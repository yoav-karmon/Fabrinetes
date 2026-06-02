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

Vivado:
  hdlforge --tool vivado --generate_prj_with_external_tcl
  hdlforge --tool vivado --build_project

LLM_orch:
  hdlforge <shortcut.path>
  hdlforge <shortcut.path> --append '<extra flags>'

Environment:
  hdlforge sources ~/.bashrc
  hdlforge runs update_repo_path
  hdlforge captures PATH, PYTHONPATH, REPO_TOP
  hdlforge accepts native --env-python / --env-path / --env-var handoff

More:
  hdlforge_project_file.md
  how_hdlforge_keeps_paths_clean.md
