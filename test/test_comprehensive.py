#!/usr/bin/env python3
"""
Comprehensive Test Suite for Fabrinetes
========================================

This test suite covers all scenarios:
1. X11 configuration scenarios (enabled/disabled/custom/empty)
2. Command generation (run/build/exec/status/help)
3. Error handling and edge cases
4. Configuration validation
5. Multiple error collection
6. Pipe-friendly output validation

All tests use environment variables and relative paths for portability.
"""

import os
import sys
import tempfile
import subprocess
from pathlib import Path
from typing import List, Tuple, Dict, Any

# Test configuration
TEST_CONFIGS = {
    "valid_config": {
        "content": """[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",
    "init_env.sh:/etc/profile.d/init_env.sh"
]

[config.X11]
enable = true
mounts = [
    "/tmp/.X11-unix:/tmp/.X11-unix",
    "$HOME/.Xauthority:$HOME/.Xauthority:ro"
]

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
""",
        "expected_errors": 0
    },
    
    "x11_disabled": {
        "content": """[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh"
]

[config.X11]
enable = false

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
""",
        "expected_errors": 0
    },
    
    "x11_empty_mounts": {
        "content": """[config]

[config.X11]
enable = true
mounts = []

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
""",
        "expected_errors": 1
    },
    
    "multiple_mount_errors": {
        "content": """[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",
    "missing1:/container/path",
    "missing2:/container/path",
    "invalid-format",
    "missing3:/container/path"
]

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
""",
        "expected_errors": 1  # All mount errors combined into one
    },
    
    "multiple_error_types": {
        "content": """[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",
    "missing-mount:/container/path"
]

[config.image]
name = "nonexistent-image"
tag = "nonexistent-tag"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
""",
        "expected_errors": 2  # Mount error + image error
    },
    
    "missing_config_sections": {
        "content": """[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh"
]
""",
        "expected_errors": 1  # Missing required sections
    }
}

COMMANDS_TO_TEST = [
    ("run", ["--rm", "--usb", "--verbose"]),
    ("build", []),
    ("exec", ["--exec-cmd", "bash"]),
    ("status", []),
    ("help", [])
]

class TestResult:
    def __init__(self, test_name: str, passed: bool, message: str = "", details: str = ""):
        self.test_name = test_name
        self.passed = passed
        self.message = message
        self.details = details

