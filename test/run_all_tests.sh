#!/bin/bash

# Master test runner for fabrinetes.py
# This script runs all test suites

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Colors for output
RED=''
GREEN=''
YELLOW=''
BLUE=''
NC=''

print_header() {
    echo "================================"
    echo "$1"
    echo "================================"
}

print_test() {
    echo "[TEST] $1"
}

print_success() {
    echo "[SUCCESS] $1"
}

print_error() {
    echo "[ERROR] $1"
}

# Function to run a test suite
run_test_suite() {
    local test_file="$1"
    local test_name="$2"
    
    print_header "RUNNING: $test_name"
    
    if [[ -f "$test_file" ]]; then
        if bash "$test_file"; then
            print_success "$test_name completed successfully"
        else
            print_error "$test_name failed"
            return 1
        fi
    else
        print_error "Test file not found: $test_file"
        return 1
    fi
    
    echo ""
}

print_header "FABRINETES.PY COMPREHENSIVE TEST SUITE"
print_test "Running all test suites for fabrinetes.py command generation"
echo ""

# Run all test suites
run_test_suite "$SCRIPT_DIR/test_command_generation.sh" "Command Generation Tests"
run_test_suite "$SCRIPT_DIR/test_error_handling.sh" "Error Handling Tests"
run_test_suite "$SCRIPT_DIR/test_config_validation.sh" "Configuration Validation Tests"

print_header "FINAL TEST SUMMARY"
print_success "All test suites completed!"
print_test "fabrinetes.py is working correctly for command generation"
print_test "Remember: All tests use --ask flag to prevent command execution"
print_test "Commands are generated but not executed - this is the expected behavior"
