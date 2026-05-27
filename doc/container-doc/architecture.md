# Fabrinetes Container Architecture

## Overview

Fabrinetes provides the base FPGA development container image and the shared
container environment hooks used by consuming FPGA repositories.

The supported launch model is Dev Containers. Image creation and container
launch are intentionally split:

- `.devcontainer/fabrinetes-build/` builds the local Fabrinetes image.
- `.devcontainer/fabrinetes-run/` launches an already-built local image.
- Consuming repositories can provide their own `.devcontainer/` launch files
  that use the Fabrinetes image and mount the project-specific workspace.

## Build Configuration

The build configuration lives under:

```text
.devcontainer/fabrinetes-build/
```

It is a build-only example. Use it to create a local image tag such as
`fabrinetes-dev:local`:

```bash
docker build \
  -t fabrinetes-dev:local \
  -f .devcontainer/fabrinetes-build/Dockerfile \
  .
```

The build does not push an image. Publishing to a registry is a separate,
explicit operation.

## Run Configuration

The local run configuration lives under:

```text
.devcontainer/fabrinetes-run/
```

It uses the local `fabrinetes-dev:local` image and passes Docker `--pull=never`
so Dev Containers will not fetch from a registry.

Launch it with:

```bash
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/fabrinetes-run/devcontainer.json
```

Then execute a smoke command:

```bash
LOCAL_UID="$(id -u)" LOCAL_GID="$(id -g)" \
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/fabrinetes-run/devcontainer.json \
  bash -ic 'whoami; id; pwd; command -v hdlforge'
```

## Dynamic User Setup

The runtime entrypoint creates or updates the container user from environment
variables:

```text
CONTAINER_USER
CONTAINER_UID
CONTAINER_GID
CONTAINER_HOME
```

The run devcontainer maps these from the host user. This keeps bind-mounted
files writable by the host account and avoids root-owned build artifacts.

Use `LOCAL_UID` and `LOCAL_GID` on the host command line because `UID` is a
readonly shell variable in Bash.

## Environment Setup

The run devcontainer installs the shared environment hooks:

- `entrypoint.sh` creates the requested user and starts the requested command.
- `init_env.sh` configures Fabrinetes and HDLForge environment variables.
- `bashrc-root` and `bashrc-func` provide shell startup behavior.

The container shell should expose `hdlforge` from the mounted repository.

## Consuming Repository Pattern

A consuming FPGA repository should own its project-specific `.devcontainer`
files. Those files should:

- choose the image tag to use,
- define the correct workspace mount,
- set the remote user and home,
- pass UID/GID environment values,
- mount any project-specific hardware, license, cache, or tool directories.

The Fabrinetes repo remains the shared source for the base image and common
container environment scripts.

## Related Documentation

- [Dev Containers CLI Launch](devcontainer-cli.md)
- [Testing Guide](testing_guide.md)
- [Docker Installation](docker-installation.md)
- [GitHub Container Registry](github-container-registry.md)
