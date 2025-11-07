#!/usr/bin/env python3

import os
import sys
from pathlib import Path
from command.helper_functions.command_builder import CommandBuilder, CmdPartEnv, CmdPartArg, CmdPartFile, CmdPartName
from command.help.help import show_build_help

def build(args, container_info):
    """Generate Docker build commands for image using ubuntu:24.04 base"""
    # Extract arguments
    help_flag = args.show_help
    
    # Check for help flag first
    if help_flag:
        show_build_help()
        return
    
    # Detect Fabrinetes repo location (where fabrinetes.py is located)
    fabrinetes_script = Path(__file__).resolve()
    # Go up from command/build/build.py -> command/build -> command -> repo root
    fabrinetes_repo_root = fabrinetes_script.parent.parent.parent
    fabrinetes_repo_path = str(fabrinetes_repo_root.resolve())
    
    # Expand $HOME in the expected mount path
    home_dir = os.path.expanduser("~")
    # Container path should always be $HOME/repo/Fabrinetes
    expected_container_path = "$HOME/repo/Fabrinetes"
    
    # Define mandatory mounts (exact values as specified by user)
    # Note: Fabrinetes mount host path can use $HOME or be absolute - we'll resolve and compare
    mandatory_mounts = [
        "$HOME/.ssh:$HOME/.ssh",
        None,  # Fabrinetes mount - will be checked separately
        "entrypoint.sh:/usr/local/bin/entrypoint.sh",
        "init_env.sh:/etc/profile.d/init_env.sh",
        "bashrc-root:$HOME/.bashrc",
        "bashrc-func:/etc/bashrc-func"
    ]
    
    # Validate mandatory mounts are present in config
    config_mounts = container_info.mounts
    missing_mounts = []
    fabrinetes_mount_found = False
    
    for mandatory_mount in mandatory_mounts:
        found = False
        
        # Skip None (Fabrinetes mount - handled separately)
        if mandatory_mount is None:
            continue
        
        # For other mounts, do normal comparison
        # Expand $HOME and ~ in mandatory mount for comparison
        mandatory_expanded = os.path.expandvars(os.path.expanduser(mandatory_mount))
        
        for config_mount in config_mounts:
            # Expand $HOME and ~ in config mount for comparison
            config_expanded = os.path.expandvars(os.path.expanduser(config_mount))
            
            # Compare both host and container paths
            if ':' in mandatory_expanded and ':' in config_expanded:
                mandatory_host, mandatory_container = mandatory_expanded.split(':', 1)
                config_host, config_container = config_expanded.split(':', 1)
                
                # Resolve absolute paths for host comparison
                try:
                    mandatory_host_resolved = str(Path(mandatory_host).resolve())
                    config_host_resolved = str(Path(config_host).resolve())
                    
                    # Expand $HOME and ~ in container paths for comparison
                    mandatory_container_expanded = os.path.expandvars(os.path.expanduser(mandatory_container))
                    config_container_expanded = os.path.expandvars(os.path.expanduser(config_container))
                    
                    # Check if both host and container paths match
                    if mandatory_host_resolved == config_host_resolved and mandatory_container_expanded == config_container_expanded:
                        found = True
                        break
                except Exception as e:
                    # If path resolution fails, do string comparison after expansion
                    if mandatory_expanded == config_expanded:
                        found = True
                        break
            else:
                # Direct string comparison if no colon (shouldn't happen for mounts)
                if mandatory_expanded == config_expanded:
                    found = True
                    break
        
        if not found:
            missing_mounts.append(mandatory_mount)
    
    # Special handling for Fabrinetes mount - allow $HOME in host path
    for config_mount in config_mounts:
        if ':' in config_mount:
            config_host, config_container = config_mount.split(':', 1)
            # Check if container path matches expected Fabrinetes container path
            config_container_expanded = os.path.expandvars(os.path.expanduser(config_container))
            expected_container_expanded = os.path.expandvars(os.path.expanduser(expected_container_path))
            
            if config_container_expanded == expected_container_expanded:
                # Resolve host path to absolute (allowing $HOME, etc.)
                try:
                    config_host_expanded = os.path.expandvars(os.path.expanduser(config_host))
                    config_host_resolved = str(Path(config_host_expanded).resolve())
                    
                    # Compare resolved absolute paths
                    if config_host_resolved == fabrinetes_repo_path:
                        fabrinetes_mount_found = True
                        break
                except Exception as e:
                    pass
    
    if not fabrinetes_mount_found:
        missing_mounts.append(f"<Fabrinetes repo>:$HOME/repo/Fabrinetes (detected: {fabrinetes_repo_path})")
    
    if missing_mounts:
        print("Error: Missing or incorrect mandatory mounts in config.toml:")
        for mount in missing_mounts:
            print(f"  - {mount}")
        print(f"\nDetected Fabrinetes repo location: {fabrinetes_repo_path}")
        print(f"Expected Fabrinetes mount container path: {expected_container_path}")
        print(f"  (Host path can use $HOME or be absolute, e.g., '$HOME/repo/Fabrinetes' or '{fabrinetes_repo_path}')")
        print(f"\nCurrent mounts in config:")
        for mount in config_mounts:
            print(f"  - {mount}")
        sys.exit(1)
    
    # Verify required files exist
    config_dir = Path(container_info.config_file_resolved).parent
    required_files = {
        "entrypoint.sh": config_dir / "entrypoint.sh",
        "init_env.sh": config_dir / "init_env.sh",
        "bashrc-root": config_dir / "bashrc-root",
        "bashrc-func": config_dir / "bashrc-func"
    }
    
    missing_files = []
    for file_name, file_path in required_files.items():
        if not file_path.exists():
            missing_files.append(f"{file_name} (expected at: {file_path})")
    
    if missing_files:
        print("Error: Required files not found:")
        for file_info in missing_files:
            print(f"  - {file_info}")
        sys.exit(1)
    
    # Get paths
    working_dir = container_info.working_directory
    packages_path = container_info.image_package_list_resolved
    python_packages_path = container_info.resolve("python-packages.txt")
    
    # Validate required files exist
    if not packages_path:
        print(f"Error: packages.txt not found at {container_info.image_package_list}")
        return
    
    # Note: entrypoint.sh will be mounted at runtime, not copied during build
    # Temporary container name for build process
    temp_container_name = f"{container_info.container_name}-build-temp"
    
    # Image name:tag
    image_name_tag = container_info.image_docker
    
    # Step 0: Clean up any existing temporary container
    print("# Step 0: Clean up any existing temporary container")
    print(f"docker rm -f {temp_container_name} 2>/dev/null || true")
    print("")
    
    # Step 1: Pull ubuntu:24.04
    print("# Step 1: Pull ubuntu:24.04 base image")
    print(f"docker pull ubuntu:24.04")
    print("")
    
    # Step 2: Run temporary container
    print("# Step 2: Run temporary container from ubuntu:24.04")
    print(f"docker run -d --name {temp_container_name} ubuntu:24.04 tail -f /dev/null")
    print("")
    
    # Step 3: Set up container (as root)
    print("# Step 3: Set up container (as root)")
    print("")
    
    # Copy packages.txt
    print(f"# Copy packages.txt to container")
    print(f"docker cp {packages_path} {temp_container_name}:/tmp/packages.txt")
    print("")
    
    # Install packages
    print(f"# Install packages from packages.txt")
    print(f"docker exec -e DEBIAN_FRONTEND=noninteractive {temp_container_name} bash -c 'apt-get update && xargs -a /tmp/packages.txt apt-get install -y && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/packages.txt'")
    print("")
    
    # Install Python packages if python-packages.txt exists
    if python_packages_path:
        print(f"# Copy python-packages.txt to container")
        print(f"docker cp {python_packages_path} {temp_container_name}:/tmp/python-packages.txt")
        print(f"# Install Python packages")
        print(f"docker exec {temp_container_name} bash -c 'pip install --no-cache-dir --break-system-packages -r /tmp/python-packages.txt && rm /tmp/python-packages.txt'")
        print("")
    
    # Set up locales
    print(f"# Set up locales")
    print(f"docker exec -e DEBIAN_FRONTEND=noninteractive {temp_container_name} bash -c 'locale-gen en_US.UTF-8 && update-locale LANG=en_US.UTF-8'")
    print("")
    
    # Create dummy entrypoint (will be replaced by mounted entrypoint at runtime)
    print(f"# Create dummy entrypoint (will be replaced by mounted entrypoint at runtime)")
    print(f"docker exec {temp_container_name} bash -c 'echo \"#!/bin/bash\" > /usr/local/bin/entrypoint.sh && echo \"exec \\\"\\$@\\\"\" >> /usr/local/bin/entrypoint.sh && chmod +x /usr/local/bin/entrypoint.sh'")
    print("")
    
    # Step 4: Commit the image with entrypoint and environment variables
    print("# Step 4: Commit the container as image with entrypoint and environment")
    print(f"docker commit --change 'ENV DEBIAN_FRONTEND=noninteractive' \\")
    print(f"  --change 'ENV LANG=en_US.UTF-8' \\")
    print(f"  --change 'ENV LANGUAGE=en_US:en' \\")
    print(f"  --change 'ENV LC_ALL=en_US.UTF-8' \\")
    print(f"  --change 'ENTRYPOINT [\"/usr/local/bin/entrypoint.sh\"]' \\")
    print(f"  {temp_container_name} {image_name_tag}")
    print("")
    
    # Step 5: Clean up temporary container
    print("# Step 5: Clean up temporary container")
    print(f"docker rm -f {temp_container_name}")
    print("")
    
    print(f"# Build complete! Image: {image_name_tag}")
