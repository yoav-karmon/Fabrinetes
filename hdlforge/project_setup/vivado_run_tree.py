"""Discover marked synthesis/IP definitions independently of output folders."""

import re


RUN_KEY = re.compile(r'[A-Za-z0-9_][A-Za-z0-9_-]*\Z')
MARKER = 'is_hdlforge_run'


def run_tree(data: dict) -> dict:
    return data.get('vivado', {}).get('non_project', {}).get('runs', {})


def discover_runs(tree: dict, *, include_unmarked: bool = False) -> dict[str, dict]:
    """Walk groups until a marker identifies a run; never walk its payload."""
    ###########################################################################
    # Only explicit initialization uses include_unmarked to migrate old JSON. #
    # Runtime discovery always requires the marker, including IP definitions. #
    ###########################################################################
    if not isinstance(tree, dict):
        raise ValueError('vivado.non_project.runs must be an object')
    result = {}

    def visit(node: dict, parts: tuple[str, ...]) -> None:
        marker = node.get(MARKER)
        if MARKER in node and not (isinstance(marker, bool) or marker in ('true', 'false')):
            raise ValueError(f"{'.'.join(parts)}.{MARKER} must be true or false")
        enabled = marker is True or marker == 'true'
        legacy = include_unmarked and MARKER not in node and 'script' in node
        if parts and (enabled or legacy):
            if any(not RUN_KEY.fullmatch(part) for part in parts):
                raise ValueError(f"Invalid run path: {'.'.join(parts)}; use letters, digits, underscores or hyphens per key")
            result['.'.join(parts)] = node
            return
        for key, child in node.items():
            if not key.startswith('#') and isinstance(child, dict):
                visit(child, (*parts, key))

    visit(tree, ())
    return result


def run_definition(tree: dict, path: str) -> dict:
    """Read a known JSON path, including historical snapshots without markers."""
    node = tree
    for key in path.split('.'):
        if not isinstance(node, dict) or key not in node:
            raise ValueError(f'Unknown synthesis/IP run: {path}')
        node = node[key]
    if not isinstance(node, dict):
        raise ValueError(f'Invalid synthesis/IP run: {path}')
    return node


def selected_run(value: str, runs: dict) -> str | None:
    """Find the complete marked prefix before parsing attempt/action suffixes."""
    return next((name for name in runs if value == name or value.startswith(name + '.')), None)
