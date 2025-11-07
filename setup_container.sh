#!/bin/bash

# HDLForge Integration Test / Container Setup
# Tests the complete workflow: clean, build, run container, compile and simulate example project
#
# Usage: ./setup_container.sh <config_file>
#   config_file: Path to config.toml file (required)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$SCRIPT_DIR"

# Config file is required
if [ -z "$1" ]; then
    echo "[ERROR] Config file is required"
    echo "Usage: $0 <config_file>"
    echo "Example: $0 containers/fabrinetes-dev-docker/config.toml"
    exit 1
fi

CONFIG_FILE="$1"
# If relative path, make it relative to FABRINETES_ROOT
if [[ ! "$CONFIG_FILE" = /* ]]; then
    CONFIG_FILE="$FABRINETES_ROOT/$CONFIG_FILE"
fi

# Validate config file exists
if [ ! -f "$CONFIG_FILE" ]; then
    echo "[ERROR] Config file not found: $CONFIG_FILE"
    echo "Usage: $0 <config_file>"
    exit 1
fi

EXAMPLE_PROJECT="$FABRINETES_ROOT/examples/addr_32bit"

print_info() { echo "[INFO] $1"; }
print_success() { echo "[SUCCESS] $1"; }
print_error() { echo "[ERROR] $1"; }
print_warning() { echo "[WARNING] $1"; }

# Get container name from config
CONTAINER_NAME=$(grep -A 2 "\[config.container\]" "$CONFIG_FILE" | grep "name" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/')
if [ -z "$CONTAINER_NAME" ]; then
    print_error "Could not extract container name from config"
    exit 1
fi
CONTAINER_RUN_NAME="${CONTAINER_NAME}.run"

# Get image name from config
IMAGE_NAME=$(grep -A 3 "\[config.image\]" "$CONFIG_FILE" | grep "name" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/')
IMAGE_TAG=$(grep -A 3 "\[config.image\]" "$CONFIG_FILE" | grep "tag" | head -1 | sed 's/.*= *"\([^"]*\)".*/\1/')
if [ -z "$IMAGE_NAME" ] || [ -z "$IMAGE_TAG" ]; then
    print_error "Could not extract image name/tag from config"
    print_error "Image name: '$IMAGE_NAME', Tag: '$IMAGE_TAG'"
    exit 1
fi
IMAGE_FULL="${IMAGE_NAME}:${IMAGE_TAG}"

print_info "HDLForge Integration Test / Container Setup"
print_info "==========================================="
print_info "Config: $CONFIG_FILE"
print_info "Container: $CONTAINER_RUN_NAME"
print_info "Image: $IMAGE_FULL"
print_info "Example: $EXAMPLE_PROJECT"
echo ""

# Step 1: Clean - Remove running container and image
print_info "Step 1: Cleaning existing container and image..."
if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_RUN_NAME}$"; then
    print_info "Stopping and removing container: $CONTAINER_RUN_NAME"
    docker stop "$CONTAINER_RUN_NAME" 2>/dev/null || true
    docker rm "$CONTAINER_RUN_NAME" 2>/dev/null || true
    print_success "Container removed"
else
    print_info "No existing container found"
fi

if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_FULL}$"; then
    print_info "Removing image: $IMAGE_FULL"
    docker rmi "$IMAGE_FULL" 2>/dev/null || true
    print_success "Image removed"
else
    print_info "No existing image found"
fi
echo ""

# Step 2: Rebuild image
print_info "Step 2: Rebuilding image with fabrinetes.py..."
print_info "  This will: 1) Create temp container, 2) Set it up, 3) Commit as image, 4) Remove temp container"
cd "$FABRINETES_ROOT"
if ! "$FABRINETES_ROOT/fabrinetes.py" --cmd build --config-file "$CONFIG_FILE" | bash; then
    print_error "Image build failed"
    exit 1
fi

# Verify temp container was removed
TEMP_CONTAINER="${CONTAINER_NAME}-build-temp"
if docker ps -a --format '{{.Names}}' | grep -q "^${TEMP_CONTAINER}$"; then
    print_error "Temporary build container ${TEMP_CONTAINER} still exists (should have been removed)"
    exit 1
else
    print_success "Temporary build container removed (as expected)"
fi

# Verify image was created
if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_FULL}$"; then
    print_success "Image created successfully: $IMAGE_FULL"
else
    print_error "Image $IMAGE_FULL was not created"
    exit 1
fi
echo ""

