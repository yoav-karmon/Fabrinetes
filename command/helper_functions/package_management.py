#!/usr/bin/env python3

import os
import time
from tabulate import tabulate

def extract_package_lists(dockerfile_path):
    apt_packages = []
    python_packages = []
    
    with open(dockerfile_path, 'r') as f:
        content = f.read()
    
    lines = content.split('\n')
    
    for i, line in enumerate(lines):
        line = line.strip()
        
        if 'RUN apt-get install' in line or 'RUN apt install' in line:
            if 'apt-get install' in line:
                packages = line.split('apt-get install')[1].split('&&')[0].strip()
            else:
                packages = line.split('apt install')[1].split('&&')[0].strip()
            
            packages = packages.replace('-y', '').replace('--no-install-recommends', '').strip()
            if packages:
                apt_packages.extend([pkg.strip() for pkg in packages.split() if pkg.strip()])
        
        elif 'RUN pip install' in line or 'RUN pip3 install' in line:
            pip_line = line
            j = i + 1
            while j < len(lines) and lines[j].strip().endswith('\\'):
                pip_line += ' ' + lines[j].strip().rstrip('\\')
                j += 1
            
            if 'pip install' in pip_line:
                packages = pip_line.split('pip install')[1].split('&&')[0].strip()
            else:
                packages = pip_line.split('pip3 install')[1].split('&&')[0].strip()
            
            packages = packages.replace('--no-cache-dir', '').replace('--break-system-packages', '').strip()
            if packages:
                filtered_packages = [pkg.strip() for pkg in packages.split() if pkg.strip() and not pkg.startswith('-') and pkg != '\\']
                python_packages.extend(filtered_packages)
    
    apt_packages = [pkg for i, pkg in enumerate(apt_packages) if pkg and pkg not in apt_packages[:i]]
    python_packages = [pkg for i, pkg in enumerate(python_packages) if pkg and pkg not in python_packages[:i]]
    
    return apt_packages, python_packages

def install_apt_packages(ctx, container_name, packages):
    success_count = 0
    failed_packages = []
    
    for package in packages:
        print(f"  Installing {package}...", end=" ")
        result = ctx.run(f"docker exec {container_name} sudo apt-get install -y {package}", hide=True, warn=True)
        if result.exited == 0:
            print("SUCCESS")
            success_count += 1
        else:
            print("FAILED")
            failed_packages.append(package)
    
    print(f"  Apt packages: {success_count}/{len(packages)} installed successfully")
    if failed_packages:
        print(f"  Failed packages: {', '.join(failed_packages)}")

def install_python_packages(ctx, container_name, packages):
    success_count = 0
    failed_packages = []
    
    for package in packages:
        print(f"  Installing {package}...", end=" ")
        result = ctx.run(f"docker exec {container_name} sudo pip3 install --break-system-packages {package}", hide=True, warn=True)
        if result.exited == 0:
            print("SUCCESS")
            success_count += 1
        else:
            print("FAILED")
            failed_packages.append(package)
    
    print(f"  Python packages: {success_count}/{len(packages)} installed successfully")
    if failed_packages:
        print(f"  Failed packages: {', '.join(failed_packages)}")
