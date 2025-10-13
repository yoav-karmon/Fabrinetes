#!/usr/bin/env python3

import os
import re
import json
from datetime import datetime
from invoke import task
from tabulate import tabulate
import toml

@task
def pkg(ctx, container_name=None, container_id=None, help=False, recover=False, install=False, pkg_cache=None, offline=False, online=False, package=None):
    """Package recovery and installation: extract packages from containers or install from pkg-cache"""
    from invoke_tasks.help.help import show_pkg_help
    
    # Check for help flag or missing required arguments
    if help or (not container_name and not container_id):
        show_pkg_help()
        return
    
    # Determine container identifier
    container_identifier = container_id if container_id else container_name
    
    # Check if container is running
    try:
        if container_id:
            result = ctx.run(f"docker ps --filter id={container_id} --format '{{{{.Names}}}}'", hide=True, warn=True)
        else:
            result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
        
        if not result.stdout.strip():
            print(f"Error: Container '{container_identifier}' is not running")
            print("Available running containers:")
            ctx.run("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}'", pty=True)
            return
    except Exception:
        print(f"Error: Could not check container status")
        return
    
    # Test container accessibility
    try:
        test_result = ctx.run(f"docker exec {container_identifier} echo 'test'", hide=True, warn=True)
        if not test_result.ok:
            print(f"Error: Container '{container_identifier}' is not accessible")
            return
    except Exception:
        print(f"Error: Could not access container '{container_identifier}'")
        return
    
    print(f"Package management for container: {container_identifier}")
    print("=" * 80)
    
    if recover:
        # Execute package recovery
        recover_packages(ctx, container_identifier)
        return
    elif install:
        # Execute package installation
        if not pkg_cache:
            print("Error: --pkg-cache is required for installation")
            show_pkg_help()
            return
        
        if not offline and not online:
            print("Error: Either --offline or --online must be specified for installation")
            show_pkg_help()
            return
        
        install_packages(ctx, container_identifier, pkg_cache, offline, online, package)
        return
    else:
        # Show help for recovery/installation modes
        print("Use --recover flag to start package recovery or --install flag to install packages")
        show_pkg_help()

