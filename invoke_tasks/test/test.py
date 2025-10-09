
import os
import time
import glob
from invoke import task
from helper_functions.config.name_generator import get_image_name, get_run_name, get_tarball_path, get_tarball_directory
from helper_functions.image_management import check_image_exists, save_image_to_tarball
from tabulate import tabulate


@task
def test(ctx, command=None, test_number=None):

    from tasks import show_command_help, COMMAND_HELP

    if not command:
        show_command_help('test', COMMAND_HELP['test'])
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
        results = run_generic_test(ctx, config_file, command=command)
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

def setup_gen_image_test_state(ctx, config_file, test_params):
    """Setup test state for gen-image tests"""
    print(f"      Setting up gen-image test state...", flush=True)
    
    test_type = test_params.get('test_type', 'regular_image')
    
    if test_type == 'base_image':
        setup_base_image_test_state(ctx, config_file, test_params)
    else:
        setup_regular_image_test_state(ctx, config_file, test_params)
    
    print(f"      Gen-image test state setup complete", flush=True)

def setup_base_image_test_state(ctx, config_file, test_params):
    """Setup test state for base image tests"""
    import toml
    
    # Load config to get base image name
    config = toml.load(config_file)
    base_image_name = config['config']['base_image']
    
    dockerfile_exists = test_params.get('dockerfile_exists', True)
    base_image_in_repo = test_params.get('base_image_in_repo', True)
    base_tarball_exists = test_params.get('base_tarball_exists', True)
    
    config_dir = os.path.dirname(config_file)
    dockerfile_path = os.path.join(config_dir, "Dockerfile")
    base_tarball_path = os.path.join(config_dir, "images", f"{base_image_name.replace(':', '.')}.tar.gz")
    
    # Setup Dockerfile state
    if dockerfile_exists:
        if not os.path.exists(dockerfile_path):
            # Copy Dockerfile from skeleton
            skeleton_dockerfile = "base_images/fabrinetes-skeleton/Dockerfile"
            if os.path.exists(skeleton_dockerfile):
                ctx.run(f"cp {skeleton_dockerfile} {dockerfile_path}", hide=True)
    else:
        # For test scenarios that need no Dockerfile, create an empty one instead of removing it
        # This ensures the restore function can always find the file
        if os.path.exists(dockerfile_path):
            ctx.run(f"mv {dockerfile_path} {dockerfile_path}.backup", hide=True, warn=True)
        # Create empty Dockerfile
        ctx.run(f"touch {dockerfile_path}", hide=True)
    
    # Setup base image state
    if base_image_in_repo:
        if not check_image_exists(ctx, base_image_name):
            print(f"Building base image {base_image_name}...")
            # First ensure Dockerfile exists for building
            if not os.path.exists(dockerfile_path):
                skeleton_dockerfile = "base_images/fabrinetes-skeleton/Dockerfile"
                if os.path.exists(skeleton_dockerfile):
                    ctx.run(f"cp {skeleton_dockerfile} {dockerfile_path}", hide=True)
            # Build the base image
            ctx.run(f"./fabrinetes gen-image {config_file} --base-image", hide=True, warn=True)
            # Remove Dockerfile if test scenario requires no Dockerfile
            if not dockerfile_exists and os.path.exists(dockerfile_path):
                ctx.run(f"mv {dockerfile_path} {dockerfile_path}.backup", hide=True, warn=True)
    else:
        ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
    
    # Setup base tarball state
    if base_tarball_exists:
        if not os.path.exists(base_tarball_path):
            # Create tarball from existing image
            if check_image_exists(ctx, base_image_name):
                os.makedirs(os.path.dirname(base_tarball_path), exist_ok=True)
                ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
    else:
        if os.path.exists(base_tarball_path):
            ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)

