#!/usr/bin/env python3

import os
import time
from invoke import task
from helper_functions.name_generator import get_container_info
from helper_functions.package_management import install_apt_packages, install_python_packages
from helper_functions.image_management import save_image_to_tarball, restore_image_from_tarball, check_image_exists, convert_to_docker_format

def handle_base_image_generation(ctx, dry_run, tarball, docker, clean, ask, container_info):
    """Handle base image generation with new flags"""
    # Use the passed container_info (no need to generate it again)
    base_image_name = container_info.base_image_docker
    base_tarball_path = f"{container_info.tarball_directory}/{container_info.base_image_tarball}"
    
    # If no specific flags provided, default to both docker and tarball
    if not tarball and not docker and not clean:
        tarball = True
        docker = True
    
    # Handle clean flag
    if clean:
        if not handle_cleanup(ctx, base_image_name, base_tarball_path, docker, tarball, ask, dry_run):
            return False
    
    success = True
    
    # Handle docker flag
    if docker:
        if not handle_docker_generation(ctx, dry_run, clean, container_info):
            success = False
    
    # Handle tarball flag - always after docker generation
    if tarball:
        if not handle_tarball_generation(ctx, dry_run, clean, container_info):
            success = False
    
    return success

def handle_cleanup(ctx, base_image_name, base_tarball_path, docker, tarball, ask, dry_run):
    """Handle cleanup of existing files"""
    removed_items = []
    
    # Check what needs to be removed
    if docker and check_image_exists(ctx, base_image_name):
        removed_items.append(f"Docker image: {base_image_name}")
    
    if tarball and os.path.exists(base_tarball_path):
        removed_items.append(f"Tarball: {base_tarball_path}")
    
    if not removed_items:
        print("No existing files to clean")
        return True
    
    print("The following files will be removed:")
    for item in removed_items:
        print(f"  - {item}")
    
    if ask and not dry_run:
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            print("Cleanup cancelled")
            return False
    
    if dry_run:
        print("[DRY RUN] Would remove the above files")
        return True
    
    # Remove files
    if docker and check_image_exists(ctx, base_image_name):
        print(f"Removing Docker image: {base_image_name}")
        ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
    
    if tarball and os.path.exists(base_tarball_path):
        print(f"Removing tarball: {base_tarball_path}")
        os.remove(base_tarball_path)
    
    print("✅ Cleanup completed")
    return True

def handle_docker_generation(ctx, dry_run, clean, container_info):
    """Handle Docker image generation"""
    base_image_name = container_info.base_image_docker
    
    # If no clean flag and image exists, skip reproduction
    if not clean and check_image_exists(ctx, base_image_name):
        print(f"✅ Docker image '{base_image_name}' already exists - skipping reproduction")
        return True
    
    # If both tarball and docker flags are set, remove existing image and rebuild
    if clean and check_image_exists(ctx, base_image_name):
        print(f"Removing existing Docker image '{base_image_name}' for rebuild...")
        if not dry_run:
            ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        else:
            print(f"[DRY RUN] Would remove Docker image: {base_image_name}")
    
    # Try to restore from tarball first
    print(f"Docker image '{base_image_name}' not found, attempting to restore from tarball...")
    if restore_image_from_tarball(ctx, base_image_name):
        if check_image_exists(ctx, base_image_name):
            print(f"✅ Docker image '{base_image_name}' successfully restored")
            return True
        else:
            print(f"❌ Docker image '{base_image_name}' restore failed")
            return False
    
    # Build from Dockerfile
    print(f"Docker image '{base_image_name}' not available from tarball, building from Dockerfile...")
    return build_base_image_from_dockerfile(ctx, dry_run, container_info)

def handle_tarball_generation(ctx, dry_run, clean, container_info):
    """Handle tarball generation"""
    base_image_name = container_info.base_image_docker
    base_tarball_path = f"{container_info.tarball_directory}/{container_info.base_image_tarball}"
    
    # Check if tarball already exists and no clean flag - skip reproduction
    if not clean and os.path.exists(base_tarball_path):
        print(f"✅ Tarball '{base_tarball_path}' already exists - skipping reproduction")
        return True
    
    # Check if Docker image exists
    if not check_image_exists(ctx, base_image_name):
        print(f"❌ Cannot create tarball: Docker image '{base_image_name}' not found")
        return False
    
    # Create tarball
    print(f"Creating tarball from Docker image '{base_image_name}'...")
    if dry_run:
        print(f"[DRY RUN] Would create tarball: {base_tarball_path}")
        return True
    else:
        if save_image_to_tarball(ctx, base_image_name, container_info.config_file, is_base_image=True):
            print(f"✅ Tarball created successfully: {base_tarball_path}")
            return True
        else:
            print(f"❌ Failed to create tarball")
            return False

