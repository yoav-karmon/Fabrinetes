Docker installation

Install Docker:
  sudo apt update
  sudo apt install -y docker.io

Start Docker:
  sudo systemctl enable --now docker

Allow current user to use Docker:
  sudo usermod -aG docker "$USER"

Apply group change:
  log out and back in

  or:
    newgrp docker

Check:
  docker --version
  docker ps

Install Dev Containers CLI:
  npm install -g @devcontainers/cli

Check:
  devcontainer --help

If global npm install is not allowed:
  npx @devcontainers/cli --help
