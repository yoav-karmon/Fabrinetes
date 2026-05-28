Bug prevention guide

Path bugs:
  do not hardcode project paths in the image.
  put repo paths in <REPO_TOP>/init_repo_env.sh.
  use add_to_path.
  use add_to_pythonpath.
  run update_repo_path after changing repos.

Container bugs:
  build image explicitly.
  run container explicitly.
  do not mix build and run scripts.
  do not push images as part of build.

Doc bugs:
  keep docs flat under doc/.
  do not add container-doc/ or hdlforge-doc/.
  do not add compatibility pointer docs.
  update DOCUMENTATION_INDEX.md when adding docs.

HDLForge config bugs:
  use <project>.hdlforge.json.
  keep paths relative to the project file.
  keep Verilator setup under verilator.config.
  keep Vivado setup under vivado.config and vivado.external_config.
  keep shortcuts under LLM_orch.

Shell bugs:
  use bash -i when opening an interactive Docker shell.
  set HOME and workdir when using raw docker exec.
  prefer .devcontainer/open_container_shell.sh.

Git bugs:
  do not commit generated container output.
  do not commit local logs.
  do not revert unrelated user changes.
