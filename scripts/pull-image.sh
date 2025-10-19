#!/bin/bash

# GitHub Container Registry Pull Script
# This script pulls the fabrinetes-image from GitHub Container Registry (GHCR)

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"
IMAGE_NAME="fabrinetes-image"

# Default values
VERSION="latest"
GITHUB_USERNAME=""
REGISTRY="ghcr.io"
LOCAL_TAG=""

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
    echo "Pull fabrinetes-image from GitHub Container Registry"
    echo ""
    echo "Options:"
    echo "  -u, --username USERNAME    GitHub username (required)"
    echo "  -l, --local-tag TAG        Local tag name (default: fabrinetes-image:VERSION)"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Arguments:"
    echo "  VERSION                    Version tag to pull (default: latest)"
    echo ""
    echo "Examples:"
    echo "  $0 -u myusername"
    echo "  $0 -u myusername v1.0.0"
    echo "  $0 --username myusername --local-tag my-fabrinetes:latest"
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

# Function to pull image
pull_image() {
    local remote_tag="$1"
    local local_tag="$2"
    
    print_info "Pulling image from GHCR..."
    if docker pull "$remote_tag"; then
        print_success "Successfully pulled $remote_tag from GHCR"
        
        # Tag locally if different from remote
        if [[ "$remote_tag" != "$local_tag" ]]; then
            print_info "Tagging image locally as $local_tag..."
            docker tag "$remote_tag" "$local_tag"
            print_success "Image tagged as $local_tag"
        fi
    else
        print_error "Failed to pull image from GHCR"
        exit 1
    fi
}

# Function to show image info
show_image_info() {
    local image_tag="$1"
    
    print_info "Image information:"
    docker images "$image_tag" --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}"
    
    print_info "Image details:"
    docker inspect "$image_tag" --format "{{.Config.Labels}}" 2>/dev/null || print_warning "No labels found"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--username)
            GITHUB_USERNAME="$2"
            shift 2
            ;;
        -l|--local-tag)
            LOCAL_TAG="$2"
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

# Set up image tags
if [[ -z "$LOCAL_TAG" ]]; then
    LOCAL_TAG="$IMAGE_NAME:$VERSION"
fi

REMOTE_TAG="$REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:$VERSION"

print_info "Starting GHCR pull process..."
print_info "Remote tag: $REMOTE_TAG"
print_info "Local tag: $LOCAL_TAG"
print_info "GitHub username: $GITHUB_USERNAME"

# Check prerequisites
check_docker
check_auth

# Pull the image
pull_image "$REMOTE_TAG" "$LOCAL_TAG"

# Show image information
show_image_info "$LOCAL_TAG"

# Show final information
print_success "Pull completed successfully!"
print_info "Image is now available locally as: $LOCAL_TAG"
print_info "You can run it with: docker run -it $LOCAL_TAG"

# Optional: Show package URL
print_info "View package at: https://github.com/$GITHUB_USERNAME/packages"