def setup_regular_image_test_state(ctx, config_file, test_params):
    """Setup test state for regular image tests"""
    import toml
    
    # Handle case where config file is empty or malformed
    try:
        config = toml.load(config_file)
        target_image_name = config['config']['image_name']
        base_image_name = config['config']['base_image']
    except Exception as e:
        # Use default values for testing when config is empty
        print(f"Warning: Could not read config file {config_file}: {e}")
        target_image_name = "fabrinetes-dev-testing:latest"
        base_image_name = "fabrinetes-skeleton:latest"
    
    target_image_in_repo = test_params.get('target_image_in_repo', True)
    target_tarball_exists = test_params.get('target_tarball_exists', True)
    base_image_in_repo = test_params.get('base_image_in_repo', True)
    base_tarball_exists = test_params.get('base_tarball_exists', True)
    
    config_dir = os.path.dirname(config_file)
    target_tarball_path = os.path.join(config_dir, "images", f"{target_image_name.replace(':', '.')}.tar.gz")
    base_tarball_path = os.path.join(config_dir, "images", f"{base_image_name.replace(':', '.')}.tar.gz")
    
    # Setup base image state
    if base_image_in_repo:
        if not check_image_exists(ctx, base_image_name):
            print(f"Building base image {base_image_name}...")
            ctx.run(f"./fabrinetes gen-image {config_file} --base-image", hide=True, warn=True)
    else:
        ctx.run(f"docker rmi -f {base_image_name}", hide=True, warn=True)
    
    # Setup base tarball state
    if base_tarball_exists:
        if not os.path.exists(base_tarball_path):
            # Create tarball from existing image
            if check_image_exists(ctx, base_image_name):
                os.makedirs(os.path.dirname(base_tarball_path), exist_ok=True)
                ctx.run(f"docker save {base_image_name} | gzip > {base_tarball_path}", hide=True)
    else:
        if os.path.exists(base_tarball_path):
            ctx.run(f"mv {base_tarball_path} {base_tarball_path}.backup", hide=True, warn=True)
    
    # Setup target image state
    if target_image_in_repo:
        if not check_image_exists(ctx, target_image_name):
            print(f"Building target image {target_image_name}...")
            # Ensure base image exists before building target image
            if not check_image_exists(ctx, base_image_name):
                print(f"Building base image {base_image_name} first...")
                dockerfile_path = os.path.join(config_dir, "Dockerfile")
                if not os.path.exists(dockerfile_path):
                    skeleton_dockerfile = "base_images/fabrinetes-skeleton/Dockerfile"
                    if os.path.exists(skeleton_dockerfile):
                        ctx.run(f"cp {skeleton_dockerfile} {dockerfile_path}", hide=True)
                ctx.run(f"./fabrinetes gen-image {config_file} --base-image", hide=True, warn=True)
            ctx.run(f"./fabrinetes gen-image {config_file}", hide=True, warn=True)
    else:
        ctx.run(f"docker rmi -f {target_image_name}", hide=True, warn=True)
    
    # Setup target tarball state
    if target_tarball_exists:
        if not os.path.exists(target_tarball_path):
            # Create tarball from existing image
            if check_image_exists(ctx, target_image_name):
                os.makedirs(os.path.dirname(target_tarball_path), exist_ok=True)
                ctx.run(f"docker save {target_image_name} | gzip > {target_tarball_path}", hide=True)
    else:
        if os.path.exists(target_tarball_path):
            ctx.run(f"mv {target_tarball_path} {target_tarball_path}.backup", hide=True, warn=True)