def build_base_image_from_dockerfile(ctx, dry_run, container_info):
    """Build base image from Dockerfile in the same directory as config file"""
    config_dir = os.path.dirname(container_info.config_file)
    dockerfile_path = os.path.join(config_dir, "Dockerfile")
    
    # Get base image name using the passed container_info
    base_image_name = container_info.base_image_docker
    
    # Step 1: Check if base image already exists in repo
    if check_image_exists(ctx, base_image_name):
        print(f"✅ Base image '{base_image_name}' already exists locally")
        
        # Always export to tarball, even if image exists
        print(f"Exporting existing base image to tarball...")
        if dry_run:
            print(f"[DRY RUN] Would export base image to: {container_info.tarball_directory}/{container_info.base_image_tarball}")
            return True
        else:
            if save_image_to_tarball(ctx, base_image_name, container_info.config_file, is_base_image=True):
                print(f"✅ Base image exported to tarball successfully")
                return True
            else:
                print(f"❌ Failed to export base image to tarball")
                return False
    
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
            if save_image_to_tarball(ctx, base_image_name, container_info.config_file, is_base_image=True):
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

def ensure_base_image_available(ctx, dry_run, container_info):
    """Ensure base image is available - restore or build if needed"""
    # Use the passed container_info
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
    config_dir = os.path.dirname(container_info.config_file)
    base_dockerfile = os.path.join(config_dir, "Dockerfile")
    
    if os.path.exists(base_dockerfile):
        return build_base_image_from_dockerfile(ctx, dry_run, container_info)
    else:
        print(f"❌ Error: Base image '{base_image_name}' not available and no Dockerfile found at {base_dockerfile}")
        return False

def handle_main_image_generation(ctx, file, dry_run, tarball, docker, clean, ask, container_info):
    """Handle main image generation with new flags"""
    target_image_name = container_info.image_full
    target_image_docker = container_info.image_docker
    target_tarball_path = container_info.tarball_path
    
    # If no specific flags provided, default behavior (restore/build/save)
    if not tarball and not docker and not clean:
        # Default behavior: try to restore, then build if needed, always save tarball
        return handle_default_main_image_generation(ctx, file, dry_run, container_info)
    
    # Handle clean flag
    if clean:
        if not handle_main_image_cleanup(ctx, target_image_docker, target_tarball_path, docker, tarball, ask, dry_run):
            return False
    
    success = True
    
    # Handle docker flag
    if docker:
        if not handle_main_image_docker_generation(ctx, file, dry_run, clean, container_info):
            success = False
    
    # Handle tarball flag - always after docker generation
    if tarball:
        if not handle_main_image_tarball_generation(ctx, dry_run, clean, container_info):
            success = False
    
    return success

def handle_default_main_image_generation(ctx, file, dry_run, container_info):
    """Handle default main image generation (restore/build/save)"""
    target_image_name = container_info.image_full
    
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
    if not ensure_base_image_available(ctx, dry_run, container_info):
        return False
    
    # Get base image using the dataclass
    base_image_name = container_info.base_image_docker
    
    # Check for package list
    config_dir = os.path.dirname(file)
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
        if save_image_to_tarball(ctx, target_image_name, file):
            print(f"Image saved for future restoration")
        
    finally:
        # Clean up container
        print(f"Cleaning up container: {container_name}")
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
    
    return True

def handle_main_image_cleanup(ctx, target_image_docker, target_tarball_path, docker, tarball, ask, dry_run):
    """Handle cleanup of main image files"""
    removed_items = []
    
    # Check what needs to be removed
    if docker and check_image_exists(ctx, target_image_docker):
        removed_items.append(f"Docker image: {target_image_docker}")
    
    if tarball and os.path.exists(target_tarball_path):
        removed_items.append(f"Tarball: {target_tarball_path}")
    
    if not removed_items:
        print("No existing main image files to clean")
        return True
    
    print("The following main image files will be removed:")
    for item in removed_items:
        print(f"  - {item}")
    
    if ask and not dry_run:
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            print("Cleanup cancelled")
            return False
    
    if dry_run:
        print("[DRY RUN] Would remove the above main image files")
        return True
    
    # Remove files
    if docker and check_image_exists(ctx, target_image_docker):
        print(f"Removing Docker image: {target_image_docker}")
        ctx.run(f"docker rmi -f {target_image_docker}", hide=True, warn=True)
    
    if tarball and os.path.exists(target_tarball_path):
        print(f"Removing tarball: {target_tarball_path}")
        os.remove(target_tarball_path)
    
    print("✅ Main image cleanup completed")
    return True

