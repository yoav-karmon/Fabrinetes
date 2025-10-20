#!/bin/bash

# Simple Docker Image Setup Script

set -e

print_info() { echo "$1"; }
print_success() { echo "[SUCCESS] $1"; }
print_warning() { echo "[WARNING] $1"; }
print_error() { echo "[ERROR] $1"; }

show_usage() {
    echo "Usage: $0 -f <config_file>"
    echo "  -f FILE          Config file (required)"
    echo "  -h, --help       Show help"
    echo ""
    echo "Examples:"
    echo "  $0 -f containers/fabrinetes-dev-local/config.toml"
    echo ""
    echo "Note: Image name and tag are read from [config.image] section in the config file"
}

# Read image configuration from TOML file
read_image_config() {
    local config_file="$1"
    
    # Create a Python script to parse TOML using tomli
    local python_script="
import sys
try:
    import tomli
except ImportError:
    print('ERROR: tomli not found. Installing...', file=sys.stderr)
    import subprocess
    import os
    try:
        subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'tomli', '--user'], 
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import tomli
    except:
        print('ERROR: Failed to install tomli. Please install manually: pip3 install tomli', file=sys.stderr)
        sys.exit(1)

try:
    with open('$config_file', 'rb') as f:
        config = tomli.load(f)
    
    image_name = config.get('config', {}).get('image', {}).get('name')
    image_tag = config.get('config', {}).get('image', {}).get('tag')
    
    if not image_name or not image_tag:
        print('ERROR: Could not read image configuration from config file', file=sys.stderr)
        print('ERROR: Make sure [config.image] section exists with name and tag fields', file=sys.stderr)
        sys.exit(1)
    
    print(f'{image_name}:{image_tag}')
    
except Exception as e:
    print(f'ERROR: Failed to parse config file: {e}', file=sys.stderr)
    sys.exit(1)
"
    
    # Execute the Python script to get the image ID
    IMAGE_ID=$(python3 -c "$python_script" 2>/dev/null)
    
    if [[ $? -ne 0 || -z "$IMAGE_ID" ]]; then
        print_error "Failed to read image configuration from config file"
        exit 1
    fi
    
    print_info "Using image from config: $IMAGE_ID"
}

# Parse arguments
CONFIG_FILE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -f) CONFIG_FILE="$2"; shift 2 ;;
        -h|--help) show_usage; exit 0 ;;
        *) print_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

# Validate required config file
if [[ -z "$CONFIG_FILE" ]]; then
    print_error "Config file is required. Use -f <config_file>"
    show_usage
    exit 1
fi

# Validate config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Config file '$CONFIG_FILE' not found"
    exit 1
fi

# Read image configuration from config file
print_info "Docker Image Setup"
echo ""
read_image_config "$CONFIG_FILE"
echo ""

# Pull the Docker image
pull_docker_image() {
    print_info "Pulling Docker image: $IMAGE_ID"
    if docker pull "$IMAGE_ID"; then
        print_success "Successfully pulled image: $IMAGE_ID"
    else
        print_error "Failed to pull image: $IMAGE_ID"
        exit 1
    fi
}

pull_docker_image
echo ""

# Run fabrinetes with config file
run_fabrinetes() {
    print_info "Fabrinetes Container Runner"
    print_info "Config file: $CONFIG_FILE"
    
    # Get the directory where this script is located
    SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    
    # Check if fabrinetes.py exists in the same directory as this script
    if [[ ! -f "$SCRIPT_DIR/fabrinetes.py" ]]; then
        print_error "fabrinetes.py not found in $SCRIPT_DIR"
        exit 1
    fi
    
    # Run the command
    print_info "Running: $SCRIPT_DIR/fabrinetes.py --config-file $CONFIG_FILE --cmd run | bash"
    echo ""
    print_info "=========================================="
    echo "START OF FABRINETES OUTPUT"
    print_info "=========================================="
    
    "$SCRIPT_DIR/fabrinetes.py" --config-file "$CONFIG_FILE" --cmd run | bash
    
    print_info "=========================================="
    echo "END OF FABRINETES OUTPUT"
    print_info "=========================================="
    print_success "Fabrinetes command completed!"
}

# Main execution
# Run fabrinetes
run_fabrinetes

print_success "Done!"