# Fabrinetes setup.sh Script Guide

## Overview

The `setup.sh` script is a powerful container and image management tool that provides fine-grained control over Docker container and image operations in the Fabrinetes ecosystem. It serves as a wrapper around the core `fabrinetes.py` script with additional lifecycle management capabilities.

## Purpose

While the main `fabrinetes` wrapper script provides basic build and run functionality, `setup.sh` offers:
- **Granular control** over individual operations
- **Image lifecycle management** (pull, build, commit, push)
- **Container lifecycle management** (start, stop, restart, run)
- **Operation chaining** for complex workflows
- **Interactive confirmations** for safety

## Location

```bash
/home/yoav.karmon/repo/Fabrinetes/setup.sh
```

---

## Quick Start

### Basic Usage

```bash
./setup.sh -f <config_file> [OPTIONS]
```

### Common Workflows

```bash
# Pull image and run container
./setup.sh -f config.toml --image-pull --run

# Build image and run container
./setup.sh -f config.toml --image-build --run

# Stop container, commit as image, push to registry
./setup.sh -f config.toml --stop --image-commit --image-push

# Just restart an existing container
./setup.sh -f config.toml --restart

# Reuse existing local image and run
./setup.sh -f config.toml --image-reuse --run
```

---

## Command-Line Options

### Required Arguments

| Option | Description |
|--------|-------------|
| `-f, --config-file <file>` | Path to config.toml file (required for all operations) |

### Container Operations

| Option | Short | Description |
|--------|-------|-------------|
| `--start` | `-s` | Start existing stopped container |
| `--stop` | `-S` | Stop running container |
| `--restart` | `-r` | Restart container (stop then start) |
| `--run` | `-R` | Run new container (create and start) |

### Image Operations

| Option | Short | Description |
|--------|-------|-------------|
| `--image-pull` | `-p` | Pull image from Docker registry |
| `--image-build` | `-b` | Build image from scratch using Dockerfile |
| `--image-reuse` | `-u` | Use existing local image (verify only) |
| `--image-commit` | `-c` | Commit running container to image |
| `--image-push` | `-P` | Push image to registry |

### Other Options

| Option | Short | Description |
|--------|-------|-------------|
| `--help` | `-h` | Show help message |
| `--force` | | Skip interactive confirmations |

---

## Detailed Operation Descriptions

### Container Operations

#### Start (`--start`)
- **Purpose**: Start an existing stopped container
- **Prerequisites**: Container must exist in stopped state
- **Behavior**: 
  - Checks if container is already running (no-op if running)
  - Starts the container using `docker start`
  - Fails if container doesn't exist

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --start
```

#### Stop (`--stop`)
- **Purpose**: Stop a running container
- **Prerequisites**: Container must exist
- **Behavior**:
  - Checks if container is already stopped (no-op if stopped)
  - Gracefully stops the container using `docker stop`
  - Fails if container doesn't exist

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --stop
```

#### Restart (`--restart`)
- **Purpose**: Restart an existing container
- **Prerequisites**: Container must exist (running or stopped)
- **Behavior**:
  - Uses `docker restart` to restart container
  - Works on both running and stopped containers
  - Fails if container doesn't exist

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --restart
```

#### Run (`--run`)
- **Purpose**: Create and start a new container
- **Prerequisites**: Image must exist (locally or in registry)
- **Behavior**:
  - Checks if container already exists
  - Prompts to remove existing container (unless `--force`)
  - Runs `fabrinetes.py --cmd run` to create container
  - Verifies container is running after creation

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --run
```

### Image Operations

#### Pull (`--image-pull`)
- **Purpose**: Pull image from Docker registry
- **Prerequisites**: 
  - Docker login (use `scripts/docker-login.sh`)
  - Network connectivity to registry
- **Behavior**:
  - Verifies Docker login status
  - Pulls image using `docker pull`
  - Provides detailed error analysis if pull fails
  - Shows available images on failure

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --image-pull
```

**Error Handling**:
- **Permission denied**: Checks Docker permissions and login status
- **Connectivity issues**: Detects network problems
- **Image not found**: Shows available images from repository
- **Daemon issues**: Detects if Docker daemon is running

#### Build (`--image-build`)
- **Purpose**: Build image from Dockerfile
- **Prerequisites**: Dockerfile must exist in container directory
- **Behavior**:
  - Checks if image already exists (prompts to overwrite unless `--force`)
  - Runs `fabrinetes.py --cmd build` to build image
  - Verifies image was created successfully

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --image-build
```

