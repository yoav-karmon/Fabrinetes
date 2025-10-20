#!/usr/bin/env python3

"""
Command-specific validation functions for test framework.

This module contains validation logic for each command type, providing
detailed analysis of command outputs for both success and failure cases.
"""

from invoke import Context


def validate_command_result(ctx: Context, result, container_name: str, command: str, expected_results: dict) -> str:
    """
    Main validation dispatcher that routes to command-specific validators.
    
    Args:
        ctx: Invoke context
        result: Command execution result
        container_name: Name of the container being tested
        command: Command being tested
        expected_results: Expected results dictionary
        
    Returns:
        "PASS" or "FAIL" based on validation
    """
    
    # General crash detection - check for system errors
    if _is_crash_error(result):
        return "FAIL"
    
    # Route to command-specific validator
    validator_map = {
        "run": validate_run_result,
        "gen-image": validate_gen_image_result,
        "gen-image-base": validate_gen_image_base_result,
        "clean-image": validate_clean_image_result,
        "exec": validate_exec_result,
        "shell": validate_shell_result,
        "clean": validate_clean_result,
    }
    
    validator_func = validator_map.get(command, validate_default_result)
    return validator_func(ctx, result, container_name, expected_results)


def _is_crash_error(result) -> bool:
    """
    Check for system-level errors that indicate a crash or configuration issue.
    
    Args:
        result: Command execution result
        
    Returns:
        True if crash detected, False otherwise
    """
    crash_indicators = [
        "TomlDecodeError",
        "KeyError", 
        "FileNotFoundError",
        "ModuleNotFoundError",
        "ImportError",
        "SyntaxError",
        "IndentationError",
        "AttributeError",
        "TypeError",
        "ValueError",
        "PermissionError",
        "OSError",
        "EOFError",
        "KeyboardInterrupt",
        "SystemExit",
        "Traceback",
        "Exception:",
        "Error:",
        "Fatal:",
        "Critical:",
        "Aborted",
        "Segmentation fault",
        "Bus error",
        "Stack overflow"
    ]
    
    stdout_text = result.stdout.lower()
    stderr_text = result.stderr.lower()
    
    for indicator in crash_indicators:
        if indicator.lower() in stdout_text or indicator.lower() in stderr_text:
            return True
    
    return False


def validate_run_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate run command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "already running",
            "already exists", 
            "not available and restore failed",
            "Error:",
            "not found",
            "not running"
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases
        success_indicators = [
            "started successfully",
            "restarted successfully",
            "Container",
            "✅"
        ]
        
        for indicator in success_indicators:
            if indicator in result.stdout:
                # Verify container is actually running
                running_check = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True)
                return "PASS" if running_check.stdout.strip() else "FAIL"
        
        return "FAIL"


def validate_gen_image_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate gen-image command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "not available and restore failed",
            "Error:",
            "not found",
            "Cannot install packages",
            "No packages found",
            "❌",
            "gen-image",  # Help text contains command name
            "Generate Docker image",  # Help text contains description
            "Arguments:",  # Help text contains arguments section
            "Examples:"  # Help text contains examples section
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases
        success_indicators = [
            "already exists locally",
            "already exists - skipping reproduction",
            "Successfully",
            "successfully",
            "✅",
            "Image",
            "Tarball",
            "created successfully",
            "restored successfully",
            "built successfully",
            "exported successfully"
        ]
        
        for indicator in success_indicators:
            if indicator in result.stdout:
                return "PASS"
        
        return "FAIL"


def validate_gen_image_base_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate gen-image --base-image command results"""
    return validate_gen_image_result(ctx, result, container_name, expected_results)


def validate_clean_image_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate clean-image command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "Error:",
            "not found",
            "❌"
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases
        success_indicators = [
            "Successfully",
            "successfully",
            "✅",
            "cleaned",
            "removed",
            "deleted",
            "Clean operation completed"
        ]
        
        for indicator in success_indicators:
            if indicator in result.stdout:
                return "PASS"
        
        return "FAIL"


def validate_exec_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate exec command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "Error:",
            "not found",
            "not running",
            "❌"
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases
        success_indicators = [
            "echo test",
            "test",
            "✅",
            "executed"
        ]
        
        for indicator in success_indicators:
            if indicator in result.stdout:
                return "PASS"
        
        return "FAIL"


def validate_shell_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate shell command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "Error:",
            "not found",
            "not running",
            "❌"
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases - shell commands typically don't return to stdout
        # They either succeed (return to shell) or fail
        if result.ok:
            return "PASS"
        else:
            return "FAIL"


def validate_clean_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Validate clean command results"""
    if expected_results.get(1) == "FAIL":
        # Expected failure cases
        failure_indicators = [
            "Error:",
            "not found",
            "❌"
        ]
        
        for indicator in failure_indicators:
            if indicator in result.stdout:
                return "FAIL"
        
        return "PASS"  # Unexpected success
    else:
        # Expected success cases
        success_indicators = [
            "Successfully",
            "successfully",
            "✅",
            "Clean operation completed",
            "cleaned",
            "removed",
            "deleted"
        ]
        
        for indicator in success_indicators:
            if indicator in result.stdout:
                return "PASS"
        
        return "FAIL"


def validate_default_result(ctx: Context, result, container_name: str, expected_results: dict) -> str:
    """Default validator for unknown commands"""
    if expected_results.get(1) == "FAIL":
        # For unknown commands, any output indicates failure
        return "FAIL" if result.ok else "PASS"
    else:
        # For unknown commands, success means command executed without error
        return "PASS" if result.ok else "FAIL"
