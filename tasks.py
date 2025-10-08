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

# Check if tasks.py is being called directly (not from fabrinetes script)
def check_invocation_method():
    """Check if tasks.py is being called directly and exit with error if so"""
    # Check if we're being called from the fabrinetes script via environment variable
    if os.environ.get('FABRINETES_CALLED', 'false') == 'true':
        return True  # Called from fabrinetes script - OK
    
    # If we get here, we weren't called from fabrinetes script
    print("=" * 60)
    print("ERROR: tasks.py should not be called directly!")
    print("=" * 60)
    print("")
    print("This file contains internal tasks for the Fabrinetes system.")
    print("Please use the 'fabrinetes' script instead:")
    print("")
    print("  ./fabrinetes <command> [options]")
    print("")
    print("Examples:")
    print("  ./fabrinetes                    # Show help")
    print("  ./fabrinetes list               # List repositories")
    print("  ./fabrinetes build <repo>       # Build container")
    print("  ./fabrinetes run --file <config> --name <repo>  # Run container")
    print("  ./fabrinetes restore <repo>     # Restore from tar file")
    print("  ./fabrinetes commit --container-name <name>  # Commit container")
    print("")
    print("For more information, run: ./fabrinetes")
    print("=" * 60)
    sys.exit(1)

# Check invocation method before defining any tasks
check_invocation_method()
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
def build(ctx, repo=None, dry_run=False, export=False):
    """Build Docker image for the specified repository"""
    
    # Check for missing required arguments
    if not repo:
        show_command_help('build', COMMAND_HELP['build'])
        return
    
    username = os.getenv("USER") or os.getenv("USERNAME")
    uid = os.getuid()
    gid = os.getgid()
    home_dir = os.path.expanduser("~")

    repos = [repo]
    
    for repo_name in repos:
        dockerfile_path = f"containers/{repo_name}/Dockerfile"
        if not os.path.exists(dockerfile_path):
            print(f"Warning: Dockerfile not found for {repo_name} at {dockerfile_path}")
            continue
        
        # Build the docker command
        docker_cmd = (
        f"docker build "
        f"--build-arg USERNAME={username} "
        f"--build-arg UID={uid} "
        f"--build-arg GID={gid} "
        f"--build-arg HOME_DIR={home_dir} "
            f"-t {repo_name}:latest -f {dockerfile_path} containers/{repo_name}/"
        )
        
        if dry_run:
            print(f"[DRY RUN] Would build {repo_name}...")
            print(f"[DRY RUN] Command: {docker_cmd}")
            print(f"[DRY RUN] Dockerfile: {dockerfile_path}")
            print(f"[DRY RUN] Build context: containers/{repo_name}/")
            print(f"[DRY RUN] Build args:")
            print(f"  USERNAME={username}")
            print(f"  UID={uid}")
            print(f"  GID={gid}")
            print(f"  HOME_DIR={home_dir}")
            print(f"[DRY RUN] Target image: {repo_name}:latest")
            if export:
                print(f"[DRY RUN] Would export image to: images/{repo_name}/{repo_name}-latest.tar.gz")
        else:
            print(f"Building {repo_name}...")
            ctx.run(docker_cmd, pty=True)
            
            # Export image if requested
            if export:
                export_image(ctx, repo_name, "latest")