def recover_packages(ctx, container_identifier):
    """Recover manually installed packages with dependencies"""
    print(f"📦 Starting package recovery from container: {container_identifier}")
    
    try:
        # Get manually installed packages
        result = ctx.run(f"docker exec {container_identifier} apt-mark showmanual", hide=True, warn=True)
        
        if not result.stdout.strip():
            print("No manually installed packages found")
            return
        
        manual_packages = result.stdout.strip().split('\n')
        manual_packages = [pkg.strip() for pkg in manual_packages if pkg.strip()]
        manual_packages.sort()
        
        print(f"Found {len(manual_packages)} manually installed packages")
        
        # Extract repository name from container identifier
        repo_name = extract_repo_name(container_identifier)
        
        # Create pkg-cache directory structure
        container_dir = f"containers/{repo_name}"
        pkg_cache_dir = f"{container_dir}/pkg-cache"
        debs_dir = f"{pkg_cache_dir}/debs"
        
        os.makedirs(pkg_cache_dir, exist_ok=True)
        os.makedirs(debs_dir, exist_ok=True)
        
        print(f"📁 Created package cache directory: {pkg_cache_dir}")
        
        # Initialize recovery data
        packages_data = {}
        failed_packages = []
        downloaded_packages = set()
        
        # Update package lists in container
        print("📋 Updating package lists in container...")
        update_cmd = f"docker exec {container_identifier} sudo apt-get update"
        ctx.run(update_cmd, hide=True, warn=True)
        
        # Create container temp directory
        mkdir_cmd = f"docker exec {container_identifier} sudo mkdir -p /var/cache/fabrinetes-pkg-recovery"
        ctx.run(mkdir_cmd, hide=True, warn=True)
        
        # Process each package individually with its own folder
        for i, pkg in enumerate(manual_packages, 1):
            print(f"📦 Processing package {i}/{len(manual_packages)}: {pkg}")
            
            try:
                # Create package-specific folder
                pkg_folder = f"{debs_dir}/{pkg}"
                os.makedirs(pkg_folder, exist_ok=True)
                
                # Get package version
                version_result = ctx.run(f"docker exec {container_identifier} dpkg-query -W -f='${{Package}}=${{Version}}' {pkg}", hide=True, warn=True)
                if not version_result.stdout.strip():
                    print(f"  ⚠️  Could not get version for {pkg}")
                    failed_packages.append(pkg)
                    continue
                
                version = version_result.stdout.strip().split('=')[1] if '=' in version_result.stdout.strip() else "unknown"
                print(f"  📋 Version: {version}")
                
                # Get dependencies using apt-cache depends
                deps_result = ctx.run(f"docker exec {container_identifier} apt-cache depends {pkg}", hide=True, warn=True)
                if not deps_result.ok:
                    print(f"  ⚠️  Could not get dependencies for {pkg}")
                    failed_packages.append(pkg)
                    continue
                
                # Parse dependencies
                deps = parse_dependencies_apt_cache(deps_result.stdout)
                print(f"  📋 Dependencies to download: {deps}")
                
                # Clean container temp directory before download
                cleanup_cmd = f"docker exec {container_identifier} sudo rm -rf /var/cache/fabrinetes-pkg-recovery/*"
                ctx.run(cleanup_cmd, hide=True, warn=True)
                
                # Download dependencies including the main package
                all_packages_to_download = [pkg] + deps
                print(f"  📥 Downloading {len(all_packages_to_download)} packages: {all_packages_to_download}")
                
                download_cmd = f"docker exec {container_identifier} sh -c 'cd /var/cache/fabrinetes-pkg-recovery && sudo apt-get download --fix-missing --allow-unauthenticated {' '.join(all_packages_to_download)}'"
                download_result = ctx.run(download_cmd, hide=True, warn=True)
                
                if download_result.ok:
                    # Verify what was actually downloaded
                    list_cmd = f"docker exec {container_identifier} ls /var/cache/fabrinetes-pkg-recovery/"
                    list_result = ctx.run(list_cmd, hide=True, warn=True)
                    
                    if list_result.ok:
                        downloaded_files = list_result.stdout.strip().split('\n')
                        print(f"  ✅ Actually downloaded: {downloaded_files}")
                        
                        # Copy downloaded files to package folder
                        copy_cmd = f"docker cp {container_identifier}:/var/cache/fabrinetes-pkg-recovery/. {pkg_folder}/"
                        ctx.run(copy_cmd, hide=True, warn=True)
                        
                        # Verify files were copied
                        copied_files = os.listdir(pkg_folder)
                        print(f"  📁 Copied to {pkg_folder}: {copied_files}")
                        
                        # Clean container temp directory
                        cleanup_cmd = f"docker exec {container_identifier} sudo rm -rf /var/cache/fabrinetes-pkg-recovery/*"
                        ctx.run(cleanup_cmd, hide=True, warn=True)
                        
                        downloaded_packages.update(all_packages_to_download)
                        print(f"  ✅ Successfully processed {pkg}")
                    else:
                        print(f"  ❌ Could not verify downloaded files for {pkg}")
                        failed_packages.append(pkg)
                        continue
                else:
                    print(f"  ❌ Failed to download packages for {pkg}")
                    print(f"  Error: {download_result.stderr}")
                    failed_packages.append(pkg)
                    continue
                
                # Store package data with correct file paths
                deb_files = [f"{pkg}/{f}" for f in os.listdir(pkg_folder)]
                packages_data[pkg] = {
                    "name": pkg,
                    "version": version,
                    "dependencies": deps,
                    "deb_files": deb_files
                }
                
            except Exception as e:
                print(f"  ❌ Error processing {pkg}: {e}")
                failed_packages.append(pkg)
        
        # Generate TOML file
        generate_toml_file(packages_data, pkg_cache_dir)
        
        # Generate metadata
        generate_metadata(container_identifier, packages_data, failed_packages, downloaded_packages, pkg_cache_dir)
        
        # Show summary
        show_recovery_summary(packages_data, failed_packages, downloaded_packages, pkg_cache_dir)
        
    except Exception as e:
        print(f"Error during package recovery: {e}")

