# Fabrinetes Development Best Practices

## Code Design Guidelines

### 1. Single Source of Truth
- **Consolidate Queries**: If there are queries in the code, consolidate them into one source using a single data class
- **Centralized Configuration**: All configuration managed through `ContainerInfo` dataclass
- **Consistent Naming**: Use centralized naming system for containers and images

### 2. Data Classes
- **Member Functions**: Put all functions used as member functions
- **Process Once**: Call process once in code, then pass as reference
- **Validation**: Include validation methods in data classes

### 3. Import Organization
- **Top of File**: All imports done on top of file
- **Standard Library First**: Standard library imports first
- **Third-Party Second**: Third-party imports second
- **Local Last**: Local imports last
- **Alphabetical Ordering**: Within each import group

### 4. File Size Management
- **Under 400 Lines**: Keep files under ~400 lines per file
- **Reuse Functions**: Extract common functionality into shared utilities
- **Helper Functions**: Create helper functions in new files if needed
- **Cache Operations**: Cache frequently used operations at function start

## Command Development Patterns

### 1. Command Structure
All commands should follow this consistent pattern:

```python
def command_name(args, container_info):
    """Generate Docker command for specific operation"""
    # Extract arguments
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_command_help()
        return
    
    # Create command builder
    builder = CommandBuilder("Command Type")
    builder.set_base_command(["docker", "command"])
    
    # Add parts
    builder.add_part("workdir", CmdPartEnv("WORKDIR", container_member="working_directory"))
    builder.add_part("image_name", CmdPartArg("-t", "image_docker"))
    
    # Build and execute command
    commented_str, execution_str, errors = builder.build_command(container_info)
    print(commented_str)
    print(execution_str)
```

### 2. Error Handling
- **Consistent Format**: Use `echo 'error: ...'` format for all errors
- **Command Structure**: Always show full command structure even on validation failure
- **Piped Execution**: Design commands to work with `| bash` piping

### 3. Path Handling
- **Dual Display**: Show original TOML values in comments, resolved paths in executable commands
- **Validation**: Validate all paths before command execution
- **Error Messages**: Provide clear error messages when paths don't exist

## Testing Guidelines

### 1. Command Testing
- **Test All Commands**: Verify all commands work correctly
- **Test Error Cases**: Test validation failures and error handling
- **Test Help**: Verify help functionality works
- **Test Piped Execution**: Test commands with `| bash` piping

### 2. Integration Testing
- **Full Workflow**: Test complete container lifecycle
- **Multiple Configs**: Test with different configuration files
- **Error Scenarios**: Test with missing files and invalid configurations

## Documentation Standards

### 1. Code Documentation
- **Docstrings**: Include docstrings for all functions and classes
- **Comments**: Add comments for complex logic
- **Type Hints**: Use type hints for function parameters and return values

### 2. User Documentation
- **Help Text**: Provide comprehensive help text for all commands
- **Examples**: Include usage examples in help text
- **README**: Keep README updated with new features

## Common Pitfalls to Avoid

### 1. Import Issues
- **Don't**: Import inside functions
- **Do**: Import at top of file
- **Don't**: Use conditional imports unless necessary
- **Do**: Organize imports by standard library → third-party → local

### 2. Path Handling
- **Don't**: Mix original and resolved paths in comments
- **Do**: Show original TOML values in comments, resolved paths in executable commands
- **Don't**: Skip path validation
- **Do**: Validate all paths before command execution

### 3. Error Handling
- **Don't**: Use inconsistent error message formats
- **Do**: Use `echo 'error: ...'` format for all errors
- **Don't**: Hide command structure on errors
- **Do**: Always show full command structure for debugging

### 4. File Organization
- **Don't**: Create files over 400 lines
- **Do**: Split large files into smaller, focused modules
- **Don't**: Duplicate code across files
- **Do**: Extract common functionality into shared utilities

## Performance Considerations

### 1. Import Optimization
- **Module-Level Imports**: Import at module level for better performance
- **Lazy Loading**: Avoid importing heavy modules unless needed
- **Import Caching**: Python caches imports, so module-level imports are more efficient

### 2. Function Design
- **Cache Operations**: Cache frequently used operations at function start
- **Avoid Repeated Calculations**: Store results of expensive operations
- **Efficient Data Structures**: Use appropriate data structures for the task

### 3. Memory Management
- **Avoid Large Objects**: Keep large objects in scope only when needed
- **Clean Up Resources**: Properly clean up file handles and other resources
- **Efficient String Operations**: Use string builders for multiple concatenations

## Code Review Checklist

### 1. Code Quality
- [ ] All imports at top of file
- [ ] File under 400 lines
- [ ] Consistent error handling
- [ ] Proper path validation
- [ ] Clear documentation

### 2. Functionality
- [ ] Command works correctly
- [ ] Error handling works
- [ ] Help functionality works
- [ ] Piped execution works
- [ ] Dual path display works

### 3. Testing
- [ ] All commands tested
- [ ] Error cases tested
- [ ] Integration tested
- [ ] Performance acceptable

## Future Development

### 1. New Commands
When adding new commands:
- Follow the established command pattern
- Use the unified command building system
- Include comprehensive help text
- Test thoroughly

### 2. New Features
When adding new features:
- Consider impact on existing commands
- Maintain backward compatibility
- Update documentation
- Follow established patterns

### 3. Refactoring
When refactoring:
- Maintain existing functionality
- Update all affected files
- Test thoroughly
- Update documentation

This guide ensures consistent, maintainable, and reliable code across the Fabrinetes project.
