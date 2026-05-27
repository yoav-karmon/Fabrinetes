# Devcontainer Testing Guide

## Overview

Use this guide to verify that a project-owned `.devcontainer` setup starts,
attaches, and exposes the expected development environment. Build and image
generation flows are intentionally outside this guide.

## Prerequisites

- Docker is installed and usable by the current user.
- Dev Containers CLI is installed, or `npx @devcontainers/cli` is available.
- The consuming project repository has a `.devcontainer/<config-folder>/devcontainer.json`.

See [Docker Installation](docker-installation.md) and
[Dev Containers CLI Launch](devcontainer-cli.md) for host setup.

## Start The Container

Run from the consuming project repository:

```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

If the CLI is not installed globally:

```bash
npx @devcontainers/cli up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

## Verify The Container

Check that Docker sees the container:

```bash
docker ps
```

Run a basic command inside the devcontainer:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'whoami; pwd; echo "$HOME"'
```

Verify project tooling:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'command -v hdlforge || true; command -v python3; command -v git'
```

Verify repository mounts:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'git rev-parse --show-toplevel; ls .devcontainer'
```

## Attach With VS Code Or Cursor

After `devcontainer up` succeeds:

```text
Command Palette -> Dev Containers: Attach to Running Container
```

Select the project container and open a terminal inside the attached session.

## Raw Docker Exec

Prefer `devcontainer exec` for repeatable tests. If you need direct Docker
access to an already-running container:

```bash
docker exec -u <container-user> -it <container-name> bash -i
```

If the shell starts in the wrong home directory, set `HOME` and working
directory explicitly:

```bash
docker exec \
  -u <container-user> \
  -e HOME=/home/<container-user> \
  -w /home/<container-user> \
  -it <container-name> \
  bash -i
```

## Stop And Recreate

Stop the container:

```bash
docker stop <container-name>
```

Remove it when you want a fresh create from `devcontainer.json`:

```bash
docker rm <container-name>
```

Then rerun `devcontainer up`.

## Troubleshooting

### Docker Permission Denied

Confirm the user is in the `docker` group and start a fresh login shell:

```bash
groups
newgrp docker
```

### Devcontainer CLI Missing

Install it:

```bash
npm install -g @devcontainers/cli
```

Or run through `npx`:

```bash
npx @devcontainers/cli --help
```

### Wrong User Or Home Directory

Check the project `devcontainer.json` for:

```json
{
  "remoteUser": "<container-user>",
  "containerUser": "<container-user>",
  "workspaceFolder": "/home/<container-user>/repo/<project>"
}
```

For raw Docker access, pass `-u`, `-e HOME=...`, and `-w ...` explicitly.
