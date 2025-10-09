#!/bin/bash
# Package management script for Fabrinetes containers
# This script helps manage apt-get packages across different containers

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PACKAGES_FILE="$SCRIPT_DIR/packages.list"

# Source the packages list
if [[ -f "$PACKAGES_FILE" ]]; then
    source "$PACKAGES_FILE"
else
    echo "Error: packages.list not found at $PACKAGES_FILE"
    exit 1
fi

# Function to install packages
install_packages() {
    local package_type="$1"
    local packages_var="${package_type^^}_PACKAGES"
    local packages="${!packages_var}"
    
    if [[ -n "$packages" ]]; then
        echo "Installing $package_type packages: $packages"
        apt-get update && apt-get install -y $packages && apt-get clean && rm -rf /var/lib/apt/lists/*
    else
        echo "No $package_type packages defined"
    fi
}

# Function to generate Dockerfile snippet
generate_dockerfile_snippet() {
    local container_type="$1"
    
    case "$container_type" in
        "testing")
            echo "RUN apt-get update && apt-get install -y $BASE_PACKAGES && apt-get clean && rm -rf /var/lib/apt/lists/*"
            ;;
        "dev")
            echo "RUN apt-get update && apt-get install -y $BASE_PACKAGES $DEV_PACKAGES && apt-get clean && rm -rf /var/lib/apt/lists/*"
            ;;
        "fpga")
            echo "RUN apt-get update && apt-get install -y $BASE_PACKAGES $DEV_PACKAGES $NETWORK_PACKAGES $GUI_PACKAGES $FPGA_PACKAGES && apt-get clean && rm -rf /var/lib/apt/lists/*"
            ;;
        "all")
            echo "RUN apt-get update && apt-get install -y $ALL_PACKAGES && apt-get clean && rm -rf /var/lib/apt/lists/*"
            ;;
        *)
            echo "Usage: $0 generate <testing|dev|fpga|all>"
            exit 1
            ;;
    esac
}

# Function to list available packages
list_packages() {
    echo "Available package categories:"
    echo "  BASE_PACKAGES: $BASE_PACKAGES"
    echo "  DEV_PACKAGES: $DEV_PACKAGES"
    echo "  NETWORK_PACKAGES: $NETWORK_PACKAGES"
    echo "  GUI_PACKAGES: $GUI_PACKAGES"
    echo "  FPGA_PACKAGES: $FPGA_PACKAGES"
    echo "  ALL_PACKAGES: $ALL_PACKAGES"
}

# Main script logic
case "$1" in
    "install")
        install_packages "$2"
        ;;
    "generate")
        generate_dockerfile_snippet "$2"
        ;;
    "list")
        list_packages
        ;;
    *)
        echo "Usage: $0 {install|generate|list} [package_type|container_type]"
        echo ""
        echo "Commands:"
        echo "  install <package_type>  - Install packages of specified type"
        echo "  generate <container_type> - Generate Dockerfile snippet for container type"
        echo "  list                    - List all available package categories"
        echo ""
        echo "Package types: base, dev, network, gui, fpga"
        echo "Container types: testing, dev, fpga, all"
        exit 1
        ;;
esac
