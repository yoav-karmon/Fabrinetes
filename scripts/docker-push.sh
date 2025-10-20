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

print_warning() {
    echo "[WARNING] $1"
}

# Function to check if tag exists on Docker Hub
check_tag_exists() {
    local tag="$1"
    local exists=$(curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | jq -r ".results[] | select(.name == \"$tag\") | .name" 2>/dev/null)
    [[ -n "$exists" ]]
}

# Function to get tag details
get_tag_info() {
    local tag="$1"
    curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | jq -r ".results[] | select(.name == \"$tag\") | \"Size: \(.full_size)B (\(.full_size | . / 1024 / 1024 | floor)MB) - Updated: \(.last_updated)\"" 2>/dev/null
}

# Function to show usage
show_usage() {
    echo "Usage: $0 USERNAME IMAGE_ID [TAG]"
    echo ""
    echo "Push Docker image to Docker Hub"
    echo ""
    echo "Arguments:"
    echo "  USERNAME    Docker Hub username (required)"
    echo "  IMAGE_ID    Full image ID or name:tag to push (required)"
    echo "  TAG         Target tag on Docker Hub (optional, uses IMAGE_ID tag if not specified)"
    echo ""
    echo "Examples:"
    echo "  $0 ykarmon fabrinetes-local:latest"
    echo "  $0 ykarmon sha256:abc123... v1.0"
    echo "  $0 ykarmon ykarmon/fabrinetes:latest"
    echo ""
    echo "Note: Script will check if tag exists on Docker Hub and ask for confirmation to overwrite"
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

if [[ -z "$2" ]]; then
    print_error "Image ID is required"
    echo ""
    print_info "Available images:"
    docker images
    echo ""
    show_usage
    exit 1
fi

USERNAME="$1"
SOURCE_IMAGE="$2"
TARGET_TAG="$3"

# Verify source image exists
if ! docker images --format "{{.Repository}}:{{.Tag}}" | grep -q "^${SOURCE_IMAGE}$"; then
    # Try with image ID
    if ! docker images --format "{{.ID}}" | grep -q "^${SOURCE_IMAGE}"; then
        print_error "Image not found: $SOURCE_IMAGE"
        echo ""
        print_info "Available images:"
        docker images
        exit 1
    fi
fi

# Extract tag from source image if not provided
if [[ -z "$TARGET_TAG" ]]; then
    if [[ "$SOURCE_IMAGE" == *":"* ]]; then
        TARGET_TAG="${SOURCE_IMAGE##*:}"
    else
        TARGET_TAG="latest"
    fi
fi

print_header "DOCKER PUSH - FABRINETES"
print_info "Username: $USERNAME"
print_info "Source Image: $SOURCE_IMAGE"
print_info "Target: $IMAGE_NAME:$TARGET_TAG"
echo ""

# Check if tag already exists on Docker Hub
print_info "Checking if tag '$TARGET_TAG' exists on Docker Hub..."
if check_tag_exists "$TARGET_TAG"; then
    print_warning "Tag '$TARGET_TAG' already exists on Docker Hub:"
    get_tag_info "$TARGET_TAG"
    echo ""
    
    # Ask for confirmation to overwrite
    while true; do
        read -p "Do you want to overwrite the existing tag '$TARGET_TAG'? (y/n): " -n 1 -r
        echo
        case $REPLY in
            [Yy]* ) 
                print_info "Proceeding with overwrite..."
                break
                ;;
            [Nn]* ) 
                print_info "Please specify a different tag:"
                read -p "Enter new tag: " TARGET_TAG
                if [[ -z "$TARGET_TAG" ]]; then
                    print_error "Tag cannot be empty"
                    exit 1
                fi
                print_info "New target: $IMAGE_NAME:$TARGET_TAG"
                break
                ;;
            * ) 
                print_error "Please answer yes (y) or no (n)"
                ;;
        esac
    done
else
    print_success "Tag '$TARGET_TAG' does not exist on Docker Hub - safe to push"
fi

echo ""

# Tag the image
print_info "Tagging image for Docker Hub..."
docker tag "$SOURCE_IMAGE" "$IMAGE_NAME:$TARGET_TAG"
print_success "Image tagged as: $IMAGE_NAME:$TARGET_TAG"

# Final confirmation
echo ""
print_info "Ready to push:"
print_data "Source: $SOURCE_IMAGE"
print_data "Target: $IMAGE_NAME:$TARGET_TAG"
echo ""

while true; do
    read -p "Proceed with push? (y/n): " -n 1 -r
    echo
    case $REPLY in
        [Yy]* ) break ;;
        [Nn]* ) 
            print_info "Push cancelled"
            exit 0
            ;;
        * ) print_error "Please answer yes (y) or no (n)" ;;
    esac
done

# Check if logged in
print_info "Checking Docker Hub authentication..."
if ! docker info | grep -q "Username:"; then
    print_warning "Not logged into Docker Hub"
    print_info "Please run: ./docker-login.sh $USERNAME"
    exit 1
fi

# Push the image
print_info "Pushing image to Docker Hub..."
if docker push "$IMAGE_NAME:$TARGET_TAG"; then
    print_success "Successfully pushed $IMAGE_NAME:$TARGET_TAG to Docker Hub"
    print_data "Image URL: https://hub.docker.com/r/$IMAGE_NAME"
    print_data "Pull command: docker pull $IMAGE_NAME:$TARGET_TAG"
else
    print_error "Failed to push image to Docker Hub"
    exit 1
fi

print_header "SUMMARY"
print_success "Push completed successfully!"
print_info "Image is now available at: https://hub.docker.com/r/$IMAGE_NAME"

