# Test Task Documentation

## Overview

The `test` task provides comprehensive automated testing for all Fabrinetes commands. It uses a sophisticated test framework that can test individual commands or run full test suites with automatic permutation generation.

## Usage

```bash
# Test all scenarios for a specific command
./fabrinetes test --command <command-name>

# Test a specific test number for a command
./fabrinetes test --command <command-name> --test-number <number>

# Show help for test command
./fabrinetes test
```

## Supported Commands

The test framework supports testing the following commands:

- **`run`** - Container execution tests
- **`gen-image`** - Regular image build tests  
- **`gen-image-base`** - Base image build tests
- **`clean-image`** - Image cleanup tests
- **`kill`** - Container termination tests
- **`commit`** - Container commit tests
- **`exec`** - Container execution tests
- **`shell`** - Interactive shell tests
- **`pkg`** - Package management tests

## Test Framework Architecture

### Unified Setup System

The test framework uses a unified `setup_test_state()` function that handles all command types:

- **`setup_gen_image_state()`** - Handles image build tests (base and regular)
- **`setup_regular_command_state()`** - Handles container operation tests

### Test Parameters

Each command has specific test parameters that define different scenarios:

#### Run Command Tests (6 tests)
- Fresh run - should PASS
- Container already running - should FAIL (duplicate)
- Container stopped - should restart
- No tarball - should PASS
- Restore from tarball - should PASS
- No image, no restore - should FAIL

#### Gen-Image Command Tests (5 tests)
- Target image in repo, target tarball exists, base image in repo - should PASS (use existing)
- Target image not in repo, target tarball exists, base image in repo - should PASS (restore target)
- Target image not in repo, no target tarball, base image in repo - should PASS (build from base)
- Target image not in repo, no target tarball, base image not in repo, base tarball exists - should PASS (restore base, then build)
- Target image not in repo, no target tarball, base image not in repo, no base tarball - should FAIL (no base image source)

#### Gen-Image-Base Command Tests (3 tests)
- Base image in repo, tarball exists - should PASS (use existing)
- Base image not in repo, tarball exists - should PASS (restore)
- Base image not in repo, no tarball - should PASS (build from Dockerfile)

## Test Execution Process

### 1. Test Setup
- **Step 0**: Prepare test environment
  - Sets up image state (in repo/not in repo)
  - Sets up tarball state (exists/doesn't exist)
  - Sets up container state (running/stopped/none)

### 2. Test Execution
- **Step 1**: Run the command being tested
  - Executes the actual command
  - Captures output and exit code

### 3. Validation
- Compares actual results with expected results
- Validates each step passes/fails as expected
- Generates detailed test report

## Test Results Format

The test framework generates comprehensive reports with:

- **Test Name**: Descriptive name for each test scenario
- **Description**: Detailed explanation of what the test validates
- **Steps**: Step-by-step execution results
- **Expected**: Expected results for each step
- **Pass**: Whether the test passed or failed
- **Error Details**: Specific error information for failed tests

## Example Output

```
Testing RUN command with automatic permutation generation
================================================================================
Generated 6 test cases for RUN command
================================================================================

Test 1/6: Fresh run - should PASS
------------------------------------------------------------
      Expected: Fresh run - should PASS
      Step 0: Preparing test environment...
      Setting up test state...
      Test state setup complete
      Step 0: Environment prepared
      Step 1: Running run command...
      Step 1: Command succeeded as expected
      Validating step results...
      Step 0: 'PASS' matches expected
      Step 1: 'PASS' matches expected
      All steps match expected results!
```

## Test Configuration

Tests use the `fabrinetes-dev-testing` container configuration:

- **Config File**: `containers/fabrinetes-dev-testing/config.toml`
- **Dockerfile**: `containers/fabrinetes-dev-testing/Dockerfile`
- **Package List**: `containers/fabrinetes-dev-testing/packages.txt`

## Key Features

### Automatic State Management
- **Image State**: Ensures images exist or are removed as needed
- **Tarball State**: Creates or removes tarballs for restore testing
- **Container State**: Manages running/stopped/none container states

### Comprehensive Coverage
- **Success Scenarios**: Tests that should pass
- **Failure Scenarios**: Tests that should fail gracefully
- **Edge Cases**: Boundary conditions and error states

### Detailed Reporting
- **Step-by-step Results**: Shows each test step execution
- **Expected vs Actual**: Compares results with expectations
- **Error Analysis**: Provides specific error details for debugging

## Best Practices

1. **Always test both success and failure scenarios**
2. **Use specific test numbers for debugging individual tests**
3. **Review test output carefully for unexpected behavior**
4. **Ensure test environment is clean before running tests**
5. **Use the testing container for all test operations**

## Troubleshooting

### Common Issues

1. **Test Setup Failures**: Usually indicate image/tarball state issues
2. **Command Execution Failures**: May indicate command logic problems
3. **Validation Failures**: Suggest expected results need updating

### Debugging Steps

1. Run individual test numbers to isolate issues
2. Check test setup output for state preparation problems
3. Review command execution output for specific errors
4. Verify expected results match actual command behavior

## Integration

The test framework integrates with:

- **Invoke Task System**: Uses `invoke` for task execution
- **Docker Management**: Handles image and container operations
- **Configuration System**: Uses TOML config files for test setup
- **Helper Functions**: Leverages shared utility functions

This comprehensive testing system ensures all Fabrinetes commands work correctly across all supported scenarios and edge cases.
