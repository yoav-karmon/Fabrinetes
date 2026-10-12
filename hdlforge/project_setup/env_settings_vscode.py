"""Capture and compare repository VS Code extensions and workspace settings."""

import json
from pathlib import Path
import re
import subprocess


EXTENSION = re.compile(r'([A-Za-z0-9][A-Za-z0-9-]*\.[A-Za-z0-9][A-Za-z0-9-]*)(?:@([^\s@]+))?')


def extension(value: str) -> tuple[str, str | None]:
    """Parse one extension ID with an optional version."""
    match = EXTENSION.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f'Invalid VS Code extension {value!r}')
    return match[1].lower(), match[2]


def validate(value: dict, location: str) -> dict:
    """Validate a VS Code settings object and reject duplicate extension IDs."""
    allowed = {'extensions', 'settings', '#extension_format'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError(f'{location} must contain only {sorted(allowed)}')
    if not isinstance(value.get('extensions', []), list) or not isinstance(value.get('settings', {}), dict):
        raise ValueError(f'{location} extensions must be a list and settings must be an object')
    names = set()
    for item in value.get('extensions', []):
        name, _ = extension(item)
        if name in names:
            raise ValueError(f'{location} repeats extension {name}')
        names.add(name)
    return value


def capture(repository: Path) -> dict:
    """Capture installed extension versions and repository workspace settings."""
    installed = {}
    registry_path = Path.home() / '.vscode-server/extensions/extensions.json'
    if registry_path.is_file():
        for item in json.loads(registry_path.read_text()):
            identifier = item.get('identifier', {}).get('id')
            version = item.get('version')
            if identifier and version:
                installed[identifier.lower()] = identifier.lower() + '@' + version
    result = subprocess.run(['code', '--list-extensions', '--show-versions'], text=True,
                            capture_output=True, timeout=30)
    if result.returncode and not installed:
        raise ValueError(result.stderr.strip() or 'Cannot list installed VS Code extensions')
    for line in result.stdout.splitlines() if result.returncode == 0 else []:
        value = line.strip()
        if value:
            installed.setdefault(extension(value)[0], value)
    path = repository.parent / '.vscode/settings.json'
    settings = json.loads(path.read_text()) if path.is_file() else {}
    return validate(dict(extensions=list(installed.values()), settings=settings), 'active VS Code settings')


def filter_required(captured: dict, required: dict, current: dict) -> dict:
    """Import allowlisted extensions while preserving manual host extras."""
    order = [extension(value)[0] for value in required.get('extensions', [])]
    required_names = set(order)
    available = {extension(value)[0]: value for value in captured.get('extensions', [])}
    manual = [value for value in current.get('extensions', []) if extension(value)[0] not in required_names]
    return dict(extensions=[available[name] for name in order if name in available] + manual)


def merge(existing: dict, incoming: dict, collision: str) -> dict:
    """Merge extension versions by ID and settings by key."""
    result = dict(existing)
    extensions = {extension(value)[0]: value for value in existing.get('extensions', [])}
    for value in incoming.get('extensions', []):
        name, version = extension(value)
        previous = extensions.get(name)
        if previous and extension(previous)[1] != version:
            if collision == 'error':
                raise ValueError(f'VS Code extension conflict: {previous} vs {value}')
            if collision == 'existing':
                continue
        extensions[name] = value
    result['extensions'] = list(extensions.values())
    settings = dict(existing.get('settings', {}))
    for name, value in incoming.get('settings', {}).items():
        if name in settings and settings[name] != value and collision == 'error':
            raise ValueError(f'VS Code setting conflict: {name}')
        if name not in settings or settings[name] == value or collision == 'incoming':
            settings[name] = value
    if settings:
        result['settings'] = settings
    return validate(result, 'vscode')


def verify(required: dict, active: dict) -> list[dict]:
    """Compare extensions by ID and workspace settings by key."""
    installed = {extension(value)[0]: extension(value)[1] for value in active.get('extensions', [])}
    rows = []
    for value in required.get('extensions', []):
        name, version = extension(value)
        actual = installed.get(name)
        rows.append(dict(name='extension.' + name, required=version or 'installed', actual=actual,
                         status='PASS' if actual is not None and (version is None or actual == version) else 'FAIL'))
    for name, expected in required.get('settings', {}).items():
        actual = active.get('settings', {}).get(name)
        equal = set(expected) == set(actual) if isinstance(expected, list) and isinstance(actual, list) else expected == actual
        rows.append(dict(name='setting.' + name, required=expected, actual=actual,
                         status='PASS' if equal else 'FAIL'))
    return rows
