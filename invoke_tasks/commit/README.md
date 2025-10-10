# Commit Task Documentation

## Overview

The `commit` task commits a running Docker container to a new image. It captures the current state of a container and saves it as a reusable image with optional tarball export.

## Usage

```bash
# Commit running container
./fabrinetes commit --container-name <container-name> [--tag <tag>] [--message <message>]

# Show help
./fabrinetes commit
```

## Arguments

- `--container-name`: Name of the running container to commit (required)
- `--tag`: Tag for the new image (optional)
- `--message`: Commit message (optional)

## Features

### Container Validation
- Verifies container is running
- Checks container exists
- Validates container state

### Image Creation
- Commits container to new image
- Applies specified tag
- Generates commit metadata

### Tarball Export
- Exports committed image to tarball
- Saves tarball in container's images directory
- Enables image restoration

## Example Usage

```bash
# Commit with default settings
./fabrinetes commit --container-name fabrinetes-dev-testing.latest.run

# Commit with custom tag and message
./fabrinetes commit --container-name my-container --tag v1.0 --message "Added new features"

# Commit and export to tarball
./fabrinetes commit --container-name test-container --tag latest
```

## Process Flow

1. **Validation**: Check container name is provided
2. **Container Check**: Verify container exists and is running
3. **Image Commit**: Create new image from container
4. **Tagging**: Apply specified tag to image
5. **Tarball Export**: Save image as tarball for persistence
6. **Cleanup**: Report success and provide usage information

## Configuration Integration

### Image Naming
- Uses configuration system for image names
- Generates consistent naming conventions
- Integrates with tarball management

### Tarball Management
- Saves tarballs in `containers/<name>/images/` directory
- Uses standardized tarball naming
- Enables image restoration

## Error Handling

- **Missing Arguments**: Shows help if container name not provided
- **Container Not Found**: Handles non-existent containers
- **Container Not Running**: Validates container state
- **Commit Failures**: Handles Docker commit errors
- **Tarball Export Failures**: Continues even if tarball export fails

## Integration

### With Other Tasks
- **run**: Commits containers started by run task
- **exec**: Commits containers after modifications
- **gen_image**: Alternative to building from Dockerfile
- **test**: Commits test containers for reuse

### Docker Integration
- Uses `docker commit` command
- Handles Docker image tagging
- Manages Docker image metadata

## Files

- `commit.py`: Main commit task implementation

## Dependencies

- Docker
- Python invoke framework
- Helper functions for image management
- Configuration name generation
- Tarball management functions

## Use Cases

### Development Workflow
1. Start container with `run` task
2. Make modifications via `exec` or `shell`
3. Commit changes with `commit` task
4. Use committed image for future runs

### Testing Workflow
1. Run test container
2. Install test dependencies
3. Commit test environment
4. Reuse committed image for tests

### Customization Workflow
1. Start base container
2. Customize environment
3. Commit customized image
4. Share customized image

## Best Practices

1. **Always commit running containers** - stopped containers can't be committed
2. **Use descriptive tags** - helps identify image versions
3. **Add commit messages** - documents changes made
4. **Regular commits** - save work frequently
5. **Test committed images** - verify they work as expected

## Troubleshooting

### Common Issues

1. **Container not running**: Start container before committing
2. **Permission denied**: Check Docker access permissions
3. **Commit fails**: Verify container state and Docker resources
4. **Tarball export fails**: Check disk space and permissions

### Debug Steps

1. Check container status: `docker ps`
2. Verify container exists: `docker ps -a`
3. Check Docker resources: `docker system df`
4. Verify tarball location: `ls containers/*/images/`

## Safety Features

- **State Validation**: Ensures container is in commitable state
- **Error Recovery**: Continues process even if some steps fail
- **Resource Management**: Handles Docker resource constraints
- **Logging**: Provides detailed output for troubleshooting
