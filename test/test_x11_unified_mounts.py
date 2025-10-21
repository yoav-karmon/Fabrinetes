#!/usr/bin/env python3
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Test scenarios:
# 1. X11 enabled with default mounts
# 2. X11 enabled with custom mounts
# 3. X11 disabled (enable = false)
# 4. X11 with empty mounts (should error)
# 5. No X11 section (should use defaults)
# 6. Combined: regular + X11 + USB mounts

def create_test_config(config_dir, x11_config):
    """Create test config with specified X11 configuration"""
    config_content = f"""[config]
mounts = [
    "$HOME/.ssh:$HOME/.ssh",
    "init_env.sh:/etc/profile.d/init_env.sh"
]

{x11_config}

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
"""
    config_path = config_dir / "config.toml"
    config_path.write_text(config_content)
    return config_path

def create_empty_test_config(config_dir, x11_config):
    """Create test config with NO regular mounts for empty mount testing"""
    config_content = f"""[config]
{x11_config}

[config.image]
name = "ubuntu"
tag = "20.04"
dockerfile_path = "Dockerfile"

[config.container]
name = "test-container"
"""
    config_path = config_dir / "config.toml"
    config_path.write_text(config_content)
    return config_path

def run_empty_test(test_name, x11_config, expected_patterns, unexpected_patterns=[]):
    """Run a test case with no regular mounts"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    
    # Create temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        
        # Create dummy files
        (config_dir / "Dockerfile").write_text("FROM ubuntu:latest")
        
        config_path = create_empty_test_config(config_dir, x11_config)
        
        # Run fabrinetes with test config
        cmd = f"python3 fabrinetes.py --cmd run --config-file {config_path}"
        output = os.popen(cmd).read()
        
        # Print actual output
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        print(output)
        print("-" * 40)
        
        # Check expected patterns
        passed = True
        for pattern in expected_patterns:
            if pattern in output:
                print(f"✓ Found: {pattern}")
            else:
                print(f"✗ Missing: {pattern}")
                passed = False
        
        # Check unexpected patterns
        for pattern in unexpected_patterns:
            if pattern not in output:
                print(f"✓ Absent: {pattern}")
            else:
                print(f"✗ Found (unexpected): {pattern}")
                passed = False
        
        print(f"\nResult: {'PASS' if passed else 'FAIL'}")
        return passed

def run_test(test_name, x11_config, expected_patterns, unexpected_patterns=[]):
    """Run a single test case"""
    print(f"\n{'='*60}")
    print(f"TEST: {test_name}")
    print(f"{'='*60}")
    
    # Create temp directory for test
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir)
        
        # Create dummy files
        (config_dir / "Dockerfile").write_text("FROM ubuntu:latest")
        (config_dir / "init_env.sh").write_text("#!/bin/bash")
        
        config_path = create_test_config(config_dir, x11_config)
        
        # Run fabrinetes with test config
        cmd = f"python3 fabrinetes.py --cmd run --config-file {config_path}"
        output = os.popen(cmd).read()
        
        # Print actual output
        print("\nACTUAL OUTPUT:")
        print("-" * 40)
        print(output)
        print("-" * 40)
        
        # Check expected patterns
        passed = True
        for pattern in expected_patterns:
            if pattern in output:
                print(f"✓ Found: {pattern}")
            else:
                print(f"✗ Missing: {pattern}")
                passed = False
        
        # Check unexpected patterns
        for pattern in unexpected_patterns:
            if pattern not in output:
                print(f"✓ Absent: {pattern}")
            else:
                print(f"✗ Found (unexpected): {pattern}")
                passed = False
        
        print(f"\nResult: {'PASS' if passed else 'FAIL'}")
        return passed

# Test cases
tests = [
    ("X11 enabled with defaults", 
     "[config.X11]\nenable = true",
     ["--net=host", "-e DISPLAY", "/tmp/.X11-unix", ".Xauthority"],
     []),
    
    ("X11 enabled with custom mounts",
     "[config.X11]\nenable = true\nmounts = [\"/custom/path:/container/path\"]",
     ["--net=host", "-e DISPLAY", "/custom/path:/container/path"],
     []),
    
    ("X11 disabled",
     "[config.X11]\nenable = false",
     [],
     ["--net=host", "-e DISPLAY", "# X11 GUI support"]),
    
    ("X11 empty mounts (error)",
     "[config.X11]\nenable = true\nmounts = []",
     ["echo 'error:"],
     []),
    
    ("No X11 section (defaults)",
     "",
     ["--net=host", "-e DISPLAY", "/tmp/.X11-unix"],
     []),
    
    ("Unified mounts comment",
     "[config.X11]\nenable = true",
     ["# Volume mounts"],
     ["# Enable X11 GUI support"]),
]

# Run all tests
print("X11 UNIFIED MOUNTS TEST SUITE")
print("="*60)

# Run regular tests
results = []
for name, config, expected, unexpected in tests:
    if name == "X11 empty mounts (error)":
        # Use empty test for this case
        result = run_empty_test(name, config, expected, unexpected)
    else:
        result = run_test(name, config, expected, unexpected)
    results.append(result)

# Summary
print(f"\n{'='*60}")
print(f"SUMMARY: {sum(results)}/{len(results)} tests passed")
print(f"{'='*60}")
sys.exit(0 if all(results) else 1)
