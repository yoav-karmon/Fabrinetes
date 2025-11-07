#!/bin/bash

# Simple Fabrinetes Setup Script

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
    echo "  $0 -f config.toml"
    echo ""
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
    print_error "Current directory: $(pwd)"
    print_error "Available files:"
    ls -la *.toml 2>/dev/null || echo "  No .toml files found in current directory"
    exit 1
fi

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if fabrinetes.py exists in the same directory as this script
if [[ ! -f "$SCRIPT_DIR/fabrinetes.py" ]]; then
    print_error "fabrinetes.py not found in $SCRIPT_DIR"
    exit 1
fi

# Run fabrinetes with config file
print_info "Fabrinetes Container Runner"
print_info "Config file: $CONFIG_FILE"
print_info "Script directory: $SCRIPT_DIR"
echo ""

print_info "Running: $SCRIPT_DIR/fabrinetes.py --config-file $CONFIG_FILE --cmd run | bash"
echo ""
print_info "=========================================="
echo "START OF FABRINETES OUTPUT"
print_info "=========================================="
echo ""

# Run fabrinetes command and capture output
echo "=== FABRINETES.PY OUTPUT ==="
"$SCRIPT_DIR/fabrinetes.py" --config-file "$CONFIG_FILE" --cmd run
echo "=== END FABRINETES.PY OUTPUT ==="
echo ""
echo "=== EXECUTING COMMANDS ==="
"$SCRIPT_DIR/fabrinetes.py" --config-file "$CONFIG_FILE" --cmd run | bash
echo "=== END EXECUTING COMMANDS ==="

echo ""
print_info "=========================================="
echo "END OF FABRINETES OUTPUT"
print_info "=========================================="
print_success "Fabrinetes command completed!"