#!/bin/bash

# Test script for fabrinetes.py configuration validation
# This script tests different configuration scenarios

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$SCRIPT_DIR")"

# Colors for output
RED=''''
GREEN=''''
YELLOW=''''
BLUE=''''
NC='''' # No Color

print_header() {
    echo "================================"
    echo "$1"
    echo "================================"
}

print_test() {
    echo -e "${YELLOW}[TEST]${NC} $1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_error() {
    echo "[ERROR] $1"
}

# Function to test config validation
test_config() {
    local config_file="$1"
    local description="$2"
    
    print_test "Testing config: $description"
    print_test "Config file: $config_file"
    
    if [[ ! -f "$config_file" ]]; then
        print_error "Config file not found: $config_file"
        return 1
    fi
    
    # Test status command to validate config
    local output
    if output=$(cd "$FABRINETES_ROOT" && python3 fabrinetes.py --cmd status --config-file "$config_file" 2>&1); then
        print_success "Config validation passed"
        echo "$output" | head -5  # Show first 5 lines
        echo "..."
    else
        print_error "Config validation failed"
        echo "$output"
    fi
    echo ""
}

print_header "FABRINETES.PY CONFIGURATION VALIDATION TESTS"

# Test main config file
test_config "containers/fabrinetes-dev-testing/config.toml" "Main development config"

# Test if there are other config files
print_test "Looking for additional config files..."
find "$FABRINETES_ROOT/containers" -name "*.toml" -type f | while read -r config_file; do
    relative_path="${config_file#$FABRINETES_ROOT/}"
    test_config "$relative_path" "Additional config: $relative_path"
done

print_header "TEST SUMMARY"
print_success "All configuration validation tests completed!"
print_test "Check output above to verify configuration files are valid"
