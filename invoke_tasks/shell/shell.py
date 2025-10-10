#!/usr/bin/env python3

from invoke import task
from tabulate import tabulate

@task
def shell(ctx, container_name=None):
    """
    Open an interactive shell in a running container
    
    Args:
        container_name: Name of the running container
    """
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not container_name:
        show_command_help('shell', COMMAND_HELP['shell'])
        return
    
    # Check if container is running
    try:
        result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
        if not result.stdout.strip():
            print(f"Error: Container '{container_name}' is not running")
            print("Available running containers:")
            
            # Show running containers in a pretty table
            containers_result = ctx.run("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}'", hide=True, warn=True)
            if containers_result.stdout.strip():
                print(containers_result.stdout)
            else:
                print("No running containers found")
            return
    except Exception:
        print(f"Error: Could not check container status")
        return
    
    # Open interactive shell
    print(f"Opening shell in container '{container_name}'...")
    ctx.run(f"docker exec -it {container_name} bash", pty=True)

