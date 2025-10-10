#!/usr/bin/env python3

from invoke import task
from tabulate import tabulate

@task
def list(ctx):
    """List Docker images and containers with pretty formatting"""
    print("Docker Images:")
    print("=" * 50)
    
    # List images
    images_result = ctx.run("docker images --format 'table {{.Repository}}\\t{{.Tag}}\\t{{.ID}}\\t{{.CreatedAt}}\\t{{.Size}}'", hide=True, warn=True)
    if images_result.stdout.strip():
        print(images_result.stdout)
    else:
        print("No images found")
    
    print("\nDocker Containers:")
    print("=" * 50)
    
    # List all containers (running and stopped)
    containers_result = ctx.run("docker ps -a --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'", hide=True, warn=True)
    if containers_result.stdout.strip():
        print(containers_result.stdout)
    else:
        print("No containers found")

