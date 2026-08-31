# How To Connect Vivado

Declare Vivado as a required tool in the selected consumer-specific config and
mount the host directory that contains it:

```json
"requiredTools": {
  "vivado": {
    "settingsScript": "/DATA/amd/2025.1/Vivado/settings64.sh",
    "settingsEnvironmentVariable": "VIVADO_SETTINGS"
  }
},
"additionalMounts": [
  {
    "serverPath": "/DATA/amd",
    "containerPath": "/DATA/amd"
  }
]
```

`settingsScript` is the path inside the container. It must be covered by
exactly one `additionalMounts` target. The merger translates it back to the
server source and fails unless that settings file exists.

Set the license variable in the consumer's mounted runtime `init_env.sh`, using
a path available inside the container:

```bash
export XILINXD_LICENSE_FILE="$HOME/repo/fpga/Xilinx_edgehog.lic"
```

If the license is not inside the mounted repository, expose its host directory
with another `additionalMounts` entry and use the matching container path.

After starting the selected container, verify:

```bash
printf '%s\n' "$VIVADO_SETTINGS" "$XILINXD_LICENSE_FILE"
test -f "$VIVADO_SETTINGS"
test -f "$XILINXD_LICENSE_FILE"
command -v vivado
vivado -version
```
