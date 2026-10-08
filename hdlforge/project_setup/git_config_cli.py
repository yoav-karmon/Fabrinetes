"""Point checkout-local Git SSH at the current host/user's repository config."""
import argparse
import getpass
import json
from pathlib import Path
import shlex
import socket
import subprocess

from environment_defaults import resolve


def git(root, *args):
    return subprocess.run(['git', '-C', str(root), *args], text=True,
                          capture_output=True, check=False)


def update(root: Path, action: str, host: str, user: str) -> int:
    """Resolve the repository setting before inspecting or changing local Git."""
    projects = list(root.glob('*.hdlforge.json'))
    if len(projects) != 1:
        raise ValueError('Repository root must contain exactly one *.hdlforge.json')
    data = json.loads(projects[0].read_text())
    value = resolve(data, host, user)[0].get('ssh_config_file')
    if not isinstance(value, str) or not value:
        raise ValueError(f'Missing settings.env.{host}.{user}.ssh_config_file')
    config = (root / value).resolve()
    if not config.is_relative_to(root.resolve()) or not config.is_file():
        raise ValueError(f'SSH config must be an existing file inside the repository: {config}')
    expected = shlex.join(['ssh', '-F', str(config)])
    current = git(root, 'config', '--local', '--get-all', 'core.sshCommand')
    if current.returncode not in (0, 1):
        raise ValueError(current.stderr.strip())
    matches = current.stdout.splitlines() == [expected]
    print(f'Local account: {host}/{user}\nSSH config: {config}')
    print(f'Current core.sshCommand: {current.stdout.strip() or "(unset)"}')
    print(f'Expected core.sshCommand: {expected}')
    if action == 'verify':
        print('PASS' if matches else 'MISMATCH: run hdlforge git-config.update')
        return 0 if matches else 1
    if action == 'update-dry-run':
        print('DRY RUN: ' + ('already matches' if matches else 'would update local Git config'))
        return 0
    if not matches:
        result = git(root, 'config', '--local', '--replace-all', 'core.sshCommand', expected)
        if result.returncode:
            raise ValueError(result.stderr.strip())
    print('PASS: checkout-local Git SSH configuration updated')
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['verify', 'update', 'update-dry-run'])
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    result = git(Path.cwd(), 'rev-parse', '--show-toplevel')
    if result.returncode:
        parser.error(result.stderr.strip())
    try:
        return update(Path(result.stdout.strip()),
                      'update-dry-run' if args.dry_run else args.action,
                      socket.gethostname().split('.')[0], getpass.getuser())
    except (OSError, ValueError) as error:
        parser.exit(1, f'ERROR: {error}\n')


if __name__ == '__main__':
    raise SystemExit(main())
