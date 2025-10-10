#!/usr/bin/env python3

import os
import time
from invoke import task
from helper_functions.package_management import extract_package_lists, install_apt_packages, install_python_packages
from helper_functions.image_management import save_image_to_tarball, restore_image_from_tarball, check_image_exists

def handle_restore_only(ctx, repo):
    """Handle restore-only mode - only restore from tarball, don't build"""
    image_name = f"{repo}:latest"
    
    print(f"🔄 Restore-only mode: Attempting to restore {image_name}")
    
    # Check if image already exists
    if check_image_exists(ctx, image_name):
        print(f"✅ Image '{image_name}' already exists locally")
        return True
    
    # Try to restore from tarball
    if restore_image_from_tarball(ctx, image_name):
        print(f"✅ Successfully restored image: {image_name}")
        return True
    else:
        print(f"❌ Failed to restore image '{image_name}'. No tarball found.")
        print(f"   Available options:")
        print(f"   1. Build the image: ./fabrinetes build {repo}")
        print(f"   2. Check available tarballs in base_images/{repo}/images/")
        return False

@task
def build(ctx, repo=None, dry_run=False, export=False, skeleton=False, restore_only=False, help=False):
    """Build Docker image for the specified repository from skeleton by default"""
    
    # Check for help flag or missing required arguments
    if help or not repo:
        from invoke_tasks.help.help import show_build_help
        show_build_help()
        return
    
    # Handle restore-only mode
    if restore_only:
        return handle_restore_only(ctx, repo)
    
    # Handle skeleton rebuild
    if skeleton and repo == "skeleton":
        print("Rebuilding skeleton container...")
        skeleton_dockerfile = "base_images/fabrinetes-skeleton/Dockerfile"
        if not os.path.exists(skeleton_dockerfile):
            print(f"Error: Skeleton Dockerfile not found at {skeleton_dockerfile}")
            return
        
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
            f"-t fabrinetes-skeleton:latest -f {skeleton_dockerfile} base_images/fabrinetes-skeleton/"
        )
        
        if dry_run:
            print(f"[DRY RUN] Would rebuild skeleton container...")
            print(f"[DRY RUN] Command: {docker_cmd}")
        else:
            print(f"Rebuilding skeleton container...")
            ctx.run(docker_cmd, pty=True)
            print("✅ Skeleton container rebuilt successfully")
        return
    
    username = os.getenv("USER") or os.getenv("USERNAME")
    uid = os.getuid()
    gid = os.getgid()
    home_dir = os.path.expanduser("~")

    repos = [repo]
    
    for repo_name in repos:
        # Load container config to get base image
        config_file = f"containers/{repo_name}/config.toml"
        if not os.path.exists(config_file):
            print(f"Error: Config file not found for {repo_name} at {config_file}")
            continue
            
        try:
            import toml
            config = toml.load(config_file)
            base_image = config['config'].get('base_image', 'fabrinetes-skeleton:latest')
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            continue
        
        # Check if base image exists
        base_image_exists = ctx.run(f"docker images {base_image} --format '{{.Repository}}'", hide=True, warn=True)
        if not base_image_exists.stdout.strip():
            print(f"Error: Base image '{base_image}' not found")
            print(f"Please build the base image first: ./fabrinetes build skeleton --skeleton")
            continue
        
        # Check if package list exists
        package_list_path = f"containers/{repo_name}/packages.txt"
        if not os.path.exists(package_list_path):
            print(f"Warning: Package list not found for {repo_name} at {package_list_path}")
            print("Cannot install packages for skeleton-based build")
            continue
        
        if dry_run:
            print(f"[DRY RUN] Would build {repo_name} from skeleton...")
            print(f"[DRY RUN] Base image: fabrinetes-skeleton:latest")
            print(f"[DRY RUN] Package source: {package_list_path}")
            print(f"[DRY RUN] Target image: {repo_name}:latest")
            if export:
                print(f"[DRY RUN] Would export image to: containers/{repo_name}/images/{repo_name}-latest.tar.gz")
        else:
            print(f"Building {repo_name} from skeleton...")
            
            # Read package list from file
            with open(package_list_path, 'r') as f:
                package_lines = f.readlines()
            
            # Parse packages (assuming Python packages for now)
            python_packages = []
            apt_packages = []
            
            for line in package_lines:
                package = line.strip()
                if package and not package.startswith('#'):
                    # For now, assume all packages are Python packages
                    # Could be extended to support apt packages with a different format
                    python_packages.append(package)
            
            print(f"Package list:")
            print(f"  Python packages: {python_packages}")
            print(f"  Apt packages: {apt_packages}")
            
            if not apt_packages and not python_packages:
                print(f"No packages found in {package_list_path}")
                continue
            
            # Start skeleton container
            container_name = f"{repo_name}-build-{int(time.time())}"
            print(f"Starting skeleton container: {container_name}")
            
            start_cmd = f"docker run -dit --name {container_name} {base_image} bash"
            ctx.run(start_cmd, hide=True)
            
            try:
                # Install apt packages
                if apt_packages:
                    print(f"Installing {len(apt_packages)} apt packages...")
                    install_apt_packages(ctx, container_name, apt_packages)
                
                # Install python packages
                if python_packages:
                    print(f"Installing {len(python_packages)} python packages...")
                    install_python_packages(ctx, container_name, python_packages)
                
                # Commit container as new image
                print(f"Committing container as {repo_name}:latest...")
                commit_cmd = f"docker commit {container_name} {repo_name}:latest"
                ctx.run(commit_cmd, hide=True)
                
                print(f"✅ Successfully built {repo_name}:latest from skeleton")
                
                # Save image to tarball for restoration
                image_name = f"{repo_name}:latest"
                if save_image_to_tarball(ctx, image_name, repo_name):
                    print(f"✅ Image saved for future restoration")
                
                # Export image if requested
                if export:
                    from tasks import export_image
                    export_image(ctx, repo_name, "latest")
                    
            finally:
                # Clean up container
                print(f"Cleaning up container: {container_name}")
                ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)