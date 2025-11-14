#!/usr/bin/env python3
"""
Environment and repository validation utilities for HDLForge
"""

import os
from pathlib import Path
import invoke


def capture_environment_variables(c: invoke.Context):
    """Capture environment variables set by update_repo_path function and validate repository environment"""
    invoked_dir = os.environ.get('ROOT_FOLDER', os.getcwd())
    
    # Run update_repo_path and capture environment variables
    try:
        result = c.run(f"cd {invoked_dir} && bash -i -c 'source ~/.bashrc && update_repo_path && env | grep -E \"^(REPO_TOP|PATH|PYTHONPATH)=\"'", hide=True)
    except Exception as e:
        print("❌ ERROR: Failed to run update_repo_path")
        print("   This usually means you're not in a Git repository")
        print(f"   Current directory: {invoked_dir}")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    # Parse the captured environment variables
    captured_vars = {}
    for line in result.stdout.split('\n'):
        if line.startswith('REPO_TOP='):
            repo_top = line.split('=', 1)[1]
            os.environ['REPO_TOP'] = repo_top
            captured_vars['REPO_TOP'] = repo_top
        elif line.startswith('PATH='):
            path = line.split('=', 1)[1]
            os.environ['PATH'] = path
            captured_vars['PATH'] = path
        elif line.startswith('PYTHONPATH='):
            pythonpath = line.split('=', 1)[1]
            os.environ['PYTHONPATH'] = pythonpath
            captured_vars['PYTHONPATH'] = pythonpath
    
    # Validate repository environment
    validate_repository_environment(captured_vars, invoked_dir)
    
    # Print captured environment variables nicely
    print("=" * 60)
    print("ENVIRONMENT VARIABLES SET BY update_repo_path:")
    print("=" * 60)
    for var_name, var_value in captured_vars.items():
        if var_name == 'PATH':
            # Show PATH entries on separate lines for readability
            path_entries = var_value.split(':')
            print(f"{var_name}:")
            for i, entry in enumerate(path_entries):
                print(f"  [{i+1}] {entry}")
        elif var_name == 'PYTHONPATH':
            # Show PYTHONPATH entries on separate lines for readability
            pythonpath_entries = var_value.split(':') if var_value else []
            print(f"{var_name}:")
            if pythonpath_entries:
                for i, entry in enumerate(pythonpath_entries):
                    print(f"  [{i+1}] {entry}")
            else:
                print("  (empty)")
        else:
            print(f"{var_name}: {var_value}")
    print("=" * 60)
    
    return captured_vars


def validate_repository_environment(captured_vars: dict, invoked_dir: str):
    """Validate that we're in a proper repository environment based on update_repo_path results"""
    
    # Check if REPO_TOP was captured
    if 'REPO_TOP' not in captured_vars or not captured_vars['REPO_TOP']:
        print("❌ ERROR: REPO_TOP not set by update_repo_path")
        print("   This usually means you're not in a Git repository")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    repo_top = captured_vars['REPO_TOP']
    repo_top_path = Path(repo_top)
    invoked_path = Path(invoked_dir)
    
    # Validate REPO_TOP directory exists
    if not repo_top_path.exists():
        print(f"❌ ERROR: REPO_TOP directory does not exist: {repo_top}")
        print("   Please check your Git repository structure")
        exit(1)
    
    # Validate REPO_TOP is a Git repository
    git_dir = repo_top_path / '.git'
    if not git_dir.exists():
        print(f"❌ ERROR: REPO_TOP is not a Git repository: {repo_top}")
        print("   Missing .git directory")
        exit(1)
    
    # Validate current directory is under REPO_TOP
    try:
        invoked_resolved = invoked_path.resolve()
        repo_top_resolved = repo_top_path.resolve()
        
        # Check if invoked directory is under REPO_TOP
        if not str(invoked_resolved).startswith(str(repo_top_resolved)):
            print(f"❌ ERROR: Current directory is not under REPO_TOP")
            print(f"   Current directory: {invoked_resolved}")
            print(f"   REPO_TOP: {repo_top_resolved}")
            print("   Please run HDLForge commands from within the repository")
            exit(1)
            
    except Exception as e:
        print(f"❌ ERROR: Failed to validate directory structure: {e}")
        exit(1)
    
    # Validate PATH contains expected repository tools
    if 'PATH' in captured_vars:
        path_entries = captured_vars['PATH'].split(':')
        repo_tools_path = str(repo_top_path / 'tools' / 'tool_box')
        
        if repo_tools_path not in path_entries:
            print(f"⚠️  WARNING: Repository tools not found in PATH")
            print(f"   Expected: {repo_tools_path}")
            print("   This may cause issues with HDLForge tools")
    
    print("✅ Repository environment validation passed")
    print(f"   REPO_TOP: {repo_top}")
    print(f"   Current directory: {invoked_dir}")
    print(f"   Git repository: ✓")
    print(f"   Directory structure: ✓")

