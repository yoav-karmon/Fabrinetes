#!/bin/bash

# Fabrinetes Container and Image Management Script
# Provides fine-grained control over container and image operations
#
# Usage: ./setup.sh -f <config_file> [OPTIONS]
#   -f, --config-file: Path to config.toml file (required)
#   Options: --start, --stop, --restart, --run, --image-pull, --image-build, --image-reuse, --image-commit, --image-push

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$SCRIPT_DIR"

# Print functions
print_info() { echo "[INFO] $1"; }
print_success() { echo "[SUCCESS] $1"; }
print_error() { echo "[ERROR] $1"; }
print_warning() { echo "[WARNING] $1"; }

# Show usage/help
show_usage() {
    cat << EOF
Fabrinetes Container and Image Management

Usage: $0 -f <config_file> [OPTIONS]

Required:
  -f, --config-file <file>    Path to config.toml file

Container Operations:
  -s, --start                 Start existing stopped container
                              (automatically runs X11 setup after start)
  -S, --stop                  Stop running container
  -r, --run                   Run container from image
  -x, --setup-x11             Manually run X11 setup for running container

Image Operations:
  -p, --image-pull            Pull image from Docker registry
  -b, --image-build           Build image from scratch
  -u, --image-reuse           Use existing local image (verify only)
  -c, --image-commit          Commit running container to image
  -P, --image-push            Push image to registry

Other:
  -h, --help                  Show this help message

Notes:
  - X11 setup (copy .Xauthority and create DISPLAY env file) runs automatically
    after successful container start or restart operations
  - Use '--setup-x11' flag to manually run X11 setup for a running container

Examples:
  # Pull image and run container
  $0 -f config.toml --image-pull --run

  # Build image and run container
  $0 -f config.toml --image-build --run

  # Stop container, commit as image, push
  $0 -f config.toml --stop --image-commit --image-push

  # Reuse existing image and run
  $0 -f config.toml --image-reuse --run

  # Run and start container (combine -r and -s)
  $0 -f config.toml --run --start

  # Stop and start container (combine -S and -s)
  $0 -f config.toml --stop --start

  # Manually run X11 setup for running container
  $0 -f config.toml --setup-x11
EOF
}

# Parse arguments
CONFIG_FILE=""
FLAG_START=false
FLAG_STOP=false
FLAG_RUN=false
FLAG_IMAGE_PULL=false
FLAG_IMAGE_BUILD=false
FLAG_IMAGE_REUSE=false
FLAG_IMAGE_COMMIT=false
FLAG_IMAGE_PUSH=false
FLAG_FORCE=false
FLAG_SETUP_X11=false

parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            -f|--config-file)
                CONFIG_FILE="$2"
                shift 2
                ;;
            -s|--start)
                FLAG_START=true
                shift
                ;;
            -S|--stop)
                FLAG_STOP=true
                shift
                ;;
            -r|--run)
                FLAG_RUN=true
                shift
                ;;
            -p|--image-pull)
                FLAG_IMAGE_PULL=true
                shift
                ;;
            -b|--image-build)
                FLAG_IMAGE_BUILD=true
                shift
                ;;
            -u|--image-reuse)
                FLAG_IMAGE_REUSE=true
                shift
                ;;
            -c|--image-commit)
                FLAG_IMAGE_COMMIT=true
                shift
                ;;
            -P|--image-push)
                FLAG_IMAGE_PUSH=true
                shift
                ;;
            -x|--setup-x11)
                FLAG_SETUP_X11=true
                shift
                ;;
            --force)
                FLAG_FORCE=true
                shift
                ;;
            -h|--help)
                show_usage
                exit 0
                ;;
            -i|--image-id)
                # Legacy flag, ignore for now
                shift 2
                ;;
            *)
                print_error "Unknown option: $1"
                show_usage
                exit 1
                ;;
        esac
    done

    # Validate config file is provided
    if [ -z "$CONFIG_FILE" ]; then
        print_error "Config file is required"
        show_usage
        exit 1
    fi

    # Resolve config file path
    if [[ ! "$CONFIG_FILE" = /* ]]; then
        if [[ "$CONFIG_FILE" == */* ]]; then
            CONFIG_FILE="$(cd "$(dirname "$CONFIG_FILE")" && pwd)/$(basename "$CONFIG_FILE")"
        else
            CONFIG_FILE="$(pwd)/$CONFIG_FILE"
        fi
    fi

    # Validate config file exists
    if [ ! -f "$CONFIG_FILE" ]; then
        print_error "Config file not found: $CONFIG_FILE"
        exit 1
    fi

    # Check if any operation flags are provided
    local has_operation=false
    if $FLAG_START || $FLAG_STOP || $FLAG_RUN || \
       $FLAG_IMAGE_PULL || $FLAG_IMAGE_BUILD || $FLAG_IMAGE_REUSE || \
       $FLAG_IMAGE_COMMIT || $FLAG_IMAGE_PUSH || $FLAG_SETUP_X11; then
        has_operation=true
    fi

    if [ "$has_operation" = false ]; then
        print_error "No operation specified. Please provide at least one operation flag."
        echo ""
        show_usage
        exit 1
    fi

    # Validate mutually exclusive flags
    if $FLAG_IMAGE_PULL && $FLAG_IMAGE_BUILD && [ "$FLAG_FORCE" = false ]; then
        print_error "--image-pull and --image-build are mutually exclusive (use --force to override)"
        exit 1
    fi

    if $FLAG_START && $FLAG_RUN && [ "$FLAG_FORCE" = false ]; then
        print_error "--start and --run are mutually exclusive (use --force to override)"
        exit 1
    fi
}

