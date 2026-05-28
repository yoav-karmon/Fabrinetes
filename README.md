# Fabrinetes

Shared FPGA devcontainer and HDLForge tooling.

What this repo provides:
  .devcontainer/fabrinetes-build/     -> build local image
  .devcontainer/fabrinetes-run/       -> run local image
  hdlforge/project_setup/             -> hdlforge command
  examples/                           -> small HDLForge examples
  doc/                                -> flat docs

Quick start:
  cd <Fabrinetes repo top>
  .devcontainer/build_image.sh
  .devcontainer/run_container.sh
  .devcontainer/open_container_shell.sh

What each command does:
  .devcontainer/build_image.sh         -> builds image fabrinetes-dev:local
  .devcontainer/run_container.sh       -> starts container <user>_fabrinetes_dev.run
  .devcontainer/open_container_shell.sh -> opens shell in the running container

Host tools:
  Docker
  Dev Containers CLI

Install Dev Containers CLI:
  npm install -g @devcontainers/cli

Docs:
  doc/README.md
  doc/DOCUMENTATION_INDEX.md
  doc/how_to_build_start_shell.md
  doc/how_to_connect_vivado.md
  doc/how_to_make_sure_hdlforge_works.md
  doc/hdlforge.md
  doc/hdlforge_project_file.md

Current project file format:
  <project>.hdlforge.json

Current path model:
  bashrc-root captures container baseline
  update_repo_path resets to baseline
  <REPO_TOP>/init_repo_env.sh adds repo paths
  hdlforge captures the launch directory environment
