How to make sure HDLForge works

Folder structure used by the examples:

   host/server:
     /home/<user>/repo/fpga/git-sub-module/Fabrinetes

   this is only an example. Fabrinetes can be cloned anywhere.

1. edit .devcontainer/fabrinetes-run/devcontainer.json:

   "source=${localWorkspaceFolder}/<relative path to folder to mount>,target=<path inside the container>,type=bind"

   ##########################################################################################
   # in this example, devcontainer is launched with the Fabrinetes repo as the workspace.   #
   # ${localWorkspaceFolder} = Fabrinetes repo top                                          #
   #                                                                                        #
   # ../.. goes from:                                                                       #
   # /home/<user>/repo/fpga/git-sub-module/Fabrinetes                                       #
   #                                                                                        #
   # to:                                                                                    #
   # /home/<user>/repo/fpga                                                                 #
   ##########################################################################################

   recommended example:
   "source=${localWorkspaceFolder}/../..,target=/home/${localEnv:USER}/repo/fpga,type=bind"


2. edit .devcontainer/fabrinetes-run/devcontainer.json:

   "FABRINETES": "<Fabrinetes repo path inside the container>"

   recommended example:

   "FABRINETES": "/home/${localEnv:USER}/repo/fpga/git-sub-module/Fabrinetes"
