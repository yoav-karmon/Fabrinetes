# Dev Containers CLI Launch

Use this flow for repositories that provide `.devcontainer/devcontainer.json`
files and are launched through the VS Code/Cursor Dev Containers extension or
the Dev Containers CLI.

This document covers launching and entering containers only. Image build and
custom image generation flows remain separate and are intentionally not covered
here.

## Install CLI Tools

Install Docker first:

```bash
sudo apt update
sudo apt install -y docker.io
sudo systemctl enable --now docker
sudo usermod -aG docker "$USER"
```

Log out and back in, or run `newgrp docker`, before using Docker without sudo.

Install the Dev Containers CLI with npm:

```bash
npm install -g @devcontainers/cli
```

If global npm installs are not available, use `npx`:

```bash
npx @devcontainers/cli --help
```

Verify:

```bash
docker --version
devcontainer --help
```

## Start Or Create A Container

Run this on the host, from the repository that owns the `.devcontainer`
configuration:

```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

With `npx`:

```bash
cd <repo_top>
npx @devcontainers/cli up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

`--workspace-folder` is the host-side repository path. `workspaceFolder` inside
`devcontainer.json` is the container-side path opened by VS Code/Cursor.

## Attach With VS Code Or Cursor

After `devcontainer up`, attach to the running container:

```text
Command Palette -> Dev Containers: Attach to Running Container
```

Or open the repository on the host and use:

```text
Command Palette -> Dev Containers: Reopen in Container
```

When multiple configs exist, choose the account- or project-specific
`.devcontainer/<config-folder>/devcontainer.json`.

## Execute Commands Inside A Running Container

Use the Dev Containers CLI when possible:

```bash
devcontainer exec \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json \
  bash -ic 'whoami; pwd'
```

For raw Docker access, set the user explicitly and use an interactive bash shell
so `.bashrc` is loaded:

```bash
docker exec \
  -u <container-user> \
  -it <container-name> \
  bash -i
```

If the container was created before its config set Docker `--workdir` and
`HOME`, pass them explicitly:

```bash
docker exec \
  -u <container-user> \
  -e HOME=<container-home> \
  -w <container-home> \
  -it <container-name> \
  bash -i
```

## Stop Or Recreate

Stop:

```bash
docker stop <container-name>
```

Remove when you want `devcontainer up` to recreate it from config:

```bash
docker rm <container-name>
```

Then rerun `devcontainer up`.

## Notes

- Keep project-specific mount paths and user IDs in the consuming repository's
  `.devcontainer` files.
- Keep image build and package installation details in the image/build docs.
- Prefer Dev Containers extension/CLI launch for day-to-day development.
