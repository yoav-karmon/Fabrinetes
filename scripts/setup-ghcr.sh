#!/bin/bash

# GitHub Container Registry Setup Script
# This script helps set up authentication and initial configuration for GHCR

set -e

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
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Set up GitHub Container Registry authentication and configuration"
    echo ""
    echo "Options:"
    echo "  -u, --username USERNAME    GitHub username (required)"
    echo "  -t, --token TOKEN          Personal Access Token (optional, will prompt if not provided)"
    echo "  -h, --help                 Show this help message"
    echo ""
    echo "Examples:"
    echo "  $0 -u myusername"
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
        print_info "Please install Docker first: https://docs.docker.com/get-docker/"
        exit 1
    fi
    
    if ! docker info >/dev/null 2>&1; then
        print_error "Docker daemon is not running"
        print_info "Please start Docker daemon first"
        exit 1
    fi
    
    print_success "Docker is installed and running"
}

# Function to check GitHub CLI
check_github_cli() {
    if command_exists gh; then
        print_success "GitHub CLI is installed"
        return 0
    else
        print_warning "GitHub CLI is not installed"
        print_info "Installing GitHub CLI..."
        
        # Try to install GitHub CLI
        if command_exists apt; then
            curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg | sudo dd of=/usr/share/keyrings/githubcli-archive-keyring.gpg
            echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" | sudo tee /etc/apt/sources.list.d/github-cli.list > /dev/null
            sudo apt update
            sudo apt install gh -y
        elif command_exists yum; then
            sudo yum install -y dnf
            sudo dnf install -y 'dnf-command(config-manager)'
            sudo dnf config-manager --add-repo https://cli.github.com/packages/rpm/gh-cli.repo
            sudo dnf install -y gh
        elif command_exists brew; then
            brew install gh
        else
            print_error "Cannot install GitHub CLI automatically. Please install it manually:"
            print_info "https://cli.github.com/manual/installation"
            return 1
        fi
        
        if command_exists gh; then
            print_success "GitHub CLI installed successfully"
        else
            print_error "Failed to install GitHub CLI"
            return 1
        fi
    fi
}

# Function to authenticate with GitHub CLI
authenticate_github_cli() {
    print_info "Authenticating with GitHub CLI..."
    
    if gh auth status >/dev/null 2>&1; then
        print_success "Already authenticated with GitHub CLI"
        return 0
    fi
    
    print_info "Please authenticate with GitHub CLI..."
    if gh auth login; then
        print_success "Successfully authenticated with GitHub CLI"
    else
        print_error "Failed to authenticate with GitHub CLI"
        return 1
    fi
}

# Function to authenticate with Docker
authenticate_docker() {
    local username="$1"
    local token="$2"
    
    print_info "Authenticating Docker with GHCR..."
    
    if echo "$token" | docker login ghcr.io -u "$username" --password-stdin; then
        print_success "Successfully authenticated Docker with GHCR"
    else
        print_error "Failed to authenticate Docker with GHCR"
        return 1
    fi
}

# Function to test authentication
test_authentication() {
    print_info "Testing authentication..."
    
    # Test Docker authentication
    if docker system info | grep -q "ghcr.io"; then
        print_success "Docker is authenticated with GHCR"
    else
        print_warning "Docker authentication with GHCR not detected"
    fi
    
    # Test GitHub CLI authentication
    if gh auth status >/dev/null 2>&1; then
        print_success "GitHub CLI is authenticated"
        gh auth status
    else
        print_warning "GitHub CLI authentication not detected"
    fi
}

# Function to show next steps
show_next_steps() {
    local username="$1"
    
    print_success "Setup completed successfully!"
    echo ""
    print_info "Next steps:"
    echo "1. Build your Docker image:"
    echo "   docker build -t fabrinetes-image:latest ./Fabrinetes/363fpgadev-01/fabrinetes-dev1/"
    echo ""
    echo "2. Push your image to GHCR:"
    echo "   ./doc/scripts/push-image.sh -u $username"
    echo ""
    echo "3. Pull your image from GHCR:"
    echo "   ./doc/scripts/pull-image.sh -u $username"
    echo ""
    echo "4. View your packages:"
    echo "   https://github.com/$username/packages"
    echo ""
    print_info "For more information, see: ./doc/github-container-registry.md"
}

# Parse command line arguments
GITHUB_USERNAME=""
GITHUB_TOKEN=""

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

print_info "Starting GHCR setup for user: $GITHUB_USERNAME"

# Check prerequisites
check_docker
check_github_cli

# Authenticate with GitHub CLI
authenticate_github_cli

# Authenticate with Docker
if [[ -n "$GITHUB_TOKEN" ]]; then
    authenticate_docker "$GITHUB_USERNAME" "$GITHUB_TOKEN"
else
    print_info "No token provided. Docker authentication will use GitHub CLI token."
    print_info "If you encounter issues, you can manually authenticate with:"
    print_info "  docker login ghcr.io -u $GITHUB_USERNAME"
fi

# Test authentication
test_authentication

# Show next steps
show_next_steps "$GITHUB_USERNAME"
