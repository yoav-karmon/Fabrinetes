#!/bin/bash

# Simple Docker Image Setup Script

set -e

print_info() { echo "$1"; }
print_success() { echo "[SUCCESS] $1"; }
print_warning() { echo "[WARNING] $1"; }
print_error() { echo "[ERROR] $1"; }

show_usage() {
    echo "Usage: $0 -f <config_file> [-i <image_id>]"
    echo "  -f FILE          Config file (required)"
    echo "  -i IMAGE         Image ID (optional - will prompt if not provided)"
    echo "  -h, --help       Show help"
    echo ""
    echo "Examples:"
    echo "  $0 -f containers/fabrinetes-dev-local/config.toml"
    echo "  $0 -f containers/fabrinetes-dev-local/config.toml -i ykarmon/fabrinetes:latest"
}

# Show available images
show_images() {
    print_info "Available images:"
    local counter=1
    curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | \
    jq -r '.results[] | "ykarmon/fabrinetes:\(.name) - \(.last_updated) - \(.full_size | . / 1024 / 1024 | floor)MB"' 2>/dev/null | \
    while read -r line; do
        echo "  $counter. $line"
        ((counter++))
    done || {
        print_error "Failed to fetch images"
        exit 1
    }
}

# Parse arguments
CONFIG_FILE=""
IMAGE_ID=""

while [[ $# -gt 0 ]]; do
    case $1 in
        -f) CONFIG_FILE="$2"; shift 2 ;;
        -i) IMAGE_ID="$2"; shift 2 ;;
        -h|--help) show_usage; exit 0 ;;
        *) print_error "Unknown option: $1"; show_usage; exit 1 ;;
    esac
done

# Always show available images first
print_info "Docker Image Setup"
echo ""
show_images
echo ""

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

# Select image if not provided
select_image() {
    if [[ -n "$IMAGE_ID" ]]; then
        print_info "Using provided image: $IMAGE_ID"
        return
    fi
    
    # Get user selection
    while true; do
        read -p "Select image number or 'q' to quit: " selection
        if [[ "$selection" == "q" ]]; then
            print_info "Exiting..."
            exit 0
        fi
        
        # Get available images
        local images=($(curl -s "https://hub.docker.com/v2/repositories/ykarmon/fabrinetes/tags/?page_size=100" | jq -r '.results[] | "ykarmon/fabrinetes:\(.name)"' 2>/dev/null))
        
        # Validate selection
        if [[ "$selection" =~ ^[0-9]+$ ]] && [[ "$selection" -ge 1 ]] && [[ "$selection" -le ${#images[@]} ]]; then
            IMAGE_ID="${images[$((selection-1))]}"
            print_info "Selected image: $IMAGE_ID"
            break
        else
            print_error "Invalid selection. Please enter a number between 1 and ${#images[@]}"
        fi
    done
}

# Run fabrinetes with config file
run_fabrinetes() {
    print_info "Fabrinetes Container Runner"
    print_info "Config file: $CONFIG_FILE"
    
    # Check if fabrinetes.py exists
    if [[ ! -f "./fabrinetes.py" ]]; then
        print_error "fabrinetes.py not found in current directory"
        exit 1
    fi
    
    # Run the command
    print_info "Running: ./fabrinetes.py --config-file $CONFIG_FILE --cmd run | bash"
    echo ""
    print_info "=========================================="
    echo "START OF FABRINETES OUTPUT"
    print_info "=========================================="
    
    ./fabrinetes.py --config-file "$CONFIG_FILE" --cmd run | bash
    
    print_info "=========================================="
    echo "END OF FABRINETES OUTPUT"
    print_info "=========================================="
    print_success "Fabrinetes command completed!"
}

# Main execution
# Select image (images already shown above)
select_image

# Run fabrinetes
run_fabrinetes

print_success "Done!"