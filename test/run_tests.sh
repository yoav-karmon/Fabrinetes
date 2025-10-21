#!/bin/bash

# Comprehensive Test Runner for Fabrinetes
# This script runs the unified comprehensive test suite

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FABRINETES_ROOT="$(dirname "$SCRIPT_DIR")"

echo "Running Comprehensive Fabrinetes Test Suite..."
echo "=============================================="

cd "$FABRINETES_ROOT"
python3 test/test_comprehensive.py

echo ""
echo "Test completed!"
