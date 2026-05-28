How to build, start, and open a shell

cd to:
  <Fabrinetes repo top>

run:
  .devcontainer/build_image.sh -> .devcontainer/run_container.sh -> .devcontainer/open_container_shell.sh

what each command does:
  .devcontainer/build_image.sh         -> builds image fabrinetes-dev:local
  .devcontainer/run_container.sh       -> starts container <user>_fabrinetes_dev.run
  .devcontainer/open_container_shell.sh -> opens shell in the running container

how to remove running container:
  docker rm -f "${USER}_fabrinetes_dev.run"

how to remove local image:
  docker image rm -f fabrinetes-dev:local

how to remove Docker build cache:
  docker builder prune -af
