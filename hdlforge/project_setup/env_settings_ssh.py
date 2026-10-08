"""Read and merge SSH configuration without executing directives or connecting."""

from pathlib import Path
import re
import shlex


def blocks(content: str) -> list[tuple[str, str]]:
    """Retain original text, splitting at Host/Match declarations."""
    result, lines, key = [], [], 'global'
    if '\x00' in content:
        raise ValueError('SSH configuration cannot contain NUL bytes')
    for number, line in enumerate(content.splitlines(keepends=True), 1):
        try:
            words = shlex.split(line, comments=True)
        except ValueError as error:
            raise ValueError(f'SSH line {number}: {error}') from error
        if words:
            directive = words[0].split('=', 1)[0].lower()
            if not re.fullmatch('[a-z][a-z0-9]*', directive):
                raise ValueError(f'SSH line {number}: invalid directive (expected SSH config text)')
            if len(words) == 1 and '=' not in words[0]:
                raise ValueError(f'SSH line {number}: directive requires a value')
            if directive in ('host', 'match'):
                if '=' in words[0]:
                    words = [directive, words[0].split('=', 1)[1], *words[1:]]
                if lines:
                    result.append((key, ''.join(lines)))
                key, lines = directive + ' ' + ' '.join(words[1:]), []
        lines.append(line)
    if lines:
        result.append((key, ''.join(lines)))
    return result


def merge(existing: str, incoming: str, collision: str) -> str:
    """Merge literal Host blocks; reject ambiguous pattern/Match/Include merging."""
    if existing == incoming:
        return existing
    old, new = blocks(existing), blocks(incoming)
    for group in (old, new):
        seen = set()
        for key, content in group:
            words = [shlex.split(line, comments=True) for line in content.splitlines()]
            if key.startswith('match ') or any(row and row[0].split('=')[0].lower() == 'include' for row in words):
                raise ValueError('SSH merge does not rewrite Match/Include rules; use import for a complete reviewed file')
            if key.startswith('host ') and (len(key.split()) != 2 or any(char in key for char in '*?![')):
                raise ValueError('SSH merge requires single literal Host names; use import for pattern-based files')
            identity = key.lower()
            if identity in seen:
                raise ValueError(f'Duplicate SSH section: {key}')
            seen.add(identity)
    merged = dict((key.lower(), (key, content)) for key, content in old)
    for key, content in new:
        identity = key.lower()
        previous = merged.get(identity)
        if previous and previous[1].strip() != content.strip():
            if collision == 'error':
                raise ValueError(f'SSH merge conflict: {key}; select --on-collision existing or incoming')
            if collision == 'existing':
                continue
        merged[identity] = (key, content)
    ordered = sorted(merged.values(), key=lambda item: item[0] != 'global')
    return '\n\n'.join(content.rstrip() for _, content in ordered) + '\n'


def config_path(repository: Path, value: str) -> Path:
    """Keep maintained SSH files inside the owning repository."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError('ssh_config_file must be a nonempty repository-relative path')
    path = (repository.parent / value).resolve()
    if not path.is_relative_to(repository.parent.resolve()) or path == repository.resolve():
        raise ValueError('SSH configuration must be a separate file inside the repository')
    return path