# Extract config information
extract_config_info() {
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
}

# Check container status
check_container_status() {
    # Check if running
    if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_RUN_NAME}$"; then
        echo "running"
        return
    fi
    
    # Check if stopped
    if docker ps -a --format '{{.Names}}' | grep -q "^${CONTAINER_RUN_NAME}$"; then
        echo "stopped"
        return
    fi
    
    echo "none"
}

# Check if image exists locally
check_image_exists() {
    if docker images --format '{{.Repository}}:{{.Tag}}' | grep -q "^${IMAGE_FULL}$"; then
        return 0
    else
        return 1
    fi
}

# Check Docker login status
check_docker_login() {
    if docker info 2>/dev/null | grep -q "Username:"; then
        return 0
    else
        return 1
    fi
}

# Analyze docker pull error
analyze_pull_error() {
    local error_output="$1"
    local error_lower=$(echo "$error_output" | tr '[:upper:]' '[:lower:]')
    
    if echo "$error_lower" | grep -qiE "permission denied|access denied|unauthorized"; then
        echo "permission"
    elif echo "$error_lower" | grep -qiE "connection refused|network|timeout|dial tcp|no route to host"; then
        echo "connectivity"
    elif echo "$error_lower" | grep -qiE "not found|manifest unknown|repository.*not found|pull access denied"; then
        echo "not_found"
    elif echo "$error_lower" | grep -qiE "connection aborted|no such file or directory"; then
        echo "daemon"
    else
        echo "unknown"
    fi
}

# Show available images from repository
show_available_images() {
    local repo_name="$1"
    echo "[INFO] Available images from repository '$repo_name':"
    docker images "$repo_name" --format 'table {{.Repository}}\t{{.Tag}}\t{{.CreatedSince}}' 2>/dev/null || echo "[INFO] No images found from this repository"
}

# Image operations
image_pull() {
    print_info "Pulling image: $IMAGE_FULL"
    
    # Check Docker login
    if ! check_docker_login; then
        print_warning "Not logged into Docker"
        print_info "Please run: $FABRINETES_ROOT/scripts/docker-login.sh"
        exit 1
    fi
    
    # Attempt pull
    local pull_output
    pull_output=$(docker pull "$IMAGE_FULL" 2>&1) || {
        local pull_error="$pull_output"
        local error_type=$(analyze_pull_error "$pull_error")
        
        case "$error_type" in
            permission)
                print_error "Permission denied - check Docker permissions"
                ;;
            connectivity)
                print_error "Network connectivity issue - check Docker connectivity"
                ;;
            not_found)
                print_error "Image not found: $IMAGE_FULL"
                # Extract repository name and show available images
                local repo_name=$(echo "$IMAGE_NAME" | cut -d'/' -f1)
                show_available_images "$repo_name"
                ;;
            daemon)
                print_error "Docker daemon not running - start Docker service"
                ;;
            *)
                print_error "Failed to pull image: $IMAGE_FULL"
                echo "$pull_error"
                ;;
        esac
        exit 1
    }
    
    print_success "Successfully pulled image: $IMAGE_FULL"
}

image_build() {
    print_info "Building image: $IMAGE_FULL"
    
    # Check if image exists and ask before overwriting
    if check_image_exists && [ "$FLAG_FORCE" = false ]; then
        print_warning "Image $IMAGE_FULL already exists"
        read -p "Do you want to rebuild it? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Build cancelled"
            return 0
        fi
    fi
    
    cd "$FABRINETES_ROOT"
    if ! "$FABRINETES_ROOT/fabrinetes.py" --cmd build --config-file "$CONFIG_FILE" | bash; then
        print_error "Image build failed"
        exit 1
    fi
    
    # Verify image was created
    if check_image_exists; then
        print_success "Image built successfully: $IMAGE_FULL"
    else
        print_error "Image $IMAGE_FULL was not created"
        exit 1
    fi
}

image_reuse() {
    print_info "Checking for existing local image: $IMAGE_FULL"
    
    if check_image_exists; then
        print_success "Image exists locally: $IMAGE_FULL"
    else
        print_error "Image not found locally: $IMAGE_FULL"
        exit 1
    fi
}

