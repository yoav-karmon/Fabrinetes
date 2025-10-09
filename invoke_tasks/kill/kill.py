#!/usr/bin/env python3

from invoke import task

@task
def kill(ctx, container_name=None):
    """
    Stop and remove a specific container (not the image)
    
    Args:
        container_name: Name of the container to kill
    """
    from tasks import show_command_help, COMMAND_HELP
    
    # Check for missing required arguments
    if not container_name:
        show_command_help('kill', COMMAND_HELP['kill'])
        return
    
    print(f"🛑 Killing container: {container_name}")
    print("=" * 50)
    
    # Check if container exists
    result = ctx.run(f"docker ps -a --filter name=^{container_name}$ --format '{{{{.Names}}}}'", hide=True)
    if not result.stdout.strip():
        print(f"❌ Container '{container_name}' not found")
        return
    
    # Check if container is running
    result = ctx.run(f"docker ps --filter name=^{container_name}$ --format '{{{{.Names}}}}'", hide=True)
    if result.stdout.strip():
        print(f"🛑 Stopping running container: {container_name}")
        ctx.run(f"docker stop {container_name}", hide=True)
        print("✅ Container stopped")
    else:
        print(f"ℹ️ Container '{container_name}' is already stopped")
    
    # Remove the container
    print(f"🗑️ Removing container: {container_name}")
    result = ctx.run(f"docker rm {container_name}", hide=True, warn=True)
    if result.ok:
        print("✅ Container removed successfully")
    else:
        print(f"❌ Failed to remove container: {result.stderr}")
        return
    
    print(f"\n✅ Container '{container_name}' killed successfully")
