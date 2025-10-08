#!/usr/bin/env python3

from dataclasses import asdict, dataclass
import toml
from invoke import task
import os
import re
import sys
import shutil
import subprocess
import argparse
import time
import json
import yaml
from dataclasses import dataclass, asdict
import os
import toml
from tabulate import tabulate
import pathlib 
import logging
from typing import List, Tuple


logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def resolve_mounts(mounts: List[str], relative_path: pathlib.Path) -> List[Tuple[str, str]]:
    """
    Resolves a list of mount strings of the form 'host:container',
    expanding environment variables and resolving relative host paths
    against the provided relative_path.
    """
    resolved = []

    for entry in mounts:
        if ":" not in entry:
            raise ValueError(f"Invalid mount format (expected 'host:container'): {entry}")
        
        host_raw, container_raw = entry.split(":", 1)

        # Expand and resolve host path
        host_expanded = os.path.expandvars(host_raw)
        host_path = pathlib.Path(host_expanded)
        if not host_path.is_absolute():
            host_path = (relative_path / host_path).resolve()

        # Expand environment variables in container path
        container_path = os.path.expandvars(container_raw)

        resolved.append((str(host_path), container_path))

    return resolved


def printlocals(locals_dict,verbose=False):
    print("=== Current Argument Values ===")
    for key, value in locals_dict.items():
        if key != "ctx":
            if isinstance(value, dict) or isinstance(value, List):
                if(verbose):
                    print(f"{key:10} =")
                    print(json.dumps(value, indent=2))
            else:
                print(f"{key:10} = {value}")
        
    print("===============================")

@task
def build(ctx, repo=None):
    username = os.getenv("USER") or os.getenv("USERNAME")
    uid = os.getuid()
    gid = os.getgid()
    home_dir = os.path.expanduser("~")

    # If no repo specified, build all
    if not repo:
        repos = ["fabrinetes-dev", "fabrinetes-dev-testing"]
    else:
        repos = [repo]
    
    for repo_name in repos:
        dockerfile_path = f"containers/{repo_name}/Dockerfile"
        if not os.path.exists(dockerfile_path):
            print(f"Warning: Dockerfile not found for {repo_name} at {dockerfile_path}")
            continue
            
        print(f"Building {repo_name}...")
    ctx.run(
        f"docker build "
        f"--build-arg USERNAME={username} "
        f"--build-arg UID={uid} "
        f"--build-arg GID={gid} "
        f"--build-arg HOME_DIR={home_dir} "
            f"-t {repo_name}:latest -f {dockerfile_path} containers/{repo_name}/",
        pty=True,
    )