"""
Environment and repository validation utilities for HDLForge
"""

import os
from pathlib import Path
import invoke


def capture_environment_variables(c: invoke.Context):
    """Capture environment variables set by update_repo_path function and validate repository environment"""
    invoked_dir = os.environ.get('ROOT_FOLDER', os.getcwd())
    
    # Run update_repo_path and capture environment variables
    try:
        result = c.run(f"cd {invoked_dir} && bash -i -c 'source ~/.bashrc && update_repo_path && env | grep -E \"^(REPO_TOP|PATH|PYTHONPATH)=\"'", hide=True)
    except Exception as e:
        print("❌ ERROR: Failed to run update_repo_path")
        print("   This usually means you're not in a Git repository")
        print(f"   Current directory: {invoked_dir}")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    # Parse the captured environment variables
    captured_vars = {}
    for line in result.stdout.split('\n'):
        if line.startswith('REPO_TOP='):
            repo_top = line.split('=', 1)[1]
            os.environ['REPO_TOP'] = repo_top
            captured_vars['REPO_TOP'] = repo_top
        elif line.startswith('PATH='):
            path = line.split('=', 1)[1]
            os.environ['PATH'] = path
            captured_vars['PATH'] = path
        elif line.startswith('PYTHONPATH='):
            pythonpath = line.split('=', 1)[1]
            os.environ['PYTHONPATH'] = pythonpath
            captured_vars['PYTHONPATH'] = pythonpath
    
    # Validate repository environment
    validate_repository_environment(captured_vars, invoked_dir)
    
    # Print captured environment variables nicely
    print("=" * 60)
    print("ENVIRONMENT VARIABLES SET BY update_repo_path:")
    print("=" * 60)
    for var_name, var_value in captured_vars.items():
        if var_name == 'PATH':
            # Show PATH entries on separate lines for readability
            path_entries = var_value.split(':')
            print(f"{var_name}:")
            for i, entry in enumerate(path_entries):
                print(f"  [{i+1}] {entry}")
        elif var_name == 'PYTHONPATH':
            # Show PYTHONPATH entries on separate lines for readability
            pythonpath_entries = var_value.split(':') if var_value else []
            print(f"{var_name}:")
            if pythonpath_entries:
                for i, entry in enumerate(pythonpath_entries):
                    print(f"  [{i+1}] {entry}")
            else:
                print("  (empty)")
        else:
            print(f"{var_name}: {var_value}")
    print("=" * 60)
    
    return captured_vars


def validate_repository_environment(captured_vars: dict, invoked_dir: str):
    """Validate that we're in a proper repository environment based on update_repo_path results"""
    
    # Check if REPO_TOP was captured
    if 'REPO_TOP' not in captured_vars or not captured_vars['REPO_TOP']:
        print("❌ ERROR: REPO_TOP not set by update_repo_path")
        print("   This usually means you're not in a Git repository")
        print("   Please run: cd <your_git_repo> && hdlforge <command>")
        exit(1)
    
    repo_top = captured_vars['REPO_TOP']
    repo_top_path = Path(repo_top)
    invoked_path = Path(invoked_dir)
    
    # Validate REPO_TOP directory exists
    if not repo_top_path.exists():
        print(f"❌ ERROR: REPO_TOP directory does not exist: {repo_top}")
        print("   Please check your Git repository structure")
        exit(1)
    
    # Validate REPO_TOP is a Git repository
    git_dir = repo_top_path / '.git'
    if not git_dir.exists():
        print(f"❌ ERROR: REPO_TOP is not a Git repository: {repo_top}")
        print("   Missing .git directory")
        exit(1)
    
    # Validate current directory is under REPO_TOP
    try:
        invoked_resolved = invoked_path.resolve()
        repo_top_resolved = repo_top_path.resolve()
        
        # Check if invoked directory is under REPO_TOP
        if not str(invoked_resolved).startswith(str(repo_top_resolved)):
            print(f"❌ ERROR: Current directory is not under REPO_TOP")
            print(f"   Current directory: {invoked_resolved}")
            print(f"   REPO_TOP: {repo_top_resolved}")
            print("   Please run HDLForge commands from within the repository")
            exit(1)
            
    except Exception as e:
        print(f"❌ ERROR: Failed to validate directory structure: {e}")
        exit(1)
    
    # Validate PATH contains expected repository tools
    if 'PATH' in captured_vars:
        path_entries = captured_vars['PATH'].split(':')
        repo_tools_path = str(repo_top_path / 'tools' / 'tool_box')
        
        if repo_tools_path not in path_entries:
            print(f"⚠️  WARNING: Repository tools not found in PATH")
            print(f"   Expected: {repo_tools_path}")
            print("   This may cause issues with HDLForge tools")
    
    print("✅ Repository environment validation passed")
    print(f"   REPO_TOP: {repo_top}")
    print(f"   Current directory: {invoked_dir}")
    print(f"   Git repository: ✓")
    print(f"   Directory structure: ✓")

