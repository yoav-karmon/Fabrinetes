# Fabrinetes Bug Prevention Guide

## Overview
This document outlines common bugs and mistakes encountered during Fabrinetes development and provides guidelines to prevent them in future development.

## Critical Bug Categories

### 1. Import Organization Bugs

#### Problem: Imports Inside Functions
**Symptoms**:
- Performance degradation
- Code style violations
- Difficult debugging

**Root Cause**:
```python
def build(args, container_info):
    if help_flag:
        from command.help.help import show_build_help  # ❌ WRONG
        show_build_help()
```

**Prevention**:
```python
from command.help.help import show_build_help  # ✅ CORRECT

def build(args, container_info):
    if help_flag:
        show_build_help()
```

**Guidelines**:
- Always import at module level
- Organize imports: standard library → third-party → local
- Use alphabetical ordering within groups
- Avoid conditional imports unless absolutely necessary

### 2. Path Handling Bugs

#### Problem: Mixed Original and Resolved Paths
**Symptoms**:
- Inconsistent command output
- Confusing comments
- Debugging difficulties

**Root Cause**:
```python
# Comment shows resolved path (confusing)
print_aligned_comment(f"#     -v {resolved_path}:{container_path}", "# Mount from config", comment_column)
# Executable shows resolved path (correct)
cmd_parts.append(f"-v {resolved_path}:{container_path}")
```

**Prevention**:
```python
# Comment shows original TOML value (clear)
print_aligned_comment(f"#     -v {original_path}:{container_path}", "# Mount from config", comment_column)
# Executable shows resolved path (correct)
cmd_parts.append(f"-v {resolved_path}:{container_path}")
```

**Guidelines**:
- Always show original TOML values in comments
- Always show resolved absolute paths in executable commands
- Maintain clear separation between configuration and execution
- Use dual path display consistently across all commands

### 3. Error Handling Bugs

#### Problem: Inconsistent Error Message Formats
**Symptoms**:
- Confusing error messages
- Broken piped execution
- Inconsistent user experience

**Root Cause**:
```python
# Inconsistent error formats
print(f"Error: {error_msg}")           # ❌ WRONG
print(f"echo '{error_msg}'")           # ❌ WRONG
print(f"echo 'error: {error_msg}'")    # ✅ CORRECT
```

**Prevention**:
```python
# Always use consistent error format
print(f"echo 'error: {error_msg}'")
```

**Guidelines**:
- Always use `echo 'error: ...'` format for all errors
- Design commands to work with `| bash` piping
- Always show full command structure even on validation failure
- Provide clear, actionable error messages

### 4. Command Building Bugs

#### Problem: Duplicated Command Building Logic
**Symptoms**:
- Inconsistent command output
- Difficult maintenance
- Code duplication

**Root Cause**:
```python
# Each command has its own building logic
def build_command():
    # Custom logic for build command
    pass

def run_command():
    # Custom logic for run command (duplicated)
    pass
```

**Prevention**:
```python
# Use unified command building system
from helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartArg

def build_command():
    builder = CommandBuilder("Build")
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory"))
    builder.add_part("image_name", CmdPartArg("-t", "image_docker"))
    return builder.build_command(container_info)
```

**Guidelines**:
- Always use the unified command building system
- Use appropriate CmdPart subclasses for different command components
- Avoid duplicating command building logic
- Maintain consistent output format across all commands

### 5. File Size Management Bugs

#### Problem: Files Exceeding 400 Lines
**Symptoms**:
- Difficult maintenance
- Poor readability
- Code organization issues

**Root Cause**:
- Not extracting common functionality
- Not creating helper functions
- Not caching operations

**Prevention**:
- Extract common functionality into shared utilities
- Create helper functions in separate files
- Cache frequently used operations at function start
- Split large files into focused modules

**Guidelines**:
- Keep files under ~400 lines
- Reuse functions across files
- Create helper functions when needed
- Cache operations for efficiency

### 6. Validation Bugs

#### Problem: Missing Path Validation
**Symptoms**:
- Commands fail at runtime
- Confusing error messages
- Poor user experience

**Root Cause**:
```python
# No validation before command execution
cmd_parts.append(f"-f {dockerfile_path}")
```

**Prevention**:
```python
# Validate paths before command execution
if container_info.image_dockerfile_resolved is None:
    print(f"echo 'error: Dockerfile not found at {container_info.image_dockerfile}'")
    return
cmd_parts.append(f"-f {container_info.image_dockerfile_resolved}")
```

**Guidelines**:
- Always validate paths before command execution
- Use ContainerInfo validation methods
- Provide clear error messages for validation failures
- Show command structure even on validation failure