#### Reuse (`--image-reuse`)
- **Purpose**: Verify existing local image exists
- **Prerequisites**: Image must exist locally
- **Behavior**:
  - Checks if image exists in local Docker images
  - Succeeds if image found, fails otherwise
  - Useful for verification before running container

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --image-reuse
```

#### Commit (`--image-commit`)
- **Purpose**: Commit running container to image
- **Prerequisites**: Container must be running
- **Behavior**:
  - Verifies container is running
  - Creates new image from container's current state
  - Useful for capturing changes made inside container

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --image-commit
```

**Use Cases**:
- Saving installed packages or configuration changes
- Creating custom images with development state
- Preparing images for distribution

#### Push (`--image-push`)
- **Purpose**: Push image to Docker registry
- **Prerequisites**:
  - Image must exist locally
  - Docker login to registry
  - Write permissions to registry
- **Behavior**:
  - Verifies image exists locally
  - Checks Docker login status
  - Pushes image using `docker push`

**Example**:
```bash
./setup.sh -f containers/fabrinetes-dev/config.toml --image-push
```

---

## Configuration File Format

The script reads TOML configuration files with the following structure:

```toml
[config.container]
name = "fabrinetes-dev"

[config.image]
name = "ghcr.io/username/fabrinetes-dev"
tag = "latest"
```

**Key Fields**:
- `config.container.name`: Base name for container (script appends `.run`)
- `config.image.name`: Full image repository path
- `config.image.tag`: Image tag to use

**Container Naming Convention**:
- Container name from config: `fabrinetes-dev`
- Actual running container: `fabrinetes-dev.run`

---

## Common Workflows

### Development Workflow

#### 1. Initial Setup
```bash
# Pull latest image and start container
./setup.sh -f containers/fabrinetes-dev/config.toml --image-pull --run
```

#### 2. Make Changes Inside Container
```bash
# Access container and make changes
docker exec -it fabrinetes-dev.run bash

# Inside container: install packages, configure tools, etc.
```

#### 3. Save Changes
```bash
# Commit changes to new image
./setup.sh -f containers/fabrinetes-dev/config.toml --image-commit

# Push to registry for team use
./setup.sh -f containers/fabrinetes-dev/config.toml --image-push
```

### Build and Test Workflow

#### 1. Build Custom Image
```bash
# Build image from Dockerfile
./setup.sh -f containers/fabrinetes-dev/config.toml --image-build --run
```

#### 2. Test in Container
```bash
# Access container
docker exec -it fabrinetes-dev.run bash

# Run tests
```

#### 3. Iterate
```bash
# Stop container
./setup.sh -f containers/fabrinetes-dev/config.toml --stop

# Rebuild with changes
./setup.sh -f containers/fabrinetes-dev/config.toml --image-build

# Run again
./setup.sh -f containers/fabrinetes-dev/config.toml --run
```

### Daily Use Workflow

#### Start Day
```bash
# Start existing container
./setup.sh -f containers/fabrinetes-dev/config.toml --start
```

#### End Day
```bash
# Stop container to save resources
./setup.sh -f containers/fabrinetes-dev/config.toml --stop
```

#### Clean Restart
```bash
# Restart container if experiencing issues
./setup.sh -f containers/fabrinetes-dev/config.toml --restart
```

---

## Operation Chains

The script supports chaining multiple operations in a single command. Operations execute in a specific order:

**Execution Order**:
1. Image operations (in order specified)
   - `--image-pull`
   - `--image-build`
   - `--image-reuse`
   - `--image-commit`
   - `--image-push`
2. Container operations (in order specified)
   - `--stop`
   - `--start`
   - `--restart`
   - `--run`

**Example Chains**:

