
import os
import time
import glob
from invoke import task
from helper_functions.name_generator import get_container_info
from helper_functions.image_management import check_image_exists, save_image_to_tarball, convert_to_docker_format
from tabulate import tabulate


@task
def test(ctx, command=None, test_number=None, help=False):

    from command.help.help import show_test_help

    # Check for help flag or missing required arguments
    if help or not command:
        show_test_help()
        return

    test_container = "fabrinetes-dev-testing"
    config_file = f"containers/{test_container}/config.toml"

    print(f"Testing {command.upper()} command with automatic permutation generation")
    print("=" * 80)

    if test_number:
        try:
            test_num = int(test_number)
            result = run_single_test_by_number(ctx, config_file, command, test_num)
            if result:
                results = [result]
                display_test_results(results, command)
            else:
                print(f"Test number {test_num} not found for command '{command}'")
                return False
        except ValueError:
            print(f"Invalid test number: {test_number}. Must be a number.")
            return False
    else:
        success, results = run_generic_test(ctx, config_file, command=command)
        display_test_results(results, command)

    print(f"\n{'='*80}")
    print(f"TEST SUMMARY FOR {command.upper()} COMMAND")
    print(f"{'='*80}")

    passed = sum(1 for r in results if r['success'])
    total = len(results)

    print(f"Total Tests: {total}")
    print(f"Passed: {passed}")
    print(f"Failed: {total - passed}")
    print(f"Success Rate: {(passed/total)*100:.1f}%")

    if passed == total:
        print("All tests passed!")
    else:
        print(f"{total - passed} tests failed")
        print("\nFailed tests:")
        for result in results:
            if not result['success']:
                print(f"  - {result['description']}: {result['error']}")

    return passed == total

def setup_test_state(ctx, config_file, container_name, image_name, command=None, params=None):
    """Setup test state for all command types - OPTIMIZED VERSION"""
    print(f"      Setting up test state...", flush=True)

    try:
        # Handle different command types
        if command in ["gen-image", "gen-image-base"]:
            success = setup_gen_image_state_optimized(ctx, config_file, params)
        elif command == "clean":
            success = setup_clean_state_optimized(ctx, config_file, params)
        else:
            # Handle regular commands (run, clean-image, kill, commit, exec, shell, pkg)
            setup_params = {
                'image_in_repo': params.get('image_in_repo', True),
                'tarball_exists': params.get('tarball_exists', True),
                'container_state': params.get('container_state', 'none')
            }
            success = setup_regular_command_state_optimized(ctx, config_file, container_name, image_name, **setup_params)

        if success:
            print(f"      Test state setup complete", flush=True)
            return True
        else:
            print(f"      Test state setup failed", flush=True)
            return False
    except Exception as e:
        print(f"      Test state setup failed with exception: {e}", flush=True)
        return False

# OPTIMIZED SETUP FUNCTIONS - Much faster by avoiding unnecessary Docker operations

