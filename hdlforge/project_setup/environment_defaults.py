"""Resolve every environment field before startup or settings consumers use it."""

import argparse
from copy import deepcopy
import json
from pathlib import Path
import sys


def environments(data: dict) -> dict:
    value = data.get('settings', {}).get('env', {})
    if not isinstance(value, dict):
        raise ValueError('settings.env must be an object')
    if 'python_settings' in value:
        raise ValueError('Move settings.env.python_settings into env.default or env.<server>.<user>.python_settings')
    return value


def entries(data: dict) -> list[tuple[str, str, dict]]:
    """Enumerate user-shaped entries, including global and server defaults."""
    result = []
    for server, users in environments(data).items():
        if server.startswith('#'):
            continue
        if not isinstance(users, dict):
            raise ValueError(f'settings.env.{server} must be an object')
        if server == 'default':
            result.append((server, 'default', users))
        else:
            for user, value in users.items():
                if user.startswith('#'):
                    continue
                if not isinstance(value, dict):
                    raise ValueError(f'settings.env.{server}.{user} must be an object')
                result.append((server, user, value))
    return result


def entry(data: dict, server: str, user: str, create: bool = False) -> dict:
    """Select one literal entry; a global default has the same shape as a user."""
    env = data.setdefault('settings', {}).setdefault('env', {}) if create else environments(data)
    parent = env if server == 'default' else (env.setdefault(server, {}) if create else env.get(server, {}))
    key = 'default' if server == 'default' else user
    if not isinstance(parent, dict):
        raise ValueError(f'settings.env.{server} must be an object')
    value = parent.setdefault(key, {}) if create else parent.get(key, {})
    if not isinstance(value, dict):
        raise ValueError(f'settings.env.{server}.{user} must be an object')
    return value


def resolve(data: dict, server: str, user: str) -> tuple[dict, dict]:
    """Recursively inherit objects; explicit scalars and arrays replace defaults."""
    ###########################################################################
    # The merge is field-agnostic: future keys automatically inherit without    #
    # adding another type-specific defaults implementation.                    #
    ###########################################################################
    layers = [('settings.env.default', entry(data, 'default', 'default'))]
    if server != 'default':
        layers.append((f'settings.env.{server}.default', entry(data, server, 'default')))
        if user != 'default':
            layers.append((f'settings.env.{server}.{user}', entry(data, server, user)))
    result, sources = {}, {}
    for location, layer in layers:
        merge_object(result, layer, sources, location)
    return result, sources


def merge_object(target: dict, incoming: dict, sources: dict, location: str, prefix: str = '') -> None:
    """Preserve unspecified nested keys and record the supplying layer per leaf."""
    for key, value in incoming.items():
        if key.startswith('#'):
            continue
        path = prefix + key
        if isinstance(value, dict):
            if not isinstance(target.get(key), dict):
                target[key] = {}
                sources.pop(path, None)
            merge_object(target[key], value, sources, location, path + '.')
        else:
            for previous in list(sources):
                if previous == path or previous.startswith(path + '.'):
                    del sources[previous]
            target[key] = deepcopy(value)
            sources[path] = location + '.' + path


def locate(root: dict, name: str) -> tuple:
    """Use longest literal keys so dotted host/user names remain unambiguous."""
    node, path = root, []
    while name:
        keys = [key for key in node if name == key or name.startswith(key + '.')] if isinstance(node, dict) else []
        if not keys:
            raise ValueError('Missing environment import: ' + name)
        key = max(keys, key=len)
        path.append(key)
        node = node[key]
        name = name[len(key):].lstrip('.')
    return tuple(path)


def expand(root: dict, path: tuple, field: str, seen: tuple = ()) -> list[dict]:
    if path in seen:
        raise ValueError('Environment import cycle: ' + '.'.join(path))
    parent = root
    for key in path[:-1]:
        parent = parent[key]
    value = parent.get(path[-1])
    if not isinstance(value, dict if field == 'variables' else list):
        raise ValueError('Invalid environment import type: ' + '.'.join(path))
    imports = parent.get(path[-1] + '_import', [])
    if not isinstance(imports, list) or any(not isinstance(item, str) or not item for item in imports):
        raise ValueError('Invalid environment import list: ' + '.'.join(path))
    layers = []
    for reference in imports:
        layers.extend(expand(root, locate(root, reference), field, (*seen, path)))
    return [*layers, {field: value}]


def repository_layers(data: dict, server: str, user: str) -> list[dict]:
    """Resolve defaults first, then reuse ordered imports and strict startup keys."""
    value, _ = resolve(data, server, user)
    if not value:
        raise ValueError(f'Missing repository environment for {server}:{user}')
    required = ('path', 'path_import', 'pythonpath', 'pythonpath_import', 'variables', 'variables_import')
    if any(key not in value for key in required):
        raise ValueError('Repository environment requires path, path_import, pythonpath, pythonpath_import, variables, variables_import')
    if any(not isinstance(value[key], list) for key in ('path_import', 'pythonpath_import', 'variables_import')):
        raise ValueError('Repository environment import fields must be arrays')
    root = deepcopy(data)
    selected = entry(root, server, user, create=True)
    selected.clear()
    selected.update(value)
    base = ('settings', 'env', 'default') if server == 'default' else ('settings', 'env', server, user)
    layers = []
    for field in ('path', 'pythonpath', 'variables'):
        layers.extend(expand(root, (*base, field), field))
    layers[-1].update({key: value for key, value in value.items() if key not in required})
    return layers


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['environment', 'layers', 'list'])
    parser.add_argument('file', type=Path)
    parser.add_argument('server', nargs='?', default='default')
    parser.add_argument('user', nargs='?', default='default')
    args = parser.parse_args()
    try:
        data = json.loads(args.file.read_text())
        if args.mode == 'list':
            for server, user, _ in entries(data):
                if server != 'default' and user != 'default':
                    print(server + ':' + user)
        else:
            value = repository_layers(data, args.server, args.user) if args.mode == 'layers' else resolve(data, args.server, args.user)[0]
            print(json.dumps(value))
        return 0
    except (OSError, ValueError, TypeError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
