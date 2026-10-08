"""Inspect, import, merge and verify repository-owned environment settings."""

import argparse
import difflib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

import env_settings_model as model
import env_settings_ssh as ssh
import env_verification as python_settings
import environment_defaults
from hdlforge_json import unique_object, write_update


ACTIONS = ('show', 'import', 'import-dry-run', 'merge', 'merge-dry-run',
           'print-as-json', 'lint-user-settings', 'list-json', 'verify')


def replace_text(path: Path, original: str | None, content: str) -> None:
    """Publish a text replacement atomically, checking concurrent edits first."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, prefix='.hdlforge-settings-', delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        temporary.chmod(path.stat().st_mode if path.exists() else 0o600)
        if (path.read_text() if path.exists() else None) != original:
            raise ValueError(f'{path} changed during update; retry')
        os.replace(temporary, path)
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)


def changes(before: str, after: str, name: str) -> str:
    """Use identical diff generation for previews and executed changes."""
    return ''.join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                        fromfile=name, tofile=name + ' (proposed)'))


def update(args: argparse.Namespace, data: dict, original: str) -> dict:
    """Prepare and validate all changes before writing the selected files."""
    incoming = model.capture(args.scope, args.input)
    merge = args.action.startswith('merge')
    dry_run = args.dry_run or args.action.endswith('-dry-run')
    ssh_path, old_content, new_content = None, None, None
    if args.scope == 'ssh-config':
        value = model.entry(data, args.server, args.user).get('ssh_config_file')
        value = value or ('environment/ssh-configs/default/config' if args.server == 'default'
                          else f'environment/ssh-configs/{args.server}/{args.user}/config')
        ssh_path = ssh.config_path(args.repository, value)
        old_content = ssh_path.read_text() if ssh_path.exists() else None
        baseline = old_content or ''
        inherited = environment_defaults.resolve(data, args.server, args.user)[0].get('ssh_config_file')
        if merge and old_content is None and inherited:
            baseline = ssh.config_path(args.repository, inherited).read_text()
        new_content = ssh.merge(baseline, incoming, args.on_collision) if merge else incoming
        incoming = str(ssh_path.relative_to(args.repository.parent))
    proposed = model.propose(data, args.scope, args.server, args.user, incoming, merge, args.on_collision)
    json_text = json.dumps(proposed, indent=2) + '\n'
    json_changed = proposed != data
    ssh_changed = ssh_path is not None and old_content != new_content
    diff = changes(original, json_text, str(args.repository)) if json_changed else ''
    if ssh_changed:
        diff += changes(old_content or '', new_content, str(ssh_path))
    if not dry_run:
        if args.repository.read_text() != original:
            raise ValueError('Repository JSON changed during update; retry')
        if ssh_changed:
            replace_text(ssh_path, old_content, new_content)
        try:
            if json_changed:
                write_update(args.repository, original, proposed)
        except Exception:
            # If publishing the JSON fails, restore only the SSH edit we made.
            if ssh_changed and ssh_path.read_text() == new_content:
                if old_content is None:
                    ssh_path.unlink()
                else:
                    replace_text(ssh_path, new_content, old_content)
            raise
    return dict(status='DRY RUN' if dry_run else 'UPDATED' if diff else 'UNCHANGED',
                changed=bool(diff), diff=diff, scope=args.scope, server=args.server, user=args.user,
                repository=str(args.repository))


def show_scope(args: argparse.Namespace, data: dict, scope: str) -> dict:
    """Show configured values separately from the active interpreter environment."""
    report = model.selected(data, args.repository, scope, args.server, args.user)
    report.update(scope=scope, server=args.server, user=args.user, repository=str(args.repository))
    local = (args.server, args.user) == (args.active_server, args.active_user)
    if local:
        if scope in ('path', 'pythonpath'):
            report['active'] = os.environ.get('PATH' if scope == 'path' else 'PYTHONPATH', '').split(os.pathsep)
            if report['active'] == ['']:
                report['active'] = []
        elif scope == 'python':
            report['active'] = dict(interpreter=sys.executable, version=platform.python_version())
    if scope == 'ssh-config' and report['effective']:
        path = ssh.config_path(args.repository, report['effective'])
        report['file'] = str(path)
        report['exists'] = path.is_file()
        if path.is_file():
            report['content'] = path.read_text()
    return report


def check(args: argparse.Namespace, data: dict) -> dict:
    """Lint configured structure or verify the selected active local environment."""
    report = show_scope(args, data, args.scope)
    if args.action == 'verify' and (args.server, args.user) != (args.active_server, args.active_user):
        raise ValueError('Verification uses the active local server/user; use lint-user-settings for other entries')
    rows = []
    if args.scope == 'python' and not {'version', 'packages'} <= report['effective'].keys():
        raise ValueError('Python settings require both version and packages after resolving defaults')
    if args.scope == 'ssh-config':
        if not report.get('exists'):
            raise ValueError('Configured SSH file is missing or ssh_config_file is unset')
        ssh.blocks(report['content'])
        rows = [dict(name=report['file'], status='PASS', detail='Offline structural check; no SSH directives executed')]
    elif args.action == 'verify':
        if args.scope == 'python':
            rows = python_settings.verify(report['effective'], platform.python_version())
        else:
            rows = model.verify_paths(report['effective'], args.repository, args.scope)
    report.update(status='PASS' if all(row['status'] == 'PASS' for row in rows) else 'FAIL', checks=rows)
    return report


def run(args: argparse.Namespace) -> dict:
    """Execute exactly one settings action against the repository root JSON."""
    original = args.repository.read_text()
    data = json.loads(original, object_pairs_hook=unique_object)
    if args.action in ('import', 'import-dry-run', 'merge', 'merge-dry-run'):
        return update(args, data, original)
    if args.action == 'list-json':
        scopes = model.SCOPES if args.scope == 'all' else (args.scope,)
        return {scope: model.inventory(data, scope) for scope in scopes}
    if args.scope == 'all':
        report = dict(server=args.server, user=args.user, repository=str(args.repository),
                      project=os.environ.get('HDLFORGE_ENV_PROJECT_JSON'), settings={})
        for scope in model.SCOPES:
            try:
                report['settings'][scope] = show_scope(args, data, scope)
            except ValueError as error:
                report['settings'][scope] = dict(status='UNCONFIGURED', error=str(error))
        report['repository_entry'] = model.entry(data, args.server, args.user)
        report['effective_environment'], report['sources'] = environment_defaults.resolve(data, args.server, args.user)
        project = os.environ.get('HDLFORGE_ENV_PROJECT_JSON')
        if project and Path(project) != args.repository:
            report['project_entry'] = model.entry(json.loads(Path(project).read_text()), args.server, args.user)
        return report
    if args.action in ('lint-user-settings', 'verify'):
        return check(args, data)
    return show_scope(args, data, args.scope)


def print_report(report: dict, as_json: bool) -> None:
    """Print complete JSON or a readable report with source and result details."""
    if as_json:
        print(json.dumps(report, indent=2))
        return
    if 'diff' in report:
        print(f"{report['status']}: {report['scope']} for {report['server']}:{report['user']}")
        print(report['diff'] or 'No changes.', end='\n')
        return
    print(f"Environment settings: {report.get('server')}:{report.get('user')}")
    print(f"Repository JSON: {report.get('repository')}")
    if 'checks' in report:
        for row in report['checks']:
            details = ', '.join(f'{key}={value}' for key, value in row.items() if key not in ('name', 'status'))
            print(f"{row['status']:4} {row['name']}: {details}")
        print(f"Result: {report['status']} ({len(report['checks'])} checks)")
    else:
        for name, value in report.get('settings', {report.get('scope', 'settings'): report}).items():
            print(f'\n{name}:')
            print(json.dumps(value, indent=2))
        for key in ('repository_entry', 'effective_environment', 'sources', 'project_entry'):
            if key in report:
                print(f'\n{key}:')
                print(json.dumps(report[key], indent=2))


def main(argv: list[str] | None = None) -> int:
    """Expose a uniform CLI for all four environment-setting groups."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('scope', choices=['all', *model.SCOPES])
    parser.add_argument('action', choices=ACTIONS)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--active-server', required=True)
    parser.add_argument('--active-user', required=True)
    parser.add_argument('--launch-dir', type=Path, default=Path.cwd())
    parser.add_argument('--server')
    parser.add_argument('--user')
    parser.add_argument('--input', type=Path)
    parser.add_argument('--on-collision', choices=['error', 'existing', 'incoming'], default='error')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args(argv)
    args.repository = args.repository.resolve()
    if args.input and not args.input.is_absolute():
        args.input = args.launch_dir / args.input
    args.server = args.server or args.active_server
    args.user = args.user or args.active_user
    as_json = args.json or args.action in ('print-as-json', 'list-json')
    try:
        if any(not name or name.startswith('#') or '/' in name or '\x00' in name or name in ('.', '..') for name in (args.server, args.user)):
            raise ValueError('Server/user must be literal names, not paths')
        if args.server == python_settings.SETTINGS_KEY:
            raise ValueError('python_settings is reserved metadata, not a server')
        report = run(args)
        print_report(report, as_json)
        return 1 if report.get('status') == 'FAIL' else 0
    except (OSError, ValueError, TypeError, AttributeError, subprocess.TimeoutExpired) as error:
        if as_json:
            print(json.dumps(dict(status='ERROR', error=str(error))))
        else:
            print(f'ERROR: {error}', file=sys.stderr)
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
