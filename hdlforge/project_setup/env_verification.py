"""Read-only checks of the Python interpreter and its installed distributions."""

from importlib import metadata
import re

import environment_defaults


SETTINGS_KEY = 'python_settings'
VERSION = re.compile(r'\d+\.\d+(?:\.\d+)?')
PACKAGE = re.compile(r'([A-Za-z0-9][A-Za-z0-9._-]*)(?:==([A-Za-z0-9][A-Za-z0-9.!+_-]*))?')


def package_requirement(value: str) -> tuple[str, str | None]:
    """Accept a distribution name or an exact name==version requirement."""
    match = PACKAGE.fullmatch(value) if isinstance(value, str) else None
    if match is None:
        raise ValueError(f'Invalid package requirement {value!r}; use name or name==version')
    return match[1], match[2]


def validate_layer(layer: dict, location: str) -> None:
    """Validate supplied fields; missing fields inherit from broader defaults."""
    if not isinstance(layer, dict):
        raise ValueError(f'{location} must be an object')
    unknown = {key for key in layer if not key.startswith('#')} - {'version', 'packages'}
    if unknown:
        raise ValueError(f'{location}: unknown fields {sorted(unknown)}')
    if 'version' in layer and (not isinstance(layer['version'], str) or not VERSION.fullmatch(layer['version'])):
        raise ValueError(f'{location}.version must be major.minor or major.minor.patch')
    if 'packages' in layer:
        if not isinstance(layer['packages'], list):
            raise ValueError(f'{location}.packages must be a list')
        names = set()
        for value in layer['packages']:
            name, _ = package_requirement(value)
            normalized = re.sub(r'[-_.]+', '-', name).lower()
            if normalized in names:
                raise ValueError(f'{location}.packages repeats {name}')
            names.add(normalized)


def validate_settings(settings: dict) -> None:
    """Validate Python fields within ordinary environment entries."""
    for server, user, value in environment_defaults.entries(settings):
        if SETTINGS_KEY in value:
            validate_layer(value[SETTINGS_KEY], f'settings.env.{server}.{user}.{SETTINGS_KEY}')


def resolve_settings(settings: dict, server: str, user: str) -> tuple[dict, dict]:
    """Consume the shared environment resolver instead of Python-only defaults."""
    validate_settings(settings)
    environment, provenance = environment_defaults.resolve(settings, server, user)
    resolved = environment.get(SETTINGS_KEY, {})
    validate_layer(resolved, SETTINGS_KEY)
    sources = {key[len(SETTINGS_KEY) + 1:]: source for key, source in provenance.items()
               if key.startswith(SETTINGS_KEY + '.')}
    missing = {'version', 'packages'} - resolved.keys()
    if missing:
        raise ValueError(f'No Python requirements for {server}:{user}: missing {sorted(missing)}')
    return resolved, sources


def verify(settings: dict, actual_version: str, lookup=metadata.version) -> list[dict]:
    """Inspect distribution metadata without importing packages or installing them."""
    expected = settings['version']
    actual_parts = actual_version.split('.')
    expected_parts = expected.split('.')
    rows = [dict(name='Python', required=expected, actual=actual_version,
                 status='PASS' if actual_parts[:len(expected_parts)] == expected_parts else 'FAIL')]
    for requirement in settings['packages']:
        name, version = package_requirement(requirement)
        try:
            actual = lookup(name)
        except metadata.PackageNotFoundError:
            actual = None
        passed = actual is not None and (version is None or actual == version)
        rows.append(dict(name=name, required=version or 'installed', actual=actual,
                         status='PASS' if passed else 'FAIL'))
    return rows
