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
    echo "  -h, --help       Show help"
    echo ""
    echo "Examples:"
    echo "  $0 --info"
    echo "  $0 --pull ykarmon/fabrinetes:latest"
    echo "  $0 --pull ykarmon/fabrinetes:latest --force"
    echo "  $0"
}

# Parse arguments
INTERACTIVE=true
PULL_IMAGE=""
SHOW_INFO=false
FORCE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --pull) PULL_IMAGE="$2"; INTERACTIVE=false; shift 2 ;;
        --force) FORCE=true; shift ;;
        --info) SHOW_INFO=true; INTERACTIVE=false; shift ;;
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

# Main execution
print_info "Docker Image Setup"

if [[ "$SHOW_INFO" == "true" ]]; then
    show_images
elif [[ -n "$PULL_IMAGE" ]]; then
    pull_image "$PULL_IMAGE"
else
    show_images
    read -p "Enter image to pull (e.g., ykarmon/fabrinetes:latest) or 'q' to quit: " selected_image
    if [[ "$selected_image" != "q" ]]; then
        pull_image "$selected_image"
    fi
fi

print_success "Done!"