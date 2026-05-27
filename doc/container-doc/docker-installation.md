# Docker Installation Guide for Fabrinetes

## Overview

This guide provides step-by-step instructions for installing Docker on Ubuntu 24.04 LTS and configuring it for use with Fabrinetes. Docker is required for Fabrinetes to build, run, and manage containerized development environments.

## Prerequisites

- Ubuntu 24.04 LTS (Noble Numbat) or compatible system
- User with sudo privileges
- Internet connection for package downloads
- At least 2GB of available disk space

## Installation Steps

### 1. Check System Information

First, verify your system information:

```bash
# Check OS version
cat /etc/os-release

# Check current user
whoami

# Check user groups
groups
```

### 2. Update Package Lists

Update the package lists to ensure you have the latest package information:

```bash
sudo apt update
```

### 3. Install Docker Engine

Install Docker Engine using the Ubuntu package manager:

```bash
sudo apt install -y docker.io
```

This command installs:
- `docker.io` - Docker Engine
- `containerd` - Container runtime
- `runc` - Container runtime
- `bridge-utils` - Network bridge utilities
- `dnsmasq-base` - DNS forwarder
- `pigz` - Parallel gzip compression
- `ubuntu-fan` - Ubuntu Fan networking

### 4. Verify Installation

Check that Docker is installed correctly:

```bash
# Check Docker version
docker --version

# Check Docker service status
systemctl status docker
```

Expected output:
```
Docker version 28.2.2, build 28.2.2-0ubuntu1~24.04.1
```

### 5. Start and Enable Docker Service

Docker service should start automatically, but verify and enable it:

```bash
# Start Docker service
sudo systemctl start docker

# Enable Docker service to start on boot
sudo systemctl enable docker

# Check service status
systemctl status docker
```

### 6. Add User to Docker Group

To run Docker commands without sudo, add your user to the docker group:

```bash
# Add current user to docker group
sudo usermod -aG docker $USER

# Verify group membership
groups $USER
```

### 7. Refresh Group Membership

Apply the new group membership:

```bash
# Option 1: Refresh groups in current session
newgrp docker

# Option 2: Log out and log back in
# Option 3: Restart the system
```

## Dev Containers CLI

For repositories that use `.devcontainer/devcontainer.json`, install the Dev
Containers CLI after Docker is available:

```bash
npm install -g @devcontainers/cli
```

If global npm installs are not available, use `npx`:

```bash
npx @devcontainers/cli --help
```

Verify:

```bash
devcontainer --help
```

Then launch from the consuming repository:

```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

See [Dev Containers CLI Launch](devcontainer-cli.md) for the launch and attach
workflow. Image build and package installation workflows are documented
separately.

### 8. Verify Docker Access

Test that Docker works without sudo:

```bash
# Test Docker with hello-world container
docker run --rm hello-world

# Check Docker system information
docker info

# List Docker images
docker images
```

Expected output for hello-world:
```
Hello from Docker!
This message shows that your installation appears to be working correctly.
```

## Verification With Dev Containers

Test Docker and Dev Containers together from the consuming project repository:

```bash
cd <repo_top>
devcontainer up \
  --workspace-folder <repo_top> \
  --config <repo_top>/.devcontainer/<config-folder>/devcontainer.json
```

Expected output should show Docker connectivity and complete the devcontainer
startup sequence without Docker daemon errors.

## Troubleshooting

### Docker Permission Denied

If you get permission denied errors:

```bash
# Check if user is in docker group
groups $USER

# If not in docker group, add user
sudo usermod -aG docker $USER

# Refresh group membership
newgrp docker
```

### Docker Service Not Running

If Docker service is not running:

```bash
# Start Docker service
sudo systemctl start docker

# Check service status
systemctl status docker

# Check service logs
journalctl -u docker.service
```

### Docker Images Not Found

If Docker images are not found, this is normal for a fresh installation:

```bash
# Pull a test image
docker pull ubuntu:latest

# List available images
docker images
```

### Network Issues

If you have network connectivity issues:

```bash
# Check Docker network
docker network ls

# Check Docker daemon configuration
docker info | grep -i network
```

## Docker Configuration

### Storage Driver

Docker uses the `overlay2` storage driver by default on Ubuntu 24.04, which is optimal for most use cases.

### Network Configuration

Docker creates a default bridge network. For Fabrinetes, this default configuration is sufficient.

### Resource Limits

By default, Docker has no resource limits. For development environments, this is typically acceptable.

## Integration With Project Devcontainers

Once Docker is installed and configured:

1. **Launch Containers**: Use `devcontainer up` with the project `.devcontainer` config
2. **Attach IDEs**: Use VS Code/Cursor `Dev Containers: Attach to Running Container`
3. **Run Commands**: Use `devcontainer exec` for repeatable command execution
4. **Inspect Containers**: Use `docker ps`, `docker logs`, and `docker inspect`

## Maintenance

### Updating Docker

To update Docker to the latest version:

```bash
# Update package lists
sudo apt update

# Upgrade Docker
sudo apt upgrade docker.io

# Restart Docker service
sudo systemctl restart docker
```

### Cleaning Up

To clean up unused Docker resources:

```bash
# Remove unused containers
docker container prune

# Remove unused images
docker image prune

# Remove unused volumes
docker volume prune

# Remove unused networks
docker network prune

# Remove all unused resources
docker system prune
```

## Security Considerations

- Docker daemon runs with root privileges
- Only add trusted users to the docker group
- Regularly update Docker to get security patches
- Use official images from Docker Hub when possible
- Scan images for vulnerabilities in production environments

## Additional Resources

- [Docker Official Documentation](https://docs.docker.com/)
- [Docker Hub](https://hub.docker.com/)
- [Ubuntu Docker Installation](https://docs.docker.com/engine/install/ubuntu/)
- [Docker Security Best Practices](https://docs.docker.com/engine/security/)

## Installation Summary

This installation provides:
- Docker Engine 28.2.2
- Containerd runtime
- Overlay2 storage driver
- Default bridge networking
- User group permissions
- Systemd service integration

The installation is now ready for use with Fabrinetes and other containerized applications.

---

## Document History

**Last Updated:** Commit `0dfcbd30f42c9be4be92bcdbfb1507dd1fad77f3` - Reorganize container documentation into container-doc/ subdirectory (2025-11-11)
