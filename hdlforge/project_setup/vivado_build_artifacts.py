"""Delete a run only when every descendant is both untracked and ignored."""

from contextlib import ExitStack
import fcntl
import json
import os
from pathlib import Path
import re
import shutil
import subprocess

from vivado_build_config import build_names, synthesis_folder
from vivado_build_layout import run_lock_path, CONFIG, IDENTITY, LEGACY_CONFIG, descendant_runs, find_run, read_run, run_directories
from vivado_build_selector import parse_selector, resolve_selector

def selected_folders(project: Path, selector: str, timestamp: str | None) -> list[Path]:
    data = json.loads(project.read_text())
    if selector not in build_names(data):
        raise ValueError(f'Unknown build: {selector}')
    settings = data['vivado']['non_project']
    synthesis, _, implementation = selector.partition('.')
    root = synthesis_folder(project, settings, synthesis)
    parents = [find_run(root, timestamp)] if timestamp else run_directories(root)
    if implementation:
        return [child for parent in parents for child in run_directories(parent / 'impl_runs' / implementation, selector)]
    return parents


def cleanable(folder: Path) -> tuple[bool, str]:
    """Preserve tracked files and let Git evaluate user-written ignore exceptions."""
    if folder.is_symlink() or not folder.is_dir():
        return False, f"not a real artifact directory: {folder}"
    tracked = subprocess.run(
        ["git", "-C", str(folder), "ls-files", "--cached", "-z", "--", "."],
        capture_output=True, text=True,
    )
    if tracked.returncode:
        raise ValueError(tracked.stderr.strip() or "Cannot evaluate tracked artifact files")
    if tracked.stdout:
        return False, f"tracked by Git: {tracked.stdout.split(chr(0), 1)[0]}"
    paths = []
    # Inspect every descendant, including ignored/hidden directories. Unlike
    # glob traversal, scandir propagates unreadable-directory errors: an
    # incomplete inventory must never authorize deleting the whole tree.
    pending = [folder]
    while pending:
        directory = pending.pop()
        with os.scandir(directory) as entries:
            for entry in entries:
                if entry.name == '.git':
                    return False, f"nested Git repository: {entry.path}"
                if entry.is_dir(follow_symlinks=False):
                    pending.append(Path(entry.path))
                else:
                    paths.append(os.path.abspath(entry.path))
    if not paths:
        return True, "empty artifact folder"
    result = subprocess.run(
        ["git", "-C", str(folder), "check-ignore", "--no-index", "--stdin", "-z"],
        input="\0".join(paths) + "\0", capture_output=True, text=True,
    )
    if result.returncode not in (0, 1):
        raise ValueError(result.stderr.strip() or "Cannot evaluate .gitignore rules")
    ignored = set(result.stdout.split("\0"))
    visible = next((path for path in paths if path not in ignored), None)
    if visible:
        return False, f"not ignored by Git rules: {visible}"
    return True, "ignored by Git rules"


def cleanup_orphan_locks(root: Path, *, dry_run: bool = False) -> None:
    """Remove ignored locks only after their attempt disappears and nobody holds them."""
    if root.is_symlink() or not root.is_dir():
        return
    try:
        # Read even incomplete manifests: uncertainty must preserve their locks.
        attempts = [path for path in root.iterdir() if path.is_dir() and
                    any((path / marker).is_file() for marker in (CONFIG, LEGACY_CONFIG, IDENTITY))]
        referenced = {read_run(path)['run_id'] for path in attempts}
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'Skipped lock cleanup: {root}: {error}')
        return
    for path in sorted(root.glob('_*.run.lock')):
        match = re.fullmatch(r'_([0-9a-f]{32})\.run\.lock', path.name)
        if not match or match[1] in referenced or path.is_symlink() or not path.is_file():
            continue
        try:
            tracked = subprocess.run(['git', '-C', str(root), 'ls-files', '--cached', '--', path.name],
                                     capture_output=True, text=True, check=True)
            ignored = subprocess.run(['git', '-C', str(root), 'check-ignore', '-q', '--', path.name])
            if tracked.stdout or ignored.returncode != 0:
                continue
            with path.open('r') as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                # Recheck after locking; never unlink an inode replaced by a
                # concurrent cleanup, nor a lock whose attempt now exists.
                if not os.path.samestat(os.fstat(lock.fileno()), path.stat()):
                    continue
                if any(read_run(attempt).get('run_id') == match[1] for attempt in root.iterdir()
                       if attempt.is_dir() and any((attempt / marker).is_file() for marker in (CONFIG, LEGACY_CONFIG, IDENTITY))):
                    continue
                if dry_run:
                    print(f'Would delete orphan run lock: {path}')
                else:
                    path.unlink()
                    print(f'Deleted orphan run lock: {path}')
        except (OSError, ValueError, KeyError, TypeError, subprocess.CalledProcessError) as error:
            print(f'Skipped run lock: {path}: {error}')
    # Visit only run containers, never snapshot input trees or symlink aliases.
    for attempt in attempts:
        if attempt.is_symlink():
            continue
        for container in ('impl', 'bitstream_runs'):
            cleanup_orphan_locks(attempt / container, dry_run=dry_run)
        implementations = attempt / 'impl_runs'
        if implementations.is_dir() and not implementations.is_symlink():
            for group in implementations.iterdir():
                cleanup_orphan_locks(group, dry_run=dry_run)


def manage_artifacts(project: Path, selector: str, action: str, timestamp: str | None = None, *, dry_run: bool = False) -> int:
    """Validate the entire selected tree before deleting anything inside it."""
    if action == '--save_this_run':
        raise ValueError('Use git add -f <run-directory> to save a run; HDLForge does not write .gitignore files')
    if action != '--clean_ignore_artifacts':
        raise ValueError(f'Unknown artifact action: {action}')
    parsed = parse_selector(resolve_selector(project, selector))
    attempt = None
    if parsed:
        timestamp = parsed['synth']
        attempt = parsed['attempt']
        if timestamp == 'new' or attempt == 'new':
            raise ValueError('Cleanup requires an existing run')
        selector = parsed['run'] + ('.' + parsed['impl'] if parsed['impl'] else '')
    folders = selected_folders(project.resolve(), selector, timestamp)
    if attempt:
        folders = [folder for folder in folders if read_run(folder)['run_id'] == attempt]
    settings = json.loads(project.read_text())['vivado']['non_project']
    synthesis, _, implementation = selector.partition('.')
    root = synthesis_folder(project, settings, synthesis)
    lock_roots = ([folder.parent for folder in folders] if timestamp else
                  [parent / 'impl_runs' / implementation for parent in run_directories(root)]
                  if implementation else [root])
    lock_roots.extend(folder.parent for folder in folders)
    for folder in folders:
        # Lock every descendant run as well as the selected parent, so active
        # implementations cannot be removed by synthesis cleanup.
        with ExitStack() as stack:
            try:
                descendants = descendant_runs(folder)
                for child in sorted(set(descendants)):
                    identity = read_run(child)['run_id']
                    lock = stack.enter_context(run_lock_path(child, identity).open('a'))
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                allowed, reason = cleanable(folder)
            except (OSError, ValueError) as error:
                allowed, reason = False, str(error)
            if not allowed:
                print(f'Skipped: {folder}: {reason}')
            elif dry_run:
                print(f'Would delete: {folder}: {reason}')
            else:
                shutil.rmtree(folder)
                print(f'Deleted ignored artifacts: {folder}')
    for root in sorted(set(lock_roots)):
        cleanup_orphan_locks(root, dry_run=dry_run)
    return 0
