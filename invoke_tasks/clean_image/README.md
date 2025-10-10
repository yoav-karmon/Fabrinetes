# Clean Image Task Documentation

## Overview

The `clean_image` task removes Docker images and associated containers. It provides comprehensive cleanup functionality for managing Docker resources.

## Usage

```bash
# Clean specific image
./fabrinetes clean-image <image-name>

# Show help
./fabrinetes clean-image
```

## Arguments

- `<image-name>`: Name of the image to clean (required)

## Features

### Image Removal
- Removes specified Docker image
- Handles image dependencies
- Force removal of images in use

### Container Cleanup
- Stops running containers using the image
- Removes stopped containers
- Prevents orphaned containers

### Tarball Management
- Removes associated tarball files
- Cleans up image storage directories
- Maintains clean file system

## Example Usage

```bash
# Clean a specific image
./fabrinetes clean-image fabrinetes-dev-testing:latest

# Clean base image
./fabrinetes clean-image fabrinetes-skeleton:latest
```

## Process Flow

1. **Validation**: Verify image name is provided
2. **Container Check**: Find containers using the image
3. **Container Cleanup**: Stop and remove containers
4. **Image Removal**: Remove the Docker image
5. **Tarball Cleanup**: Remove associated tarball files
6. **Directory Cleanup**: Clean up empty directories

## Error Handling

- **Missing Arguments**: Shows help if image name not provided
- **Image Not Found**: Gracefully handles non-existent images
- **Permission Errors**: Handles Docker permission issues
- **Dependency Conflicts**: Resolves image dependency issues

## Integration

### With Other Tasks
- **gen_image**: Cleans up after failed builds
- **run**: Removes images before rebuilding
- **test**: Cleans up test images

### Configuration
- Uses image name format from config system
- Integrates with tarball management
- Follows Docker naming conventions

## Files

- `clean_image.py`: Main clean image task implementation

## Dependencies

- Docker
- Python invoke framework
- Helper functions for image management
- Configuration name generation

## Best Practices

1. **Always specify exact image name** to avoid accidental removal
2. **Check running containers** before cleaning images
3. **Use with caution** as removal is irreversible
4. **Clean up regularly** to manage disk space
5. **Test cleanup** in development environments first

## Troubleshooting

### Common Issues

1. **Image in use**: Stop containers before cleaning
2. **Permission denied**: Ensure Docker access permissions
3. **Tarball not found**: Normal if no tarball exists
4. **Directory cleanup fails**: Check file system permissions

### Debug Steps

1. Check if image exists: `docker images <image-name>`
2. Check running containers: `docker ps`
3. Check stopped containers: `docker ps -a`
4. Verify tarball location: `find . -name "*.tar.gz"`

## Safety Features

- **Validation**: Prevents accidental cleanup of wrong images
- **Dependency Checking**: Ensures safe removal order
- **Error Recovery**: Continues cleanup even if some steps fail
- **Logging**: Provides detailed output for troubleshooting
