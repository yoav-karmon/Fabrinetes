#!/bin/bash

# Test script for fabrinetes.py command generation
# This script tests that fabrinetes.py generates correct commands without executing them

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$SCRIPT_DIR")"
CONFIG_FILE="$FABRINETES_ROOT/containers/fabrinetes-dev-testing/config.toml"

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

# Function to test command generation
test_command() {
    local cmd="$1"
    local description="$2"
    local extra_flags="$3"
    
    print_test "Testing $cmd command: $description"
    
    local output
    if output=$(cd "$FABRINETES_ROOT" && python3 fabrinetes.py --cmd "$cmd" --config-file "$CONFIG_FILE" --ask $extra_flags 2>&1); then
        if echo "$output" | grep -q "Docker.*Command:"; then
            print_success "$cmd command generated successfully"
            echo "$output" | head -10  # Show first 10 lines
            echo "..."
        else
            print_error "$cmd command did not generate expected Docker command"
            echo "$output"
        fi
    else
        print_error "$cmd command failed"
        echo "$output"
    fi
    echo ""
}

# Check if config file exists
if [[ ! -f "$CONFIG_FILE" ]]; then
    print_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

print_header "FABRINETES.PY COMMAND GENERATION TESTS"
print_test "Testing command generation without execution (--ask flag)"
print_test "Config file: $CONFIG_FILE"
echo ""

# Test basic commands
test_command "run" "Basic run command"
test_command "build" "Build command with --buildbase flag" "--buildbase"
test_command "commit" "Commit command"
test_command "restore" "Restore command"
test_command "status" "Status command"

# Test commands with different flags
test_command "run" "Run with --rm flag" "--rm"
test_command "run" "Run with --x11 flag" "--x11"
test_command "run" "Run with --usb flag" "--usb"
test_command "run" "Run with --verbose flag" "--verbose"

# Test exec command
test_command "exec" "Exec command" "--exec-cmd 'hdlforge test'"

# Test restore with different options
test_command "restore" "Restore main image" "--image"
test_command "restore" "Restore base image" "--base-image"

# Test commit with tag and message
test_command "commit" "Commit with tag and message" "--tag test-tag --message 'Test commit'"

# Test push command
test_command "push" "Push command" "--github-username testuser"

print_header "TEST SUMMARY"
print_success "All command generation tests completed!"
print_test "Note: Commands are generated but not executed (--ask flag)"
print_test "Check output above to verify command generation is working correctly"
