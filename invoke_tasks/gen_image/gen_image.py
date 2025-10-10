#!/usr/bin/env python3

import os
import time
from invoke import task
from helper_functions.name_generator import get_container_info
from helper_functions.package_management import install_apt_packages, install_python_packages
from helper_functions.image_management import save_image_to_tarball, restore_image_from_tarball, check_image_exists, convert_to_docker_format

def build_base_image_from_dockerfile(ctx, config_file, dry_run):
    """Build base image from Dockerfile in the same directory as config file"""
    config_dir = os.path.dirname(config_file)
    dockerfile_path = os.path.join(config_dir, "Dockerfile")
    
    # Get base image name using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    
    # Step 1: Check if base image already exists in repo
    if check_image_exists(ctx, base_image_name):
        print(f"✅ Base image '{base_image_name}' already exists locally - doing nothing")
        return True
    
    # Step 2: Try to restore base image from tarball
    print(f"Base image '{base_image_name}' not found in repo, attempting to restore from tarball...")
    if restore_image_from_tarball(ctx, base_image_name):
        # Verify image is now in repo after restore
        if check_image_exists(ctx, base_image_name):
            print(f"✅ Base image '{base_image_name}' successfully restored and verified in repo")
            return True
        else:
            print(f"❌ Base image '{base_image_name}' restore failed - image not found in repo")
            return False
    
    # Step 3: Build from Dockerfile if no tarball available
    print(f"Base image '{base_image_name}' not available from tarball, building from Dockerfile...")
    
    # Check if Dockerfile exists
    if not os.path.exists(dockerfile_path):
        print(f"❌ Error: Dockerfile not found at {dockerfile_path}")
        return False
    
    if dry_run:
        print(f"[DRY RUN] Would build base image: {base_image_name}")
        print(f"[DRY RUN] Dockerfile: {dockerfile_path}")
        return True
    
    print(f"Building base image: {base_image_name}")
    print(f"Dockerfile: {dockerfile_path}")
    
    username = os.getenv("USER") or os.getenv("USERNAME")
    uid = os.getuid()
    gid = os.getgid()
    home_dir = os.path.expanduser("~")

    docker_cmd = (
        f"docker build "
        f"--build-arg USERNAME={username} "
        f"--build-arg UID={uid} "
        f"--build-arg GID={gid} "
        f"--build-arg HOME_DIR={home_dir} "
        f"-t {base_image_name} -f {dockerfile_path} {config_dir}/"
    )
    
    result = ctx.run(docker_cmd, hide=True)
    if result.ok:
        # Verify image is in repo after build
        if check_image_exists(ctx, base_image_name):
            print(f"✅ Successfully built base image: {base_image_name} and verified in repo")
            
            # Export to tarball
            print(f"Exporting base image to tarball...")
            if save_image_to_tarball(ctx, base_image_name, config_file, base_image_name):
                print(f"✅ Base image exported to tarball successfully")
            else:
                print(f"❌ Failed to export base image to tarball")
                return False
            return True
        else:
            print(f"❌ Failed to build base image: {base_image_name} not found in repo after build")
            return False
    else:
        print(f"❌ Failed to build base image: {result.stderr}")
        return False

def ensure_base_image_available(ctx, config_file, dry_run):
    """Ensure base image is available - restore or build if needed"""
    # Get base image name using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    
    # Step 1: Check if base image exists in repo
    if check_image_exists(ctx, base_image_name):
        print(f"✅ Base image '{base_image_name}' found locally")
        return True
    
    # Step 2: Try to restore base image from tarball
    print(f"Base image '{base_image_name}' not found in repo, attempting to restore from tarball...")
    if restore_image_from_tarball(ctx, base_image_name):
        # Verify image is now in repo after restore
        if check_image_exists(ctx, base_image_name):
            print(f"✅ Base image '{base_image_name}' successfully restored and verified in repo")
            return True
        else:
            print(f"❌ Base image '{base_image_name}' restore failed - image not found in repo")
            return False
    
    # Step 3: Try to build base image from Dockerfile in the same directory
    print(f"Base image '{base_image_name}' not available from tarball, attempting to build from Dockerfile...")
    config_dir = os.path.dirname(config_file)
    base_dockerfile = os.path.join(config_dir, "Dockerfile")
    
    if os.path.exists(base_dockerfile):
        return build_base_image_from_dockerfile(ctx, config_file, dry_run)
    else:
        print(f"❌ Error: Base image '{base_image_name}' not available and no Dockerfile found at {base_dockerfile}")
        return False

