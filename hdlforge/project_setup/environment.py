#!/usr/bin/env python3
"""
Environment and repository validation utilities for HDLForge.
"""

import os
from pathlib import Path

import invoke


ENVIRONMENT_VARIABLES = ("REPO_TOP", "PATH", "PYTHONPATH")


def capture_environment_variables(c: invoke.Context):
    """Capture inherited HDLForge environment variables and validate them."""
    _ = c
    invoked_dir = os.environ.get("ROOT_FOLDER", os.getcwd())
    captured_vars = {
        var_name: os.environ.get(var_name, "")
        for var_name in ENVIRONMENT_VARIABLES
    }

    validate_repository_environment(captured_vars, invoked_dir)
    print_environment_variables(captured_vars)

    return captured_vars


def print_environment_variables(captured_vars: dict):
    """Print captured HDLForge environment variables."""
    print("=" * 60)
    print("ENVIRONMENT VARIABLES INHERITED FROM HDLForge:")
    print("=" * 60)
    for var_name, var_value in captured_vars.items():
        if var_name == "PATH":
            print_path_entries(var_name, var_value)
        elif var_name == "PYTHONPATH":
            print_path_entries(var_name, var_value, empty_text="  (empty)")
        else:
            print(f"{var_name}: {var_value}")
    print("=" * 60)


def print_path_entries(var_name: str, var_value: str, empty_text: str | None = None):
    """Print a path-like variable one entry per line."""
    print(f"{var_name}:")
    entries = var_value.split(":") if var_value else []
    if not entries and empty_text is not None:
        print(empty_text)
        return
    for index, entry in enumerate(entries, start=1):
        print(f"  [{index}] {entry}")


def validate_repository_environment(captured_vars: dict, invoked_dir: str):
    """Validate that HDLForge inherited a usable repository environment."""
    repo_top = captured_vars.get("REPO_TOP", "")
    if not repo_top:
        print("❌ ERROR: REPO_TOP is not set")
        print("   HDLForge must source ~/.bashrc and run update_repo_path before Python tasks")
        print("   Please launch this task through the hdlforge wrapper")
        raise SystemExit(1)

    repo_top_path = Path(repo_top)
    invoked_path = Path(invoked_dir)

    if not repo_top_path.exists():
        print(f"❌ ERROR: REPO_TOP directory does not exist: {repo_top}")
        print("   Please check your Git repository structure")
        raise SystemExit(1)

    git_dir = repo_top_path / ".git"
    if not git_dir.exists():
        print(f"❌ ERROR: REPO_TOP is not a Git repository: {repo_top}")
        print("   Missing .git directory")
        raise SystemExit(1)

    try:
        invoked_resolved = invoked_path.resolve()
        repo_top_resolved = repo_top_path.resolve()
        if not str(invoked_resolved).startswith(str(repo_top_resolved)):
            print("❌ ERROR: Current directory is not under REPO_TOP")
            print(f"   Current directory: {invoked_resolved}")
            print(f"   REPO_TOP: {repo_top_resolved}")
            print("   Please run HDLForge commands from within the repository")
            raise SystemExit(1)
    except SystemExit:
        raise
    except Exception as error:
        print(f"❌ ERROR: Failed to validate directory structure: {error}")
        raise SystemExit(1)

    path_value = captured_vars.get("PATH", "")
    if path_value:
        path_entries = path_value.split(":")
        repo_tools_path = str(repo_top_path / "tools" / "tool_box")
        if repo_tools_path not in path_entries:
            print("⚠️  WARNING: Repository tools not found in PATH")
            print(f"   Expected: {repo_tools_path}")
            print("   This may cause issues with HDLForge tools")

    print("✅ Repository environment validation passed")
    print(f"   REPO_TOP: {repo_top}")
    print(f"   Current directory: {invoked_dir}")
    print("   Git repository: ✓")
    print("   Directory structure: ✓")
