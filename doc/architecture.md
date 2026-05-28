Architecture

Repository parts:
  .devcontainer/fabrinetes-build/
    builds the local image

  .devcontainer/fabrinetes-run/
    runs the local image
    owns shell setup
    owns path setup

  hdlforge/project_setup/
    provides the hdlforge command
    runs Verilator, Vivado, LLM_orch, and helper tools

  examples/
    small HDLForge examples

  doc/
    flat documentation folder

Build image:
  .devcontainer/build_image.sh

Run container:
  .devcontainer/run_container.sh

Open shell:
  .devcontainer/open_container_shell.sh

Shell startup:
  bashrc-root
    starts interactive shell setup
    sources init_env.sh
    captures INIT_PATH and INIT_PYTHONPATH
    calls update_repo_path

  init_env.sh
    sets FABRINETES
    sets HDLFORGE
    sources Vivado settings if configured
    adds hdlforge to PATH

  bashrc-func
    provides add_to_path
    provides add_to_pythonpath
    provides update_repo_path

Repo setup:
  <REPO_TOP>/init_repo_env.sh
    optional per-repo PATH/PYTHONPATH setup

HDLForge setup:
  <project>.hdlforge.json
    Verilator config
    Vivado config
    LLM_orch shortcuts