def extract_repo_name(container_identifier):
    """Extract repository name from container identifier"""
    # Try to match pattern like fabrinetes-dev-testing-20251008_154737
    repo_match = re.match(r'([^-]+(?:-[^-]+)*)-\d{8}_\d{6}', container_identifier)
    if repo_match:
        return repo_match.group(1)
    
    # Fallback: try to extract from container name
    parts = container_identifier.split('-')
    if len(parts) >= 3:
        return '-'.join(parts[:-1])
    
    return container_identifier

def get_deb_files_for_package(pkg_name, deps, debs_dir):
    """Get actual deb file paths for a package and its dependencies"""
    deb_files = []
    
    # Get list of all deb files in the directory
    try:
        all_deb_files = os.listdir(debs_dir)
    except OSError:
        return deb_files
    
    # Add the main package if it exists
    main_pkg_files = [f for f in all_deb_files if f.startswith(f"{pkg_name}_")]
    deb_files.extend([f"debs/{f}" for f in main_pkg_files])
    
    # Add dependency files
    for dep in deps:
        dep_files = [f for f in all_deb_files if f.startswith(f"{dep}_")]
        deb_files.extend([f"debs/{f}" for f in dep_files])
    
    return deb_files

def parse_dependencies_apt_cache(deps_output):
    """Parse apt-cache depends output to extract package names"""
    deps = []
    
    for line in deps_output.strip().split('\n'):
        line = line.strip()
        # Look for lines that start with dependency types
        if line.startswith('Depends:') or line.startswith('PreDepends:'):
            # Extract package name after the colon
            dep_part = line.split(':', 1)[1].strip()
            # Extract package name before any version constraints
            match = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]|[a-zA-Z0-9])', dep_part)
            if match:
                package_name = match.group(1)
                # Skip common non-package words and problematic packages
                skip_packages = {
                    'awk', 'perl', 'python', 'python3', 'bash', 'sh', 'csh', 'ksh', 'zsh',
                    'debconf-2.0', 'libgnutls30', 'libhogweed6', 'libnettle8', 'libreadline8',
                    'libstdc', 'mime-support', 'perlapi-5.38.2', 'media-types', 'netbase',
                    'tzdata', 'openssl', 'readline-common'
                }
                if package_name not in skip_packages:
                    deps.append(package_name)
    
    return deps

def generate_toml_file(packages_data, pkg_cache_dir):
    """Generate TOML file with package metadata"""
    toml_data = {"packages": {}}
    
    for pkg_name, pkg_info in packages_data.items():
        toml_data["packages"][pkg_name] = {
            "name": pkg_info["name"],
            "version": pkg_info["version"],
            "deb_files": pkg_info["deb_files"]
        }
    
    toml_file = f"{pkg_cache_dir}/packages.toml"
    with open(toml_file, 'w') as f:
        toml.dump(toml_data, f)
    
    print(f"✅ Generated TOML file: {toml_file}")

def generate_metadata(container_identifier, packages_data, failed_packages, downloaded_packages, pkg_cache_dir):
    """Generate recovery metadata JSON"""
    metadata = {
        "recovery_timestamp": datetime.now().isoformat(),
        "container_identifier": container_identifier,
        "total_manual_packages": len(packages_data),
        "successful_packages": len(packages_data) - len(failed_packages),
        "failed_packages": failed_packages,
        "total_downloaded_packages": len(downloaded_packages),
        "downloaded_packages": sorted(list(downloaded_packages))
    }
    
    metadata_file = f"{pkg_cache_dir}/recovery-metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"✅ Generated metadata file: {metadata_file}")