def handle_main_image_docker_generation(ctx, file, dry_run, clean, container_info):
    """Handle main image Docker generation"""
    target_image_name = container_info.image_full
    target_image_docker = container_info.image_docker
    
    # If no clean flag and image exists, skip reproduction
    if not clean and check_image_exists(ctx, target_image_name):
        print(f"✅ Main image '{target_image_name}' already exists - skipping reproduction")
        return True
    
    # If clean flag and image exists, remove it
    if clean and check_image_exists(ctx, target_image_name):
        print(f"Removing existing main image '{target_image_name}' for rebuild...")
        if not dry_run:
            ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
        else:
            print(f"[DRY RUN] Would remove main image: {target_image_name}")
    
    # Try to restore from tarball first
    print(f"Main image '{target_image_name}' not found, attempting to restore from tarball...")
    if restore_image_from_tarball(ctx, target_image_docker):
        if check_image_exists(ctx, target_image_name):
            print(f"✅ Main image '{target_image_name}' successfully restored")
            return True
        else:
            print(f"❌ Main image '{target_image_name}' restore failed")
            return False
    
    # Build from base image
    print(f"Main image '{target_image_name}' not available from tarball, building from base image...")
    return handle_default_main_image_generation(ctx, file, dry_run, container_info)

def handle_main_image_tarball_generation(ctx, dry_run, clean, container_info):
    """Handle main image tarball generation"""
    target_image_name = container_info.image_full
    target_image_docker = container_info.image_docker
    target_tarball_path = container_info.tarball_path
    
    # Check if tarball already exists and no clean flag - skip reproduction
    if not clean and os.path.exists(target_tarball_path):
        print(f"✅ Main image tarball '{target_tarball_path}' already exists - skipping reproduction")
        return True
    
    # Check if Docker image exists
    if not check_image_exists(ctx, target_image_name):
        print(f"❌ Cannot create main image tarball: Docker image '{target_image_name}' not found")
        return False
    
    # Create tarball
    print(f"Creating main image tarball from Docker image '{target_image_name}'...")
    if dry_run:
        print(f"[DRY RUN] Would create main image tarball: {target_tarball_path}")
        return True
    else:
        if save_image_to_tarball(ctx, target_image_name, container_info.config_file):
            print(f"✅ Main image tarball created successfully: {target_tarball_path}")
            return True
        else:
            print(f"❌ Failed to create main image tarball")
            return False

@task(help={
    'file': 'Path to config.toml file',
    'dry_run': 'Show what would be generated without actually generating',
    'base_image': 'Build base image from Dockerfile instead of creating new image',
    'tarball': 'Produce tarball from Docker image',
    'docker': 'Produce Docker image (build/restore)',
    'clean': 'Remove existing files before reproducing',
    'ask': 'Ask for confirmation before removing files (default: true)',
    'no_ask': 'Skip confirmation prompts (overrides --ask)',
    'help': 'Show help information'
})
def gen_image(ctx, file=None, dry_run=False, base_image=False, tarball=False, docker=False, clean=False, ask=True, no_ask=False, help=False):
    """Generate Docker image from config file"""
    
    # Handle --no-ask flag
    if no_ask:
        ask = False
    
    # Check for help flag or missing required arguments
    if help or not file:
        from invoke_tasks.help.help import show_gen_image_help
        show_gen_image_help()
        return
    
    # Check if config file exists
    if not os.path.exists(file):
        print(f"Error: Config file not found at {file}")
        return
    
    # Get image info from config - single call for entire function
    container_info = get_container_info(file)
    target_image_name = container_info.image_full
    
    if base_image:
        # Handle base image generation with new flags
        return handle_base_image_generation(ctx, dry_run, tarball, docker, clean, ask, container_info)
    
    # Handle main image generation with flags
    return handle_main_image_generation(ctx, file, dry_run, tarball, docker, clean, ask, container_info)