### 7. Container Lifecycle Bugs

#### Problem: Containers Not Staying Running
**Symptoms**:
- Containers exit immediately
- Commands fail to start containers
- Confusing behavior

**Root Cause**:
```python
# Missing long-running command
cmd_parts.append("bash")  # ❌ WRONG - bash exits immediately
```

**Prevention**:
```python
# Use long-running command
cmd_parts.append("sleep infinity")  # ✅ CORRECT - keeps container running
```

**Guidelines**:
- Always use long-running commands for persistent containers
- Use `sleep infinity` for containers that should stay running
- Ensure proper Docker flags (`-dit` for detached, interactive, tty)
- Test container lifecycle thoroughly

### 8. Mount Path Resolution Bugs

#### Problem: Invalid Mount Paths
**Symptoms**:
- Docker volume creation errors
- Containers fail to start
- Path resolution issues

**Root Cause**:
```python
# Relative paths not resolved to absolute paths
mounts.append(f"-v {relative_path}:{container_path}")  # ❌ WRONG
```

**Prevention**:
```python
# Resolve relative paths to absolute paths
resolved_path = os.path.abspath(os.path.join(working_directory, relative_path))
mounts.append(f"-v {resolved_path}:{container_path}")  # ✅ CORRECT
```

**Guidelines**:
- Always resolve relative paths to absolute paths
- Expand environment variables in paths
- Validate mount paths before use
- Use proper path resolution functions

## Prevention Strategies

### 1. Code Review Checklist
Before submitting code, verify:
- [ ] All imports at top of file
- [ ] File under 400 lines
- [ ] Consistent error handling
- [ ] Proper path validation
- [ ] Dual path display working
- [ ] Command structure always shown
- [ ] Piped execution works

### 2. Testing Strategy
- **Unit Testing**: Test individual functions
- **Integration Testing**: Test complete workflows
- **Error Testing**: Test error scenarios
- **Piped Execution Testing**: Test with `| bash` piping

### 3. Documentation Standards
- **Code Comments**: Document complex logic
- **Function Docstrings**: Include parameter and return descriptions
- **Help Text**: Provide comprehensive help for all commands
- **README Updates**: Keep documentation current

### 4. Development Workflow
- **Small Commits**: Make small, focused commits
- **Test Frequently**: Test after each change
- **Review Code**: Self-review before submitting
- **Follow Patterns**: Use established patterns consistently

## Common Anti-Patterns to Avoid

### 1. Import Anti-Patterns
```python
# ❌ DON'T: Import inside functions
def function():
    from module import something
    return something()

# ❌ DON'T: Conditional imports unless necessary
if condition:
    import module

# ❌ DON'T: Import everything
from module import *
```

### 2. Path Handling Anti-Patterns
```python
# ❌ DON'T: Mix original and resolved paths in comments
print(f"#     -v {resolved_path}:{container_path}")

# ❌ DON'T: Skip path validation
cmd_parts.append(f"-f {path}")

# ❌ DON'T: Use relative paths in executable commands
cmd_parts.append(f"-v {relative_path}:{container_path}")
```

### 3. Error Handling Anti-Patterns
```python
# ❌ DON'T: Use inconsistent error formats
print(f"Error: {error}")
print(f"echo '{error}'")

# ❌ DON'T: Hide command structure on errors
if error:
    print(f"Error: {error}")
    return  # Missing command structure

# ❌ DON'T: Use confusing error messages
print("Something went wrong")
```

### 4. Command Building Anti-Patterns
```python
# ❌ DON'T: Duplicate command building logic
def build_command():
    # Custom logic
    pass

def run_command():
    # Similar custom logic (duplicated)
    pass

# ❌ DON'T: Inconsistent output formats
print("# Different format for each command")
```

## Best Practices Summary

### 1. Code Organization
- Keep files under 400 lines
- Import at module level
- Use consistent patterns
- Extract common functionality

### 2. Error Handling
- Use `echo 'error: ...'` format
- Always show command structure
- Design for piped execution
- Provide clear error messages

### 3. Path Handling
- Show original TOML values in comments
- Show resolved paths in executable commands
- Validate all paths before use
- Use proper path resolution

### 4. Testing
- Test all commands
- Test error scenarios
- Test piped execution
- Test integration workflows

### 5. Documentation
- Keep documentation current
- Provide comprehensive help
- Document complex logic
- Include usage examples

Following these guidelines will help prevent common bugs and maintain high code quality in the Fabrinetes project.

---

## Document History

**Last Updated:** Commit `2b7ed23bd1f39af0323d1846d3cb68c40b31713f` - Add documentation files to doc/ folder (2025-10-19)