def export_image(ctx, repo_name, tag):
    """Export Docker image to tar.gz file"""
    import subprocess
    
    # Create images directory if it doesn't exist
    images_dir = f"images/{repo_name}"
    os.makedirs(images_dir, exist_ok=True)
    
    # Export image
    tar_filename = f"{repo_name}-{tag}.tar.gz"
    tar_path = f"{images_dir}/{tar_filename}"
    
    print(f"Exporting {repo_name}:{tag} to {tar_path}...")
    
    try:
        # Use subprocess to handle the pipe properly
        result = subprocess.run(
            f"docker save {repo_name}:{tag} | gzip > {tar_path}",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully exported image to {tar_path}")
    except subprocess.CalledProcessError as e:
        print(f"Error exporting image: {e}")
        print(f"stderr: {e.stderr}")

def import_image(ctx, tar_path):
    """Import Docker image from tar.gz file"""
    import subprocess
    
    if not os.path.exists(tar_path):
        print(f"Error: File {tar_path} does not exist")
        return False
    
    print(f"Importing image from {tar_path}...")
    
    try:
        result = subprocess.run(
            f"gunzip -c {tar_path} | docker load",
            shell=True, check=True, capture_output=True, text=True
        )
        print(f"Successfully imported image from {tar_path}")
        print(f"Output: {result.stdout}")
        return True
    except subprocess.CalledProcessError as e:
        print(f"Error importing image: {e}")
        print(f"stderr: {e.stderr}")
        return False

@task
def restore(ctx, repo=None, tar_file=None):
    """Restore Docker image from tar.gz file instead of building"""
    
    # Check for missing required arguments
    if not repo:
        show_command_help('restore', COMMAND_HELP['restore'])
        return
    
    # If no tar_file specified, look for the latest in images directory
    if not tar_file:
        images_dir = f"images/{repo}"
        if not os.path.exists(images_dir):
            print(f"Error: Images directory {images_dir} does not exist")
            print(f"Available options:")
            print(f"  1. Build the image first: ./fabrinetes build {repo}")
            print(f"  2. Specify a tar file: ./fabrinetes restore {repo} --tar-file <path>")
            return
        
        # Find the latest tar file
        import glob
        tar_files = glob.glob(f"{images_dir}/{repo}-*.tar.gz")
        if not tar_files:
            print(f"Error: No tar files found in {images_dir}")
            print(f"Available options:")
            print(f"  1. Build the image first: ./fabrinetes build {repo}")
            print(f"  2. Specify a tar file: ./fabrinetes restore {repo} --tar-file <path>")
            return
        
        # Sort by modification time and get the latest
        tar_files.sort(key=os.path.getmtime, reverse=True)
        tar_file = tar_files[0]
        print(f"Using latest tar file: {tar_file}")
    else:
        # Check if specified tar file exists
        if not os.path.exists(tar_file):
            print(f"Error: Specified tar file '{tar_file}' does not exist")
            
            # Show available tar files for this repository
            images_dir = f"images/{repo}"
            if os.path.exists(images_dir):
                import glob
                available_files = glob.glob(f"{images_dir}/{repo}-*.tar.gz")
                if available_files:
                    print(f"\nAvailable tar files for {repo}:")
                    for i, file in enumerate(available_files, 1):
                        file_size = os.path.getsize(file) / (1024*1024)  # Size in MB
                        mod_time = os.path.getmtime(file)
                        mod_time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mod_time))
                        print(f"  {i}. {file} ({file_size:.1f}MB, {mod_time_str})")
                    print(f"\nUsage examples:")
                    print(f"  ./fabrinetes restore {repo} --tar-file {available_files[0]}")
                    if len(available_files) > 1:
                        print(f"  ./fabrinetes restore {repo} --tar-file {available_files[1]}")
                else:
                    print(f"No tar files found in {images_dir}")
                    print(f"Available options:")
                    print(f"  1. Build the image first: ./fabrinetes build {repo}")
                    print(f"  2. Build with export: ./fabrinetes build {repo} --export")
            else:
                print(f"Images directory {images_dir} does not exist")
                print(f"Available options:")
                print(f"  1. Build the image first: ./fabrinetes build {repo}")
                print(f"  2. Build with export: ./fabrinetes build {repo} --export")
            return
    
    # Import the image
    success = import_image(ctx, tar_file)
    if success:
        print(f"Successfully restored {repo} from {tar_file}")
    else:
        print(f"Failed to restore {repo} from {tar_file}")

