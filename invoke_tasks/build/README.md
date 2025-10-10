# Build Task Documentation

## Overview

The `build` task provides legacy image building functionality. This task is **deprecated** in favor of the modern `gen_image` task, which offers more advanced features and better integration with the configuration system.

## Status

⚠️ **DEPRECATED** - Use `gen_image` task instead

## Usage

```bash
# Legacy build command (deprecated)
./fabrinetes build <repository-name> [--skeleton] [--restore-only]
```

## Arguments

- `<repository-name>`: Name of the repository/container to build
- `--skeleton`: Build skeleton base image
- `--restore-only`: Only restore from tarball, don't build

## Features

- Basic image building from Dockerfiles
- Skeleton image creation
- Tarball restoration
- Package installation

## Migration to gen_image

The `build` task functionality has been superseded by the `gen_image` task, which provides:

- **Better Configuration**: Uses TOML config files instead of repository names
- **Advanced Features**: Base image management, package installation via `docker exec`
- **Improved Testing**: Comprehensive test coverage
- **Better Error Handling**: More robust error handling and validation

### Migration Example

**Old (deprecated):**
```bash
./fabrinetes build fabrinetes-dev-testing --skeleton
```

**New (recommended):**
```bash
./fabrinetes gen-image containers/fabrinetes-dev-testing/config.toml --base-image
```

## Files

- `build.py`: Main build task implementation

## Dependencies

- Docker
- Python invoke framework
- Helper functions for image management

## Notes

This task is maintained for backward compatibility but should not be used for new development. All new image building should use the `gen_image` task.
