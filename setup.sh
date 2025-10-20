#!/bin/bash

# Simple Docker Image Setup Script

set -e

print_info() { echo "$1"; }
print_success() { echo "[SUCCESS] $1"; }
print_warning() { echo "[WARNING] $1"; }
print_error() { echo "[ERROR] $1"; }

show_usage() {
    echo "Usage: $0 [OPTIONS]"
    echo "  --pull IMAGE     Pull specific image"
    echo "  --force          Force remove local image before pulling"
    echo "  --info           Show available images only"
    echo "  --create-config  Create .devcontainer/devcontainer.json config file"
    echo "  -h, --help       Show help"
    echo ""
    echo "Examples:"
    echo "  $0 --info"
    echo "  $0 --pull ykarmon/fabrinetes:latest"
    echo "  $0 --pull ykarmon/fabrinetes:latest --force"
    echo "  $0 --create-config"
    echo "  $0"
}

# Parse arguments
INTERACTIVE=true
PULL_IMAGE=""
SHOW_INFO=false
FORCE=false
CREATE_CONFIG=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --pull) PULL_IMAGE="$2"; INTERACTIVE=false; shift 2 ;;
        --force) FORCE=true; shift ;;
        --info) SHOW_INFO=true; INTERACTIVE=false; shift ;;
        --create-config) CREATE_CONFIG=true; INTERACTIVE=false; shift ;;
        -h|--help) show_usage; exit 0 ;;
        *) print_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

# Show available images
show_images() {
    print_info "Available images:"
    curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | \
    jq -r '.results[] | "ykarmon/fabrinetes:\(.name) - \(.last_updated) - \(.full_size | . / 1024 / 1024 | floor)MB"' 2>/dev/null || {
        print_error "Failed to fetch images"
        exit 1
    }
}

# Pull image - let Docker handle everything
pull_image() {
    local image="$1"
    
    # Force remove local image if --force flag is used
    if [[ "$FORCE" == "true" ]]; then
        print_info "Force removing local image $image..."
        echo "Command: docker rmi $image"
        echo "=========================================="
        echo "START OF DOCKER OUTPUT"
        echo "=========================================="
        docker rmi "$image" 2>/dev/null || print_warning "Image $image not found locally or already removed"
        echo "=========================================="
        echo "END OF DOCKER OUTPUT"
        echo "=========================================="
    fi
    
    print_info "Pulling $image..."
    echo "Command: docker pull $image"
    echo "=========================================="
    echo "START OF DOCKER OUTPUT"
    echo "=========================================="
    docker pull "$image"
    echo "=========================================="
    echo "END OF DOCKER OUTPUT"
    echo "=========================================="
    print_success "Image pulled successfully!"
}

# Create devcontainer configuration
create_devcontainer_config() {
    local project_dir="$(pwd)"
    local devcontainer_dir="$project_dir/.devcontainer"
    local config_file="$devcontainer_dir/devcontainer.json"
    
    print_info "Creating devcontainer configuration..."
    
    # Create .devcontainer directory if it doesn't exist
    if [[ ! -d "$devcontainer_dir" ]]; then
        mkdir -p "$devcontainer_dir"
        print_info "Created directory: $devcontainer_dir"
    fi
    
    # Check if config file already exists
    if [[ -f "$config_file" ]]; then
        print_warning "Configuration file already exists: $config_file"
        read -p "Do you want to overwrite it? (y/N): " overwrite
        if [[ "$overwrite" != "y" && "$overwrite" != "Y" ]]; then
            print_info "Skipping configuration creation."
            return 0
        fi
    fi
    
    # Get current user info
    local current_user="${USER:-$(whoami)}"
    local current_uid="$(id -u)"
    local current_gid="$(id -g)"
    local current_home="$HOME"
    
    # Create the devcontainer.json content
    cat > "$config_file" << EOF
{
  "name": "Fabrinetes Dev Container",
  "image": "ykarmon/fabrinetes:latest",
  "remoteUser": "$current_user",
  "workspaceFolder": "/home/$current_user/workspace",
  "containerEnv": {
    "CONTAINER_USER": "$current_user",
    "CONTAINER_UID": "$current_uid",
    "CONTAINER_GID": "$current_gid",
    "CONTAINER_HOME": "/home/$current_user",
    "WORKDIR": "$project_dir"
  },
  "mounts": [
    "source=\${localWorkspaceFolder},target=/home/$current_user/workspace,type=bind"
  ],
  "postCreateCommand": "echo 'Dev container ready!'",
  "customizations": {
    "vscode": {
      "extensions": [
        "ms-python.python",
        "ms-vscode.vscode-json"
      ]
    }
  }
}
EOF
    
    print_success "Created devcontainer configuration: $config_file"
    print_info "Configuration includes:"
    print_info "  - Image: ykarmon/fabrinetes:latest"
    print_info "  - User: $current_user (UID: $current_uid)"
    print_info "  - Workspace: /home/$current_user/workspace"
    print_info "  - Environment variables for container setup"
    print_info ""
    print_info "To use this configuration:"
    print_info "  1. Open this directory in Cursor"
    print_info "  2. Cursor will detect the .devcontainer/devcontainer.json"
    print_info "  3. Attach to your running container"
    print_info "  4. Cursor will connect as user '$current_user'"
}

# Main execution
print_info "Docker Image Setup"

if [[ "$SHOW_INFO" == "true" ]]; then
    show_images
elif [[ "$CREATE_CONFIG" == "true" ]]; then
    create_devcontainer_config
elif [[ -n "$PULL_IMAGE" ]]; then
    pull_image "$PULL_IMAGE"
else
    show_images
    echo ""
    print_info "Additional options:"
    print_info "  - Create devcontainer config: $0 --create-config"
    echo ""
    read -p "Enter image to pull (e.g., ykarmon/fabrinetes:latest) or 'q' to quit: " selected_image
    if [[ "$selected_image" != "q" ]]; then
        pull_image "$selected_image"
    fi
fi

print_success "Done!"