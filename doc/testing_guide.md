Testing guide

Check Docker:
  docker ps

Check Dev Containers CLI:
  devcontainer --help

Start container:
  cd <repo top>
  .devcontainer/run_container.sh

Open shell:
  .devcontainer/open_container_shell.sh

Check user and home:
  whoami
  pwd
  echo "$HOME"

Check tools:
  command -v git
  command -v python3
  command -v hdlforge

Check Vivado if mounted:
  command -v vivado
  echo "$VIVADO_SETTINGS"
  echo "$XILINXD_LICENSE_FILE"

Check repo paths:
  git rev-parse --show-toplevel
  echo "$REPO_TOP"
  echo "$FABRINETES"
  echo "$HDLFORGE"
