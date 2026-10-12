"""Capture, validate, merge and verify host operating-system settings."""

from copy import deepcopy
import platform
import re
import subprocess


PACKAGE = re.compile(r'([A-Za-z0-9][A-Za-z0-9+.:~-]*)(?:=([^\s=]+))?')
OS_FIELDS = ('id', 'version_id', 'architecture')


def os_release() -> dict[str, str]:
    """Read stable OS identity fields from /etc/os-release."""
    values = {}
    with open('/etc/os-release', encoding='utf-8') as stream:
        for line in stream:
            key, separator, value = line.rstrip().partition('=')
            if separator:
                values[key] = value.strip('"')
    return dict(id=values.get('ID', ''), version_id=values.get('VERSION_ID', ''), architecture=platform.machine())


def validate_os(value: dict, location: str) -> dict:
    """Require the portable OS identity schema."""
    if not isinstance(value, dict) or set(value) - set(OS_FIELDS):
        raise ValueError(f'{location} must contain only {list(OS_FIELDS)}')
    if any(key not in value or not isinstance(value[key], str) or not value[key] for key in OS_FIELDS):
        raise ValueError(f'{location} requires nonempty {list(OS_FIELDS)}')
    return value


def package(value: str) -> tuple[str, str | None]:
    """Parse a Debian package requirement with an optional exact version."""
    match = PACKAGE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f'Invalid system package {value!r}; use name or name=version')
    return match[1], match[2]


def validate_packages(values: list, location: str) -> list[str]:
    """Validate and deduplicate a system package requirement list."""
    if not isinstance(values, list):
        raise ValueError(f'{location} must be a list')
    names = set()
    for value in values:
        name, _ = package(value)
        if name in names:
            raise ValueError(f'{location} repeats {name}')
        names.add(name)
    return values


def installed_packages() -> list[str]:
    """Capture installed Debian packages and their exact versions."""
    result = subprocess.run(['dpkg-query', '-W', '-f=${binary:Package}\t${Version}\n'], text=True,
                            capture_output=True, check=True, timeout=30)
    return [name + '=' + version for name, version in (line.split('\t', 1) for line in result.stdout.splitlines())]


def merge_packages(existing: list[str], incoming: list[str], collision: str) -> list[str]:
    """Merge package requirements by Debian package name."""
    result = {package(value)[0]: value for value in existing}
    for value in incoming:
        name, version = package(value)
        previous = result.get(name)
        if previous and package(previous)[1] != version:
            if collision == 'error':
                raise ValueError(f'System package conflict: {previous} vs {value}; select --on-collision existing or incoming')
            if collision == 'existing':
                continue
        result[name] = value
    return list(result.values())


def merge_os(existing: dict, incoming: dict, collision: str) -> dict:
    """Merge OS identity fields with explicit collision handling."""
    result = deepcopy(existing)
    for key, value in incoming.items():
        if key in result and result[key] != value and collision == 'error':
            raise ValueError(f'OS setting conflict: {key}={result[key]} vs {value}; select --on-collision existing or incoming')
        if key not in result or result[key] == value or collision == 'incoming':
            result[key] = value
    return result


def verify_os(required: dict) -> list[dict]:
    """Compare required OS identity with the active host."""
    active = os_release()
    return [dict(name=key, required=value, actual=active.get(key),
                 status='PASS' if active.get(key) == value else 'FAIL') for key, value in required.items()]


def verify_packages(required: list[str]) -> list[dict]:
    """Compare required packages with installed Debian package versions."""
    installed = {package(value)[0]: package(value)[1] for value in installed_packages()}
    rows = []
    for requirement in required:
        name, version = package(requirement)
        actual = installed.get(name)
        rows.append(dict(name=name, required=version or 'installed', actual=actual,
                         status='PASS' if actual is not None and (version is None or actual == version) else 'FAIL'))
    return rows