image_commit() {
    print_info "Committing container to image: $IMAGE_FULL"
    
    local container_status=$(check_container_status)
    if [ "$container_status" != "running" ]; then
        print_error "Container $CONTAINER_RUN_NAME is not running (status: $container_status)"
        exit 1
    fi
    
    if docker commit "$CONTAINER_RUN_NAME" "$IMAGE_FULL"; then
        print_success "Successfully committed container to image: $IMAGE_FULL"
    else
        print_error "Failed to commit container to image"
        exit 1
    fi
}

image_push() {
    print_info "Pushing image: $IMAGE_FULL"
    
    # Check if image exists locally
    if ! check_image_exists; then
        print_error "Image not found locally: $IMAGE_FULL"
        exit 1
    fi
    
    # Check Docker login
    if ! check_docker_login; then
        print_warning "Not logged into Docker"
        print_info "Please run: $FABRINETES_ROOT/scripts/docker-login.sh"
        exit 1
    fi
    
    if docker push "$IMAGE_FULL"; then
        print_success "Successfully pushed image: $IMAGE_FULL"
    else
        print_error "Failed to push image: $IMAGE_FULL"
        exit 1
    fi
}

# Setup X11 for container
setup_x11_for_container() {
    print_info "Setting up X11 for container: $CONTAINER_RUN_NAME"
    
    # Check if container is running
    local container_status=$(check_container_status)
    if [ "$container_status" != "running" ]; then
        print_error "Container is not running, cannot setup X11"
        exit 1
    fi
    
    # Run setup-x11 command and pipe to bash
    cd "$FABRINETES_ROOT"
    if ! "$FABRINETES_ROOT/fabrinetes.py" --cmd setup-x11 --config-file "$CONFIG_FILE" | bash; then
        print_error "X11 setup failed"
        exit 1
    fi
    
    print_success "X11 setup completed for container: $CONTAINER_RUN_NAME"
}

# Container operations
container_start() {
    print_info "Starting container: $CONTAINER_RUN_NAME"
    
    local container_status=$(check_container_status)
    case "$container_status" in
        running)
            print_warning "Container is already running"
            # Still run setup-x11 even if already running
            setup_x11_for_container
            return 0
            ;;
        stopped)
            if docker start "$CONTAINER_RUN_NAME"; then
                print_success "Container started: $CONTAINER_RUN_NAME"
                # Setup X11 after successful start
                setup_x11_for_container
            else
                print_error "Failed to start container"
                exit 1
            fi
            ;;
        none)
            print_error "Container does not exist: $CONTAINER_RUN_NAME"
            exit 1
            ;;
    esac
}

container_stop() {
    print_info "Stopping container: $CONTAINER_RUN_NAME"
    
    local container_status=$(check_container_status)
    case "$container_status" in
        running)
            if docker stop "$CONTAINER_RUN_NAME"; then
                print_success "Container stopped: $CONTAINER_RUN_NAME"
            else
                print_error "Failed to stop container"
                exit 1
            fi
            ;;
        stopped)
            print_warning "Container is already stopped"
            return 0
            ;;
        none)
            print_error "Container does not exist: $CONTAINER_RUN_NAME"
            exit 1
            ;;
    esac
}

container_run() {
    print_info "Running container: $CONTAINER_RUN_NAME"
    
    # Run container - let fabrinetes.py handle everything
    # If container doesn't exist or fails, it will fail
    cd "$FABRINETES_ROOT"
    if ! "$FABRINETES_ROOT/fabrinetes.py" --cmd run --config-file "$CONFIG_FILE" | bash; then
        print_error "Container run failed"
        exit 1
    fi
    
    print_success "Container run command executed: $CONTAINER_RUN_NAME"
}

# Main execution
main() {
    # Parse arguments
    parse_arguments "$@"
    
    # Extract config information
    extract_config_info
    
    print_info "Config: $CONFIG_FILE"
    print_info "Container: $CONTAINER_RUN_NAME"
    print_info "Image: $IMAGE_FULL"
    echo ""
    
    # Execute image operations first
    if $FLAG_IMAGE_PULL; then
        image_pull
    fi
    
    if $FLAG_IMAGE_BUILD; then
        image_build
    fi
    
    if $FLAG_IMAGE_REUSE; then
        image_reuse
    fi
    
    if $FLAG_IMAGE_COMMIT; then
        image_commit
    fi
    
    if $FLAG_IMAGE_PUSH; then
        image_push
    fi
    
    # Execute container operations second
    if $FLAG_STOP; then
        container_stop
    fi
    
    if $FLAG_START; then
        container_start
    fi
    
    if $FLAG_RUN; then
        container_run
    fi
    
    if $FLAG_SETUP_X11; then
        setup_x11_for_container
    fi
    
    print_success "Operations completed successfully"
}

# Run main function
main "$@"