def setup_test_state(ctx, config_file, container_name, image_name,
                    image_in_repo=True, tarball_exists=True,
                    container_state="none"):

    print(f"      Setting up test state...", flush=True)

    def get_current_container_state():
        running_check = ctx.run(f"docker ps --filter name=^{container_name}$ --format '{{{{.Names}}}}'", hide=True, warn=True)
        stopped_check = ctx.run(f"docker ps -a --filter name=^{container_name}$ --format '{{{{.Names}}}}'", hide=True, warn=True)
        
        if running_check.stdout.strip():
            return "running"
        elif stopped_check.stdout.strip():
            return "stopped"
        else:
            return "none"

    def ensure_image_state():
        if image_in_repo:
            if not check_image_exists(ctx, "fabrinetes-skeleton:latest"):
                print("Building skeleton image first...")
                ctx.run(f"./fabrinetes gen-image skeleton --skeleton", hide=True, warn=True)

            if image_name != "fabrinetes-skeleton:latest":
                print(f"Building {image_name} image...")
                ctx.run(f"./fabrinetes gen-image {image_name}", hide=True, warn=True)
        else:
            ctx.run(f"docker rmi -f {image_name}", hide=True, warn=True)

    def ensure_tarball_state():
        tarball_path = get_tarball_path(config_file)
        tarball_directory = get_tarball_directory(config_file)
        
        if tarball_exists:
            ctx.run(f"mkdir -p {tarball_directory}", hide=True, warn=True)
            if not os.path.exists(tarball_path):
                if image_in_repo:
                    ctx.run(f"./fabrinetes gen-image {image_name}", hide=True, warn=True)
                else:
                    backup_tarball = f"base_images/fabrinetes-skeleton/images/fabrinetes-skeleton-test-commit.tar.gz"
                    if os.path.exists(backup_tarball):
                        ctx.run(f"docker load -i {backup_tarball}", hide=True, warn=True)
                        ctx.run(f"docker tag fabrinetes-skeleton:test-commit fabrinetes-skeleton:latest", hide=True, warn=True)
                        ctx.run(f"docker save fabrinetes-skeleton:latest | gzip > {tarball_path}", hide=True, warn=True)
                        ctx.run(f"docker rmi -f fabrinetes-skeleton:test-commit fabrinetes-skeleton:latest", hide=True, warn=True)
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
                        ctx.run(f"./fabrinetes gen-image {image_name}", hide=True, warn=True)
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
                        ctx.run(f"./fabrinetes gen-image {image_name}", hide=True, warn=True)
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
    """Restore all backup files created during test setup"""
    
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

    container_name = get_run_name(config_file)
    image_info = get_image_name(config_file)
    image_name = image_info['full']

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

    return results

