"""Manage Git visibility and explicitly disposable non-project run artifacts."""

import fcntl
import json
import re
from pathlib import Path
import shutil
import subprocess

from vivado_build_selector import parse_selector, resolve_rerun
from vivado_build_config import build_names, TIMESTAMP


BEGIN = "# BEGIN HDLForge artifact visibility\n"
END = "# END HDLForge artifact visibility\n"
IGNORE = BEGIN + "# mode: ignored\n/*\n" + END
KEEP = BEGIN + "# mode: saved\n!*\n!*/\n" + END
CHILD_BEGIN = "# BEGIN HDLForge implementation visibility\n"
CHILD_END = "# END HDLForge implementation visibility\n"
CHILD_RULES = CHILD_BEGIN + "!/impl_runs/\n/impl_runs/**\n!/impl_runs/*/\n" + CHILD_END


def selected_folders(project: Path, selector: str, timestamp: str | None) -> list[Path]:
    """Select existing output folders without requiring still-existing inputs."""
    data = json.loads(project.read_text())
    if selector not in build_names(data):
        raise ValueError(f"Unknown build: {selector}")
    settings = data["vivado"]["non_project"]
    synthesis, _, implementation = selector.partition(".")
    root = project.parent / settings["output_root"] / synthesis / "artifacts"
    if timestamp is not None and not TIMESTAMP.fullmatch(timestamp):
        raise ValueError(f"Invalid synthesis timestamp: {timestamp}")
    if not root.exists():
        return []
    if root.is_symlink():
        raise ValueError(f"Refusing symlink artifact root: {root}")
    folders = []
    for parent in sorted(root.iterdir()):
        if not TIMESTAMP.fullmatch(parent.name) or (timestamp and parent.name != timestamp):
            continue
        target = parent / "impl_runs" / implementation if implementation else parent
        if not target.exists():
            continue
        if parent.is_symlink() or target.is_symlink() or (implementation and target.parent.is_symlink()):
            raise ValueError(f"Refusing symlink run folder: {target}")
        if target.is_dir():
            attempts = sorted(child for child in target.iterdir()
                              if child.is_dir() and TIMESTAMP.fullmatch(child.name)) if implementation else []
            folders.extend(attempts or [target])
    return folders