@task
def commit(ctx, container_name=None, tag=None, message=None):
    """Commit running container to new image"""
    
    # Check for missing required arguments
    if not container_name:
        show_command_help('commit', COMMAND_HELP['commit'])
        return
    
    # Check if container is running
    import subprocess
    try:
        result = subprocess.run(
            f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'",
            shell=True, capture_output=True, text=True, check=True
        )
        if not result.stdout.strip():
            print(f"Error: Container '{container_name}' is not running")
            print("Available running containers:")
            ctx.run("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}'", pty=True)
            return
    except subprocess.CalledProcessError:
        print(f"Error: Could not check container status")
        return
    
    # Determine the new image name and tag
    if not tag:
        # Extract repository name from container name (remove timestamp)
        import re
        repo_match = re.match(r'([^-]+(?:-[^-]+)*)-\d{8}-\d{6}', container_name)
        if repo_match:
            repo_name = repo_match.group(1)
        else:
            # Fallback: try to extract from container name
            parts = container_name.split('-')
            if len(parts) >= 3:  # fabrinetes-dev-testing-20251008-141316
                repo_name = '-'.join(parts[:-2])  # fabrinetes-dev-testing
            else:
                repo_name = container_name
        
        # Check if image already exists
        try:
            result = subprocess.run(
                f"docker images {repo_name}:latest --format '{{{{.Repository}}}}'",
                shell=True, capture_output=True, text=True, check=True
            )
            if result.stdout.strip():
                print(f"Image {repo_name}:latest already exists.")
                choice = input("Choose option:\n  1. Overwrite existing image\n  2. Create new tag\n  3. Cancel\nEnter choice (1-3): ").strip()
                
                if choice == "1":
                    tag = "latest"
                elif choice == "2":
                    tag = input("Enter new tag: ").strip()
                    if not tag:
                        print("Error: Tag cannot be empty")
                        return
                else:
                    print("Operation cancelled")
                    return
            else:
                tag = "latest"
        except subprocess.CalledProcessError:
            tag = "latest"
    else:
        # Extract repository name from container name (remove timestamp)
        import re
        repo_match = re.match(r'([^-]+(?:-[^-]+)*)-\d{8}-\d{6}', container_name)
        if repo_match:
            repo_name = repo_match.group(1)
        else:
            # Fallback: try to extract from container name
            parts = container_name.split('-')
            if len(parts) >= 3:  # fabrinetes-dev-testing-20251008-141316
                repo_name = '-'.join(parts[:-2])  # fabrinetes-dev-testing
            else:
                repo_name = container_name
    
    # Commit the container
    commit_cmd = f"docker commit"
    if message:
        commit_cmd += f" -m \"{message}\""
    commit_cmd += f" {container_name} {repo_name}:{tag}"
    
    print(f"Committing container {container_name} to {repo_name}:{tag}...")
    try:
        ctx.run(commit_cmd, pty=True)
        print(f"Successfully committed container to {repo_name}:{tag}")
        
        # Export the new image
        export_image(ctx, repo_name, tag)
        
    except Exception as e:
        print(f"Error committing container: {e}")

def show_command_help(command_name, command_data):
    """Show help for a specific command"""
    from tabulate import tabulate
    
    print(f"[!] Missing required arguments for '{command_name}' command!")
    print("")
    print(f"=== {command_name.upper()} Command Help ===")
    print("")
    
    # Command syntax
    print("Syntax:")
    print(f"  {command_data['syntax']}")
    print("")
    
    # Description
    print("Description:")
    print(f"  {command_data['description']}")
    print("")
    
    # Arguments table
    if 'arguments' in command_data:
        print("Arguments:")
        headers = ["Argument", "Description", "Required", "Allowed Values"]
        print(tabulate(command_data['arguments'], headers=headers, tablefmt="grid"))
        print("")
    
    # Examples
    if 'examples' in command_data:
        print("Examples:")
        for example in command_data['examples']:
            print(f"  {example}")
        print("")


