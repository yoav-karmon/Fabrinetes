#!/bin/bash

# Test script for fabrinetes.py error handling and edge cases
# This script tests error conditions and edge cases

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

# Function to test error conditions
test_error() {
    local description="$1"
    local command="$2"
    local expected_exit_code="$3"
    
    print_test "Testing error condition: $description"
    
    local output
    local exit_code
    if output=$(cd "$FABRINETES_ROOT" && eval "$command" 2>&1); then
        exit_code=0
    else
        exit_code=$?
    fi
    
    if [[ "$exit_code" == "$expected_exit_code" ]]; then
        print_success "Error handled correctly (exit code: $exit_code)"
    else
        print_error "Unexpected exit code: $exit_code (expected: $expected_exit_code)"
    fi
    
    echo "Output: $output"
    echo ""
}

print_header "FABRINETES.PY ERROR HANDLING TESTS"

# Test missing config file
test_error "Missing config file" "python3 fabrinetes.py --cmd run --config-file nonexistent.toml" "1"

# Test invalid command
test_error "Invalid command" "python3 fabrinetes.py --cmd invalid --config-file containers/fabrinetes-dev-testing/config.toml" "1"

# Test missing required arguments
test_error "Missing config file argument" "python3 fabrinetes.py --cmd run" "1"

# Test help command
print_test "Testing help command"
if output=$(cd "$FABRINETES_ROOT" && python3 fabrinetes.py --help 2>&1); then
    if echo "$output" | grep -q "Fabrinetes - Docker Container Management Tool"; then
        print_success "Help command works correctly"
    else
        print_error "Help command did not show expected output"
    fi
else
    print_error "Help command failed"
fi
echo ""

# Test no arguments (should show help)
print_test "Testing no arguments (should show help)"
if output=$(cd "$FABRINETES_ROOT" && python3 fabrinetes.py 2>&1); then
    if echo "$output" | grep -q "usage:"; then
        print_success "No arguments correctly shows help"
    else
        print_error "No arguments did not show help"
    fi
else
    print_error "No arguments failed"
fi
echo ""

print_header "TEST SUMMARY"
print_success "All error handling tests completed!"
print_test "Check output above to verify error handling is working correctly"
