# Kill Task Documentation

## Overview

The `kill` task stops and removes Docker containers. It provides safe container termination with proper cleanup and validation.

## Usage

```bash
# Kill specific container
./fabrinetes kill <container-name>

# Show help
./fabrinetes kill
```

## Arguments

- `<container-name>`: Name of the container to kill (required)

## Features

### Container Termination
- Stops running containers gracefully
- Force removes containers if needed
- Handles both running and stopped containers
- Prevents orphaned containers

### State Validation
- Verifies container exists
- Checks container state before termination
- Handles non-existent containers gracefully
- Provides clear status messages

### Cleanup Operations
- Removes container completely
- Cleans up container resources
- Prevents resource leaks
- Maintains clean Docker environment

## Example Usage

```bash
# Kill running container
./fabrinetes kill fabrinetes-dev-testing.latest.run

# Kill stopped container
./fabrinetes kill my-stopped-container

# Kill container with specific name
./fabrinetes kill test-container-123
```

## Process Flow

1. **Validation**: Check container name is provided
2. **Container Check**: Verify container exists
3. **State Check**: Determine if container is running or stopped
4. **Termination**: Stop container if running
5. **Removal**: Remove container completely
6. **Cleanup**: Clean up any remaining resources
7. **Reporting**: Report success or failure

## Integration

### With Other Tasks
- **run**: Kills containers started by run task
- **test**: Kills test containers after testing
- **exec**: Kills containers after command execution
- **clean_image**: Kills containers before image cleanup

### Docker Integration
- Uses `docker stop` for graceful termination
- Uses `docker rm -f` for force removal
- Handles Docker container state
- Manages container lifecycle

## Files

- `kill.py`: Main kill task implementation

## Dependencies

- Docker
- Python invoke framework
- Container state validation

## Use Cases

### Development Workflow
1. Start development container with `run`
2. Work with container via `exec` or `shell`
3. Kill container when done with `kill`
4. Clean up resources

### Testing Workflow
1. Start test container
2. Run tests
3. Kill test container
4. Clean up test environment

### Maintenance Workflow
1. Identify containers to remove
2. Kill containers safely
3. Clean up Docker environment
4. Free up resources

## Best Practices

1. **Always specify exact container name** to avoid accidental termination
2. **Check container status** before killing
3. **Use with caution** as termination is irreversible
4. **Kill containers regularly** to manage resources
5. **Verify termination** was successful

## Error Handling

- **Missing Arguments**: Shows help if container name not provided
- **Container Not Found**: Handles non-existent containers gracefully
- **Permission Errors**: Handles Docker permission issues
- **Termination Failures**: Handles container termination errors

## Troubleshooting

### Common Issues

1. **Container not found**: Verify container name and existence
2. **Permission denied**: Check Docker access permissions
3. **Termination fails**: Check container state and Docker resources
4. **Resource cleanup fails**: Check Docker system resources

### Debug Steps

1. Check container status: `docker ps -a`
2. Verify container exists: `docker ps --filter name=<container-name>`
3. Check Docker resources: `docker system df`
4. Test manual termination: `docker stop <container-name>`

## Advanced Usage

### Force Termination
The kill task automatically handles force termination when needed:
- Graceful stop first
- Force removal if graceful stop fails
- Complete cleanup of container resources

### Batch Operations
```bash
# Kill multiple containers
./fabrinetes kill container1
./fabrinetes kill container2
./fabrinetes kill container3
```

### Integration with Scripts
```bash
#!/bin/bash
# Kill all test containers
for container in $(docker ps -a --filter name=test --format "{{.Names}}"); do
    ./fabrinetes kill $container
done
```

## Safety Features

- **Validation**: Prevents accidental termination of wrong containers
- **State Checking**: Ensures safe termination order
- **Error Recovery**: Continues cleanup even if some steps fail
- **Resource Management**: Handles Docker resource constraints
- **Logging**: Provides detailed output for troubleshooting

## Container States

### Running Containers
- Gracefully stopped with `docker stop`
- Removed with `docker rm`
- Complete cleanup performed

### Stopped Containers
- Directly removed with `docker rm`
- No stop operation needed
- Immediate cleanup

### Non-existent Containers
- Handled gracefully
- No error thrown
- Clear status message provided