def replace_block(path: Path, begin: str, end: str, replacement: str) -> None:
    with (path.parent / ".hdlforge_ignore.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        _replace_block(path, begin, end, replacement)


def _replace_block(path: Path, begin: str, end: str, replacement: str) -> None:
    """Preserve user rules while replacing only the HDLForge-owned block."""
    if path.is_symlink():
        raise ValueError(f"Refusing symlink ignore file: {path}")
    text = path.read_text() if path.exists() else ""
    if begin in text:
        if text.count(begin) != 1 or text.count(end) != 1:
            raise ValueError(f"Malformed HDLForge block: {path}")
        start = text.index(begin)
        stop = text.index(end, start) + len(end)
        text = text[:start] + text[stop:]
    elif end in text:
        raise ValueError(f"Malformed HDLForge block: {path}")
    if text and not text.endswith("\n"):
        text += "\n"
    path.write_text(text + replacement)


ROOT_BEGIN = "# BEGIN HDLForge artifact defaults\n"
ROOT_END = "# END HDLForge artifact defaults\n"
ROOT_RULES = (
    "# Ignore published latest copies at this run root and implementation roots.\n/artifacts/latest/\n/*/artifacts/latest/\n"
    "# Git reads top to bottom; ! means do not ignore. These rules do not untrack files.\n"
    "# Allow Git to enter the artifacts directory.\n!/artifacts/\n"
    "# Ignore every artifact file by default.\n/artifacts/**\n"
    "# Allow directory traversal for later exceptions; files remain ignored.\n!/artifacts/**/\n"
)
SAVED_SYNTH_COMMENT = "# Explicitly saved synthesis/IP runs: --save_this_run adds exceptions here.\n"
IMPL_RULES = (
    "# Keep implementations ignored even when their parent synthesis is saved.\n"
    "/artifacts/*/impl_runs/**\n"
    "# Allow traversal to individually saved implementations; files remain ignored.\n"
    "!/artifacts/*/impl_runs/**/\n"
)
SAVED_IMPL_COMMENT = "# Explicitly saved implementation runs: --save_this_run adds exceptions here.\n"
DEFAULT_IGNORE = ROOT_BEGIN + ROOT_RULES + SAVED_SYNTH_COMMENT + IMPL_RULES + SAVED_IMPL_COMMENT + ROOT_END


def visibility(folder: Path) -> tuple[Path, str, str, str, str]:
    impl_parent = next((p for p in folder.parents if p.name == "impl_runs"), None)
    parent = impl_parent.parent if impl_parent else folder
    root = parent.parent.parent
    relative = folder.relative_to(root).as_posix()
    return (root / ".gitignore", ROOT_BEGIN, ROOT_END,
            ROOT_BEGIN + ROOT_RULES, f"!/{relative}/**\n")


def set_visibility(folder: Path, ignored: bool, *, preserve: bool = False) -> None:
    """Ignore all timestamps by default; list only explicitly saved exceptions."""
    marker, begin, end, ignore, keep = visibility(folder)
    old = folder / ".gitignore"
    old_text = old.read_text() if old.is_file() else ""
    if old == marker:
        text = marker.read_text() if marker.is_file() else ""
        if preserve and KEEP in text:
            ignored = False
        replace_block(marker, begin, end, ignore if ignored else keep)
        return
    with (marker.parent / ".hdlforge_ignore.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        text = marker.read_text() if marker.is_file() else ""
        saved = set(re.findall(r"^!/artifacts/([0-9][^*\n]+)/\*\*$", text, re.MULTILINE))
        key = folder.relative_to(marker.parent / "artifacts").as_posix()
        if KEEP in old_text:
            saved.add(key)
        # Migrate the previous per-timestamp format, preserving saved choices.
        text = re.sub(r"# BEGIN HDLForge artifacts [^\n]+\n.*?# END HDLForge artifacts [^\n]+\n?", "", text, flags=re.DOTALL)
        if not preserve or key not in saved:
            if ignored:
                saved.discard(key)
            else:
                saved.add(key)
        if marker.is_symlink():
            raise ValueError(f"Refusing symlink ignore file: {marker}")
        marker.write_text(text)
        block = ROOT_BEGIN + ROOT_RULES
        block += SAVED_SYNTH_COMMENT
        block += "".join(f"!/artifacts/{name}/**\n" for name in sorted(saved) if "/" not in name)
        block += IMPL_RULES
        block += SAVED_IMPL_COMMENT
        block += "".join(f"!/artifacts/{name}/**\n" for name in sorted(saved) if "/" in name)
        _replace_block(marker, ROOT_BEGIN, ROOT_END, block + ROOT_END)
    if old.is_file():
        replace_block(old, BEGIN, END, "")
        replace_block(old, CHILD_BEGIN, CHILD_END, "")
        if not old.read_text().strip():
            old.unlink()


def initialize_visibility(folder: Path) -> None:
    """Initialize the new run, preserving any existing explicit saved choice."""
    set_visibility(folder, True, preserve=True)
    if folder.parent.name == "impl_runs":
        parent = folder.parent.parent
        marker, begin, end, ignore, keep = visibility(parent)
        if marker.is_file() and begin in marker.read_text():
            set_visibility(parent, True, preserve=True)


def cleanable(folder: Path) -> tuple[bool, str]:
    """Let Git evaluate actual ignore rules, including user-written exceptions."""
    paths = []
    for path in folder.rglob("*"):
        if path.is_symlink() or not path.is_dir():
            paths.append(str(path.absolute()))
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


def manage_artifacts(project: Path, selector: str, action: str, timestamp: str | None = None) -> int:
    ###########################################################################
    # These actions manage existing outputs only; they never start a build.    #
    ###########################################################################
    selector = resolve_rerun(project, selector)
    parsed = parse_selector(selector)
    attempt = None
    if parsed:
        data = json.loads(project.read_text())
        timestamp = parsed['synth']
        if timestamp == 'latest':
            from vivado_build_config import synthesis_timestamps
            timestamps = synthesis_timestamps(project, data, parsed['run'], completed_only=True)
            if not timestamps:
                raise ValueError('No successful synthesis')
            timestamp = timestamps[-1]
        if timestamp == 'new' or parsed['attempt'] == 'new':
            raise ValueError('Artifact management requires an existing timestamp')
        attempt = parsed['attempt']
        selector = parsed['run'] + ('.' + parsed['impl'] if parsed['impl'] else '')
    folders = selected_folders(project.resolve(), selector, timestamp)
    if attempt:
        folders = [folder for folder in folders if folder.name == attempt]
    if not folders:
        print("No matching artifact folders")
        return 0
    if action == "--save_this_run" and timestamp is None:
        folders = folders[-1:]  # Save only the newest matching run by default.
    for folder in folders:
        marker = folder / ".gitignore"
        if action == "--save_this_run":
            set_visibility(folder, False)
            if "." in selector:
                impl_root = folder.parent if folder.parent.parent.name == "impl_runs" else folder
                set_visibility(impl_root, False)  # Preserve shared inputs with the saved attempt.
                set_visibility(impl_root.parent.parent, False)
            print(f"Saved from cleanup (not staged): {folder}")
        elif action == "--clean_ignore_artifacts":
            allowed, reason = cleanable(folder)
            if not allowed:
                print(f"Skipped: {folder}: {reason}")
                continue
            shutil.rmtree(folder)
            print(f"Deleted ignored artifacts: {folder}")
        else:
            raise ValueError(f"Unknown artifact action: {action}")
    return 0
