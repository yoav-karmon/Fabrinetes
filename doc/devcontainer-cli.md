Dev Containers CLI

Start container:
  cd <repo top>
  devcontainer up --workspace-folder <repo top> --config <repo top>/.devcontainer/<config>/devcontainer.json

Run command inside container:
  devcontainer exec --workspace-folder <repo top> --config <repo top>/.devcontainer/<config>/devcontainer.json bash -ic '<command>'

Open shell with devcontainer:
  devcontainer exec --workspace-folder <repo top> --config <repo top>/.devcontainer/<config>/devcontainer.json bash -i

Open shell with Docker:
  docker exec -u <user> -e HOME=/home/<user> -w /home/<user> -it <container name> bash -i

Stop container:
  docker stop <container name>

Remove container:
  docker rm -f <container name>

Recreate container:
  docker rm -f <container name>
  devcontainer up --workspace-folder <repo top> --config <repo top>/.devcontainer/<config>/devcontainer.json

Notes:
  --workspace-folder is the host repo path.
  workspaceFolder in devcontainer.json is the container repo path.
  use bash -i so .bashrc is loaded.
