#!/usr/bin/env python3

from invoke import task
from tabulate import tabulate

@task
def exec(ctx, container_name=None, command=None, interactive=False):
    """
    Execute a command in a running container
    
    Args:
        container_name: Name of the running container
        command: Command to execute (must be quoted if contains spaces)
        interactive: Whether to run in interactive mode
    """
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not container_name or not command:
        show_command_help('exec', COMMAND_HELP['exec'])
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
    
    # Build docker exec command
    cmd_parts = ["docker", "exec"]
    
    if interactive:
        cmd_parts.extend(["-it"])
    
    cmd_parts.extend([container_name, command])
    
    # Execute the command
    print(f"Executing command in container '{container_name}': {command}")
    ctx.run(" ".join(cmd_parts), pty=True)
