#!/bin/bash

# GitHub Container Registry Push Script
# This script pushes the fabrinetes-image to GitHub Container Registry (GHCR)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
IMAGE_DIR="$FABRINETES_ROOT/363fpgadev-01/fabrinetes-dev1"
IMAGE_NAME="fabrinetes-image"

# Default values
VERSION="latest"
GITHUB_USERNAME=""
REGISTRY="ghcr.io"

# Colors for output
RED=''''
GREEN=''''
YELLOW=''''
BLUE=''''
NC='''' # No Color

# Function to print colored output
print_info() {
    echo "$1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_warning() {
    echo "[WARNING] $1"
}

print_error() {
    echo "[ERROR] $1"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 [OPTIONS] [VERSION]"
    echo ""
    echo "Push fabrinetes-image to GitHub Container Registry"
    echo ""
    echo "Options:"
    echo "  -u, --username USERNAME    GitHub username (required)"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Arguments:"
    echo "  VERSION                    Version tag (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 -u myusername"
    echo "  $0 -u myusername v1.0.0"
    echo "  $0 --username myusername latest"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Docker daemon
check_docker() {
    if ! command_exists docker; then
        print_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running"
        exit 1
    fi
}

# Function to check authentication
check_auth() {
    if ! docker system info | grep -q "ghcr.io"; then
        print_warning "Not authenticated with GHCR. Attempting to authenticate..."
        
        if command_exists gh; then
            print_info "Using GitHub CLI for authentication..."
            gh auth status >/dev/null 2>&1 || {
                print_error "GitHub CLI not authenticated. Please run: gh auth login"
                exit 1
            }
        else
            print_error "Please authenticate with GHCR first:"
            print_error "  docker login ghcr.io -u $GITHUB_USERNAME"
            exit 1
        fi
    fi
}

# Function to validate image exists
validate_image() {
    local image_tag="$1"
    
    if ! docker image inspect "$image_tag" >/dev/null 2>&1; then
        print_error "Image '$image_tag' not found locally"
        print_info "Available images:"
        docker images | grep "$IMAGE_NAME" || print_warning "No fabrinetes-image found"
        exit 1
    fi
}

# Function to push image
push_image() {
    local local_tag="$1"
    local remote_tag="$2"
    
    print_info "Tagging image for GHCR..."
    docker tag "$local_tag" "$remote_tag"
    
    print_info "Pushing image to GHCR..."
    if docker push "$remote_tag"; then
        print_success "Successfully pushed $remote_tag to GHCR"
    else
        print_error "Failed to push image to GHCR"
        exit 1
    fi
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--username)
            GITHUB_USERNAME="$2"
            shift 2
            ;;
        -h|--help)
            show_usage
            exit 0
            ;;
        -*)
            print_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
        *)
            VERSION="$1"
            shift
            ;;
    esac
done

# Validate required parameters
if [[ -z "$GITHUB_USERNAME" ]]; then
    print_error "GitHub username is required"
    show_usage
    exit 1
fi

# Validate version format
if [[ "$VERSION" != "latest" && ! "$VERSION" =~ ^v?[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    print_warning "Version '$VERSION' doesn't follow semantic versioning format"
fi

# Set up image tags
LOCAL_TAG="$IMAGE_NAME:$VERSION"
REMOTE_TAG="$REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:$VERSION"

print_info "Starting GHCR push process..."
print_info "Local tag: $LOCAL_TAG"
print_info "Remote tag: $REMOTE_TAG"
print_info "GitHub username: $GITHUB_USERNAME"

# Check prerequisites
check_docker
check_auth

# Validate image exists locally
validate_image "$LOCAL_TAG"

# Push the image
push_image "$LOCAL_TAG" "$REMOTE_TAG"

# Show final information
print_success "Push completed successfully!"
print_info "Image is now available at: $REMOTE_TAG"
print_info "You can pull it with: docker pull $REMOTE_TAG"

# Optional: Show package URL
print_info "View package at: https://github.com/$GITHUB_USERNAME/packages"
