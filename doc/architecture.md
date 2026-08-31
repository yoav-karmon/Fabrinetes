# Container Architecture

Fabrinetes uses one shared generic devcontainer definition plus an explicit
consumer-specific configuration. `.devcontainer/Fabrinetes.sh` is the public
entrypoint for build, run, status, shell, editor attachment, and lifecycle
actions.

## Configuration Layers

- `.devcontainer/devcontainer.json` owns the shared image, runtime, shell-file,
  and structural mount definitions.
- A selected `*.devcontainer.json` owns consumer-specific extensions, required
  tools, additional host mounts, build context, image identity, container
  identity, and repository paths.
- `.devcontainer/merge_devcontainer_config.sh` validates both inputs, merges
  their customizations, generates tool and additional mounts, adds tool
  environment variables, and writes a temporary effective config.

Codex, VS Code, and Cursor have fixed destinations under the container home.
Their host storage paths come from `requiredTools`. Vivado declares its settings
script and environment-variable name; an `additionalMounts` entry supplies the
host directory containing that script.

## Build And Run

- `.devcontainer/build_image.sh` builds the configured local image from the
  selected build-support folder.
- `.devcontainer/run_container.sh` creates or starts the configured container
  from the effective config.
- `.devcontainer/launch_vscode.sh` attaches VS Code using the same merged
  configuration.
- `.devcontainer/open_container_shell.sh` opens an interactive shell in the
  configured running container.

The image owns installed OS and Python software. Host bind mounts own editor
servers, Codex state, SSH state, vendor tools, repositories, and consumer shell
files. Separate configs may use different images, container identities, and
host-storage folders while sharing selected external mounts.

## Shell And HDLForge Setup

- `bashrc-root` starts interactive shell setup, sources `init_env.sh`, captures
  the initial path values, and calls `update_repo_path`.
- `init_env.sh` sets Fabrinetes and HDLForge paths, sources the configured
  Vivado settings script, and adds HDLForge to `PATH`.
- `bashrc-func` provides path helpers and `update_repo_path`.
- `<REPO_TOP>/init_repo_env.sh` may add repository-specific `PATH` and
  `PYTHONPATH` values.
- Each `<project>.hdlforge.json` owns its Verilator, Vivado, and `LLM_orch`
  configuration.
