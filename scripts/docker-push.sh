#!/bin/bash

# Docker Push Script
# This script pushes Fabrinetes images to Docker Hub

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
    echo "Usage: $0 USERNAME [TAG]"
    echo ""
    echo "Push Fabrinetes image to Docker Hub"
    echo ""
    echo "Arguments:"
    echo "  USERNAME    Docker Hub username (required)"
    echo "  TAG         Image tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 ykarmon"
    echo "  $0 ykarmon v1.0"
    echo "  $0 ykarmon latest"
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

# Get arguments
if [[ -z "$1" ]]; then
    print_error "Username is required"
    show_usage
    exit 1
fi

USERNAME="$1"
TAG="${2:-latest}"

print_header "DOCKER PUSH - FABRINETES"
print_info "Username: $USERNAME"
print_info "Image: $IMAGE_NAME"
print_info "Tag: $TAG"
echo ""

# Find source image
print_info "Looking for source image..."
source_images=$(docker images | grep -E "(fabrinetes|ykarmon)" | head -1)

if [[ -z "$source_images" ]]; then
    print_error "No Fabrinetes images found locally"
    print_info "Available images:"
    docker images
    exit 1
fi

# Extract source image name and tag
source_image=$(echo "$source_images" | awk '{print $1":"$2}')
print_info "Found source image: $source_image"

# Tag the image
print_info "Tagging image for Docker Hub..."
docker tag "$source_image" "$IMAGE_NAME:$TAG"
print_success "Image tagged as: $IMAGE_NAME:$TAG"

# Check if logged in
print_info "Checking Docker Hub authentication..."
if ! docker info | grep -q "Username:"; then
    print_warning "Not logged into Docker Hub"
    print_info "Please run: ./docker-login.sh $USERNAME"
    exit 1
fi

# Push the image
print_info "Pushing image to Docker Hub..."
if docker push "$IMAGE_NAME:$TAG"; then
    print_success "Successfully pushed $IMAGE_NAME:$TAG to Docker Hub"
    print_data "Image URL: https://hub.docker.com/r/$IMAGE_NAME"
    print_data "Pull command: docker pull $IMAGE_NAME:$TAG"
else
    print_error "Failed to push image to Docker Hub"
    exit 1
fi

print_header "SUMMARY"
print_success "Push completed successfully!"
print_info "Image is now available at: https://hub.docker.com/r/$IMAGE_NAME"

