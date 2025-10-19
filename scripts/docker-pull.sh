#!/bin/bash

# Docker Pull Script
# This script pulls Fabrinetes images from Docker Hub (public access)

set -e

# Configuration
IMAGE_NAME="ykarmon/fabrinetes"
REGISTRY="docker.io"

# Colors for output
RED=''''
GREEN=''''
YELLOW=''''
BLUE=''''
CYAN=''''
MAGENTA=''''
NC='''' # No Color

print_header() {
    echo "================================"
    echo "$1"
    echo "================================"
}

print_info() {
    echo "$1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_error() {
    echo "[ERROR] $1"
}

print_data() {
    echo -e "${MAGENTA}$1${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [TAG]"
    echo ""
    echo "Pull Fabrinetes image from Docker Hub (public access)"
    echo ""
    echo "Arguments:"
    echo "  TAG         Image tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 latest"
    echo "  $0 v1.0"
}

# Check if Docker is available
if ! command -v docker >/dev/null 2>&1; then
    print_error "Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker daemon is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker daemon is not running"
    exit 1
fi

# Get tag from argument
TAG="${1:-latest}"

print_header "DOCKER PULL - FABRINETES"
print_info "Image: $IMAGE_NAME"
print_info "Tag: $TAG"
print_info "Registry: $REGISTRY"
print_info "Public access - no authentication required"
echo ""

# Check if image already exists locally
print_info "Checking for existing local image..."
if docker images | grep -q "$IMAGE_NAME.*$TAG"; then
    print_info "Image $IMAGE_NAME:$TAG already exists locally"
    print_data "Current local images:"
    docker images | grep "$IMAGE_NAME"
    echo ""
    read -p "Do you want to pull the latest version? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        print_info "Pull cancelled"
        exit 0
    fi
fi

# Pull the image
print_info "Pulling image from Docker Hub..."
if docker pull "$IMAGE_NAME:$TAG"; then
    print_success "Successfully pulled $IMAGE_NAME:$TAG from Docker Hub"
    
    # Show image info
    print_info "Image information:"
    docker images "$IMAGE_NAME:$TAG" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"
    
    echo ""
    print_data "Image size: $(docker images "$IMAGE_NAME:$TAG" --format "{{.Size}}")"
    print_data "Image ID: $(docker images "$IMAGE_NAME:$TAG" --format "{{.ID}}")"
    
else
    print_error "Failed to pull image from Docker Hub"
    print_info "Make sure the image exists and is public"
    print_data "Check: https://hub.docker.com/r/$IMAGE_NAME"
    exit 1
fi

echo ""

# Show usage instructions
print_header "USAGE INSTRUCTIONS"
print_data "Run the image: docker run -it $IMAGE_NAME:$TAG"
print_data "Run with volume: docker run -it -v \$(pwd):/workspace $IMAGE_NAME:$TAG"
print_data "Run in background: docker run -d $IMAGE_NAME:$TAG"

print_header "SUMMARY"
print_success "Pull completed successfully!"
print_info "Image is now available locally as: $IMAGE_NAME:$TAG"
print_info "Docker Hub URL: https://hub.docker.com/r/$IMAGE_NAME"

