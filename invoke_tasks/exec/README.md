# Exec Task Documentation

## Overview

The `exec` task executes commands inside running Docker containers. It provides both interactive and non-interactive command execution with output capture and proper error handling.

## Usage

```bash
# Execute command in container
./fabrinetes exec --container-name <container-name> --command <command>

# Show help
./fabrinetes exec
```

## Arguments

- `--container-name`: Name of the running container (required)
- `--command`: Command to execute in the container (required)

## Features

### Command Execution
- Executes arbitrary commands in running containers
- Captures command output and error streams
- Returns proper exit codes
- Handles command failures gracefully

### Container Validation
- Verifies container exists
- Checks container is running
- Validates container state before execution

### Output Handling
- Captures stdout and stderr
- Preserves command output formatting
- Handles interactive commands
- Returns execution results

## Example Usage

```bash
# Execute simple command
./fabrinetes exec --container-name fabrinetes-dev-testing.latest.run --command "ls -la"

# Execute with environment variables
./fabrinetes exec --container-name my-container --command "echo \$HOME"

# Execute Python script
./fabrinetes exec --container-name test-container --command "python script.py"

# Execute with pipes
./fabrinetes exec --container-name dev-container --command "ps aux | grep python"
```

## Process Flow

1. **Validation**: Check container name and command are provided
2. **Container Check**: Verify container exists and is running
3. **Command Execution**: Execute command using `docker exec`
4. **Output Capture**: Capture and process command output
5. **Result Processing**: Handle exit codes and errors
6. **Reporting**: Display results and return status

## Integration

### With Other Tasks
- **run**: Execute commands in containers started by run task
- **shell**: Alternative to interactive shell access
- **test**: Execute test commands in test containers
- **pkg**: Execute package management commands

### Docker Integration
- Uses `docker exec` command
- Handles Docker container state
- Manages command execution environment
- Preserves container state

## Files

- `exec.py`: Main exec task implementation

## Dependencies

- Docker
- Python invoke framework
- Container state validation

## Use Cases

### Development Workflow
1. Start development container with `run`
2. Execute build commands with `exec`
3. Run tests with `exec`
4. Debug issues with `exec`

### Testing Workflow
1. Start test container
2. Execute test commands
3. Capture test output
4. Validate test results

### Maintenance Workflow
1. Start maintenance container
2. Execute maintenance commands
3. Update configurations
4. Restart services

## Best Practices

1. **Always verify container is running** before executing commands
2. **Use proper command quoting** for complex commands
3. **Handle command failures** appropriately
4. **Capture important output** for logging
5. **Test commands** before using in production

## Error Handling

- **Missing Arguments**: Shows help if required arguments missing
- **Container Not Found**: Handles non-existent containers
- **Container Not Running**: Validates container state
- **Command Failures**: Handles command execution errors
- **Permission Errors**: Handles Docker permission issues

## Troubleshooting

### Common Issues

1. **Container not running**: Start container before executing commands
2. **Command not found**: Verify command exists in container
3. **Permission denied**: Check container permissions
4. **Output not captured**: Verify command produces output

### Debug Steps

1. Check container status: `docker ps`
2. Verify container exists: `docker ps -a`
3. Test command manually: `docker exec <container> <command>`
4. Check container logs: `docker logs <container>`

## Advanced Usage

### Complex Commands
```bash
# Multi-line commands
./fabrinetes exec --container-name dev --command "cd /workspace && make clean && make build"

# Commands with special characters
./fabrinetes exec --container-name test --command "find . -name '*.py' -exec grep -l 'import' {} \;"

# Commands with environment
./fabrinetes exec --container-name prod --command "export PATH=/opt/bin:\$PATH && ./deploy.sh"
```

### Script Execution
```bash
# Execute shell scripts
./fabrinetes exec --container-name dev --command "bash /scripts/setup.sh"

# Execute Python scripts
./fabrinetes exec --container-name test --command "python /tests/run_tests.py"

# Execute with arguments
./fabrinetes exec --container-name build --command "make install PREFIX=/opt"
```

## Safety Features

- **Container Validation**: Ensures container is in valid state
- **Command Sanitization**: Handles special characters safely
- **Error Recovery**: Continues execution even if some commands fail
- **Resource Management**: Handles Docker resource constraints
- **Logging**: Provides detailed output for troubleshooting
