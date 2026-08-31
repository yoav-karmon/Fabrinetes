# Container Testing Guide

Run Docker and lifecycle commands on the host server. Always pass the intended
consumer-specific configuration explicitly.

## Source Validation

From the Fabrinetes repository root:

```bash
bash -n .devcontainer/*.sh
jq -e . .devcontainer/devcontainer.json .devcontainer/Fabrinetes.devcontainer.json
.devcontainer/test_merge_devcontainer_config.sh
```

The merger tests cover recursive customization merging, mandatory tools,
generated mounts, invalid paths, missing sources, duplicate targets, and
Vivado settings-script coverage.

## Host Checks

```bash
docker ps
devcontainer --help
CONFIG=.devcontainer/Fabrinetes.devcontainer.json
.devcontainer/Fabrinetes.sh "$CONFIG" --image-status
.devcontainer/Fabrinetes.sh "$CONFIG" --container-status
```

Build or run only when that lifecycle action is intended:

```bash
.devcontainer/Fabrinetes.sh "$CONFIG" --build
.devcontainer/Fabrinetes.sh "$CONFIG" --run
.devcontainer/Fabrinetes.sh "$CONFIG" --shell
```

When two configs must coexist, verify that their image names, container names,
hostnames, and Codex/VS Code/Cursor `serverPath` values are distinct before
running the second config.

## Container Checks

Inside the selected container:

```bash
whoami
hostname
printf '%s\n' "$HOME" "$FABRINETES" "$HDLFORGE" "$VIVADO_SETTINGS"
command -v git python3 hdlforge vivado
git rev-parse --show-toplevel
test -f "$VIVADO_SETTINGS"
mountpoint "$HOME/.codex"
mountpoint "$HOME/.vscode-server"
mountpoint "$HOME/.cursor-server"
```

Also verify each configured `additionalMounts[].containerPath` and the
configured repository target with `mountpoint`. For concurrent configurations,
inspect Docker mounts and confirm each tool target maps to that configuration's
own host-storage source.
