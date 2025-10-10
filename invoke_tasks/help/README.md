# Help Task Documentation

## Overview

The `help` task provides comprehensive help and documentation for all Fabrinetes commands. It displays command-specific help, usage examples, and argument information in a user-friendly format.

## Usage

```bash
# Show general help
./fabrinetes help

# Show help for specific command
./fabrinetes help <command-name>
```

## Features

### General Help
- Displays overview of all available commands
- Shows command syntax and descriptions
- Provides usage examples
- Lists all supported commands

### Command-Specific Help
- Shows detailed help for individual commands
- Displays command arguments and options
- Provides usage examples
- Shows allowed values for arguments

### Pretty Table Formatting
- Uses tabulate library for clean output
- Organized command information
- Easy-to-read format
- Professional presentation

## Example Usage

```bash
# Show all available commands
./fabrinetes help

# Show help for run command
./fabrinetes help run

# Show help for gen-image command
./fabrinetes help gen-image
```

## Help Content Structure

### Command Table
- **Command**: Command name and syntax
- **Description**: Brief description of functionality
- **Arguments**: Required and optional arguments
- **Allowed Values**: Valid values for arguments

### Examples Section
- **Usage Examples**: Real-world usage examples
- **Command Variations**: Different ways to use commands
- **Common Patterns**: Typical usage patterns

## Integration

### With Other Tasks
- **All Commands**: Provides help for all Fabrinetes commands
- **Error Handling**: Shows help when commands fail
- **Validation**: Displays help for missing arguments

### Command System
- **Automatic Help**: Commands automatically show help when needed
- **Consistent Format**: All commands use same help format
- **Centralized Documentation**: Single source of help information

## Files

- `help.py`: Main help task implementation

## Dependencies

- Python invoke framework
- Tabulate library for table formatting
- Command help definitions

## Help Categories

### Container Management
- **run**: Start containers
- **exec**: Execute commands in containers
- **shell**: Open interactive shells
- **kill**: Stop and remove containers

### Image Management
- **gen-image**: Build images from configs
- **commit**: Commit containers to images
- **clean-image**: Remove images and containers
- **list**: Display containers and images

### Package Management
- **pkg**: Manage packages in containers

### Testing
- **test**: Run automated tests

## Best Practices

1. **Always show help** when commands fail
2. **Use descriptive examples** in help text
3. **Keep help text concise** but informative
4. **Update help** when adding new features
5. **Test help output** for accuracy

## Error Handling

- **Missing Commands**: Shows general help
- **Invalid Commands**: Shows available commands
- **Help Generation Failures**: Handles help system errors
- **Formatting Errors**: Handles table formatting issues

## Troubleshooting

### Common Issues

1. **Help not displaying**: Check Python dependencies
2. **Formatting issues**: Verify tabulate library installation
3. **Missing commands**: Check command registration
4. **Outdated help**: Update help definitions

### Debug Steps

1. Check Python installation: `python --version`
2. Verify tabulate library: `python -c "import tabulate"`
3. Test help command: `./fabrinetes help`
4. Check command registration: `./fabrinetes help <command>`

## Customization

### Adding New Commands
1. **Define Command**: Add command to help system
2. **Add Help Text**: Define help content
3. **Add Examples**: Provide usage examples
4. **Test Help**: Verify help displays correctly

### Modifying Help Content
1. **Update Definitions**: Modify help text in help.py
2. **Test Changes**: Verify help displays correctly
3. **Update Examples**: Keep examples current
4. **Validate Format**: Check table formatting

## Safety Features

- **Error Recovery**: Handles help generation failures
- **Fallback Help**: Shows basic help if detailed help fails
- **Validation**: Ensures help content is valid
- **Logging**: Provides debug information for help issues