@task
def help(ctx):
    """Show help with pretty table of available repositories"""
    from tabulate import tabulate
    import subprocess
    
    print("=== Fabrinetes Help ===")
    print("")
    print("Available repositories:")
    
    def get_container_status(repo_name):
        """Check if container is running and return status"""
        try:
            result = subprocess.run(
                f"docker ps --filter ancestor={repo_name}:latest --format '{{{{.Names}}}}'",
                shell=True, capture_output=True, text=True, timeout=5
            )
            if result.stdout.strip():
                count = len(result.stdout.strip().split('\n'))
                return f"Running ({count})"
            else:
                return "Stopped"
        except:
            return "Unknown"
    
    table_data = []
    
    # Find all config files in containers directory
    containers_dir = "containers"
    if os.path.isdir(containers_dir):
        for root, dirs, files in os.walk(containers_dir):
            if "fabrinetes.config" in files:
                config_file = os.path.join(root, "fabrinetes.config")
                repo_name = os.path.basename(os.path.dirname(root))
                status = get_container_status(repo_name)
                
                table_data.append([
                    repo_name,
                    config_file,
                    status
                ])
    else:
        table_data.append(["No containers directory found", "", ""])
    
    if table_data:
        headers = ["Repository Name", "Config File", "Status"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("No container configurations found")
    
    print("")
    print("Examples:")
    print("  ./fabrinetes build [repo]")
    print("  ./fabrinetes list")
    print("  ./fabrinetes run --file <config> --name <repository> [--rm (auto-cleanup)] [--x11 (GUI support)] [--usb (hardware access)] [--ask (confirm)] [--verbose (details)]")
    print("  ./fabrinetes exec --container-name <name> --command '<cmd>' [--interactive]")
    print("  ./fabrinetes shell --container-name <name>")
    print("  ./fabrinetes clean --file <config> [--name <repository>]")
    print("")
    print("=== Executing 'list' command ===")
    print("")
    
    # Execute the list command
    list(ctx)


@task
def list(ctx):
    from tabulate import tabulate
    
    print("Docker Images")
    print("=" * 80)
    
    # Get images with better formatting
    result = ctx.run("docker images --format '{{.Repository}}\t{{.Tag}}\t{{.ID}}\t{{.CreatedAt}}\t{{.Size}}'", hide=True, warn=True)
    if result.stdout.strip():
        lines = result.stdout.strip().split('\n')
        headers = ["Repository", "Tag", "Image ID", "Created", "Size"]
        data = [line.split('\t') for line in lines]
        print(tabulate(data, headers=headers, tablefmt="grid"))
    else:
        print("No images found")
    
    print("\nDocker Containers")
    print("=" * 80)
    
    # Get containers with better formatting
    result = ctx.run("docker ps -a --format '{{.ID}}\t{{.Image}}\t{{.Command}}\t{{.CreatedAt}}\t{{.Status}}\t{{.Ports}}\t{{.Names}}'", hide=True, warn=True)
    if result.stdout.strip():
        lines = result.stdout.strip().split('\n')
        headers = ["Container ID", "Image", "Command", "Created", "Status", "Ports", "Names"]
        data = [line.split('\t') for line in lines]
        print(tabulate(data, headers=headers, tablefmt="grid"))
    else:
        print("No containers found")
    
    print()


@task
def run(ctx, file,rm=False,verbose=False,ver=None,name=None, x11=True,usb=False,ask=True):
   
   
    print("===============================")
    ctx.run("docker images", pty=True)
    print("===============================")
    print("")
    print("===============================")
    ctx.run("docker ps", pty=True)
    print("===============================")
    print("")

    if not os.path.isabs(file):
        base_path = os.environ.get("HDLFORGE_ORIG_PATH", os.getcwd())
        file = os.path.join(base_path, file)
    file = os.path.expandvars(file)
    file = os.path.abspath(file)
    _config_file_path = pathlib.Path(file).resolve()
    RELATIVE_PATH = _config_file_path.parent
    print("_config_file_path:", _config_file_path)
    try:
        database = toml.load(str(_config_file_path))
    except Exception as e:
        sys.exit(1)
        print(f"Error loading toml file '{file}': {e}")
    
    # Find container config by name
    container_config = None
    if "container" in database and name in database["container"]:
        container_config = database["container"][name]
    
    if not container_config:
        print(f"Available config setups (use with --name):")
        if "container" in database:
            for key in database["container"].keys():
                print(f"  {key}")
        exit()
    
    _image_repository = name
    _image_tag = container_config.get("TAG", "latest")
    IMAGE_NAME = f"{_image_repository}:{_image_tag}"

    MOUNTS_LIST = container_config.get("mounts", [])
    X11_path = container_config.get("X11_path", None)
    _this_file_path = pathlib.Path(__file__).resolve().parent

    MOUNTS_LIST.append(f"{_this_file_path}/source/bashrc-root:{os.getenv('HOME')}/.bashrc")
    MOUNTS_LIST.append(f"{_this_file_path}/source/project_setup/:/opt/project_setup")

    RESOLVED_MOUNTS_LIST=resolve_mounts(MOUNTS_LIST, RELATIVE_PATH)
    RESOLVED_MOUNTS_LIST:List[Tuple[str, str]]
        
    del database
    del _image_repository
    del _image_tag
    del _config_file_path

    printlocals(locals(),verbose)
    print("")

    cmd_parts=[]
    cmd_parts = ["docker run -dit"]
    if name:
        # Generate unique container name with timestamp
        import datetime
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        container_name = f"{name}-{timestamp}"
        cmd_parts.append(f"--name {container_name}")
    else:
        print("Error: You must provide a name for the container using --name")
        sys.exit(1)
        
   
    if rm:
        cmd_parts.append("--rm")
    if x11:
        if X11_path:
            print(f"X11 support enabled at {X11_path}")
            X11_path = os.path.expandvars(X11_path)
            X11_path = pathlib.Path(X11_path)
            if not X11_path.exists():
                print(f"Error: X11 socket {X11_path} does not exist")
                sys.exit(1)
        else:
            # Default X11 socket path
            X11_path = pathlib.Path("/tmp/.X11-unix")
            print(f"X11 support enabled at {X11_path}")
        
        
        cmd_parts.append("--net=host")
        cmd_parts.append(f"-e DISPLAY={os.environ['DISPLAY']}")
        cmd_parts.append(f"-v {X11_path}:/tmp/.X11-unix")
        cmd_parts.append(f"-v {os.environ['HOME']}/.Xauthority:/home/ykarmon/.Xauthority:ro")
       

    if usb:
        cmd_parts.append("-v /dev/bus/usb:/dev/bus/usb")


    need_to_exit = False
    for mount in RESOLVED_MOUNTS_LIST:
       

        source_str, dest = mount  
        source_path = pathlib.Path(source_str)

        if not source_path.exists():
            print(f"Warning: Mount source '{source_path}' does not exist. Skipping.")
            need_to_exit= True
            continue

        cmd_parts.append(f"-v {str(source_path)}:{dest}")

    if(need_to_exit):
        print("Exiting due to missing mount source.")
        sys.exit(1)

    cmd_parts.append(IMAGE_NAME)
    cmd = " ".join(cmd_parts)

    print(f"Running command: {cmd}")
    print(f"command parts:")
    for part in cmd_parts:
        print(part)

    if(ask):
        answer = input("Do you want to continue? [y/N]: ").strip().lower()
        if answer not in ("y", "yes"):
            print("Aborted.")
            return
    
    ctx.run(cmd, pty=True)

    # Print success message with details
    print("=" * 60)
    print("CONTAINER STARTED SUCCESSFULLY!")
    print("=" * 60)
    print(f"Container Name: {container_name}")
    print(f"Image: {IMAGE_NAME}")
    print(f"Config File: {file}")
    print(f"Source Directory: {RELATIVE_PATH}")
    print(f"Mounts Applied: {len(RESOLVED_MOUNTS_LIST)}")
    for i, (source, dest) in enumerate(RESOLVED_MOUNTS_LIST, 1):
        print(f"  {i}. {source} -> {dest}")
    print(f"X11 Support: {'Enabled' if x11 else 'Disabled'}")
    print(f"USB Support: {'Enabled' if usb else 'Disabled'}")
    print(f"Auto-cleanup: {'Enabled' if rm else 'Disabled'}")
    print("=" * 60)
    print(f"To exec into container: ./fabrinetes exec --container-name {container_name} --command '<cmd>'")
    print(f"To open shell: ./fabrinetes shell --container-name {container_name}")
    print("=" * 60)

    ctx.run(f"docker exec {container_name} sudo git config --global --add safe.directory '*'", pty=True, echo=True, warn=True)


@task
def exec(ctx, container_name=None, command=None, interactive=False):
    """
    Execute a command in a running container and print the result.
    If no container name provided, shows list of available containers with commands.
    
    Args:
        container_name: Name of the container to execute command in (optional)
        command: Command to execute (use quotes for complex commands)
        interactive: Use interactive shell (bash -l) for full environment
    """
    if not container_name:
        print("Available Running Containers:")
        print("=" * 80)
        
        # Get running containers
        result = ctx.run("docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'", hide=True, warn=True)
        if not result.stdout.strip():
            print("No running containers found.")
            print("Start a container first with: ./fabrinetes run --file fabrinetes.config --name <repository> --no-ask")
            return
        
        containers = result.stdout.strip().split('\n')
        print(f"Found {len(containers)} running container(s):")
        print()
        
        # Create table data
        table_data = []
        for container_line in containers:
            parts = container_line.split('\t')
            if len(parts) >= 3:
                name, image, status = parts[0], parts[1], parts[2]
                
                # Extract repository name from container name (remove timestamp)
                repo_name = name.split('-')[0] + '-' + name.split('-')[1] if '-' in name else name
                
                # Get more container details
                inspect_result = ctx.run(f"docker inspect {name} --format='{{{{.Config.Image}}}}'", hide=True, warn=True)
                full_image = inspect_result.stdout.strip() if inspect_result.stdout.strip() else image
                
                # Determine config file location
                config_file = f"containers/{repo_name}/config/fabrinetes.config"
                
                table_data.append([
                    name,
                    full_image,
                    repo_name,
                    config_file,
                    status
                ])
        
        # Print table using tabulate
        from tabulate import tabulate
        headers = ["Container Name", "Image", "Repository", "Config File", "Status"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print()
        
        # Print commands
        print("Exec Commands:")
        print("-" * 50)
        for i, container_line in enumerate(containers, 1):
            parts = container_line.split('\t')
            if len(parts) >= 3:
                name = parts[0]
                print(f"{i}. ./fabrinetes exec --container-name {name} --command '<cmd>'")
        
        print("=" * 80)
        print("Usage: ./fabrinetes exec --container-name <container-name> --command '<cmd>'")
        return
    
    if not command:
        print("Error: Command is required")
        print("Usage: invoke exec --container-name=<name> --command='<cmd>'")
        return
    
    # Check if container exists and is running
    result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
    if not result.stdout.strip():
        print(f"Error: Container '{container_name}' is not running")
        print("Available running containers:")
        ctx.run("docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'", pty=True)
        return
    
    # Build docker exec command
    if interactive:
        # Use login shell for full environment (bashrc, PATH, etc.)
        exec_cmd = f"docker exec {container_name} bash -l -c '{command}'"
        print(f"[Interactive] Executing: {command}")
    else:
        # Regular execution
        exec_cmd = f"docker exec {container_name} bash -c '{command}'"
        print(f"[Non-interactive] Executing: {command}")
    
    print("=" * 60)
    
    # Execute command and capture output
    try:
        result = ctx.run(exec_cmd, pty=True, echo=False)
        print("=" * 60)
        print(f"Command completed successfully")
    except Exception as e:
        print("=" * 60)
        print(f"Command failed: {e}")


@task
def shell(ctx, container_name=None):
    """
    Open an interactive shell in a running container.
    If no container name provided, shows list of available containers with commands.
    
    Args:
        container_name: Name of the container to connect to (optional)
    """
    if not container_name:
        print("Available Running Containers:")
        print("=" * 80)
        
        # Get running containers
        result = ctx.run("docker ps --format '{{.Names}}\t{{.Image}}\t{{.Status}}'", hide=True, warn=True)
        if not result.stdout.strip():
            print("No running containers found.")
            print("Start a container first with: ./fabrinetes run --file fabrinetes.config --name <repository> --no-ask")
            return
        
        containers = result.stdout.strip().split('\n')
        print(f"Found {len(containers)} running container(s):")
        print()
        
        # Create table data
        table_data = []
        for container_line in containers:
            parts = container_line.split('\t')
            if len(parts) >= 3:
                name, image, status = parts[0], parts[1], parts[2]
                
                # Extract repository name from container name (remove timestamp)
                repo_name = name.split('-')[0] + '-' + name.split('-')[1] if '-' in name else name
                
                # Get more container details
                inspect_result = ctx.run(f"docker inspect {name} --format='{{{{.Config.Image}}}}'", hide=True, warn=True)
                full_image = inspect_result.stdout.strip() if inspect_result.stdout.strip() else image
                
                # Determine config file location
                config_file = f"containers/{repo_name}/config/fabrinetes.config"
                
                table_data.append([
                    name,
                    full_image,
                    repo_name,
                    config_file,
                    status
                ])
        
        # Print table using tabulate
        from tabulate import tabulate
        headers = ["Container Name", "Image", "Repository", "Config File", "Status"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
        print()
        
        # Print commands
        print("Shell Commands:")
        print("-" * 50)
        for i, container_line in enumerate(containers, 1):
            parts = container_line.split('\t')
            if len(parts) >= 3:
                name = parts[0]
                print(f"{i}. ./fabrinetes shell --container-name {name}")
        
        print("=" * 80)
        print("Usage: ./fabrinetes shell --container-name <container-name>")
        return
    
    # Check if container exists and is running
    result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
    if not result.stdout.strip():
        print(f"Error: Container '{container_name}' is not running")
        print("Available running containers:")
        ctx.run("docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'", pty=True)
        return
    
    print(f"Opening interactive shell in container: {container_name}")
    print("Use 'exit' to return to host")
    print("=" * 60)
    
    # Open interactive shell
    ctx.run(f"docker exec -it {container_name} bash -l", pty=True)


@task
def clean(ctx, file, name=None):
    """
    Clean up all images and containers for a specific config.
    
    Args:
        file: Path to the config file
        name: Container name to clean (optional, cleans all if not specified)
    """
    if not os.path.isabs(file):
        base_path = os.environ.get("HDLFORGE_ORIG_PATH", os.getcwd())
        file = os.path.join(base_path, file)
    file = os.path.expandvars(file)
    file = os.path.abspath(file)
    _config_file_path = pathlib.Path(file).resolve()
    RELATIVE_PATH = _config_file_path.parent
    
    print(f"Cleaning containers and images for config: {file}")
    print("=" * 60)
    
    try:
        database = toml.load(str(_config_file_path))
    except Exception as e:
        print(f"Error loading toml file '{file}': {e}")
        return
    
    # If name specified, clean only that container
    if name:
        if "container" not in database or name not in database["container"]:
            print(f"Container '{name}' not found in config file")
            print("Available containers:")
            if "container" in database:
                for key in database["container"].keys():
                    print(f"  {key}")
            return
        
        container_config = database["container"][name]
        _image_repository = name
        _image_tag = container_config.get("TAG", "latest")
        IMAGE_NAME = f"{_image_repository}:{_image_tag}"
        
        print(f"Cleaning container: {name}")
        print(f"Image: {IMAGE_NAME}")
        
        # Stop and remove containers
        print("Stopping containers...")
        result = ctx.run(f"docker ps -q --filter ancestor={IMAGE_NAME}", hide=True, warn=True)
        if result.stdout.strip():
            container_ids = result.stdout.strip().split('\n')
            for container_id in container_ids:
                ctx.run(f"docker stop {container_id}", pty=True, warn=True)
                ctx.run(f"docker rm {container_id}", pty=True, warn=True)
                print(f"  Stopped and removed container {container_id}")
        
        # Remove images
        print("Removing images...")
        ctx.run(f"docker rmi {IMAGE_NAME}", pty=True, warn=True)
        print(f"  Removed image {IMAGE_NAME}")
        
    else:
        # Clean all containers in the config
        if "container" not in database:
            print("No containers found in config file")
            return
        
        print(f"Cleaning all containers in config file...")
        
        for container_name, container_config in database["container"].items():
            _image_repository = container_name
            _image_tag = container_config.get("TAG", "latest")
            IMAGE_NAME = f"{_image_repository}:{_image_tag}"
            
            print(f"\nCleaning container: {container_name}")
            print(f"Image: {IMAGE_NAME}")
            
            # Stop and remove containers
            print("  Stopping containers...")
            result = ctx.run(f"docker ps -q --filter ancestor={IMAGE_NAME}", hide=True, warn=True)
            if result.stdout.strip():
                container_ids = result.stdout.strip().split('\n')
                for container_id in container_ids:
                    ctx.run(f"docker stop {container_id}", pty=True, warn=True)
                    ctx.run(f"docker rm {container_id}", pty=True, warn=True)
                    print(f"    Stopped and removed container {container_id}")
            
            # Remove images
            print("  Removing images...")
            ctx.run(f"docker rmi {IMAGE_NAME}", pty=True, warn=True)
            print(f"    Removed image {IMAGE_NAME}")
    
    print("=" * 60)
    print("Cleanup completed!")

   
