# GitHub Container Registry (GHCR) Setup Guide

This guide explains how to store and manage Docker container images in GitHub Container Registry for the Fabrinetes FPGA development environment.

## Table of Contents
- [Overview](#overview)
- [Prerequisites](#prerequisites)
- [Authentication Setup](#authentication-setup)
- [Building and Tagging Images](#building-and-tagging-images)
- [Pushing to GHCR](#pushing-to-ghcr)
- [Pulling Images](#pulling-images)
- [Configuration Updates](#configuration-updates)
- [GitHub Actions Integration](#github-actions-integration)
- [Scripts Usage](#scripts-usage)
- [Troubleshooting](#troubleshooting)

## Overview

GitHub Container Registry (GHCR) provides a secure, scalable way to store and distribute Docker container images. For the Fabrinetes project, we use GHCR to:

- Store the `fabrinetes-image` container for FPGA development
- Enable team members to pull consistent development environments
- Version control container images
- Automate builds through GitHub Actions

## Prerequisites

Before using GHCR, ensure you have:

- A GitHub account
- Docker installed locally
- GitHub CLI (`gh`) or Docker CLI configured for authentication
- Access to the Fabrinetes repository

## Authentication Setup

### Option A: Using GitHub CLI (Recommended)

```bash
# Install GitHub CLI if not already installed
# Ubuntu/Debian:
sudo apt install gh

# Then authenticate
gh auth login
```


## Building and Tagging Images

### Manual Build Process

```bash
# Navigate to the project directory
cd /DATA/repo/Fabrinetes/363fpgadev-01/fabrinetes-dev1

# Build the image
docker build -t fabrinetes-image:latest .

# Tag for GHCR (replace YOUR_USERNAME with your GitHub username)
docker tag fabrinetes-image:latest ghcr.io/YOUR_USERNAME/fabrinetes-image:latest

# Optional: Tag with version numbers
docker tag fabrinetes-image:latest ghcr.io/YOUR_USERNAME/fabrinetes-image:v1.0.0
```

### Using the Build Script

Use the provided build script for automated building:

```bash
# From the Fabrinetes root directory
./doc/scripts/build-image.sh [version]
```

## Pushing to GHCR

### Manual Push Process

```bash
# Push the image
docker push ghcr.io/YOUR_USERNAME/fabrinetes-image:latest
docker push ghcr.io/YOUR_USERNAME/fabrinetes-image:v1.0.0
```

### Using the Push Script

```bash
# From the Fabrinetes root directory
./doc/scripts/push-image.sh [version]
```

## Pulling Images

### Manual Pull Process

```bash
# Pull the latest image
docker pull ghcr.io/YOUR_USERNAME/fabrinetes-image:latest

# Pull a specific version
docker pull ghcr.io/YOUR_USERNAME/fabrinetes-image:v1.0.0
```

### Using the Pull Script

```bash
# From the Fabrinetes root directory
./doc/scripts/pull-image.sh [version]
```

## Configuration Updates

Update your `config.toml` to reference the GHCR image:

```toml
[config.image]
name = "ghcr.io/YOUR_USERNAME/fabrinetes-image"
tag = "latest"
tarball_path = "fabrinetes-image:latest.tar.gz"
dockerfile_path = "Dockerfile"
package_list_path = "packages.txt"
```

## GitHub Actions Integration

### Automated Build and Push

Create `.github/workflows/docker-build.yml` in your repository:

```yaml
name: Build and Push Docker Image

on:
  push:
    branches: [ main ]
    paths:
      - 'Fabrinetes/363fpgadev-01/fabrinetes-dev1/**'
  pull_request:
    branches: [ main ]
    paths:
      - 'Fabrinetes/363fpgadev-01/fabrinetes-dev1/**'

jobs:
  build-and-push:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Log in to GitHub Container Registry
      uses: docker/login-action@v2
      with:
        registry: ghcr.io
        username: ${{ github.actor }}
        password: ${{ secrets.GITHUB_TOKEN }}
    
    - name: Extract metadata
      id: meta
      uses: docker/metadata-action@v4
      with:
        images: ghcr.io/${{ github.repository }}/fabrinetes-image
        tags: |
          type=ref,event=branch
          type=ref,event=pr
          type=semver,pattern={{version}}
          type=semver,pattern={{major}}.{{minor}}
    
    - name: Build and push Docker image
      uses: docker/build-push-action@v4
      with:
        context: ./Fabrinetes/363fpgadev-01/fabrinetes-dev1
        push: true
        tags: ${{ steps.meta.outputs.tags }}
        labels: ${{ steps.meta.outputs.labels }}
```

## Scripts Usage

The `doc/scripts/` directory contains several helper scripts:

- `build-image.sh` - Build the Docker image locally
- `push-image.sh` - Push image to GHCR
- `pull-image.sh` - Pull image from GHCR
- `setup-ghcr.sh` - Initial GHCR setup and authentication

### Script Examples

```bash
# Build image with latest tag
./doc/scripts/build-image.sh

# Build image with specific version
./doc/scripts/build-image.sh v1.2.3

# Push latest image
./doc/scripts/push-image.sh

# Push specific version
./doc/scripts/push-image.sh v1.2.3

# Pull latest image
./doc/scripts/pull-image.sh

# Pull specific version
./doc/scripts/pull-image.sh v1.2.3
```

## Package Visibility

### Making Packages Public

By default, packages are private. To make them public:

1. Go to your GitHub repository
2. Click on "Packages" tab
3. Find your `fabrinetes-image` package
4. Click on it and go to "Package settings"
5. Scroll down to "Danger Zone" and click "Change visibility"

### Managing Package Permissions

- **Read**: Allows users to pull the image
- **Write**: Allows users to push new versions
- **Admin**: Full control over the package

## Benefits of Using GHCR

- **Free for public repositories**: Unlimited public packages
- **Integrated with GitHub**: Seamless integration with your repositories
- **Fine-grained permissions**: Control who can access your packages
- **Vulnerability scanning**: Automatic security scanning
- **Version management**: Easy versioning and rollback
- **Bandwidth efficiency**: CDN-backed distribution

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   ```bash
   # Re-authenticate
   gh auth login
   # or
   docker login ghcr.io
   ```

2. **Permission Denied**
   - Check if you have write permissions to the repository
   - Verify your Personal Access Token has correct scopes

3. **Image Not Found**
   - Ensure the image name matches exactly
   - Check if the package is public or you have read access

4. **Build Failures**
   - Check Dockerfile syntax
   - Verify all required files are present
   - Check Docker daemon is running

### Getting Help

- Check GitHub Container Registry documentation
- Review Docker build logs for detailed error messages
- Ensure all prerequisites are installed and configured

## Security Considerations

- Use specific version tags instead of `latest` in production
- Regularly update base images for security patches
- Scan images for vulnerabilities using GHCR's built-in scanning
- Use multi-stage builds to reduce image size and attack surface
- Never store secrets or credentials in images

## Best Practices

1. **Versioning**: Use semantic versioning for tags
2. **Size Optimization**: Use multi-stage builds and .dockerignore
3. **Security**: Regularly update base images and dependencies
4. **Documentation**: Keep Dockerfile and scripts well-documented
5. **Testing**: Test images before pushing to production tags