# Command-specific help data
COMMAND_HELP = {
    'run': {
        'syntax': './fabrinetes run --file <config-file> --name <repository-name> [--rm] [--x11] [--usb] [--ask] [--verbose]',
        'description': 'Run a Docker container with the specified configuration',
        'arguments': [
            ['--file', 'Path to the configuration file', 'Yes', 'containers/<path>/config/fabrinetes.config'],
            ['--name', 'Repository name from config', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full'],
            ['--rm', 'Automatically remove container when it exits', 'No', 'optional flag'],
            ['--x11', 'Enable X11 GUI support', 'No', 'optional flag'],
            ['--usb', 'Enable USB device access', 'No', 'optional flag'],
            ['--ask', 'Ask for confirmation before running', 'No', 'optional flag'],
            ['--verbose', 'Show detailed output', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes run --file containers/fabrinetes-dev-testing/config/fabrinetes.config --name fabrinetes-dev-testing',
            './fabrinetes run --file containers/fabrinetes-dev/config/fabrinetes.config --name fabrinetes-dev --rm --x11',
            './fabrinetes run --file containers/fabrinetes-fpga-full/config/fabrinetes.config --name fabrinetes-fpga-full --no-ask'
        ]
    },
    'shell': {
        'syntax': './fabrinetes shell --container-name <container-name>',
        'description': 'Open an interactive shell in a running container',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above']
        ],
        'examples': [
            './fabrinetes shell --container-name fabrinetes-dev-testing-20251008-141316',
            './fabrinetes shell --container-name fabrinetes-fpga-dev-1'
        ]
    },
    'exec': {
        'syntax': './fabrinetes exec --container-name <container-name> --command \'<command>\' [--interactive]',
        'description': 'Execute a command in a running container',
        'arguments': [
            ['--container-name', 'Name of the running container', 'Yes', 'From Docker Containers table above'],
            ['--command', 'Shell command to execute', 'Yes', 'Any valid shell command'],
            ['--interactive', 'Run command in interactive mode', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes exec --container-name fabrinetes-dev-testing-20251008-141316 --command \'ls -la\'',
            './fabrinetes exec --container-name fabrinetes-dev-testing-20251008-141316 --command \'python --version\' --interactive'
        ]
    },
    'build': {
        'syntax': './fabrinetes build <repository-name> [--dry-run] [--export]',
        'description': 'Build Docker image for the specified repository',
        'arguments': [
            ['repository-name', 'Name of the repository to build', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full'],
            ['--dry-run', 'Show what would be built without actually building', 'No', 'optional flag'],
            ['--export', 'Export built image to tar.gz file', 'No', 'optional flag']
        ],
        'examples': [
            './fabrinetes build fabrinetes-dev-testing',
            './fabrinetes build fabrinetes-dev --dry-run',
            './fabrinetes build fabrinetes-dev-testing --export'
        ]
    },
    'restore': {
        'syntax': './fabrinetes restore <repository-name> [--tar-file <path>]',
        'description': 'Restore Docker image from tar.gz file instead of building',
        'arguments': [
            ['repository-name', 'Name of the repository to restore', 'Yes', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full'],
            ['--tar-file', 'Path to specific tar.gz file (optional)', 'No', 'path to .tar.gz file']
        ],
        'examples': [
            './fabrinetes restore fabrinetes-dev-testing',
            './fabrinetes restore fabrinetes-dev --tar-file images/fabrinetes-dev/fabrinetes-dev-latest.tar.gz'
        ]
    },
    'commit': {
        'syntax': './fabrinetes commit --container-name <name> [--tag <tag>] [--message <message>]',
        'description': 'Commit running container to new image and export it',
        'arguments': [
            ['--container-name', 'Name of the running container to commit', 'Yes', 'container name from docker ps'],
            ['--tag', 'Tag for the new image (optional)', 'No', 'image tag'],
            ['--message', 'Commit message (optional)', 'No', 'commit message']
        ],
        'examples': [
            './fabrinetes commit --container-name fabrinetes-dev-testing-20251008-151924',
            './fabrinetes commit --container-name fabrinetes-dev-testing-20251008-151924 --tag v1.0',
            './fabrinetes commit --container-name fabrinetes-dev-testing-20251008-151924 --message "Added new features"'
        ]
    },
    'clean': {
        'syntax': './fabrinetes clean --file <config-file> [--name <repository-name>]',
        'description': 'Clean up containers and images for the specified configuration',
        'arguments': [
            ['--file', 'Path to the configuration file', 'Yes', 'containers/<path>/config/fabrinetes.config'],
            ['--name', 'Repository name to clean (optional)', 'No', 'fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full']
        ],
        'examples': [
            './fabrinetes clean --file containers/fabrinetes-dev-testing/config/fabrinetes.config',
            './fabrinetes clean --file containers/fabrinetes-dev-testing/config/fabrinetes.config --name fabrinetes-dev-testing'
        ]
    }
}


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
    print("=== Executing 'list' command ===")
    print("")
    
    # Execute the list command
    list(ctx)
    
    print("")
    print("Available Repository Names:")
    print("+------------------------+------------------------------------------------------------+")
    print("| Repository Name        | Config File                                                |")
    print("+========================+============================================================+")
    for repo_name, config_file, status in table_data:
        print(f"| {repo_name:<22} | {config_file:<58} |")
    print("+------------------------+------------------------------------------------------------+")
    print("")
    print("Options:")
    options_data = [
        ["./fabrinetes build", "[repository-name] [--dry-run] [--export]", "Build Docker image for repository", "fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full"],
        ["./fabrinetes restore", "[repository-name] [--tar-file <path>]", "Restore Docker image from tar.gz file", "fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full"],
        ["./fabrinetes list", "", "List Docker images and containers", "None"],
        ["./fabrinetes run", "--file [config-file] --name [repository-name] [--rm] [--x11] [--usb] [--ask] [--verbose]", "Run container with specified config", "config-file: path to .config, repository-name: from table above, flags: optional"],
        ["./fabrinetes exec", "--container-name [container-name] --command '[command]' [--interactive]", "Execute command in running container", "container-name: from Docker Containers table, command: any shell command"],
        ["./fabrinetes shell", "--container-name [container-name]", "Open interactive shell in container", "container-name: from Docker Containers table"],
        ["./fabrinetes commit", "--container-name [name] [--tag <tag>] [--message <message>]", "Commit running container to new image", "container-name: from Docker Containers table, tag: optional"],
        ["./fabrinetes clean", "--file [config-file] [--name [repository-name]]", "Clean up containers and images", "config-file: path to .config, repository-name: optional"]
    ]
    headers = ["Command", "Arguments", "Description", "Allowed Values"]
    print(tabulate(options_data, headers=headers, tablefmt="grid"))
    
    print("")
    print("Arguments:")
    arguments_data = [
        ["repository-name", "Name of the repository to build/run/restore", "fabrinetes-dev-testing, fabrinetes-dev, fabrinetes-fpga-full"],
        ["config-file", "Path to the configuration file", "containers/<path>/config/fabrinetes.config"],
        ["--rm", "Automatically remove container when it exits", "optional flag"],
        ["--x11", "Enable X11 GUI support", "optional flag"],
        ["--usb", "Enable USB device access", "optional flag"],
        ["--ask", "Ask for confirmation before running", "optional flag"],
        ["--verbose", "Show detailed output", "optional flag"],
        ["--dry-run", "Show what would be built without actually building", "optional flag"],
        ["--export", "Export built image to tar.gz file", "optional flag"],
        ["--tar-file", "Path to specific tar.gz file for restore", "path to .tar.gz file"],
        ["--container-name", "Name of the running container", "From Docker Containers table above"],
        ["--tag", "Tag for the new image when committing", "image tag"],
        ["--message", "Commit message when committing", "commit message"],
        ["command", "Shell command to execute", "Any valid shell command"],
        ["--interactive", "Run command in interactive mode", "optional flag"]
    ]
    headers = ["Argument", "Description", "Allowed Values"]
    print(tabulate(arguments_data, headers=headers, tablefmt="grid"))


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
        
        # Group containers by image
        containers_by_image = {}
        for line in lines:
            parts = line.split('\t')
            if len(parts) >= 7:
                container_id, image, command, created, status, ports, names = parts
                if image not in containers_by_image:
                    containers_by_image[image] = []
                containers_by_image[image].append([container_id, command, created, status, ports, names])
        
        # Create table data with merged cells for multiple containers
        table_data = []
        for image, containers in containers_by_image.items():
            if len(containers) == 1:
                # Single container - normal row
                container = containers[0]
                table_data.append([image] + container)
            else:
                # Multiple containers - merge names and show combined info
                container_ids = [c[0] for c in containers]
                commands = [c[1] for c in containers]
                created_times = [c[2] for c in containers]
                statuses = [c[3] for c in containers]
                ports_list = [c[4] for c in containers]
                names = [c[5] for c in containers]
                
                # Combine multiple values with newlines
                combined_container_id = "\n".join(container_ids)
                combined_command = "\n".join(commands)
                combined_created = "\n".join(created_times)
                combined_status = "\n".join(statuses)
                combined_ports = "\n".join(ports_list)
                combined_names = "\n".join(names)
                
                table_data.append([image, combined_container_id, combined_command, combined_created, combined_status, combined_ports, combined_names])
        
        headers = ["Image", "Container ID", "Command", "Created", "Status", "Ports", "Names"]
        print(tabulate(table_data, headers=headers, tablefmt="grid"))
    else:
        print("No containers found")
    
    print()


@task
def run(ctx, file=None,rm=False,verbose=False,ver=None,name=None, x11=True,usb=False,ask=True):
    """Run a Docker container with the specified configuration"""
   
    # Check for missing required arguments
    if not file or not name:
        show_command_help('run', COMMAND_HELP['run'])
        return
   
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
    init_env = container_config.get("init_env", None)
    _this_file_path = pathlib.Path(__file__).resolve().parent

    MOUNTS_LIST.append(f"{_this_file_path}/source/bashrc-root:{os.getenv('HOME')}/.bashrc")
    MOUNTS_LIST.append(f"{_this_file_path}/source/project_setup/:/opt/project_setup")
    
    # Add init_env mount if specified
    if init_env:
        MOUNTS_LIST.append(init_env)

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
        cmd_parts.append(f"-v {os.environ['HOME']}/.Xauthority:/home/{os.getenv('USER', 'user')}/.Xauthority:ro")
       

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
    If required arguments are missing, shows command-specific help.
    
    Args:
        container_name: Name of the container to execute command in (required)
        command: Command to execute (required)
        interactive: Use interactive shell (bash -l) for full environment
    """
    if not container_name or not command:
        show_command_help('exec', COMMAND_HELP['exec'])
        return
    
    # Check if container exists and is running
    result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
    if not result.stdout.strip():
        print(f"Error: Container '{container_name}' is not running")
        print("Available running containers:")
        ctx.run("docker ps --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}'", pty=True)
        return
    
    print(f"Executing command in container: {container_name}")
    print(f"Command: {command}")
    print("=" * 60)
    
    try:
        if interactive:
            # Use interactive shell
            ctx.run(f"docker exec -it {container_name} bash -l -c '{command}'", pty=True)
        else:
            # Execute command directly
            result = ctx.run(f"docker exec {container_name} bash -c '{command}'", pty=True, warn=True)
            if result.exited != 0:
                print(f"Command failed with exit code: {result.exited}")
    except Exception as e:
        print("=" * 60)
        print(f"Command failed: {e}")

@task
def shell(ctx, container_name=None):
    """
    Open an interactive shell in a running container.
    If no container name provided, shows command-specific help.
    
    Args:
        container_name: Name of the container to connect to (required)
    """
    if not container_name:
        show_command_help('shell', COMMAND_HELP['shell'])
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
def clean(ctx, file=None, name=None):
    """
    Clean up all images and containers for a specific config.
    
    Args:
        file: Path to the config file (required)
        name: Container name to clean (optional, cleans all if not specified)
    """
    # Check for missing required arguments
    if not file:
        show_command_help('clean', COMMAND_HELP['clean'])
        return
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

   