def show_recovery_summary(packages_data, failed_packages, downloaded_packages, pkg_cache_dir):
    """Show recovery summary"""
    print()
    print("=" * 80)
    print("RECOVERY SUMMARY")
    print("=" * 80)
    print(f"✅ Successfully processed: {len(packages_data) - len(failed_packages)} packages")
    print(f"📦 Total downloaded packages: {len(downloaded_packages)}")
    print(f"📁 Package cache location: {pkg_cache_dir}")
    
    if failed_packages:
        print(f"⚠️  Failed packages: {', '.join(failed_packages)}")
    
    # Count packages by category
    categories = {}
    for pkg_name in packages_data.keys():
        name = pkg_name.lower()
        if any(keyword in name for keyword in ['python', 'pip', 'py']):
            categories['Python'] = categories.get('Python', 0) + 1
        elif any(keyword in name for keyword in ['gcc', 'g++', 'clang', 'compiler', 'build']):
            categories['Development Tools'] = categories.get('Development Tools', 0) + 1
        elif any(keyword in name for keyword in ['lib', 'dev']):
            categories['Libraries'] = categories.get('Libraries', 0) + 1
        elif any(keyword in name for keyword in ['vim', 'nano', 'emacs', 'editor']):
            categories['Editors'] = categories.get('Editors', 0) + 1
        elif any(keyword in name for keyword in ['git', 'svn', 'hg']):
            categories['Version Control'] = categories.get('Version Control', 0) + 1
        else:
            categories['Other'] = categories.get('Other', 0) + 1
    
    print("\nPackage categories:")
    for category, count in sorted(categories.items()):
        print(f"  {category}: {count}")
    
    print(f"\n🎉 Package recovery completed successfully!")

def install_packages(ctx, container_identifier, pkg_cache_path, offline_mode, online_mode, specific_package):
    """Install packages from pkg-cache to target container"""
    print(f"📦 Starting package installation to container: {container_identifier}")
    print(f"📁 Package cache: {pkg_cache_path}")
    print(f"🔧 Mode: {'Offline' if offline_mode else 'Online'}")
    
    try:
        # Read packages.toml
        packages_data = read_packages_toml(pkg_cache_path)
        if not packages_data:
            print("Error: Could not read packages.toml")
            return
        
        # Filter packages if specific package requested
        if specific_package:
            if specific_package not in packages_data:
                print(f"Error: Package '{specific_package}' not found in pkg-cache")
                return
            packages_data = {specific_package: packages_data[specific_package]}
        
        print(f"📋 Found {len(packages_data)} packages to install")
        
        # Install packages based on mode
        if offline_mode:
            install_offline(ctx, container_identifier, packages_data, pkg_cache_path)
        else:
            install_online(ctx, container_identifier, packages_data)
            
    except Exception as e:
        print(f"Error during package installation: {e}")

def read_packages_toml(pkg_cache_path):
    """Read and parse packages.toml file"""
    toml_file = f"{pkg_cache_path}/packages.toml"
    
    if not os.path.exists(toml_file):
        print(f"Error: packages.toml not found at {toml_file}")
        return None
    
    try:
        with open(toml_file, 'r') as f:
            data = toml.load(f)
        
        if 'packages' not in data:
            print("Error: Invalid packages.toml format - missing 'packages' section")
            return None
        
        return data['packages']
    except Exception as e:
        print(f"Error reading packages.toml: {e}")
        return None

