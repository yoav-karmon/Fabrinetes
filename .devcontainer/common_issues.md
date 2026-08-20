# Fabrinetes Devcontainer Common Issues

This file covers shared Fabrinetes devcontainer failure modes. Keep examples
generic so downstream repositories can link to this file from their own
`.devcontainer/` directory.

## Docker Socket Permission Denied

Symptom:

```text
permission denied while trying to connect to the docker API at unix:///var/run/docker.sock
```

Cause:

`docker.socket` can fail during host boot if systemd cannot resolve the
`docker` group yet. When that happens, `/run/docker.sock` may be created as
`root:root` instead of `root:docker`, so users in the `docker` group still
cannot access Docker.

Check:

```bash
id
ls -l /run/docker.sock /var/run/docker.sock
systemctl status docker.socket --no-pager
```

Fix:

```bash
sudo systemctl reset-failed docker.socket docker.service
sudo systemctl start docker.socket
ls -l /run/docker.sock /var/run/docker.sock
```

Expected socket ownership:

```text
root docker
```

## Devcontainer CLI Rejects Generated Config Name

Symptom:

```text
Filename must be devcontainer.json or .devcontainer.json
```

Cause:

Recent `@devcontainers/cli` versions require the config file basename passed
with `--config` to be exactly `devcontainer.json` or `.devcontainer.json`.
Generated files such as `/tmp/fabrinetes-<id>.devcontainer.json` are rejected.

Fix:

Generate the merged effective config in a directory and name the file
`devcontainer.json`, for example:

```text
.devcontainer/.generated/<config-hash>/devcontainer.json
```

Do not use a deleted temporary config path for a container label. If an existing
container has a `devcontainer.config_file` label pointing into a removed `/tmp`
directory, recreate that file from the current generated config or recreate the
container.

## Wrapper `--run` Rebuilds Instead Of Starting Existing Container

Symptom:

Running:

```bash
.devcontainer/Fabrinetes.sh <Fabrinetes-devcontainer-json> --run
```

starts a Docker build even though the configured container already exists.

Cause:

The wrapper delegated directly to `devcontainer up`. That command reconciles the
Dev Containers configuration and can rebuild/recreate when image/config labels
do not match, especially after the generated config path changes.

Expected wrapper behavior:

1. Resolve `customizations.Fabrinetes.runner.containerName`.
2. If the container exists and is running, report `status: running`.
3. If it exists but is stopped, run `docker start`.
4. Only call `devcontainer up` when the container is missing.

## VS Code Container Attach Spins Forever After Reboot

Symptom:

VS Code `Dev Containers: Attach to Running Container...` opens a container
window, then stays on `Opening Remote...` forever. Repeated attach attempts keep
cycling after a host reboot or power cycle.

Cause:

The mounted container-side VS Code Server cache can be left with an interrupted
install. VS Code repeatedly tries to unpack the same server commit into
timestamped temporary directories under:

```text
~/.vscode-server/bin/<commit>_<timestamp>
```

but never creates the completed directory:

```text
~/.vscode-server/bin/<commit>
```

Check from the SSH host:

```bash
container=<container-name>
commit=$(code --version | sed -n '2p')

docker exec -u "$USER" -e HOME="$HOME" "$container" \
  bash -c "ps -ef | grep -E 'tar --no-same-owner|$commit' | grep -v grep || true"

docker exec -u "$USER" -e HOME="$HOME" "$container" \
  bash -c "ls -ld ~/.vscode-server/bin/${commit}* 2>/dev/null || true"
```

Fix:

Stop the stuck container-side VS Code Server unpack, move only the broken temp
directories aside, and seed the completed server directory from the SSH host's
healthy VS Code Server install:

```bash
container=<container-name>
commit=$(code --version | sed -n '2p')

docker exec -u "$USER" -e HOME="$HOME" "$container" \
  bash -c "ps -ef | awk '/tar --no-same-owner.*\\.vscode-server\\/bin\\/$commit/ && !/awk/ {print \$2}' | xargs -r kill"

src="$HOME/.vscode-server/cli/servers/Stable-$commit/server"
dst="$HOME/vscode-server-container/.vscode-server/bin/$commit"
backup="$HOME/vscode-server-container/.vscode-server/bin/broken-$(date +%Y%m%d_%H%M%S)"

test -d "$src"
mkdir -p "$backup"
if [ -e "$dst" ]; then
  mv "$dst" "$backup"/
fi
shopt -s nullglob
for broken_dir in "$HOME"/vscode-server-container/.vscode-server/bin/${commit}_*; do
  mv "$broken_dir" "$backup"/
done
cp -a "$src" "$dst"
test -x "$dst/node"
test -f "$dst/out/server-main.js"
```

Retry `Dev Containers: Attach to Running Container...` after the completed
server directory exists.
