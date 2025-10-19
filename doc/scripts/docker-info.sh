#!/bin/bash

# Docker Information Script
# This script provides comprehensive information about Docker images and GitHub Container Registry

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$(dirname "$SCRIPT_DIR")")"

# Default values
GITHUB_USERNAME=""
REGISTRY="ghcr.io"
IMAGE_NAME="fabrinetes-image"
GITHUB_TOKEN=""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Function to print colored output
print_header() {
    echo -e "${CYAN}================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}================================${NC}"
}

print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_data() {
    echo -e "${MAGENTA}$1${NC}"
}

# Function to show usage
show_usage() {
    echo "Usage: $0 -u USERNAME -t TOKEN [OPTIONS]"
    echo ""
    echo "Display comprehensive Docker and GitHub Container Registry information"
    echo ""
    echo "Required Options:"
    echo "  -u, --username USERNAME    GitHub username (required)"
    echo "  -t, --token TOKEN          GitHub personal access token (required)"
    echo ""
    echo "Optional Options:"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u yoav-karmon -t ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
    echo "  $0 --username myusername --token ghp_xxxxxxxxxxxx"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to check Docker daemon
check_docker() {
    if ! command_exists docker; then
        print_error "Docker is not installed or not in PATH"
        return 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running"
        return 1
    fi
    return 0
}

# Function to get GitHub Container Registry packages
get_ghcr_packages() {
    if [[ -z "$GITHUB_TOKEN" ]]; then
        print_warning "No GitHub token provided. Cannot fetch GHCR package information."
        return 1
    fi
    
    print_info "Fetching GitHub Container Registry packages..."
    
    local packages_json
    packages_json=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/user/packages?package_type=container" 2>/dev/null)
    
    if [[ $? -eq 0 && -n "$packages_json" ]]; then
        echo "$packages_json"
    else
        print_warning "Failed to fetch GHCR packages"
        return 1
    fi
}

# Function to get package versions
get_package_versions() {
    local package_name="$1"
    
    if [[ -z "$GITHUB_TOKEN" ]]; then
        return 1
    fi
    
    local versions_json
    versions_json=$(curl -s -H "Authorization: token $GITHUB_TOKEN" \
        "https://api.github.com/users/$GITHUB_USERNAME/packages/container/$package_name/versions" 2>/dev/null)
    
    if [[ $? -eq 0 && -n "$versions_json" ]]; then
        echo "$versions_json"
    else
        return 1
    fi
}

# Function to display local Docker images
show_local_images() {
    print_header "LOCAL DOCKER IMAGES"
    
    if ! check_docker; then
        print_error "Docker is not available"
        return 1
    fi
    
    print_info "All local Docker images:"
    docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.Size}}\t{{.CreatedSince}}" | head -20
    
    echo ""
    print_info "Images from GitHub Container Registry:"
    docker images | grep "ghcr.io" || print_warning "No GHCR images found locally"
    
    echo ""
    print_info "Fabrinetes-related images:"
    docker images | grep -i "fabrinetes" || print_warning "No Fabrinetes images found locally"
    
    echo ""
    print_info "Docker system information:"
    print_data "Total images: $(docker images -q | wc -l)"
    print_data "Total containers: $(docker ps -aq | wc -l)"
    print_data "Docker version: $(docker --version)"
}

# Function to display GitHub Container Registry information
show_ghcr_info() {
    print_header "GITHUB CONTAINER REGISTRY INFORMATION"
    
    local packages_json
    packages_json=$(get_ghcr_packages)
    
    if [[ $? -ne 0 ]]; then
        print_warning "Skipping GHCR information (no token or API error)"
        return 1
    fi
    
    # Parse and display package information
    echo "$packages_json" | jq -r '.[] | 
        "Package: " + .name + 
        "\nRegistry: " + (.owner.login + "/" + .name) +
        "\nVisibility: " + .visibility +
        "\nCreated: " + .created_at +
        "\nUpdated: " + .updated_at +
        "\nRepository: " + (.repository.name // "N/A") +
        "\nURL: " + .html_url +
        "\n"' 2>/dev/null || {
        print_warning "jq not available, showing raw JSON:"
        echo "$packages_json"
    }
    
    # Get versions for each package
    echo "$packages_json" | jq -r '.[].name' 2>/dev/null | while read -r package_name; do
        if [[ -n "$package_name" ]]; then
            echo ""
            print_info "Versions for package: $package_name"
            local versions_json
            versions_json=$(get_package_versions "$package_name")
            
            if [[ $? -eq 0 ]]; then
                echo "$versions_json" | jq -r '.[] | 
                    "  Tag: " + (.metadata.container.tags | join(", ")) +
                    "\n  Created: " + .created_at +
                    "\n  ID: " + .name +
                    "\n"' 2>/dev/null || echo "$versions_json"
            else
                print_warning "Could not fetch versions for $package_name"
            fi
        fi
    done
}

