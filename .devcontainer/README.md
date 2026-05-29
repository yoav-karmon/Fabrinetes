# Devcontainer Configurations

## Short Commands

From the Fabrinetes repo root:

```bash
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --build
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --run
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --vscode
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --stop
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --remove-image
```

## Build

The single devcontainer config builds a per-user Fabrinetes development image
from the package lists in `.devcontainer`. The image default user matches the
host user and has passwordless sudo.

Launch from the Fabrinetes repo root:

```bash
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --build
```

## Run

Runtime devcontainer for the local image. It sets `--pull=never`, mounts the
parent FPGA checkout into the expected container path, and provides the
shell/env support files used by HDLForge.

Launch from the Fabrinetes repo root:

```bash
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --run
```

Open a shell inside it:

```bash
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --shell
```

Launch VS Code attached to it:

```bash
.devcontainer/Fabrinetes.sh .devcontainer/Fabrinetes.devcontainer.json --vscode
```