def setup_gen_image_state_optimized(ctx, config_file, params):
    """OPTIMIZED: Setup state for gen-image commands - avoids rebuilding existing images"""
    from helper_functions.name_generator import get_container_info
    
    # Get container info using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    target_image_name = container_info.image_docker
    
    test_type = params.get('test_type', 'regular_image')
    print(f"        [OPTIMIZED] Setting up {test_type} test...")
    
    if test_type == 'base_image':
        # Handle base image tests - OPTIMIZED
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state - SKIP if already exists
        if base_image_in_repo:
            if not check_image_exists(ctx, base_image_name):
                print(f"        [OPTIMIZED] Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base image {base_image_name} already exists - SKIPPING build")
        else:
            # Only remove if it exists
            if check_image_exists(ctx, base_image_name):
                print(f"        [OPTIMIZED] Removing base image {base_image_name}...")
                ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base image {base_image_name} already removed - SKIPPING")
        
        # Setup base tarball state - SKIP if already exists
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    print(f"        [OPTIMIZED] Creating base tarball {base_tarball_path}...")
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
                else:
                    print(f"        [OPTIMIZED] ⚠️ Cannot create tarball - base image {base_image_name} not found")
            else:
                print(f"        [OPTIMIZED] ✅ Base tarball {base_tarball_path} already exists - SKIPPING")
        else:
            if os.path.exists(base_tarball_path):
                print(f"        [OPTIMIZED] Moving base tarball to backup...")
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base tarball already removed - SKIPPING")
    
    elif test_type in ['base_image_tarball', 'base_image_docker', 'base_image_clean', 'base_image_docker_tarball']:
        # Handle base image with flags tests - OPTIMIZED
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state - SKIP if already exists
        if base_image_in_repo:
            if not check_image_exists(ctx, base_image_name):
                print(f"Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        else:
            if check_image_exists(ctx, base_image_name):
                ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        
        # Setup base tarball state - SKIP if already exists
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
        else:
            if os.path.exists(base_tarball_path):
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    elif test_type in ['main_image_tarball', 'main_image_docker', 'main_image_clean', 'main_image_docker_tarball']:
        # Handle main image with flags tests - OPTIMIZED
        target_image_in_repo = params.get('target_image_in_repo', True)
        target_tarball_exists = params.get('target_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
        
        # Ensure base image exists for main image tests - SKIP if already exists
        if not check_image_exists(ctx, base_image_name):
            print(f"Building base image {base_image_name}...")
            ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        
        # Setup target image state - SKIP if already exists
        if target_image_in_repo:
            if not check_image_exists(ctx, target_image_name):
                print(f"Building target image {target_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
        else:
            if check_image_exists(ctx, target_image_name):
                ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
        
        # Setup target tarball state - SKIP if already exists
        if target_tarball_exists:
            if not os.path.exists(target_tarball_path):
                if check_image_exists(ctx, target_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
        else:
            if os.path.exists(target_tarball_path):
                ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
    
    else:
        # Handle main image tests - OPTIMIZED
        target_image_in_repo = params.get('target_image_in_repo', True)
        target_tarball_exists = params.get('target_tarball_exists', True)
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        print(f"        [OPTIMIZED] Setting up main_image test...")
        
        # Setup base image state - SKIP if already exists
        if base_image_in_repo:
            # Check both formats: fabrinetes-skeleton:latest and fabrinetes-skeleton-latest:latest
            skeleton_exists = check_image_exists(ctx, "fabrinetes-skeleton:latest") or check_image_exists(ctx, base_image_name)
            if not skeleton_exists:
                print(f"        [OPTIMIZED] Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base image already exists - SKIPPING build")
        else:
            if check_image_exists(ctx, base_image_name):
                print(f"        [OPTIMIZED] Removing base image {base_image_name}...")
                ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base image {base_image_name} already removed - SKIPPING")
        
        # Setup base tarball state - SKIP if already exists
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    print(f"        [OPTIMIZED] Creating base tarball {base_tarball_path}...")
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
                else:
                    print(f"        [OPTIMIZED] ⚠️ Cannot create tarball - base image {base_image_name} not found")
            else:
                print(f"        [OPTIMIZED] ✅ Base tarball {base_tarball_path} already exists - SKIPPING")
        else:
            if os.path.exists(base_tarball_path):
                print(f"        [OPTIMIZED] Moving base tarball to backup...")
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base tarball already removed - SKIPPING")
        
        # Setup target image state - SKIP if already exists
        if target_image_in_repo:
            if not check_image_exists(ctx, target_image_name):
                print(f"        [OPTIMIZED] Building target image {target_image_name}...")
                if not check_image_exists(ctx, base_image_name):
                    print(f"        [OPTIMIZED] Building base image {base_image_name} first...")
                    ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
                ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Target image {target_image_name} already exists - SKIPPING build")
        else:
            if check_image_exists(ctx, target_image_name):
                print(f"        [OPTIMIZED] Removing target image {target_image_name}...")
                ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Target image {target_image_name} already removed - SKIPPING")
        
        # Setup target tarball state - SKIP if already exists
        if target_tarball_exists:
            if not os.path.exists(target_tarball_path):
                if check_image_exists(ctx, target_image_name):
                    print(f"        [OPTIMIZED] Creating target tarball {target_tarball_path}...")
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
                else:
                    print(f"        [OPTIMIZED] ⚠️ Cannot create tarball - target image {target_image_name} not found")
            else:
                print(f"        [OPTIMIZED] ✅ Target tarball {target_tarball_path} already exists - SKIPPING")
        else:
            if os.path.exists(target_tarball_path):
                print(f"        [OPTIMIZED] Moving target tarball to backup...")
                ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Target tarball already removed - SKIPPING")
    
    return True

def setup_clean_state_optimized(ctx, config_file, params):
    """OPTIMIZED: Setup state for clean command tests - avoids rebuilding existing images"""
    from helper_functions.name_generator import get_container_info
    
    # Get container info using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    target_image_name = container_info.image_docker
    container_name = container_info.run_name
    
    print(f"        [OPTIMIZED] Setting up clean test state...")
    
    config_dir = os.path.dirname(config_file)
    base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
    target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
    
    # Setup base image state - SKIP if already exists
    base_image_in_repo = params.get('base_image_in_repo', True)
    if base_image_in_repo:
        # Check both formats: fabrinetes-skeleton:latest and fabrinetes-skeleton-latest:latest
        skeleton_exists = check_image_exists(ctx, "fabrinetes-skeleton:latest") or check_image_exists(ctx, base_image_name)
        if not skeleton_exists:
            print(f"        [OPTIMIZED] Building base image {base_image_name}...")
            result = ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
            if not result.ok:
                print(f"        [OPTIMIZED] ❌ Failed to build base image: {result.stderr}")
                return False
        else:
            print(f"        [OPTIMIZED] ✅ Base image already exists - SKIPPING build")
    else:
        if check_image_exists(ctx, base_image_name):
            print(f"        [OPTIMIZED] Removing base image {base_image_name}...")
            ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        else:
            print(f"        [OPTIMIZED] ✅ Base image {base_image_name} already removed - SKIPPING")
    
    # Setup base tarball state - SKIP if already exists
    base_tarball_exists = params.get('base_tarball_exists', True)
    if base_tarball_exists:
        if not os.path.exists(base_tarball_path):
            if check_image_exists(ctx, base_image_name):
                os.makedirs(config_dir, exist_ok=True)
                result = ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
                if not result.ok:
                    print(f"        [OPTIMIZED] ❌ Failed to create base tarball: {result.stderr}")
                    return False
    else:
        if os.path.exists(base_tarball_path):
            ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    # Setup target image state - SKIP if already exists
    target_image_in_repo = params.get('target_image_in_repo', True)
    if target_image_in_repo:
        if not check_image_exists(ctx, target_image_name):
            print(f"Building target image {target_image_name}...")
            result = ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
            if not result.ok:
                print(f"        [OPTIMIZED] ❌ Failed to build target image: {result.stderr}")
                return False
    else:
        if check_image_exists(ctx, target_image_name):
            ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
    
    # Setup target tarball state - SKIP if already exists
    target_tarball_exists = params.get('target_tarball_exists', True)
    if target_tarball_exists:
        if not os.path.exists(target_tarball_path):
            if check_image_exists(ctx, target_image_name):
                os.makedirs(config_dir, exist_ok=True)
                result = ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
                if not result.ok:
                    print(f"        [OPTIMIZED] ❌ Failed to create target tarball: {result.stderr}")
                    return False
        else:
            print(f"        [OPTIMIZED] ✅ Target tarball {target_tarball_path} already exists - SKIPPING")
    else:
        if os.path.exists(target_tarball_path):
            ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
    
    # Setup container state - OPTIMIZED
    container_state = params.get('container_state', 'none')
    if container_state == 'running':
        if not check_container_running(ctx, container_name):
            print(f"Starting container {container_name}...")
            result = ctx.run(f"./fabrinetes run --file {config_file} --no-ask", hide=True, warn=True)
            if not result.ok:
                print(f"        [OPTIMIZED] ❌ Failed to start container: {result.stderr}")
                return False
    elif container_state == 'stopped':
        # Kill if running, then create stopped container
        if check_container_running(ctx, container_name):
            ctx.run(f"docker kill {container_name}", hide=True, warn=True)
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
        # Create stopped container
        result = ctx.run(f"docker create --name {container_name} {target_image_name}", hide=True, warn=True)
        if not result.ok:
            print(f"        [OPTIMIZED] ❌ Failed to create stopped container: {result.stderr}")
            return False
    else:  # none
        if check_container_running(ctx, container_name):
            ctx.run(f"docker kill {container_name}", hide=True, warn=True)
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
    
    return True

def setup_regular_command_state_optimized(ctx, config_file, container_name, image_name,
                               image_in_repo=True, tarball_exists=True,
                               container_state="none", params=None):
    """OPTIMIZED: Setup state for regular commands - avoids rebuilding existing images"""
    
    try:
        print(f"        [OPTIMIZED] Setting up regular command state...")
        
        # Get container info for tarball paths
        container_info = get_container_info(config_file)
        base_image_name = container_info.base_image_docker
        target_image_name = container_info.image_docker
        
        config_dir = os.path.dirname(config_file)
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state - SKIP if already exists
        if params is None:
            params = {}
        base_image_in_repo = params.get('base_image_in_repo', True)
        if base_image_in_repo:
            # Check both formats: fabrinetes-skeleton:latest and fabrinetes-skeleton-latest:latest
            skeleton_exists = check_image_exists(ctx, "fabrinetes-skeleton:latest") or check_image_exists(ctx, base_image_name)
            if not skeleton_exists:
                print(f"        [OPTIMIZED] Building base image {base_image_name}...")
                result = ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
                if not result.ok:
                    print(f"        [OPTIMIZED] ❌ Failed to build base image: {result.stderr}")
                    return False
            else:
                print(f"        [OPTIMIZED] ✅ Base image already exists - SKIPPING build")
        else:
            if check_image_exists(ctx, base_image_name):
                print(f"        [OPTIMIZED] Removing base image {base_image_name}...")
                ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
            else:
                print(f"        [OPTIMIZED] ✅ Base image {base_image_name} already removed - SKIPPING")
        
        # Setup base tarball state - SKIP if already exists
        base_tarball_exists = params.get('base_tarball_exists', True)
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    result = ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
                    if not result.ok:
                        print(f"        [OPTIMIZED] ❌ Failed to create base tarball: {result.stderr}")
                        return False
        else:
            if os.path.exists(base_tarball_path):
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
        
        # Setup target image state - SKIP if already exists
        target_image_in_repo = params.get('target_image_in_repo', True)
        if target_image_in_repo:
            if not check_image_exists(ctx, target_image_name):
                print(f"Building target image {target_image_name}...")
                result = ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
                if not result.ok:
                    print(f"        [OPTIMIZED] ❌ Failed to build target image: {result.stderr}")
                    return False
        else:
            if check_image_exists(ctx, target_image_name):
                ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
        
        # Setup target tarball state - SKIP if already exists
        target_tarball_exists = params.get('target_tarball_exists', True)
        if target_tarball_exists:
            if not os.path.exists(target_tarball_path):
                if check_image_exists(ctx, target_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    result = ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
                    if not result.ok:
                        print(f"        [OPTIMIZED] ❌ Failed to create target tarball: {result.stderr}")
                        return False
            else:
                print(f"        [OPTIMIZED] ✅ Target tarball {target_tarball_path} already exists - SKIPPING")
        else:
            if os.path.exists(target_tarball_path):
                ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
        
        # Setup container state - OPTIMIZED
        container_state = params.get('container_state', 'none')
        if container_state == 'running':
            if not check_container_running(ctx, container_name):
                print(f"Starting container {container_name}...")
                result = ctx.run(f"./fabrinetes run --file {config_file} --no-ask", hide=True, warn=True)
                if not result.ok:
                    print(f"        [OPTIMIZED] ❌ Failed to start container: {result.stderr}")
                    return False
        elif container_state == 'stopped':
            # Kill if running, then create stopped container
            if check_container_running(ctx, container_name):
                ctx.run(f"docker kill {container_name}", hide=True, warn=True)
            ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
            # Create stopped container
            result = ctx.run(f"docker create --name {container_name} {target_image_name}", hide=True, warn=True)
            if not result.ok:
                print(f"        [OPTIMIZED] ❌ Failed to create stopped container: {result.stderr}")
                return False
        else:  # none
            if check_container_running(ctx, container_name):
                ctx.run(f"docker kill {container_name}", hide=True, warn=True)
            ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
        
        return True
    except Exception as e:
        print(f"        [OPTIMIZED] ❌ Setup failed with exception: {e}", flush=True)
        return False

def setup_gen_image_state(ctx, config_file, params):
    """Setup state for gen-image commands"""
    from helper_functions.name_generator import get_container_info
    
    # Get container info using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    target_image_name = container_info.image_docker
    
    test_type = params.get('test_type', 'regular_image')
    
    if test_type == 'base_image':
        # Handle base image tests
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state
        if base_image_in_repo:
            if not check_image_exists(ctx, base_image_name):
                print(f"Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        
        # Setup base tarball state
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
        else:
            if os.path.exists(base_tarball_path):
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    elif test_type in ['base_image_tarball', 'base_image_docker', 'base_image_clean', 'base_image_docker_tarball']:
        # Handle base image with flags tests
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state
        if base_image_in_repo:
            if not check_image_exists(ctx, base_image_name):
                print(f"Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        
        # Setup base tarball state
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
        else:
            if os.path.exists(base_tarball_path):
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    elif test_type in ['main_image_tarball', 'main_image_docker', 'main_image_clean', 'main_image_docker_tarball']:
        # Handle main image with flags tests
        target_image_in_repo = params.get('target_image_in_repo', True)
        target_tarball_exists = params.get('target_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
        
        # Ensure base image exists for main image tests
        if not check_image_exists(ctx, base_image_name):
            print(f"Building base image {base_image_name}...")
            ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        
        # Setup target image state
        if target_image_in_repo:
            if not check_image_exists(ctx, target_image_name):
                print(f"Building target image {target_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
        
        # Setup target tarball state
        if target_tarball_exists:
            if not os.path.exists(target_tarball_path):
                if check_image_exists(ctx, target_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
        else:
            if os.path.exists(target_tarball_path):
                ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
    
    else:
        # Handle regular image tests
        target_image_in_repo = params.get('target_image_in_repo', True)
        target_tarball_exists = params.get('target_tarball_exists', True)
        base_image_in_repo = params.get('base_image_in_repo', True)
        base_tarball_exists = params.get('base_tarball_exists', True)
        
        config_dir = os.path.dirname(config_file)
        target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
        base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
        
        # Setup base image state
        if base_image_in_repo:
            if not check_image_exists(ctx, base_image_name):
                print(f"Building base image {base_image_name}...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
        
        # Setup base tarball state
        if base_tarball_exists:
            if not os.path.exists(base_tarball_path):
                if check_image_exists(ctx, base_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
        else:
            if os.path.exists(base_tarball_path):
                ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
        
        # Setup target image state
        if target_image_in_repo:
            if not check_image_exists(ctx, target_image_name):
                print(f"Building target image {target_image_name}...")
                if not check_image_exists(ctx, base_image_name):
                    print(f"Building base image {base_image_name} first...")
                    ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
                ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
        
        # Setup target tarball state
        if target_tarball_exists:
            if not os.path.exists(target_tarball_path):
                if check_image_exists(ctx, target_image_name):
                    os.makedirs(config_dir, exist_ok=True)
                    ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
        else:
            if os.path.exists(target_tarball_path):
                ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)

def check_container_running(ctx, container_name):
    """Check if container is running"""
    result = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True, warn=True)
    return bool(result.stdout.strip())

def setup_clean_state(ctx, config_file, params):
    """Setup state for clean command tests"""
    from helper_functions.name_generator import get_container_info
    
    # Get container info using the dataclass
    container_info = get_container_info(config_file)
    base_image_name = container_info.base_image_docker
    target_image_name = container_info.image_docker
    container_name = container_info.run_name
    
    config_dir = os.path.dirname(config_file)
    base_tarball_path = os.path.join(config_dir, f"{base_image_name.replace(':', '-')}.tar.gz")
    target_tarball_path = os.path.join(config_dir, f"{target_image_name.replace(':', '-')}.tar.gz")
    
    # Setup base image state
    base_image_in_repo = params.get('base_image_in_repo', True)
    if base_image_in_repo:
        if not check_image_exists(ctx, base_image_name):
            print(f"Building base image {base_image_name}...")
            ctx.run(f"./fabrinetes gen-image --file {config_file} --base-image", hide=True, warn=True)
    else:
        ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
    
    # Setup base tarball state
    base_tarball_exists = params.get('base_tarball_exists', True)
    if base_tarball_exists:
        if not os.path.exists(base_tarball_path):
            if check_image_exists(ctx, base_image_name):
                os.makedirs(config_dir, exist_ok=True)
                ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
    else:
        if os.path.exists(base_tarball_path):
            ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    # Setup target image state
    target_image_in_repo = params.get('target_image_in_repo', True)
    if target_image_in_repo:
        if not check_image_exists(ctx, target_image_name):
            print(f"Building target image {target_image_name}...")
            ctx.run(f"./fabrinetes gen-image --file {config_file}", hide=True, warn=True)
    else:
        ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
    
    # Setup target tarball state
    target_tarball_exists = params.get('target_tarball_exists', True)
    if target_tarball_exists:
        if not os.path.exists(target_tarball_path):
            if check_image_exists(ctx, target_image_name):
                os.makedirs(config_dir, exist_ok=True)
                ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
    else:
        if os.path.exists(target_tarball_path):
            ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)
    
    # Setup container state
    container_state = params.get('container_state', 'none')
    if container_state == 'running':
        if not check_container_running(ctx, container_name):
            print(f"Starting container {container_name}...")
            ctx.run(f"./fabrinetes run --file {config_file} --no-ask", hide=True, warn=True)
    elif container_state == 'stopped':
        # Kill if running, then create stopped container
        ctx.run(f"docker kill {container_name}", hide=True, warn=True)
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
        # Create stopped container
        ctx.run(f"docker create --name {container_name} {target_image_name}", hide=True, warn=True)
    else:  # none
        ctx.run(f"docker kill {container_name}", hide=True, warn=True)
        ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)

def setup_regular_command_state(ctx, config_file, container_name, image_name,
                               image_in_repo=True, tarball_exists=True,
                               container_state="none"):
    """Setup state for regular commands (run, clean-image, kill, commit, exec, shell, pkg)"""
    
    # Get container info for tarball paths
    container_info = get_container_info(config_file)


    def ensure_image_state():
        if image_in_repo:
            if not check_image_exists(ctx, "fabrinetes-skeleton:latest"):
                print("Building skeleton image first...")
                ctx.run(f"./fabrinetes gen-image --file skeleton --skeleton", hide=True, warn=True)

            if image_name != "fabrinetes-skeleton:latest":
                print(f"Building {image_name} image...")
                ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
        else:
            docker_image_name = convert_to_docker_format(image_name)
            ctx.run(f"docker rmi -f {docker_image_name}", hide=True, warn=True)

    def ensure_tarball_state():
        tarball_path = container_info.tarball_path
        tarball_directory = container_info.tarball_directory
        
        if tarball_exists:
            ctx.run(f"mkdir -p {tarball_directory}", hide=True, warn=True)
            if not os.path.exists(tarball_path):
                # Ensure image exists first, then create tarball
                docker_image_name = convert_to_docker_format(image_name)
                if not check_image_exists(ctx, docker_image_name):
                    # Build the image if it doesn't exist
                    ctx.run(f"./fabrinetes gen-image --file {config_file} --docker --tarball", hide=True, warn=True)
                # Create tarball with correct image name
                ctx.run(f"docker save {docker_image_name} | gzip > {tarball_path}", hide=True, warn=True)
        else:
            ctx.run(f"rm -f {tarball_path}", hide=True, warn=True)

    def ensure_container_state():
        current_state = get_current_container_state()
        
        if container_state == "none":
            if current_state != "none":
                ctx.run(f"docker rm -f {container_name}", hide=True, warn=True)
        
        elif container_state == "running":
            if current_state == "none":
                if not image_in_repo:
                    print(f"Warning: Cannot set container to 'running' if image is not in repo. Building image for {image_name}...")
                    if not check_image_exists(ctx, image_name):
                        ctx.run(f"./fabrinetes gen-image --file {image_name}", hide=True, warn=True)
                ctx.run(f"./fabrinetes run --file {config_file} --no-ask", hide=True, warn=True)
                time.sleep(1)
                if get_current_container_state() != "running":
                    print(f"Warning: Container failed to start properly")
            elif current_state == "stopped":
                ctx.run(f"docker start {container_name}", hide=True, warn=True)
                time.sleep(1)
                if get_current_container_state() != "running":
                    print(f"Warning: Container failed to start properly")
        
        elif container_state == "stopped":
            if current_state == "none":
                if not image_in_repo:
                    print(f"Warning: Cannot set container to 'stopped' if image is not in repo. Building image for {image_name}...")
                    if not check_image_exists(ctx, image_name):
                        ctx.run(f"./fabrinetes gen-image --file {image_name}", hide=True, warn=True)
                ctx.run(f"./fabrinetes run --file {config_file} --no-ask", hide=True, warn=True)
                ctx.run(f"docker stop {container_name}", hide=True, warn=True)
                time.sleep(1)
                if get_current_container_state() != "stopped":
                    print(f"Warning: Container failed to stop properly")
            elif current_state == "running":
                ctx.run(f"docker stop {container_name}", hide=True, warn=True)
                time.sleep(1)
                if get_current_container_state() != "stopped":
                    print(f"Warning: Container failed to stop properly")

    ensure_image_state()
    ensure_tarball_state()
    ensure_container_state()

    print(f"      Test state setup complete", flush=True)


def restore_test_state(ctx, config_file):
    """Restore all backup files created during test setup
    
    NOTE: This function is currently NOT called after tests to enable resource reuse.
    Tests are ordered optimally so that resources created by early tests can be
    reused by later tests, significantly improving performance.
    
    If you need to clean up after tests, call this function manually.
    """
    
    # Restore Dockerfile
    config_dir = os.path.dirname(config_file)
    dockerfile_path = os.path.join(config_dir, "Dockerfile")
    dockerfile_backup = f"{dockerfile_path}.backup"
    if os.path.exists(dockerfile_backup):
        ctx.run(f"mv {dockerfile_backup} {dockerfile_path}", hide=True, warn=True)
        print(f"      Dockerfile restored", flush=True)
    
    # Restore tarball files
    images_dir = os.path.join(config_dir, "images")
    if os.path.exists(images_dir):
        tarball_backups = glob.glob(f"{images_dir}/*.tar.gz.backup")
        for backup in tarball_backups:
            original = backup.replace('.backup', '')
            ctx.run(f"mv {backup} {original}", hide=True, warn=True)
            print(f"      Tarball restored: {os.path.basename(original)}", flush=True)


def run_generic_test(ctx, config_file, command="run"):

    container_info = get_container_info(config_file)
    container_name = container_info.run_name
    image_name = container_info.image_full

    if not container_name or not image_name:
        print(f"Error: Could not get container/image names from config file {config_file}")
        return False, "Config parsing error", "", "", ""

    parameter_list = get_command_parameters(command)

    print(f"Generated {len(parameter_list)} test cases for {command.upper()} command")
    print("=" * 80)

    results = []

    for i, params in enumerate(parameter_list):
        test_desc = params['description']

        print(f"\nTest {i+1}/{len(parameter_list)}: {test_desc}")
        print("-" * 60)

        success, error, actual, expected, steps = run_single_test(
            ctx, config_file, container_name, image_name,
            test_desc, command, params
        )

        results.append({
            'name': f"test_{i+1}",
            'description': test_desc,
            'success': success,
            'error': error,
            'actual': actual,
            'expected': expected,
            'steps': steps
        })
        
        # Exit immediately on failure
        if not success:
            print(f"\n❌ Test {i+1}/{len(parameter_list)} FAILED - Stopping execution")
            print(f"Failed test: {test_desc}")
            if error:
                print(f"Error details: {error}")
            return False, results

    return True, results

def run_single_test_by_number(ctx, config_file, command, test_number):
    try:
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        image_name = container_info.image_full
        
        if not container_name or not image_name:
            print(f"Error: Could not get container/image names from config file {config_file}")
            return None
    except Exception as e:
        # Handle case where config file is empty or malformed
        print(f"Warning: Could not read config file {config_file}: {e}")
        # Use default values for testing
        container_name = "test-container"
        image_name = "test-image"
    
    parameter_list = get_command_parameters(command)
    
    if test_number < 1 or test_number > len(parameter_list):
        return None
    
    params = parameter_list[test_number - 1]
    test_desc = params['description']
    
    print(f"Running Test {test_number}/{len(parameter_list)}: {test_desc}")
    print("-" * 60)
    
    success, error, actual, expected, steps = run_single_test(
        ctx, config_file, container_name, image_name,
        test_desc, command, params
    )
    
    return {
        'name': f"test_{test_number}",
        'description': test_desc,
        'success': success,
        'error': error,
        'actual': actual,
        'expected': expected,
        'steps': steps
    }

def get_command_parameters(command):

    if command == "run":
        return [
            {'image_in_repo': True, 'tarball_exists': True, 'container_state': 'none', 'description': 'Fresh run - should PASS'},
            {'image_in_repo': True, 'tarball_exists': True, 'container_state': 'running', 'description': 'Container already running - should FAIL (duplicate)'},
            {'image_in_repo': True, 'tarball_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should restart'},
            {'image_in_repo': True, 'tarball_exists': False, 'container_state': 'none', 'description': 'No tarball - should PASS'},
            {'image_in_repo': False, 'tarball_exists': True, 'container_state': 'none', 'description': 'Restore from tarball - should PASS'},
            {'image_in_repo': False, 'tarball_exists': False, 'container_state': 'none', 'description': 'No image, no restore - should FAIL'},
        ]

    elif command == "gen-image":
        return [
            # NO FLAGS TEST - Both base and main image require at least one flag
            {'test_type': 'no_flags', 'description': 'No flags provided - should FAIL (shows help)'},
            
            # BASE IMAGE TESTS - Individual flag testing (ordered for optimal performance)
            
            # Base image with --tarball flag only (create tarball first, then skip)
            {'test_type': 'base_image_tarball', 'base_image_in_repo': True, 'base_tarball_exists': False, 'description': 'Base --tarball: Image in repo, no tarball - should PASS (create tarball)'},
            {'test_type': 'base_image_tarball', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base --tarball: Image in repo, tarball exists - should PASS (skip reproduction)'},
            {'test_type': 'base_image_tarball', 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Base --tarball: Image not in repo, tarball exists - should PASS (restore then create tarball)'},
            
            # Base image with --docker flag only (build first, then skip)
            {'test_type': 'base_image_docker', 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Base --docker: Image not in repo, no tarball - should PASS (build from Dockerfile)'},
            {'test_type': 'base_image_docker', 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Base --docker: Image not in repo, tarball exists - should PASS (restore from tarball)'},
            {'test_type': 'base_image_docker', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base --docker: Image in repo, tarball exists - should PASS (skip reproduction)'},
            
            # Base image with --clean flag only (clean operations last)
            {'test_type': 'base_image_clean_docker', 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Base --clean --docker: Image not in repo, no tarball - should PASS (build from Dockerfile)'},
            {'test_type': 'base_image_clean_docker', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base --clean --docker: Image in repo, tarball exists - should PASS (remove docker and rebuild)'},
            
            {'test_type': 'base_image_clean_tarball', 'base_image_in_repo': True, 'base_tarball_exists': False, 'description': 'Base --clean --tarball: Image in repo, no tarball - should PASS (create tarball)'},
            {'test_type': 'base_image_clean_tarball', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base --clean --tarball: Image in repo, tarball exists - should PASS (remove tarball and recreate)'},
            
            # MAIN IMAGE TESTS - Individual flag testing (ordered for optimal performance)
            
            # Main image with --tarball flag only (create tarball first, then skip)
            {'test_type': 'main_image_tarball', 'target_image_in_repo': True, 'target_tarball_exists': False, 'description': 'Main --tarball: Image in repo, no tarball - should PASS (create tarball)'},
            {'test_type': 'main_image_tarball', 'target_image_in_repo': True, 'target_tarball_exists': True, 'description': 'Main --tarball: Image in repo, tarball exists - should PASS (skip reproduction)'},
            {'test_type': 'main_image_tarball', 'target_image_in_repo': False, 'target_tarball_exists': True, 'description': 'Main --tarball: Image not in repo, tarball exists - should FAIL (no image to create tarball from)'},
            
            # Main image with --docker flag only (build first, then skip)
            {'test_type': 'main_image_docker', 'target_image_in_repo': False, 'target_tarball_exists': False, 'description': 'Main --docker: Image not in repo, no tarball - should PASS (build from base)'},
            {'test_type': 'main_image_docker', 'target_image_in_repo': False, 'target_tarball_exists': True, 'description': 'Main --docker: Image not in repo, tarball exists - should PASS (restore from tarball)'},
            {'test_type': 'main_image_docker', 'target_image_in_repo': True, 'target_tarball_exists': True, 'description': 'Main --docker: Image in repo, tarball exists - should PASS (skip reproduction)'},
            
            # Main image with --clean flag only (clean operations last)
            {'test_type': 'main_image_clean_docker', 'target_image_in_repo': False, 'target_tarball_exists': False, 'description': 'Main --clean --docker: Image not in repo, no tarball - should PASS (build from base)'},
            {'test_type': 'main_image_clean_docker', 'target_image_in_repo': True, 'target_tarball_exists': True, 'description': 'Main --clean --docker: Image in repo, tarball exists - should PASS (remove docker and rebuild)'},
            
            {'test_type': 'main_image_clean_tarball', 'target_image_in_repo': True, 'target_tarball_exists': False, 'description': 'Main --clean --tarball: Image in repo, no tarball - should PASS (create tarball)'},
            {'test_type': 'main_image_clean_tarball', 'target_image_in_repo': True, 'target_tarball_exists': True, 'description': 'Main --clean --tarball: Image in repo, tarball exists - should PASS (remove tarball and recreate)'},
        ]

    elif command == "gen-image-base":
        return [
            # Base image tests only
            {'test_type': 'base_image', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base image: Base image in repo, tarball exists - should PASS (use existing)'},
            {'test_type': 'base_image', 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Base image: Base image not in repo, tarball exists - should PASS (restore)'},
            {'test_type': 'base_image', 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Base image: Base image not in repo, no tarball - should PASS (create from Dockerfile)'},
        ]

    elif command == "clean-image":
        return [
            {'image_in_repo': True, 'tarball_exists': True, 'description': 'Image exists - should PASS (clean)'},
            {'image_in_repo': True, 'tarball_exists': False, 'description': 'Image exists, no tarball - should PASS (clean)'},
            {'image_in_repo': False, 'tarball_exists': True, 'description': 'No image, tarball exists - should PASS (nothing to clean)'},
            {'image_in_repo': False, 'tarball_exists': False, 'description': 'No image - should PASS (nothing to clean)'},
        ]

    elif command == "kill":
        return [
            {'container_state': 'running', 'description': 'Container running - should PASS (kill)'},
            {'container_state': 'stopped', 'description': 'Container stopped - should PASS (remove)'},
            {'container_state': 'none', 'description': 'No container - should PASS (nothing to kill)'},
        ]

    elif command == "commit":
        return [
            {'container_state': 'running', 'description': 'Container running - should PASS (commit)'},
            {'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "exec":
        return [
            {'container_state': 'running', 'description': 'Container running - should PASS (exec)'},
            {'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "shell":
        return [
            {'container_state': 'running', 'description': 'Container running - should PASS (shell)'},
            {'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "pkg":
        return [
            {'container_state': 'running', 'description': 'Container running - should PASS (pkg)'},
            {'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "clean":
        return [
            # Test different clean options
            {'clean_target': 'base_image', 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Clean base image: Base image in repo, tarball exists - should PASS'},
            {'clean_target': 'base_image', 'base_image_in_repo': True, 'base_tarball_exists': False, 'description': 'Clean base image: Base image in repo, no tarball - should PASS'},
            {'clean_target': 'base_image', 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Clean base image: Base image not in repo, tarball exists - should PASS'},
            {'clean_target': 'base_image', 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Clean base image: Base image not in repo, no tarball - should PASS'},
            
            {'clean_target': 'image', 'target_image_in_repo': True, 'target_tarball_exists': True, 'description': 'Clean image: Image in repo, tarball exists - should PASS'},
            {'clean_target': 'image', 'target_image_in_repo': True, 'target_tarball_exists': False, 'description': 'Clean image: Image in repo, no tarball - should PASS'},
            {'clean_target': 'image', 'target_image_in_repo': False, 'target_tarball_exists': True, 'description': 'Clean image: Image not in repo, tarball exists - should PASS'},
            {'clean_target': 'image', 'target_image_in_repo': False, 'target_tarball_exists': False, 'description': 'Clean image: Image not in repo, no tarball - should PASS'},
            
            {'clean_target': 'container', 'container_state': 'running', 'description': 'Clean container: Container running - should PASS'},
            {'clean_target': 'container', 'container_state': 'stopped', 'description': 'Clean container: Container stopped - should PASS'},
            {'clean_target': 'container', 'container_state': 'none', 'description': 'Clean container: No container - should PASS'},
            
            {'clean_target': 'dangling', 'description': 'Clean dangling: Should PASS (always works)'},
            
            {'clean_target': 'all', 'base_image_in_repo': True, 'base_tarball_exists': True, 'target_image_in_repo': True, 'target_tarball_exists': True, 'container_state': 'running', 'description': 'Clean all: Everything exists - should PASS'},
            {'clean_target': 'all', 'base_image_in_repo': False, 'base_tarball_exists': False, 'target_image_in_repo': False, 'target_tarball_exists': False, 'container_state': 'none', 'description': 'Clean all: Nothing exists - should PASS'},
        ]

    else:
        return [
            {'description': 'Default test - should PASS'},
        ]


def run_single_test(ctx, config_file, container_name, image_name, description, command, params):

    steps = []

    expected_results = determine_expected_results(command, params)

    print(f"      Expected: {description}", flush=True)

    print(f"      Step 0: Preparing test environment...", flush=True)

    setup_params = {
        'image_in_repo': params.get('image_in_repo', True),
        'tarball_exists': params.get('tarball_exists', True),
        'container_state': params.get('container_state', 'none')
    }

    try:
        setup_success = setup_test_state(ctx, config_file, container_name, image_name, command, params)
        if setup_success:
            steps.append(("Prepare test", "PASS"))
            print(f"      Step 0: Environment prepared", flush=True)
        else:
            steps.append(("Prepare test", "FAIL"))
            print(f"      Step 0: Environment preparation FAILED", flush=True)
            return False, "Test setup failed", gen_results_table_str(steps), gen_expected_table_str(expected_results), gen_results_table_str(steps)
    except Exception as e:
        steps.append(("Prepare test", "FAIL"))
        print(f"      Step 0: Environment preparation FAILED: {e}", flush=True)
        print(f"      DETAILED ERROR LOG:", flush=True)
        print(f"      - Config file: {config_file}", flush=True)
        print(f"      - Container name: {container_name}", flush=True)
        print(f"      - Image name: {image_name}", flush=True)
        if command == "gen-image":
            print(f"      - Test params: {params}", flush=True)
        else:
            print(f"      - Setup params: {setup_params}", flush=True)
        print(f"      - Error: {str(e)}", flush=True)
        
        # Note: Not calling restore_test_state to allow resource reuse between tests
        return False, f"Preparation failed: {str(e)}", gen_results_table_str(steps), gen_expected_table_str(expected_results), gen_results_table_str(steps)

    print(f"      Step 1: Running {command} command...", flush=True)

    command_to_run = generate_command(command, config_file, params)

    result = ctx.run(command_to_run, hide=True, warn=False)

    step1_result = validate_command_result(ctx, result, container_name, command, expected_results)
    steps.append((f"Run {command}", step1_result))

    if step1_result == "PASS":
        print(f"      Step 1: Command succeeded as expected", flush=True)
    else:
        print(f"      Step 1: Command failed as expected", flush=True)

    # Note: Not calling restore_test_state to allow resource reuse between tests

    print(f"      Validating step results...", flush=True)
    all_match = True
    for step_num, (step_name, actual_result) in enumerate(steps):
        expected_result = get_expected_result_str(step_num, expected_results)
        if actual_result != expected_result:
            all_match = False
            print(f"      Step {step_num}: Expected '{expected_result}', got '{actual_result}'", flush=True)
        else:
            print(f"      Step {step_num}: '{actual_result}' matches expected", flush=True)

    if all_match:
        print(f"      All steps match expected results!", flush=True)
        return True, "", gen_results_table_str(steps), gen_expected_table_str(expected_results), gen_results_table_str(steps)
    else:
        error_details = gen_error_table_str(steps, expected_results)
        print(f"      Some steps didn't match expected results", flush=True)
        return False, error_details, gen_results_table_str(steps), gen_expected_table_str(expected_results), gen_results_table_str(steps)

def determine_expected_results(command, params):

    if command == "run":
        if not params.get('image_in_repo', True) and not params.get('tarball_exists', True):
            return {1: "FAIL"}
        elif params.get('container_state', 'none') == "running":
            return {1: "FAIL"}
        else:
            return {}

    elif command in ["gen-image", "gen-image-base", "clean-image"]:
        # Handle gen-image specific test cases
        if command == "gen-image":
            # Get test type to determine expected behavior
            test_type = params.get('test_type', 'main_image')
            
            # No flags test should FAIL (shows help)
            if test_type == 'no_flags':
                return {1: "FAIL"}
            
            # Base image tests without flags should FAIL
            if test_type == 'base_image':
                return {1: "FAIL"}
            
            # Main image tests without flags should FAIL
            if test_type == 'main_image':
                return {1: "FAIL"}
            
            # Main image tests - check for failure conditions
            target_image_in_repo = params.get('target_image_in_repo', True)
            target_tarball_exists = params.get('target_tarball_exists', True)
            base_image_in_repo = params.get('base_image_in_repo', True)
            base_tarball_exists = params.get('base_tarball_exists', True)
            
            # Should FAIL if no target image AND no target tarball AND no base image AND no base tarball
            if not target_image_in_repo and not target_tarball_exists and not base_image_in_repo and not base_tarball_exists:
                return {1: "FAIL"}
            
            # Main image tarball tests that should fail
            if test_type == 'main_image_tarball' and not target_image_in_repo and target_tarball_exists:
                return {1: "FAIL"}
            
            # Should PASS in all other cases
            return {}
        
        elif command == "gen-image-base":
            # Base image tests only - all should PASS since Dockerfile is available
            return {}
        
        # For clean-image, all steps should PASS
        return {}

    elif command == "kill":
        return {}

    elif command == "clean":
        # Clean command tests - all should PASS since clean operations are safe
        return {}

    elif command in ["commit", "exec", "shell", "pkg"]:
        if params.get('container_state', 'none') != "running":
            return {1: "FAIL"}
        else:
            return {}

    return {}

def generate_command(command, config_file, test_params=None):

    if command == "run":
        return f"./fabrinetes run --file {config_file} --no-ask"
    elif command == "gen-image":
        # Generate gen-image command based on test type
        test_type = test_params.get('test_type', 'main_image') if test_params else 'main_image'
        
        if test_type == 'no_flags':
            return f"./fabrinetes gen-image --file {config_file}"
        elif test_type == 'main_image':
            return f"./fabrinetes gen-image --file {config_file}"
        elif test_type == 'base_image':
            return f"./fabrinetes gen-image --file {config_file} --base-image"
        elif test_type == 'main_image_tarball':
            return f"./fabrinetes gen-image --file {config_file} --tarball"
        elif test_type == 'main_image_docker':
            return f"./fabrinetes gen-image --file {config_file} --docker"
        elif test_type == 'main_image_clean_docker':
            return f"./fabrinetes gen-image --file {config_file} --clean --docker --no-ask"
        elif test_type == 'main_image_clean_tarball':
            return f"./fabrinetes gen-image --file {config_file} --clean --tarball --no-ask"
        elif test_type == 'base_image_tarball':
            return f"./fabrinetes gen-image --file {config_file} --base-image --tarball"
        elif test_type == 'base_image_docker':
            return f"./fabrinetes gen-image --file {config_file} --base-image --docker"
        elif test_type == 'base_image_clean_docker':
            return f"./fabrinetes gen-image --file {config_file} --base-image --clean --docker --no-ask"
        elif test_type == 'base_image_clean_tarball':
            return f"./fabrinetes gen-image --file {config_file} --base-image --clean --tarball --no-ask"
        else:
            return f"./fabrinetes gen-image --file {config_file}"
    elif command == "gen-image-base":
        return f"./fabrinetes gen-image --file {config_file} --base-image"
    elif command == "clean-image":
        container_info = get_container_info(config_file)
        image_name = container_info.image_full
        return f"./fabrinetes clean-image {image_name}"
    elif command == "kill":
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        return f"./fabrinetes kill {container_name}"
    elif command == "commit":
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        return f"./fabrinetes commit --container-name {container_name}"
    elif command == "exec":
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        return f"./fabrinetes exec --container-name {container_name} --command 'echo test'"
    elif command == "shell":
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        return f"./fabrinetes shell --container-name {container_name}"
    elif command == "pkg":
        container_info = get_container_info(config_file)
        container_name = container_info.run_name
        return f"./fabrinetes pkg --container-name {container_name}"
    elif command == "clean":
        # Generate clean command based on test parameters
        clean_target = test_params.get('clean_target', 'all') if test_params else 'all'
        if clean_target == 'base_image':
            return f"./fabrinetes clean {config_file} --base-image"
        elif clean_target == 'image':
            return f"./fabrinetes clean {config_file} --image"
        elif clean_target == 'container':
            return f"./fabrinetes clean {config_file} --container"
        elif clean_target == 'dangling':
            return f"./fabrinetes clean {config_file} --dangling"
        elif clean_target == 'all':
            return f"./fabrinetes clean {config_file} --all"
        else:
            return f"./fabrinetes clean {config_file} --all"
    else:
        return f"./fabrinetes {command} --file {config_file} --no-ask"

def validate_command_result(ctx, result, container_name, command, expected_results):
    """Validate command result using the new command-specific validation system"""
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from command_validators import validate_command_result as validate_cmd_result
    
    return validate_cmd_result(ctx, result, container_name, command, expected_results)
def accumulate_test_steps(steps):

    if not steps:
        return "No steps executed"

    result_lines = []
    for i, (step_name, step_result) in enumerate(steps, 0):
        result_lines.append(f"{i}: {step_name} = {step_result}")

    return "\n".join(result_lines)

def get_expected_result_str(step_number, expected_results):

    if step_number in expected_results:
        return expected_results[step_number]
    return "PASS"

def gen_error_table_str(results, expected):

    error_lines = []
    for step_num, (step_name, actual_result) in enumerate(results):
        expected_result = get_expected_result_str(step_num, expected)
        if actual_result != expected_result:
            error_lines.append(f"Step {step_num}: Expected '{expected_result}', got '{actual_result}'")

    return "\n".join(error_lines) if error_lines else ""

def gen_results_table_str(results):

    result_lines = []
    for step_num, (step_name, step_result) in enumerate(results):
        result_lines.append(f"{step_num}: {step_name} = {step_result}")
    return "\n".join(result_lines)

def gen_expected_table_str(expected):

    if not expected:
        return "All steps: PASS"

    expected_lines = []
    for step_num, expected_result in expected.items():
        expected_lines.append(f"Step {step_num}: {expected_result}")

    return "\n".join(expected_lines)


   

RUN_TEST_VECTORS = [
    {'name': 'run_tests', 'description': 'All run command permutations', 'command': 'run'}
]

CLEAN_IMAGE_TEST_VECTORS = [
    {'name': 'clean_image_tests', 'description': 'All clean-image command permutations', 'command': 'clean-image'}
]

KILL_TEST_VECTORS = [
    {'name': 'kill_tests', 'description': 'All kill command permutations', 'command': 'kill'}
]

def display_test_results(results, command):
    if not results:
        print("No test results to display")
        return
    
    print(f"\nTest Results for {command.upper()} Command")
    print("=" * 100)
    
    headers = ["#", "Test", "Description", "Steps", "Expected", "Pass", "Error Details"]
    
    table_data = []
    for i, result in enumerate(results, 1):
        test_name = result['name']
        description = result['description']
        steps = result['steps']
        expected = result['expected']
        pass_status = "YES" if result['success'] else "NO"
        error_details = result['error'] if not result['success'] else ""
        
        table_data.append([
            i,
            test_name,
            description,
            steps,
            expected,
            pass_status,
            error_details
        ])
    
    print(tabulate(table_data, headers=headers, tablefmt="fancy_grid", stralign="left"))


if __name__ == "__main__":
    import sys
    from invoke import Context
    
    if len(sys.argv) < 3:
        print("Usage: python3 test.py <config_file> <command> [--test-number <number>]")
        print("Example: python3 test.py containers/fabrinetes-dev-testing/config.toml gen-image")
        print("Available commands: run, gen-image, gen-image-base, clean-image, kill, commit, exec, shell, pkg, clean")
        sys.exit(1)
    
    config_file = sys.argv[1]
    command = sys.argv[2]
    test_number = None
    
    # Parse test number if provided
    if len(sys.argv) > 3 and sys.argv[3] == "--test-number":
        if len(sys.argv) > 4:
            test_number = int(sys.argv[4])
        else:
            print("Error: --test-number requires a number")
            sys.exit(1)
    
    # Run the test
    ctx = Context()
    if test_number:
        run_single_test_by_number(ctx, config_file, command, test_number)
    else:
        all_passed, results = run_generic_test(ctx, config_file, command)
        sys.exit(0 if all_passed else 1)