def run_single_test_by_number(ctx, config_file, command, test_number):
    try:
        container_name = get_run_name(config_file)
        image_info = get_image_name(config_file)
        image_name = image_info['full']
        
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
            {'image_in_repo': True, 'tarball_exists': True, 'config_exists': True, 'container_state': 'none', 'description': 'Fresh run - should PASS'},
            {'image_in_repo': True, 'tarball_exists': True, 'config_exists': True, 'container_state': 'running', 'description': 'Container already running - should FAIL (duplicate)'},
            {'image_in_repo': True, 'tarball_exists': True, 'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should restart'},
            {'image_in_repo': True, 'tarball_exists': False, 'config_exists': True, 'container_state': 'none', 'description': 'No tarball - should PASS'},
            {'image_in_repo': False, 'tarball_exists': True, 'config_exists': True, 'container_state': 'none', 'description': 'Restore from tarball - should PASS'},
            {'image_in_repo': False, 'tarball_exists': False, 'config_exists': True, 'container_state': 'none', 'description': 'No image, no restore - should FAIL'},
        ]

    elif command == "gen-image":
        return [
            # Base image tests
            {'test_type': 'base_image', 'dockerfile_exists': True, 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base image: Dockerfile exists, base image in repo, tarball exists - should PASS (use existing)'},
            {'test_type': 'base_image', 'dockerfile_exists': True, 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Base image: Dockerfile exists, base image not in repo, tarball exists - should PASS (restore)'},
            {'test_type': 'base_image', 'dockerfile_exists': True, 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Base image: Dockerfile exists, base image not in repo, no tarball - should PASS (build from Dockerfile)'},
            {'test_type': 'base_image', 'dockerfile_exists': False, 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Base image: No Dockerfile, base image in repo, tarball exists - should PASS (use existing)'},
            {'test_type': 'base_image', 'dockerfile_exists': False, 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Base image: No Dockerfile, base image not in repo, tarball exists - should PASS (restore)'},
            {'test_type': 'base_image', 'dockerfile_exists': False, 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Base image: No Dockerfile, base image not in repo, no tarball - should FAIL'},
            
            # Regular image tests
            {'test_type': 'regular_image', 'target_image_in_repo': True, 'target_tarball_exists': True, 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Regular: Target image in repo, target tarball exists, base image in repo - should PASS (use existing)'},
            {'test_type': 'regular_image', 'target_image_in_repo': False, 'target_tarball_exists': True, 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Regular: Target image not in repo, target tarball exists, base image in repo - should PASS (restore target)'},
            {'test_type': 'regular_image', 'target_image_in_repo': False, 'target_tarball_exists': False, 'base_image_in_repo': True, 'base_tarball_exists': True, 'description': 'Regular: Target image not in repo, no target tarball, base image in repo - should PASS (build from base)'},
            {'test_type': 'regular_image', 'target_image_in_repo': False, 'target_tarball_exists': False, 'base_image_in_repo': False, 'base_tarball_exists': True, 'description': 'Regular: Target image not in repo, no target tarball, base image not in repo, base tarball exists - should PASS (restore base, then build)'},
            {'test_type': 'regular_image', 'target_image_in_repo': False, 'target_tarball_exists': False, 'base_image_in_repo': False, 'base_tarball_exists': False, 'description': 'Regular: Target image not in repo, no target tarball, base image not in repo, no base tarball - should FAIL (no base image source)'},
        ]

    elif command == "clean-image":
        return [
            {'image_in_repo': True, 'tarball_exists': True, 'config_exists': True, 'description': 'Image exists - should PASS (clean)'},
            {'image_in_repo': True, 'tarball_exists': False, 'config_exists': True, 'description': 'Image exists, no tarball - should PASS (clean)'},
            {'image_in_repo': False, 'tarball_exists': True, 'config_exists': True, 'description': 'No image, tarball exists - should PASS (nothing to clean)'},
            {'image_in_repo': False, 'tarball_exists': False, 'config_exists': True, 'description': 'No image - should PASS (nothing to clean)'},
        ]

    elif command == "kill":
        return [
            {'config_exists': True, 'container_state': 'running', 'description': 'Container running - should PASS (kill)'},
            {'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should PASS (remove)'},
            {'config_exists': True, 'container_state': 'none', 'description': 'No container - should PASS (nothing to kill)'},
        ]

    elif command == "commit":
        return [
            {'config_exists': True, 'container_state': 'running', 'description': 'Container running - should PASS (commit)'},
            {'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'config_exists': True, 'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "exec":
        return [
            {'config_exists': True, 'container_state': 'running', 'description': 'Container running - should PASS (exec)'},
            {'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'config_exists': True, 'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "shell":
        return [
            {'config_exists': True, 'container_state': 'running', 'description': 'Container running - should PASS (shell)'},
            {'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'config_exists': True, 'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    elif command == "pkg":
        return [
            {'config_exists': True, 'container_state': 'running', 'description': 'Container running - should PASS (pkg)'},
            {'config_exists': True, 'container_state': 'stopped', 'description': 'Container stopped - should FAIL (not running)'},
            {'config_exists': True, 'container_state': 'none', 'description': 'No container - should FAIL'},
        ]

    else:
        return [
            {'config_exists': True, 'description': 'Config exists - should PASS'},
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
        if command == "gen-image":
            setup_gen_image_test_state(ctx, config_file, params)
        else:
            setup_test_state(ctx, config_file, container_name, image_name, **setup_params)
        steps.append(("Prepare test", "PASS"))
        print(f"      Step 0: Environment prepared", flush=True)
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
        
        restore_test_state(ctx, config_file)
        return False, f"Preparation failed: {str(e)}", gen_results_table_str(steps), gen_expected_table_str(expected_results), gen_results_table_str(steps)

    print(f"      Step 1: Running {command} command...", flush=True)

    command_to_run = generate_command(command, config_file, params)

    result = ctx.run(command_to_run, hide=True, warn=False)

    step1_result = validate_command_result(ctx, result, container_name, expected_results)
    steps.append((f"Run {command}", step1_result))

    if step1_result == "PASS":
        print(f"      Step 1: Command succeeded as expected", flush=True)
    else:
        print(f"      Step 1: Command failed as expected", flush=True)

    restore_test_state(ctx, config_file)

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

    elif command in ["gen-image", "clean-image"]:
        # Handle gen-image specific test cases
        if command == "gen-image":
            test_type = params.get('test_type', 'regular_image')
            
            # Base image tests
            if test_type == 'base_image':
                dockerfile_exists = params.get('dockerfile_exists', True)
                base_image_in_repo = params.get('base_image_in_repo', True)
                base_tarball_exists = params.get('base_tarball_exists', True)
                
                # Should FAIL if no Dockerfile AND no base image AND no tarball
                if not dockerfile_exists and not base_image_in_repo and not base_tarball_exists:
                    return {1: "FAIL"}
                # Should PASS in all other cases
                else:
                    return {}
            
            # Regular image tests
            else:
                target_image_in_repo = params.get('target_image_in_repo', True)
                target_tarball_exists = params.get('target_tarball_exists', True)
                base_image_in_repo = params.get('base_image_in_repo', True)
                base_tarball_exists = params.get('base_tarball_exists', True)
                
                # Should FAIL if no target image AND no target tarball AND no base image AND no base tarball
                if not target_image_in_repo and not target_tarball_exists and not base_image_in_repo and not base_tarball_exists:
                    return {1: "FAIL"}
                # Should PASS in all other cases
                else:
                    return {}
        
        # For clean-image, all steps should PASS
        return {}

    elif command == "kill":
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
        if test_params and test_params.get('test_type') == 'base_image':
            return f"./fabrinetes gen-image {config_file} --base-image"
        else:
            return f"./fabrinetes gen-image {config_file}"
    elif command == "clean-image":
        image_info = get_image_name(config_file)
        image_name = image_info['full']
        return f"./fabrinetes clean-image {image_name}"
    elif command == "kill":
        container_name = get_run_name(config_file)
        return f"./fabrinetes kill {container_name}"
    elif command == "commit":
        container_name = get_run_name(config_file)
        return f"./fabrinetes commit --container-name {container_name}"
    elif command == "exec":
        container_name = get_run_name(config_file)
        return f"./fabrinetes exec --container-name {container_name} --command 'echo test'"
    elif command == "shell":
        container_name = get_run_name(config_file)
        return f"./fabrinetes shell --container-name {container_name}"
    elif command == "pkg":
        container_name = get_run_name(config_file)
        return f"./fabrinetes pkg --container-name {container_name}"
    else:
        return f"./fabrinetes {command} --file {config_file} --no-ask"

def validate_command_result(ctx, result, container_name, expected_results):

    if expected_results.get(1) == "FAIL":
        if "not available and restore failed" in result.stdout:
            return "FAIL"
        elif "TomlDecodeError" in result.stdout or "KeyError" in result.stdout or "TomlDecodeError" in result.stderr or "KeyError" in result.stderr:
            return "FAIL"
        elif "already running" in result.stdout or "already exists" in result.stdout:
            return "FAIL"
        elif "not running" in result.stdout or "not found" in result.stdout:
            return "FAIL"
        elif "Error:" in result.stdout and ("not running" in result.stdout or "not found" in result.stdout):
            return "FAIL"
        else:
            return "PASS"
    else:
        if result.ok and ("started successfully" in result.stdout or "restarted successfully" in result.stdout):
            running_check = ctx.run(f"docker ps --filter name={container_name} --format '{{{{.Names}}}}'", hide=True)
            return "PASS" if running_check.stdout.strip() else "FAIL"
        elif result.ok and ("Successfully" in result.stdout or "successfully" in result.stdout):
            return "PASS"
        elif result.ok and "already exists locally" in result.stdout:
            return "PASS"
        elif result.ok and "echo test" in result.stdout:
            return "PASS"
        else:
            return "FAIL"
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


   

BUILD_TEST_VECTORS = [
    {'name': 'build_tests', 'description': 'All build command permutations', 'command': 'build'}
]

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


