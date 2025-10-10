#!/usr/bin/env python3

import os
import re
from invoke import task
from tabulate import tabulate

@task
def pkg(ctx, container_name=None, help=False):
    """Package management: generate package file with versions and download .deb files from containers"""
    from invoke_tasks.help.help import show_pkg_help
    
    # Check for help flag or missing required arguments
    if help or not container_name:
        show_pkg_help()
        return
    
    # Check if container is running
    try:
        result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
        if not result.stdout.strip():
            print(f"Error: Container '{container_name}' is not running")
            print("Available running containers:")
            ctx.run("docker ps --format 'table {{.Names}}\\t{{.Image}}\\t{{.Status}}'", pty=True)
            return
    except Exception:
        print(f"Error: Could not check container status")
        return
    
    print(f"Package management for container: {container_name}")
    print("=" * 80)
    
    # Execute package management (always runs when container_name is provided)
    print(f"📦 Generate package file with versions and download .deb files with dependencies...")
        
    try:
        # Get manually installed packages
        result = ctx.run(f"docker exec {container_name} apt-mark showmanual", hide=True, warn=True)
        
        if not result.stdout.strip():
            print("No manually installed packages found")
        else:
            manual_packages = result.stdout.strip().split('\n')
            manual_packages.sort()
            
            # Get detailed info for each package
            packages = []
            for package_name in manual_packages:
                if package_name.strip():
                    # Get package details
                    detail_result = ctx.run(f"docker exec {container_name} dpkg-query -W -f='${{Version}}\\t${{Description}}' {package_name}", hide=True, warn=True)
                    
                    if detail_result.stdout.strip():
                        parts = detail_result.stdout.strip().split('\t', 1)
                        version = parts[0] if len(parts) > 0 else "Unknown"
                        description = parts[1] if len(parts) > 1 else "No description"
                        
                        packages.append([package_name, version, description])
            
            if packages:
                # Display in pretty table
                print(f"Found {len(packages)} manually installed packages:")
                print()
                
                headers = ["Package Name", "Version", "Description"]
                print(tabulate(packages, headers=headers, tablefmt="grid", maxcolwidths=[25, 15, 100]))
                
                # Generate package files
                # Extract repository name from container name (remove timestamp)
                repo_match = re.match(r'([^-]+(?:-[^-]+)*)-\d{8}_\d{6}', container_name)
                if repo_match:
                    repo_name = repo_match.group(1)
                else:
                    # Fallback: try to extract from container name
                    parts = container_name.split('-')
                    if len(parts) >= 3:  # fabrinetes-dev-testing-20251008_141316
                        repo_name = '-'.join(parts[:-1])  # fabrinetes-dev-testing
                    else:
                        repo_name = container_name
                
                container_dir = f"containers/{repo_name}"
                deb_cache_dir = f"{container_dir}/deb-cache"
                
                # Create deb-cache directory if it doesn't exist
                os.makedirs(deb_cache_dir, exist_ok=True)
                
                # Create package data file (names with versions) inside deb-cache
                pkg_data_file = f"{deb_cache_dir}/package-list"
                with open(pkg_data_file, 'w') as f:
                    for pkg in manual_packages:
                        try:
                            result = ctx.run(f"docker exec {container_name} dpkg-query -W -f='${{Package}}=${{Version}}' {pkg}", hide=True, warn=True)
                            if result.stdout.strip():
                                f.write(f"{result.stdout.strip()}\n")
                            else:
                                f.write(f"{pkg}=unknown\n")
                        except Exception:
                            f.write(f"{pkg}=unknown\n")
                
                print(f"✅ Generated package file:")
                print(f"  📄 {pkg_data_file}")
                
                # Download .deb files with dependencies
                print(f"📥 Downloading .deb files with dependencies...")
                
                # Update package lists once at the beginning
                print("  Updating package lists...")
                update_cmd = f"docker exec {container_name} sudo apt-get update"
                ctx.run(update_cmd, hide=True, warn=True)
                
                downloaded_count = 0
                failed_packages = []
                
                # Create dedicated directory for .deb files
                mkdir_cmd = f"docker exec {container_name} sudo mkdir -p /var/cache/fabrinetes-deb-cache"
                ctx.run(mkdir_cmd, hide=True, warn=True)
                
                # Collect all dependencies from all packages
                all_deps = set()
                for pkg in manual_packages:
                    if pkg.strip():
                        try:
                            print(f"  Processing {pkg}...")
                            
                            # Get dependencies including the package itself
                            deps_result = ctx.run(f"docker exec {container_name} apt-rdepends {pkg}", hide=True, warn=True)
                            
                            # Parse dependencies (remove indentation, conflicts, and version constraints)
                            deps = []
                            dependency_keywords = {'Depends:', 'PreDepends:', 'Conflicts:', 'Recommends:', 'Suggests:', 'Breaks:', 'Replaces:', 'Provides:', 'Enhances:'}
                            
                            for line in deps_result.stdout.strip().split('\n'):
                                line = line.strip()
                                if line and not line.startswith(' ') and not line.startswith('Conflicts'):
                                    # Skip dependency keywords and lines that start with them
                                    if line in dependency_keywords or line.startswith('Depends:') or line.startswith('PreDepends:'):
                                        continue
                                    
                                    # Extract package name only (remove version constraints like ">= 2.39")
                                    # Match package name before any version constraint
                                    match = re.match(r'^([a-zA-Z0-9][a-zA-Z0-9._-]*[a-zA-Z0-9]|[a-zA-Z0-9])', line)
                                    if match:
                                        package_name = match.group(1)
                                        # Skip common non-package words and problematic packages
                                        skip_packages = {
                                            'awk', 'perl', 'python', 'python3', 'bash', 'sh', 'csh', 'ksh', 'zsh',
                                            'debconf-2.0', 'libgnutls30', 'libhogweed6', 'libnettle8', 'libreadline8',
                                            'libstdc', 'mime-support', 'perlapi-5.38.2', 'media-types', 'netbase',
                                            'tzdata', 'openssl', 'readline-common', 'Depends', 'PreDepends'
                                        }
                                        if package_name not in skip_packages:
                                            deps.append(package_name)
                            
                            if deps:
                                all_deps.update(deps)
                                print(f"    ✅ Found {len(deps)} dependencies")
                            
                        except Exception as e:
                            print(f"    ❌ Failed to process {pkg}: {e}")
                            failed_packages.append(pkg)
                
                # Download all packages at once
                if all_deps:
                    print(f"📥 Downloading {len(all_deps)} unique packages...")
                    download_cmd = f"docker exec {container_name} sh -c 'cd /var/cache/fabrinetes-deb-cache && sudo apt-get download --fix-missing --allow-unauthenticated {' '.join(sorted(all_deps))}'"
                    result = ctx.run(download_cmd, hide=True, warn=True)
                    if result.exited != 0:
                        print(f"Warning: apt-get download failed with exit code {result.exited}")
                        print(f"Command: {download_cmd}")
                        print(f"Error: {result.stderr}")
                    
                    # Create tarball with all .deb files
                    tar_cmd = f"docker exec {container_name} sh -c 'tar -czf /tmp/deb-files.tar.gz -C /var/cache/fabrinetes-deb-cache .'"
                    ctx.run(tar_cmd, hide=True, warn=True)
                    
                    # Copy tarball to host (keep as tarball, don't extract)
                    copy_tar_cmd = f"docker cp {container_name}:/tmp/deb-files.tar.gz {deb_cache_dir}/deb-files.tar.gz"
                    ctx.run(copy_tar_cmd, hide=True, warn=True)
                    
                    # Clean up container files
                    cleanup_cmd = f"docker exec {container_name} sudo rm -rf /var/cache/fabrinetes-deb-cache /tmp/deb-files.tar.gz"
                    ctx.run(cleanup_cmd, hide=True, warn=True)
                    
                    print(f"✅ Downloaded {len(all_deps)} unique packages")
                
                # Check if tarball exists in cache
                tarball_path = f"{deb_cache_dir}/deb-files.tar.gz"
                tarball_exists = os.path.exists(tarball_path)
                
                print(f"✅ Download completed:")
                if tarball_exists:
                    # Get tarball size
                    tarball_size = os.path.getsize(tarball_path)
                    tarball_size_mb = tarball_size / (1024 * 1024)
                    print(f"  📦 deb-files.tar.gz ({tarball_size_mb:.1f}MB) in {deb_cache_dir}")
                else:
                    print(f"  📦 No tarball found in {deb_cache_dir}")
                if failed_packages:
                    print(f"  ⚠️  Failed packages: {', '.join(failed_packages)}")
                
                # Show summary
                print()
                print("=" * 80)
                print(f"SUMMARY: {len(packages)} manually installed packages processed")
                
                # Count packages by category
                categories = {}
                for package in packages:
                    name = package[0].lower()
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
                
                print("Package categories:")
                for category, count in sorted(categories.items()):
                    print(f"  {category}: {count}")
            else:
                print("No packages found")
    
    except Exception as e:
        print(f"Error processing packages: {e}")