@task(help={
    'config_file': 'Path to config.toml file',
    'dry_run': 'Show what would be generated without actually generating',
    'base_image': 'Build base image from Dockerfile instead of creating new image',
    'help': 'Show help information'
})
def gen_image(ctx, config_file=None, dry_run=False, base_image=False, help=False):
    """Generate Docker image from config file"""
    
    # Check for help flag or missing required arguments
    if help or not config_file:
        from invoke_tasks.help.help import show_gen_image_help
        show_gen_image_help()
        return
    
    # Check if config file exists
    if not os.path.exists(config_file):
        print(f"Error: Config file not found at {config_file}")
        return
    
    # Get image info from config
    container_info = get_container_info(config_file)
    target_image_name = container_info.image_full
    
    if base_image:
        # Build base image from Dockerfile
        return build_base_image_from_dockerfile(ctx, config_file, dry_run)
    
    # Check if target image already exists
    if check_image_exists(ctx, target_image_name):
        print(f"Image '{target_image_name}' already exists locally")
        return True
    
    # Try to restore target image from tarball
    print(f"Image '{target_image_name}' not found locally, attempting to restore...")
    if restore_image_from_tarball(ctx, container_info.image_docker):
        return True
    
    # Create new image from base image
    print(f"Image '{target_image_name}' not available, creating from base image...")
    
    # Ensure base image is available
    if not ensure_base_image_available(ctx, config_file, dry_run):
        return False
    
    # Get base image using the dataclass
    base_image_name = container_info.base_image_docker
    
    # Check for package list
    config_dir = os.path.dirname(config_file)
    package_list_path = os.path.join(config_dir, "packages.txt")
    
    if not os.path.exists(package_list_path):
        print(f"Warning: Package list not found at {package_list_path}")
        print("Cannot install packages for skeleton-based build")
        return False
    
    if dry_run:
        print(f"[DRY RUN] Would build {target_image_name} from base image...")
        print(f"[DRY RUN] Base image: {base_image_name}")
        print(f"[DRY RUN] Package source: {package_list_path}")
        print(f"[DRY RUN] Would export image to: {container_info.tarball_path}")
        return True
    
    print(f"Building {target_image_name} from base image...")
    
    # Read package list
    with open(package_list_path, 'r') as f:
        package_lines = f.readlines()
    
    python_packages = []
    apt_packages = []
    
    for line in package_lines:
        package = line.strip()
        if package and not package.startswith('#'):
            python_packages.append(package)
    
    print(f"Package list:")
    print(f"  Python packages: {python_packages}")
    print(f"  Apt packages: {apt_packages}")
    
    if not apt_packages and not python_packages:
        print(f"No packages found in {package_list_path}")
        return False
    
    # Create temporary container
    container_name = f"{container_info.image_name}-build-{int(time.time())}"
    print(f"Starting container from base image: {container_name}")
    
    start_cmd = f"docker run -dit --name {container_name} {base_image_name} bash"
    ctx.run(start_cmd, hide=True)
    
    try:
        # Install packages
        if apt_packages:
            print(f"Installing {len(apt_packages)} apt packages...")
            install_apt_packages(ctx, container_name, apt_packages)
        
        if python_packages:
            print(f"Installing {len(python_packages)} python packages...")
            install_python_packages(ctx, container_name, python_packages)
        
        # Commit container as new image
        print(f"Committing container as {target_image_name}...")
        docker_image_name = convert_to_docker_format(target_image_name)
        commit_cmd = f"docker commit {container_name} {docker_image_name}"
        ctx.run(commit_cmd, hide=True)
        
        print(f"Successfully built {docker_image_name} from base image")
        
        # Save image tarball
        if save_image_to_tarball(ctx, target_image_name, config_file):
            print(f"Image saved for future restoration")
        
    finally:
        # Clean up container
        print(f"Cleaning up container: {container_name}")
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)