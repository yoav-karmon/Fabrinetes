# How To Verify HDLForge Setup

The selected consumer-specific `*.devcontainer.json` owns the repository mount
and Fabrinetes location. Configure its runner fields with absolute or
user-relative paths:

```json
"runner": {
  "home": "~",
  "repoMountSource": "~/repo/fpga",
  "repoMountTarget": "~/repo/fpga",
  "fabrinetes": "~/repo/fpga/git-sub-module/Fabrinetes"
}
```

`repoMountSource` is a host/server path. `repoMountTarget` and `fabrinetes` are
container paths. The source directory and the Fabrinetes checkout must exist
before starting the container.

From the repository that owns the selected config, run host-side status checks:

```bash
CONFIG=.devcontainer/Fabrinetes.devcontainer.json
.devcontainer/Fabrinetes.sh "$CONFIG" --image-status
.devcontainer/Fabrinetes.sh "$CONFIG" --container-status
```

After the container is running, open its shell and verify the resolved setup:

```bash
.devcontainer/Fabrinetes.sh "$CONFIG" --shell
printf '%s\n' "$REPO_TOP" "$FABRINETES" "$HDLFORGE"
test -d "$FABRINETES/hdlforge/project_setup"
command -v hdlforge
hdlforge --help
```

The mounted `init_env.sh` sets `HDLFORGE` from `FABRINETES`, adds the HDLForge
entrypoint to `PATH`, and allows the mounted repository's `init_repo_env.sh` to
add repository-specific environment values.
