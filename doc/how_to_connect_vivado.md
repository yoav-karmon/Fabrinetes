How to connect Vivado

Folder structure used by the examples:

   host/server:
     /DATA/amd/2025.1/Vivado/settings64.sh    <----- this is where vivado is intalled in this example , on the server
     /home/<user>/repo/fpga/vivado.lic        <----- this is where vivado is licasen file in this example  , on the server

1. edit .devcontainer/fabrinetes-run/devcontainer.json:

   "source=<your Vivado install path on the host server>,target=<path inside the container>,type=bind"

   recommended example:

   "source=/DATA/amd,target=/DATA/amd,type=bind"

2. edit .devcontainer/fabrinetes-run/devcontainer.json:

   "VIVADO_SETTINGS": "<Vivado installation path inside the container>/Vivado/settings64.sh"

   recommended example:

   "VIVADO_SETTINGS": "/DATA/amd/2025.1/Vivado/settings64.sh"

3. edit .devcontainer/fabrinetes-run/devcontainer.json:

   "XILINXD_LICENSE_FILE": "<path inside the container to the Vivado license file>"

   recommended example:

   "XILINXD_LICENSE_FILE": "/home/${localEnv:USER}/repo/fpga/vivado.lic"
