# Devcontainer Configurations

## Short Commands

From the Fabrinetes repo root:

```bash
.devcontainer/build_image.sh
.devcontainer/run_container.sh
.devcontainer/open_container_shell.sh
```

## `fabrinetes-build`

Build-only example for creating a local Fabrinetes development image from the
repo package lists. This config is intentionally minimal: it does not model the
full runtime mount layout and it does not run HDLForge smoke tests.

Launch from the Fabrinetes repo root:

```bash
devcontainer up \
  --workspace-folder "$PWD" \
  --config "$PWD/.devcontainer/fabrinetes-build/devcontainer.json"
```

This config builds locally only. It does not push any image to a registry.

For a stable local image name used by `fabrinetes-run`, build/tag the image with
Docker:

```bash
docker build \
  -t fabrinetes-dev:local \
  -f "$PWD/.devcontainer/fabrinetes-build/Dockerfile" \
  "$PWD"
```

## `fabrinetes-run`

Runtime devcontainer for an already-present local image. It uses
`fabrinetes-dev:local`, sets `--pull=never`, mounts the opened Fabrinetes repo
through its parent FPGA checkout into the expected container path, and provides
the shell/env support files used by HDLForge. This preserves submodule Git
metadata because the parent checkout's `.git/modules` directory is mounted too.

Launch from the Fabrinetes repo root:

```bash
devcontainer up \
  --workspace-folder "$PWD" \
  --config "$PWD/.devcontainer/fabrinetes-run/devcontainer.json"
```

Run a command inside it:

```bash
devcontainer exec \
  --workspace-folder "$PWD" \
  --config "$PWD/.devcontainer/fabrinetes-run/devcontainer.json" \
  bash -ic 'whoami; command -v hdlforge; hdlforge projects'
```