def install_offline(ctx, container_identifier, packages_data, pkg_cache_path):
    """Install packages offline using local .deb files"""
    print(f"🔧 Installing packages offline...")
    
    try:
        # Create temp directory in container
        mkdir_cmd = f"docker exec {container_identifier} sudo mkdir -p /tmp/fabrinetes-pkg-install"
        ctx.run(mkdir_cmd, hide=True, warn=True)
        
        debs_dir = f"{pkg_cache_path}/debs"
        if not os.path.exists(debs_dir):
            print(f"Error: debs directory not found at {debs_dir}")
            return
        
        # Get list of packages to install
        packages_to_install = list(packages_data.keys())
        print(f"📦 Installing {len(packages_to_install)} packages...")
        
        # Copy only the specific package folders needed
        for pkg_name in packages_to_install:
            pkg_folder = f"{debs_dir}/{pkg_name}"
            if os.path.exists(pkg_folder):
                copy_cmd = f"docker cp {pkg_folder}/. {container_identifier}:/tmp/fabrinetes-pkg-install/"
                ctx.run(copy_cmd, hide=True, warn=True)
            else:
                print(f"⚠️  Package folder not found: {pkg_folder}")
        
        # Install all packages at once
        print("📦 Installing packages...")
        install_cmd = f"docker exec {container_identifier} sh -c 'find /tmp/fabrinetes-pkg-install -name \"*.deb\" -exec sudo dpkg -i {{}} \\;'"
        result = ctx.run(install_cmd, hide=False, warn=True, timeout=300)  # Show live output
        
        # Fix missing dependencies
        print("🔧 Fixing dependencies...")
        fix_cmd = f"docker exec {container_identifier} sudo apt-get install -f -y"
        fix_result = ctx.run(fix_cmd, hide=False, warn=True, timeout=120)  # Show live output
        
        # Verify installation
        verify_installation(ctx, container_identifier, packages_data)
        
        # Cleanup
        cleanup_cmd = f"docker exec {container_identifier} sudo rm -rf /tmp/fabrinetes-pkg-install"
        ctx.run(cleanup_cmd, hide=True, warn=True)
        
        print("✅ Offline installation completed")
        
    except Exception as e:
        print(f"Error during offline installation: {e}")

def install_online(ctx, container_identifier, packages_data):
    """Install packages online using apt-get"""
    print(f"🔧 Installing packages online using apt-get...")
    
    try:
        # Update package lists
        print("📦 Updating package lists...")
        update_cmd = f"docker exec {container_identifier} sudo apt-get update"
        ctx.run(update_cmd, hide=False, warn=True, timeout=60)  # Show live output
        
        # Install packages
        package_names = list(packages_data.keys())
        print(f"📦 Installing {len(package_names)} packages...")
        
        install_cmd = f"docker exec {container_identifier} sudo apt-get install -y {' '.join(package_names)}"
        result = ctx.run(install_cmd, hide=False, warn=True, timeout=300)  # Show live output
        
        if not result.ok:
            print("⚠️  Some packages failed to install")
            print(f"Error: {result.stderr}")
        
        # Verify installation
        verify_installation(ctx, container_identifier, packages_data)
        
        print("✅ Online installation completed")
        
    except Exception as e:
        print(f"Error during online installation: {e}")

def verify_installation(ctx, container_identifier, packages_data):
    """Verify that packages were installed successfully"""
    print("🔍 Verifying installation...")
    
    try:
        # Get all installed packages at once
        check_cmd = f"docker exec {container_identifier} dpkg -l"
        result = ctx.run(check_cmd, hide=True, warn=True, timeout=30)
        
        if not result.ok:
            print("⚠️  Could not verify installation (dpkg command failed)")
            return
        
        installed_packages = result.stdout
        installed_count = 0
        failed_packages = []
        
        for package_name in packages_data.keys():
            if f"ii  {package_name}" in installed_packages:
                installed_count += 1
            else:
                failed_packages.append(package_name)
        
        print(f"✅ Successfully installed: {installed_count}/{len(packages_data)} packages")
        
        if failed_packages:
            print(f"⚠️  Failed packages: {', '.join(failed_packages)}")
            
    except Exception as e:
        print(f"⚠️  Verification failed: {e}")
    
    return installed_count, failed_packages