class ComprehensiveTestSuite:
    def __init__(self):
        self.results: List[TestResult] = []
        self.fabrinetes_root = Path(__file__).parent.parent
        
    def run_test(self, test_name: str, test_func) -> TestResult:
        """Run a single test and record the result"""
        try:
            print(f"\n{'='*60}")
            print(f"TEST: {test_name}")
            print(f"{'='*60}")
            
            result = test_func()
            self.results.append(result)
            
            status = "PASS" if result.passed else "FAIL"
            print(f"\nResult: {status}")
            if result.message:
                print(f"Message: {result.message}")
            if result.details:
                print(f"Details: {result.details}")
                
            return result
            
        except Exception as e:
            error_result = TestResult(test_name, False, f"Test failed with exception: {e}")
            self.results.append(error_result)
            print(f"\nResult: FAIL")
            print(f"Exception: {e}")
            return error_result
    
    def create_test_config(self, config_name: str, config_dir: Path) -> Path:
        """Create a test configuration file"""
        config_data = TEST_CONFIGS[config_name]
        config_path = config_dir / "config.toml"
        config_path.write_text(config_data["content"])
        
        # Create dummy files that might be referenced
        (config_dir / "Dockerfile").write_text("FROM ubuntu:latest")
        (config_dir / "init_env.sh").write_text("#!/bin/bash")
        
        return config_path
    
    def run_fabrinetes_command(self, config_path: Path, command: str, extra_args: List[str] = None) -> Tuple[str, int]:
        """Run a fabrinetes command and return output and exit code"""
        cmd = [
            sys.executable, str(self.fabrinetes_root / "fabrinetes.py"),
            "--cmd", command,
            "--config-file", str(config_path)
        ]
        
        if extra_args:
            cmd.extend(extra_args)
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=self.fabrinetes_root)
            return result.stdout, result.returncode
        except Exception as e:
            return f"Error running command: {e}", 1
    
    def test_x11_scenarios(self) -> TestResult:
        """Test all X11 configuration scenarios"""
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        
        all_passed = True
        details = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Test valid X11 config
            config_path = self.create_test_config("valid_config", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "--net=host" in output and "-e DISPLAY" in output and "/tmp/.X11-unix" in output:
                details.append("✓ Valid X11 config: X11 support enabled")
            else:
                details.append("✗ Valid X11 config: Missing X11 support")
                all_passed = False
            
            # Test X11 disabled
            config_path = self.create_test_config("x11_disabled", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "--net=host" not in output and "-e DISPLAY" not in output:
                details.append("✓ X11 disabled: No X11 support")
            else:
                details.append("✗ X11 disabled: X11 support still present")
                all_passed = False
            
            # Test X11 empty mounts error
            config_path = self.create_test_config("x11_empty_mounts", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "echo 'error:" in output and "X11 is enabled but no mounts" in output:
                details.append("✓ X11 empty mounts: Proper error message")
            else:
                details.append("✗ X11 empty mounts: Missing or incorrect error")
                all_passed = False
        
        print(output)
        print("-" * 40)
        
        return TestResult(
            "X11 Configuration Scenarios",
            all_passed,
            f"X11 scenarios {'passed' if all_passed else 'failed'}",
            "\n".join(details)
        )
    
    def test_command_generation(self) -> TestResult:
        """Test all command generation scenarios"""
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        
        all_passed = True
        details = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_path = self.create_test_config("valid_config", config_dir)
            
            for command, extra_args in COMMANDS_TO_TEST:
                output, exit_code = self.run_fabrinetes_command(config_path, command, extra_args)
                
                # Different commands have different output patterns
                if command == "help":
                    if "Fabrinetes - Docker Container Management Tool" in output:
                        details.append(f"✓ {command} command: Generated successfully")
                    else:
                        details.append(f"✗ {command} command: Failed to generate")
                        all_passed = False
                elif command == "status":
                    if "Config Status:" in output or "Error:" in output:
                        details.append(f"✓ {command} command: Generated successfully")
                    else:
                        details.append(f"✗ {command} command: Failed to generate")
                        all_passed = False
                elif command == "build":
                    if "Docker Build (Image) Command:" in output:
                        details.append(f"✓ {command} command: Generated successfully")
                    else:
                        details.append(f"✗ {command} command: Failed to generate")
                        all_passed = False
                else:
                    if f"Docker {command.title()} Command:" in output:
                        details.append(f"✓ {command} command: Generated successfully")
                    else:
                        details.append(f"✗ {command} command: Failed to generate")
                        all_passed = False
        
        print(output)
        print("-" * 40)
        
        return TestResult(
            "Command Generation",
            all_passed,
            f"Command generation {'passed' if all_passed else 'failed'}",
            "\n".join(details)
        )
    
    def test_error_handling(self) -> TestResult:
        """Test error handling and edge cases"""
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        
        all_passed = True
        details = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Test missing config file
            nonexistent_config = config_dir / "nonexistent.toml"
            output, exit_code = self.run_fabrinetes_command(nonexistent_config, "run")
            
            if "Config file not found" in output:
                details.append("✓ Missing config file: Proper error message")
            else:
                details.append("✗ Missing config file: Missing error message")
                all_passed = False
            
            # Test invalid config structure - this should exit with error code, not generate echo
            config_path = self.create_test_config("missing_config_sections", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            # Config validation errors cause the program to exit, not generate echo commands
            if exit_code != 0 and "Error:" in output:
                details.append("✓ Invalid config: Proper error handling (program exits)")
            else:
                details.append("✗ Invalid config: Missing error handling")
                all_passed = False
        
        print(output)
        print("-" * 40)
        
        return TestResult(
            "Error Handling",
            all_passed,
            f"Error handling {'passed' if all_passed else 'failed'}",
            "\n".join(details)
        )
    
    def test_multiple_error_collection(self) -> TestResult:
        """Test comprehensive error collection"""
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        
        all_passed = True
        details = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            
            # Test multiple mount errors
            config_path = self.create_test_config("multiple_mount_errors", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "echo 'error:" in output and "missing1" in output and "missing2" in output and "invalid-format" in output:
                details.append("✓ Multiple mount errors: All errors collected")
            else:
                details.append("✗ Multiple mount errors: Not all errors collected")
                all_passed = False
            
            # Test multiple error types
            config_path = self.create_test_config("multiple_error_types", config_dir)
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "echo 'error:" in output and "missing-mount" in output and "nonexistent-image" in output:
                details.append("✓ Multiple error types: All error types collected")
            else:
                details.append("✗ Multiple error types: Not all error types collected")
                all_passed = False
        
        print(output)
        print("-" * 40)
        
        return TestResult(
            "Multiple Error Collection",
            all_passed,
            f"Error collection {'passed' if all_passed else 'failed'}",
            "\n".join(details)
        )
    
    def test_pipe_friendly_output(self) -> TestResult:
        """Test pipe-friendly output format"""
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        
        all_passed = True
        details = []
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir)
            config_path = self.create_test_config("multiple_error_types", config_dir)
            
            # Test pipe-friendly format
            output, exit_code = self.run_fabrinetes_command(config_path, "run")
            
            if "echo 'error:" in output and not output.strip().startswith("Error:"):
                details.append("✓ Pipe-friendly format: Uses echo 'error:' format")
            else:
                details.append("✗ Pipe-friendly format: Not using proper format")
                all_passed = False
            
            # Test that output can be piped to bash
            try:
                result = subprocess.run(
                    [sys.executable, str(self.fabrinetes_root / "fabrinetes.py"), 
                     "--cmd", "run", "--config-file", str(config_path)],
                    capture_output=True, text=True, cwd=self.fabrinetes_root
                )
                
                # Pipe the output to bash
                pipe_result = subprocess.run(
                    ["bash", "-c", result.stdout],
                    capture_output=True, text=True
                )
                
                if "error:" in pipe_result.stdout:
                    details.append("✓ Bash piping: Output pipes correctly to bash")
                else:
                    details.append("✗ Bash piping: Output doesn't pipe correctly")
                    all_passed = False
                    
            except Exception as e:
                details.append(f"✗ Bash piping: Exception during test: {e}")
                all_passed = False
        
        print(output)
        print("-" * 40)
        
        return TestResult(
            "Pipe-Friendly Output",
            all_passed,
            f"Pipe-friendly output {'passed' if all_passed else 'failed'}",
            "\n".join(details)
        )
    
    def run_all_tests(self):
        """Run all test scenarios"""
        print("COMPREHENSIVE FABRINETES TEST SUITE")
        print("="*60)
        print("Testing all scenarios: X11, commands, errors, validation, piping")
        print("="*60)
        
        # Run all test scenarios
        self.run_test("X11 Configuration Scenarios", self.test_x11_scenarios)
        self.run_test("Command Generation", self.test_command_generation)
        self.run_test("Error Handling", self.test_error_handling)
        self.run_test("Multiple Error Collection", self.test_multiple_error_collection)
        self.run_test("Pipe-Friendly Output", self.test_pipe_friendly_output)
        
        # Print summary
        print(f"\n{'='*60}")
        print("FINAL TEST SUMMARY")
        print(f"{'='*60}")
        
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        
        print(f"Tests passed: {passed}/{total}")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED!")
            return True
        else:
            print("❌ SOME TESTS FAILED!")
            print("\nFailed tests:")
            for result in self.results:
                if not result.passed:
                    print(f"  - {result.test_name}: {result.message}")
            return False

def main():
    """Main test runner"""
    test_suite = ComprehensiveTestSuite()
    success = test_suite.run_all_tests()
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
