# Devcontainer Configurations

Common troubleshooting notes live in `common_issues.md`.

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

The selected config must declare all four required tools under
`customizations.Fabrinetes.requiredTools`. `codex`, `vscode`, and `cursor`
each take a host `serverPath`; the merger mounts them at their fixed folders
under the container user's home. `vivado` declares the container-side
`settingsScript` and `settingsEnvironmentVariable`. The settings script must
be inside exactly one declared additional mount and must exist on the server.

Use `customizations.Fabrinetes.additionalMounts` for other bind mounts:

```json
"additionalMounts": [
  {
    "serverPath": "/DATA/amd",
    "containerPath": "/DATA/amd"
  }
]
```

Every `serverPath`, `containerPath`, runner home, and runner path must be
absolute or start with `~`. The merger resolves `~`, rejects relative paths
and duplicate container targets, and fails when any declared server source is
missing. JSON does not support comments, so examples belong in this README
rather than in the configuration file.

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
