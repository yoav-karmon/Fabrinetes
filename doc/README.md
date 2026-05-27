# Fabrinetes Documentation

## Overview

Fabrinetes provides the shared FPGA development container image, environment
hooks, and HDLForge tooling used by consuming FPGA repositories.

The supported container flow is Dev Containers:

- build the local image from `.devcontainer/fabrinetes-build/`,
- launch a local-image container from `.devcontainer/fabrinetes-run/`,
- let consuming repositories own their project-specific `.devcontainer`
  launch files.

## Repository Structure

```text
Fabrinetes/
├── .devcontainer/
│   ├── README.md
│   ├── fabrinetes-build/
│   │   ├── Dockerfile
│   │   └── devcontainer.json
│   └── fabrinetes-run/
│       ├── bashrc-func
│       ├── bashrc-root
│       ├── devcontainer.json
│       ├── entrypoint.sh
│       └── init_env.sh
├── doc/
├── examples/
├── hdlforge/
└── README.md
```

## Key Components

### Devcontainer Build

`.devcontainer/fabrinetes-build/` is the build-only example for producing a
local Fabrinetes image.

```bash
docker build \
  -t fabrinetes-dev:local \
  -f .devcontainer/fabrinetes-build/Dockerfile \
  .
```

Building does not push the image. Registry publication is always a separate
explicit step.

### Devcontainer Run

`.devcontainer/fabrinetes-run/` runs an already-built local image. It uses
Docker `--pull=never` so the CLI does not fetch a registry image.

```bash
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/fabrinetes-run/devcontainer.json
```

### Dynamic User Setup

The runtime entrypoint creates the requested user from:

```text
CONTAINER_USER
CONTAINER_HOME
```

It derives UID/GID from the mounted repository by default, keeping bind-mounted
files writable by the host user without requiring per-command UID variables.

### PATH Management

The shell setup detects the active Git repository and applies repository-local
tooling paths when available. Consuming repositories can expose their own
tooling through their project setup scripts.

## Usage

Start a project-owned devcontainer:

```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

Execute inside it:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'whoami; pwd; command -v hdlforge'
```

## Documentation Map

- [Documentation Index](DOCUMENTATION_INDEX.md)
- [Dev Containers CLI Launch](container-doc/devcontainer-cli.md)
- [Architecture](container-doc/architecture.md)
- [Testing Guide](container-doc/testing_guide.md)
- [Docker Installation](container-doc/docker-installation.md)
- [HDLForge API Reference](hdlforge-doc/HDLForge.md)