# Step 3: Run fresh container from committed image
print_info "Step 3: Running fresh container from committed image with fabrinetes.py --cmd run..."
if ! "$FABRINETES_ROOT/fabrinetes.py" --cmd run --config-file "$CONFIG_FILE" | bash; then
    print_error "Container run failed"
    exit 1
fi

# Wait a moment for container to start
sleep 2

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_RUN_NAME}$"; then
    print_success "Container running: $CONTAINER_RUN_NAME"
else
    print_error "Container failed to start"
    exit 1
fi

# Verify mount: ~/repo/Fabrinetes is mounted to $HOME/repo/Fabrinetes
print_info "Verifying mount: ~/repo/Fabrinetes -> \$HOME/repo/Fabrinetes"
HOST_REPO_PATH="$HOME/repo/Fabrinetes"
CONTAINER_REPO_PATH="/home/$(whoami)/repo/Fabrinetes"

if docker exec --user "$(whoami)" "$CONTAINER_RUN_NAME" test -d "$CONTAINER_REPO_PATH"; then
    print_success "Mount verified: $CONTAINER_REPO_PATH exists in container"
    
    # Verify it's actually the same directory (check for a known file)
    if docker exec --user "$(whoami)" "$CONTAINER_RUN_NAME" test -f "$CONTAINER_REPO_PATH/fabrinetes.py"; then
        print_success "Mount verified: fabrinetes.py found at $CONTAINER_REPO_PATH"
    else
        print_error "Mount issue: fabrinetes.py not found at $CONTAINER_REPO_PATH"
        exit 1
    fi
else
    print_error "Mount failed: $CONTAINER_REPO_PATH does not exist in container"
    print_error "Expected mount: $HOST_REPO_PATH -> $CONTAINER_REPO_PATH"
    exit 1
fi
echo ""

# Step 4: Wait for entrypoint to complete
print_info "Step 4: Waiting for container initialization..."
sleep 3
echo ""

# Step 5: Compile example project (build step)
print_info "Step 5: Compiling example project with Verilator (build step)..."
cd "$FABRINETES_ROOT"

# Use container path for hdlforge (mounted from host)
CONTAINER_HDLFORGE_PATH="$CONTAINER_REPO_PATH/hdlforge/project_setup/hdlforge"

# Use container path for example project (mounted from host)
CONTAINER_EXAMPLE_PROJECT="$CONTAINER_REPO_PATH/examples/addr_32bit"

if "$FABRINETES_ROOT/fabrinetes.py" --cmd exec --config-file "$CONFIG_FILE" \
    --exec-cmd "cd $CONTAINER_EXAMPLE_PROJECT && update_repo_path && $CONTAINER_HDLFORGE_PATH Verilator --project addr_32bit.hdlforge.toml --step build --SimTargetName basic_test" | bash 2>&1; then
    print_success "Example project compiled successfully!"
    
    # Verify the executable was created
    if docker exec --user "$(whoami)" "$CONTAINER_RUN_NAME" test -f "$CONTAINER_EXAMPLE_PROJECT/_verilator/addr_32bit_top"; then
        print_success "Verilator executable created: addr_32bit_top"
    else
        print_warning "Executable not found (but build reported success)"
    fi
else
    print_error "Example project compilation failed"
    exit 1
fi
echo ""

# Step 6: Run simulation (sim step)
print_info "Step 6: Running simulation with Verilator (sim step)..."
cd "$FABRINETES_ROOT"

if "$FABRINETES_ROOT/fabrinetes.py" --cmd exec --config-file "$CONFIG_FILE" \
    --exec-cmd "cd $CONTAINER_EXAMPLE_PROJECT && update_repo_path && $CONTAINER_HDLFORGE_PATH Verilator --project addr_32bit.hdlforge.toml --step sim --SimTargetName basic_test" | bash 2>&1; then
    print_success "Simulation completed successfully!"
    
    # Verify simulation artifacts were created (VCD file, etc.)
    if docker exec --user "$(whoami)" "$CONTAINER_RUN_NAME" test -d "$CONTAINER_EXAMPLE_PROJECT/_verilator"; then
        print_success "Simulation artifacts directory exists"
    else
        print_warning "Simulation artifacts directory not found (but simulation reported success)"
    fi
else
    print_error "Simulation failed"
    exit 1
fi
echo ""

print_success "All tests passed!"
print_info "Container: $CONTAINER_RUN_NAME"
print_info "Image: $IMAGE_FULL"
print_info "Example project compiled and simulated successfully"

