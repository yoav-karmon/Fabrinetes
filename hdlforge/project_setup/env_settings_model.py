"""Repository environment selection, captures and non-destructive merges."""

from copy import deepcopy
from importlib import metadata
import json
import os
from pathlib import Path
import platform
import re
import subprocess

import env_settings_ssh as ssh
import env_settings_system as system
import env_settings_vscode as vscode
import env_verification as python_settings
import environment_defaults


SCOPES = ('os', 'path', 'python', 'pythonpath', 'ssh-config', 'system-packages', 'vscode')


def entry(data: dict, server: str, user: str) -> dict:
    """Read literal server/user keys, including dotted usernames."""
    return environment_defaults.entry(data, server, user)


def path_list(value: list) -> list[str]:
    """Require explicit, nonempty paths; remove duplicates without reordering."""
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() or '\n' in item or '\x00' in item for item in value):
        raise ValueError('Paths must be a JSON array of nonempty strings')
    return list(dict.fromkeys(value))


def repository_paths(repository: Path, server: str, user: str, scope: str) -> list[str]:
    """Reuse startup's import resolver, including dotted keys and cycle checks."""
    script = Path(__file__).with_name('hdlforge_environment.bash')
    result = subprocess.run(['bash', '-c', 'source "$1"; HDLFORGE_JQ="$2"; hdlforge_read_repository_environment "$3" "$4" "$5"',
                             'settings', str(script), os.environ.get('HDLFORGE_JQ', 'jq'), str(repository), server, user],
                            text=True, capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError(result.stderr.strip() or 'Cannot resolve repository path imports')
    paths = []
    for layer in json.loads(result.stdout):
        paths.extend(path_list(layer.get(scope, [])))
    return list(dict.fromkeys(paths))


def selected(data: dict, repository: Path, scope: str, server: str, user: str) -> dict:
    """Return configured and resolved settings with their source locations."""
    environment, sources = environment_defaults.resolve(data, server, user)
    configured = entry(data, server, user)
    if scope == 'python':
        effective, sources = python_settings.resolve_settings(data, server, user)
        return dict(configured=configured.get('python_settings', {}), effective=effective, sources=sources)
    if scope == 'os':
        effective = environment.get('os_settings', {})
        system.validate_os(effective, 'os_settings')
        return dict(configured=configured.get('os_settings', {}), effective=effective,
                    sources={key.removeprefix('os_settings.'): value for key, value in sources.items()
                             if key.startswith('os_settings.')})
    if scope == 'system-packages':
        effective = system.validate_packages(environment.get('system_packages', []), 'system_packages')
        return dict(configured=configured.get('system_packages', []), effective=effective,
                    sources={'system_packages': sources.get('system_packages')})
    if scope == 'vscode':
        required = entry(data, 'repo-requirement', '').get('vscode', {})
        host = configured.get('vscode', {})
        vscode.validate(required, 'settings.env.repo-requirement.vscode')
        vscode.validate(host, f'settings.env.{server}.{user}.vscode')
        return dict(configured=host,
                    effective=dict(extensions=host.get('extensions', []), settings=required.get('settings', {})),
                    sources=dict(extensions=f'settings.env.{server}.{user}.vscode.extensions',
                                 settings='settings.env.repo-requirement.vscode.settings'))
    if scope in ('path', 'pythonpath'):
        local = path_list(configured.get(scope, []))
        return dict(configured=local, imports=environment.get(scope + '_import', []),
                    effective=repository_paths(repository, server, user, scope),
                    sources={key: value for key, value in sources.items() if key in (scope, scope + '_import')})
    value = environment.get('ssh_config_file', '')
    if value and not isinstance(value, str):
        raise ValueError('ssh_config_file must be a path string')
    return dict(configured=configured.get('ssh_config_file', ''), effective=value, sources=[sources.get('ssh_config_file')])


def inventory(data: dict, scope: str) -> dict:
    """List saved entries without probing other servers or executing settings."""
    field = {'os': 'os_settings', 'ssh-config': 'ssh_config_file', 'python': 'python_settings',
             'system-packages': 'system_packages'}.get(scope, scope)
    result = {}
    for server, user, settings in environment_defaults.entries(data):
        selected = {key: value for key, value in settings.items() if key in (field, field + '_import')}
        if server == 'default':
            result['default'] = selected
        else:
            result.setdefault(server, {})[user] = selected
    return result


def installed_python() -> dict:
    """Capture distributions visible to this interpreter, without importing them."""
    names = {}
    for distribution in metadata.distributions():
        name = distribution.metadata.get('Name')
        if name:
            names.setdefault(re.sub(r'[-_.]+', '-', name).lower(), name)
    return dict(version=platform.python_version(), packages=[name + '==' + metadata.version(name) for _, name in sorted(names.items())])


def import_requirements(data: dict, scope: str, captured: object, current: object) -> object:
    """Limit automatic host discovery to repo requirements and retain manual extras."""
    requirements = entry(data, 'repo-requirement', '')
    if scope == 'python':
        required = requirements.get('python_settings', {})
        required_order = [
            re.sub(r'[-_.]+', '-', python_settings.package_requirement(value)[0]).lower()
            for value in required.get('packages', [])
        ]
        required_names = set(required_order)
        captured_packages = {}
        for value in captured['packages']:
            name, _ = python_settings.package_requirement(value)
            captured_packages[re.sub(r'[-_.]+', '-', name).lower()] = value
        manual = []
        for value in current.get('packages', []) if isinstance(current, dict) else []:
            name, _ = python_settings.package_requirement(value)
            if re.sub(r'[-_.]+', '-', name).lower() not in required_names:
                manual.append(value)
        result = {key: value for key, value in current.items() if key.startswith('#')} if isinstance(current, dict) else {}
        result['version'] = captured['version'] if 'version' in required else current.get('version')
        result['packages'] = [
            captured_packages[name] for name in required_order if name in captured_packages
        ] + manual
        return result
    if scope == 'system-packages':
        required_order = [system.package(value)[0] for value in requirements.get('system_packages', [])]
        required_names = set(required_order)
        captured_packages = {system.package(value)[0]: value for value in captured}
        manual = [value for value in current if system.package(value)[0] not in required_names]
        return [captured_packages[name] for name in required_order if name in captured_packages] + manual
    if scope == 'os':
        required_keys = set(requirements.get('os_settings', {}))
        return {**current, **{key: value for key, value in captured.items() if key in required_keys}}
    if scope == 'vscode':
        return vscode.filter_required(captured, requirements.get('vscode', {}), current)
    return captured


def capture(scope: str, input_file: Path | None, repository: Path | None = None) -> object:
    """Capture an explicit input or the active local environment."""
    if scope == 'ssh-config':
        content = (input_file or Path.home() / '.ssh/config').read_text()
        ssh.blocks(content)
        return content
    if input_file:
        value = json.loads(input_file.read_text())
        if isinstance(value, dict) and 'effective' in value:
            value = value['effective']
    elif scope == 'python':
        value = installed_python()
    elif scope == 'os':
        value = system.os_release()
    elif scope == 'system-packages':
        value = system.installed_packages()
    elif scope == 'vscode':
        value = vscode.capture(repository)
    else:
        value = [item for item in os.environ.get('PATH' if scope == 'path' else 'PYTHONPATH', '').split(os.pathsep) if item]
    if scope == 'python':
        python_settings.validate_layer(value, 'input')
        if not {'version', 'packages'} <= value.keys():
            raise ValueError('Python import requires version and packages')
        return value
    if scope == 'os':
        return system.validate_os(value, 'input')
    if scope == 'system-packages':
        return system.validate_packages(value, 'input')
    if scope == 'vscode':
        return vscode.validate(value, 'input')
    return path_list(value)


def merge_python(existing: dict, incoming: dict, collision: str) -> dict:
    """Combine packages by normalized name; never silently discard version conflicts."""
    result = deepcopy(existing)
    for key, value in incoming.items():
        if key.startswith('#'):
            result.setdefault(key, value)
        elif key == 'version':
            old = result.get(key)
            if old and old != value and collision == 'error':
                raise ValueError(f'Python version conflict: {old} vs {value}; select --on-collision existing or incoming')
            if not old or old == value or collision == 'incoming':
                result[key] = value
        elif key == 'packages':
            packages = {}
            for requirement in result.get(key, []):
                name, _ = python_settings.package_requirement(requirement)
                packages[re.sub(r'[-_.]+', '-', name).lower()] = requirement
            for requirement in value:
                name, _ = python_settings.package_requirement(requirement)
                identity = re.sub(r'[-_.]+', '-', name).lower()
                previous = packages.get(identity)
                if previous and python_settings.package_requirement(previous)[1] != python_settings.package_requirement(requirement)[1]:
                    if collision == 'error':
                        raise ValueError(f'Package conflict: {previous} vs {requirement}; select --on-collision existing or incoming')
                    if collision == 'existing':
                        continue
                packages[identity] = requirement
            result[key] = list(packages.values())
    return result


def propose(data: dict, scope: str, server: str, user: str, incoming: object, merge: bool, collision: str) -> dict:
    """Change only the selected setting; preserve unrelated hosts and fields."""
    result = deepcopy(data)
    target = environment_defaults.entry(result, server, user, create=True)
    effective = environment_defaults.resolve(data, server, user)[0]
    if scope == 'python':
        if merge:
            target['python_settings'] = merge_python(effective.get('python_settings', {}), incoming, collision)
        else:
            target['python_settings'] = incoming
        python_settings.validate_settings(result)
    elif scope == 'os':
        target['os_settings'] = system.merge_os(effective.get('os_settings', {}), incoming, collision) if merge else incoming
        system.validate_os(target['os_settings'], 'os_settings')
    elif scope == 'system-packages':
        target['system_packages'] = system.merge_packages(effective.get('system_packages', []), incoming, collision) if merge else incoming
        system.validate_packages(target['system_packages'], 'system_packages')
    elif scope == 'vscode':
        target['vscode'] = vscode.merge(effective.get('vscode', {}), incoming, collision) if merge else incoming
        vscode.validate(target['vscode'], 'vscode')
    else:
        if scope in ('path', 'pythonpath'):
            target[scope] = path_list([*effective.get(scope, []), *incoming] if merge else incoming)
            if not merge:
                target[scope + '_import'] = []
        else:
            target['ssh_config_file'] = incoming
    return result


def verify_paths(values: list[str], repository: Path, scope: str) -> list[dict]:
    """Check directories and their presence in the active search path."""
    active = os.environ.get('PATH' if scope == 'path' else 'PYTHONPATH', '').split(os.pathsep)
    rows = []
    for value in values:
        path = (repository.parent / os.path.expandvars(os.path.expanduser(value))).resolve()
        # PYTHONPATH also accepts archive files.
        exists = path.is_dir() or (scope == 'pythonpath' and path.is_file() and path.suffix in ('.zip', '.egg'))
        present = str(path) in [str(Path(item).resolve()) for item in active if item]
        rows.append(dict(name=value, status='PASS' if exists and present else 'FAIL', exists=exists, active=present))
    return rows