# Function to display Docker system information
show_docker_system_info() {
    print_header "DOCKER SYSTEM INFORMATION"
    
    if ! check_docker; then
        print_error "Docker is not available"
        return 1
    fi
    
    print_info "Docker version and build info:"
    docker version --format "Client: {{.Client.Version}}\nServer: {{.Server.Version}}" 2>/dev/null || docker --version
    
    echo ""
    print_info "Docker system usage:"
    docker system df 2>/dev/null || print_warning "Could not get system usage"
    
    echo ""
    print_info "Docker info summary:"
    docker info --format "{{.ServerVersion}}" 2>/dev/null | head -1
    docker info --format "{{.ContainersRunning}} containers running, {{.ContainersStopped}} stopped" 2>/dev/null
    docker info --format "{{.Images}} images" 2>/dev/null
}

# Function to display authentication status
show_auth_status() {
    print_header "AUTHENTICATION STATUS"
    
    print_info "Docker authentication status:"
    if docker system info | grep -q "ghcr.io"; then
        print_success "Authenticated with GitHub Container Registry"
    else
        print_warning "Not authenticated with GitHub Container Registry"
    fi
    
    echo ""
    print_info "GitHub CLI status:"
    if command_exists gh; then
        if gh auth status >/dev/null 2>&1; then
            print_success "GitHub CLI is authenticated"
            gh auth status 2>/dev/null || true
        else
            print_warning "GitHub CLI is not authenticated"
        fi
    else
        print_warning "GitHub CLI is not installed"
    fi
}

# Function to display registry URLs and commands
show_registry_info() {
    print_header "REGISTRY INFORMATION & COMMANDS"
    
    print_info "GitHub Container Registry URLs:"
    print_data "Registry: $REGISTRY"
    print_data "Your packages: https://github.com/$GITHUB_USERNAME/packages"
    print_data "Package URL: https://github.com/users/$GITHUB_USERNAME/packages/container/package/$IMAGE_NAME"
    
    echo ""
    print_info "Common Docker commands:"
    print_data "Login: docker login $REGISTRY -u $GITHUB_USERNAME"
    print_data "Pull: docker pull $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest"
    print_data "Push: docker push $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest"
    print_data "Run: docker run -it $REGISTRY/$GITHUB_USERNAME/$IMAGE_NAME:latest"
    
    echo ""
    print_info "Local image commands:"
    print_data "List images: docker images"
    print_data "Remove image: docker rmi <image_id>"
    print_data "Inspect image: docker inspect <image_name>"
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -u|--username)
            GITHUB_USERNAME="$2"
            shift 2
            ;;
        -t|--token)
            GITHUB_TOKEN="$2"
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
            print_error "Unknown argument: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Validate required parameters
if [[ -z "$GITHUB_USERNAME" ]]; then
    print_error "GitHub username is required"
    show_usage
    exit 1
fi

if [[ -z "$GITHUB_TOKEN" ]]; then
    print_error "GitHub personal access token is required"
    show_usage
    exit 1
fi

# Main execution
print_header "DOCKER & GITHUB CONTAINER REGISTRY INFORMATION"
print_info "GitHub Username: $GITHUB_USERNAME"
print_info "Registry: $REGISTRY"
print_info "Image Name: $IMAGE_NAME"
echo ""

# Display all information sections
show_local_images
echo ""
show_docker_system_info
echo ""
show_auth_status
echo ""
show_ghcr_info
echo ""
show_registry_info

print_header "SUMMARY"
print_success "Information gathering completed!"
print_info "For more details, visit: https://github.com/$GITHUB_USERNAME/packages"