```bash
# Pull, verify, and run
./setup.sh -f config.toml --image-pull --image-reuse --run

# Stop, commit changes, and push
./setup.sh -f config.toml --stop --image-commit --image-push

# Build, commit, and push
./setup.sh -f config.toml --image-build --image-commit --image-push

# Complete workflow: build → run → commit → push
./setup.sh -f config.toml --image-build --run
# ... work in container ...
./setup.sh -f config.toml --stop --image-commit --image-push
```

---

## Safety Features

### Interactive Confirmations

The script prompts for confirmation in potentially destructive operations:

1. **Overwriting Existing Image**:
   - When building image that already exists
   - Bypass with `--force` flag

2. **Removing Existing Container**:
   - When running new container when one exists
   - Bypass with `--force` flag

### Validation Checks

- **Config file existence**: Verifies config file exists before proceeding
- **Container state**: Checks container state before operations
- **Image existence**: Verifies images exist for operations that need them
- **Docker login**: Checks authentication before push/pull operations

### Mutually Exclusive Flags

The script prevents conflicting operations (unless `--force` is used):

- `--image-pull` and `--image-build` (can't pull and build simultaneously)
- `--start` and `--run` (can't start existing and create new)

---

## Error Handling

### Pull Operation Errors

The script provides intelligent error analysis for pull failures:

| Error Type | Cause | Solution |
|------------|-------|----------|
| **Permission** | Access denied, unauthorized | Check Docker login and permissions |
| **Connectivity** | Network issues, timeout | Verify network connection, check firewall |
| **Not Found** | Image doesn't exist, wrong tag | Shows available images, verify image name |
| **Daemon** | Docker not running | Start Docker service |

### Common Error Messages

**"Container does not exist"**:
- **Cause**: Container hasn't been created yet
- **Solution**: Use `--run` to create container

**"Container is already running"**:
- **Cause**: Attempting to start already-running container
- **Solution**: Use `--restart` or `--stop` first

**"Image not found locally"**:
- **Cause**: Image doesn't exist for commit/push
- **Solution**: Use `--image-build` or `--image-pull` first

**"Not logged into Docker"**:
- **Cause**: Registry requires authentication
- **Solution**: Run `$FABRINETES_ROOT/scripts/docker-login.sh`

---

## Integration with Fabrinetes Ecosystem

### Relationship to Other Scripts

| Script | Purpose | Relationship |
|--------|---------|--------------|
| `fabrinetes` | Main wrapper, basic operations | `setup.sh` wraps `fabrinetes.py` for granular control |
| `fabrinetes.py` | Core Python implementation | Called by `setup.sh` for build/run operations |
| `scripts/docker-login.sh` | Docker registry authentication | Required before push/pull operations |

### Configuration Files

`setup.sh` uses the same configuration format as `fabrinetes.py`:
- Individual container configs: `containers/*/config.toml`
- Master config: `fabrinetes.config`

---

## Advanced Usage

### Using with Multiple Containers

```bash
# Manage different containers
./setup.sh -f containers/fabrinetes-dev/config.toml --run
./setup.sh -f containers/fabrinetes-dev-testing/config.toml --run

# Stop all
./setup.sh -f containers/fabrinetes-dev/config.toml --stop
./setup.sh -f containers/fabrinetes-dev-testing/config.toml --stop
```

### Force Mode

Skip interactive confirmations with `--force`:

```bash
# Force rebuild without confirmation
./setup.sh -f config.toml --image-build --force

# Force run, removing existing container
./setup.sh -f config.toml --run --force
```

### Path Resolution

The script automatically resolves config file paths:
- Relative paths resolved from current directory
- Absolute paths used as-is
- Validates config file exists before proceeding

**Example**:
```bash
# All equivalent if run from Fabrinetes root
./setup.sh -f containers/fabrinetes-dev/config.toml --run
./setup.sh -f ./containers/fabrinetes-dev/config.toml --run
./setup.sh -f /home/user/repo/Fabrinetes/containers/fabrinetes-dev/config.toml --run
```

---

## Troubleshooting

### Script Doesn't Find Container

**Problem**: "Container does not exist" error

**Solutions**:
1. Check container was created: `docker ps -a | grep fabrinetes`
2. Verify config file has correct container name
3. Use `--run` to create container first

### Image Pull Fails

**Problem**: "Failed to pull image" error

**Solutions**:
1. Check Docker login: Run `scripts/docker-login.sh`
2. Verify image name in config file
3. Check network connectivity
4. Review available images: `docker images`

### Container Won't Start

**Problem**: "Container failed to start" error

**Solutions**:
1. Check Docker daemon: `docker info`
2. Review container logs: `docker logs <container_name>`
3. Verify image exists: `docker images`
4. Try removing and recreating: `--run --force`

### Permission Errors

**Problem**: Permission denied errors

**Solutions**:
1. Verify user in docker group: `groups $USER`
2. Re-login after adding to docker group
3. Check Docker socket permissions: `ls -l /var/run/docker.sock`

---

## Best Practices

### 1. Development Workflow
- Use `--image-pull --run` for quick start with latest image
- Use `--image-commit` regularly to save work
- Use `--image-push` to share images with team

### 2. Image Management
- Tag images with meaningful versions
- Use `--image-commit` before making major changes
- Push committed images for backup and sharing

### 3. Container Lifecycle
- Use `--stop` when done to save resources
- Use `--restart` to fix container issues
- Use `--run --force` for clean slate

### 4. Safety
- Review prompts carefully before confirming
- Use `--image-reuse` to verify image before running
- Commit changes before stopping containers

### 5. Team Collaboration
- Document custom image versions in config
- Use consistent image tags across team
- Push images to shared registry regularly

---

## Examples by Use Case

### Use Case 1: New Team Member Setup

```bash
# Pull latest team image and start
./setup.sh -f containers/fabrinetes-dev/config.toml --image-pull --run

# Verify everything works
docker exec -it fabrinetes-dev.run bash -c "hdlforge --help"
```

### Use Case 2: Custom Development Environment

```bash
# Build custom image from Dockerfile
./setup.sh -f containers/fabrinetes-dev/config.toml --image-build --run

# Install additional tools inside container
docker exec -it fabrinetes-dev.run bash
# ... install tools ...
# ... exit container ...

# Commit and push for team
./setup.sh -f containers/fabrinetes-dev/config.toml --stop --image-commit --image-push
```

### Use Case 3: Testing New Configuration

```bash
# Build test image
./setup.sh -f containers/fabrinetes-dev-testing/config.toml --image-build --run

# Test inside container
docker exec -it fabrinetes-dev-testing.run bash -c "cd /root/repos/fpga && make test"

# Clean up if not needed
docker stop fabrinetes-dev-testing.run
docker rm fabrinetes-dev-testing.run
```

### Use Case 4: Daily Development Routine

```bash
# Morning: Start container
./setup.sh -f containers/fabrinetes-dev/config.toml --start

# Work all day...

# Evening: Stop container to save resources
./setup.sh -f containers/fabrinetes-dev/config.toml --stop

# Weekly: Commit changes
./setup.sh -f containers/fabrinetes-dev/config.toml --image-commit --image-push
```

---

## Comparison: setup.sh vs fabrinetes

| Feature | setup.sh | fabrinetes |
|---------|----------|-----------|
| **Purpose** | Granular lifecycle management | Quick build and run |
| **Operations** | 9+ operations | 2 operations (build, run) |
| **Image Management** | Full (pull, build, commit, push) | Build only |
| **Container Control** | Full (start, stop, restart, run) | Run only |
| **Safety Features** | Interactive confirmations | Basic |
| **Error Handling** | Detailed analysis | Basic |
| **Use Case** | Advanced workflows | Quick start |

**When to Use**:
- **Use setup.sh** for: Development workflows, image management, container lifecycle control
- **Use fabrinetes** for: Quick builds, simple container starts, basic operations

---

## Related Documentation

- **[Architecture](architecture.md)** - Core container architecture
- **[Docker Installation](docker-installation.md)** - Docker setup
- **[GitHub Container Registry](github-container-registry.md)** - Registry setup
- **[Testing Guide](testing_guide.md)** - Testing procedures
- **[Main README](../../README.md)** - Project overview

---

## Document History

**Last Updated:** 2025-11-12 (Created)

