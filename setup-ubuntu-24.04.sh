#!/usr/bin/env bash
set -euo pipefail

echo "====================================="
echo " Step 1: Install Python dependencies "
echo "====================================="
sudo apt update
sudo apt install -y python3-pip python3-invoke python3-toml python3-tomli python3-tabulate

echo
echo "====================================="
echo " Step 2: Install Docker Engine       "
echo "====================================="

# Remove old versions
sudo apt-get remove -y docker docker-engine docker.io containerd runc || true

# Install dependencies
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg lsb-release

# Add Docker’s official GPG key
sudo mkdir -m 0755 -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Set up stable repo
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Install Docker
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# Enable service
sudo systemctl enable --now docker

echo
echo "====================================="
echo " Step 3: Configure Docker permissions"
echo "====================================="
sudo groupadd docker 2>/dev/null || true
sudo usermod -aG docker "$USER"
echo "🚨 Please log out and log back in (or run: newgrp docker) to refresh group membership."

echo
echo "====================================="
echo " Step 4: Verify installations        "
echo "====================================="
docker --version || { echo "Docker not found in PATH"; exit 1; }
docker run --rm hello-world || { echo "Docker test container failed"; exit 1; }

echo
echo "====================================="
echo " Step 5: Test Fabrinetes CLI         "
echo "====================================="
if [[ -x ./fabrinetes ]]; then
    ./fabrinetes --help || true
else
    echo "⚠️  ./fabrinetes not found or not executable. Run: chmod +x ./fabrinetes"
fi

echo
echo "✅ Setup complete!"
echo "Next steps:"
echo "1. Restart your shell or run: newgrp docker"
echo "2. Go to your repo folder with containers.toml"
echo "3. Run: <path-to-Fabrinetes>/fabrinetes build"

