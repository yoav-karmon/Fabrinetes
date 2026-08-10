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

The wrapper builds a per-user Fabrinetes development image. The selected
Fabrinetes config can provide a `builder.buildDir`; when it does, that support
directory becomes the Docker build context and supplies `packages.txt` and
`python-packages.txt`. The shared Dockerfile stays in this `.devcontainer`
directory. The image default user matches the host user and has passwordless
sudo.

Before build or run, the wrapper validates the generic and selected Fabrinetes
JSON files, recursively merges their `customizations`, and validates the
effective temporary config. Objects merge recursively, arrays combine without
duplicates, and selected-config scalars override generic values. A reported
`[config N/4]` error stops before `devcontainer build` or `up`.

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
