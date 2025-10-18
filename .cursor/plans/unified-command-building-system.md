# Unified Command Building System

## Overview
Create a unified command building system using a `cmd_part` class hierarchy to standardize command generation across all Docker commands (build, run, commit, restore).

## Design Goals
- Single source of truth for command building logic
- Consistent output format across all commands
- Unified error handling and path resolution
- Reusable components for different command types

## Architecture

### Base CmdPart Class
```python
class CmdPart:
    def __init__(self, prefix=None, hardcoded=None, container_member=None):
        self.prefix = prefix
        self.hardcoded = hardcoded
        self.container_member = container_member
        self.resolved_value = None
        self.error = None
    
    def comment_str(self) -> str:
        """Return commented version for display"""
        pass
    
    def execution_str(self) -> str:
        """Return executable version (no newlines)"""
        pass
    
    def resolve(self, container_info) -> bool:
        """Resolve values and return True if successful, False if error"""
        pass
```

### Specialized CmdPart Subclasses
- `CmdPartMount`: Handles volume mounts (-v)
- `CmdPartName`: Handles container/image names
- `CmdPartFile`: Handles file paths with validation
- `CmdPartFlag`: Handles boolean flags (--rm, --x11, etc.)
- `CmdPartEnv`: Handles environment variables (-e)
- `CmdPartArg`: Handles general arguments

### CommandBuilder Class
```python
class CommandBuilder:
    def __init__(self, command_type):
        self.command_type = command_type
        self.cmd_parts = {}
    
    def add_part(self, name, cmd_part):
        """Add a CmdPart to the builder"""
        pass
    
    def build_command(self, container_info) -> tuple:
        """Build command and return (commented_str, execution_str, errors)"""
        pass
```

## Task List

### Phase 1: Analysis and Design
1. **Analyze current command building patterns across all commands**
   - Files: `command/build/build.py`, `command/run/run.py`, `command/commit/commit.py`, `command/restore/restore.py`
   - Identify common patterns and differences

2. **Design base CmdPart class with comment_str and execution_str methods**
   - File: `helper_functions/command_builder.py` (new)
   - Define interface and base functionality

### Phase 2: Implementation
3. **Create specialized CmdPart subclasses (CmdPartMount, CmdPartName, CmdPartFile, etc.)**
   - File: `helper_functions/command_builder.py`
   - Implement specific logic for each command part type

4. **Implement resolve() method for each CmdPart subclass with error handling**
   - File: `helper_functions/command_builder.py`
   - Handle path resolution, validation, and error reporting

5. **Create CommandBuilder class to manage dictionary of CmdPart objects**
   - File: `helper_functions/command_builder.py`
   - Implement command building logic

### Phase 3: Refactoring
6. **Refactor build command to use new CommandBuilder system**
   - File: `command/build/build.py`
   - Replace existing command building logic

7. **Refactor run command to use new CommandBuilder system**
   - File: `command/run/run.py`
   - Replace existing command building logic

8. **Refactor commit command to use new CommandBuilder system**
   - File: `command/commit/commit.py`
   - Replace existing command building logic

9. **Refactor restore command to use new CommandBuilder system**
   - File: `command/restore/restore.py`
   - Replace existing command building logic

### Phase 4: Testing and Optimization
10. **Test all commands with new unified system**
    - Verify all commands work correctly
    - Test error handling scenarios

11. **Review and optimize file sizes to keep under ~400 lines**
    - Split large files if needed
    - Consolidate common functionality

12. **Update README with new unified command building approach**
    - File: `README.md`
    - Document new architecture and usage

## Benefits
- Consistent command output format
- Unified error handling
- Reusable components
- Easier maintenance and testing
- Single source of truth for command logic
