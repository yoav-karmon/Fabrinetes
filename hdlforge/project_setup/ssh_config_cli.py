#!/usr/bin/env python3
"""HDLForge SSH inventory CLI; no connection or SSH command execution."""

import argparse
from datetime import datetime, timezone
import difflib
import getpass
import json
import os
from pathlib import Path
import stat
import socket
import sys
import tempfile

from ssh_config_inventory import get_inventory, merge, parse_config, read_document, render, report, set_inventory, signature


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(
        prog="hdlforge --tool ssh", allow_abbrev=False,
        description="Import, export, verify or merge SSH inventories keyed by connection Host alias.",
        epilog="Writes show a diff and require approval unless --force. Every existing destination is backed up "
               "as <filename>.<UTC timestamp>.bak. Dry-run and verify never write or create backups. "
               "--force never resolves collisions: use --on-collision explicitly. "
               "Inventory path: settings.env.<local-host>.<local-user>.ssh_config. "
               "Only literal single-host blocks are supported; comments/formatting are not inventoried.")
    result.add_argument("action", choices=["import", "export", "verify", "merge"])
    result.add_argument("--json", "--project", dest="json_path", type=Path,
                        help="Destination/source repository JSON; default: exactly one *.hdlforge.json in cwd")
    result.add_argument("--ssh-config", type=Path, default=Path.home() / ".ssh/config", help="SSH config path (default: ~/.ssh/config)")
    result.add_argument("--local-host", default=socket.gethostname(), help="Local environment hostname (default: this machine)")
    result.add_argument("--local-user", default=getpass.getuser(), help="Local environment user (default: current user)")
    result.add_argument("--input", type=Path, action="append", default=[], help="Merge input JSON; repeat in precedence order")
    result.add_argument("--on-collision", choices=["error", "keep", "incoming"], default="error", help="Merge resolution: error (default), first wins, or last wins")
    result.add_argument("--dry-run", action="store_true", help="Report and show diff without writes, backups or prompts")
    result.add_argument("--force", "-f", action="store_true", help="Apply without approval; still show diff and create backup")
    return result


def show_diff(old: str, new: str, path: Path) -> None:
    for line in difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), fromfile=str(path), tofile=f"{path} (proposed)"):
        print(line, end="" if line.endswith("\n") else "\n")


def write_reviewed(path: Path, new: str, dry_run: bool, force: bool) -> int:
    """Review, back up, and atomically replace a file, rejecting concurrent edits."""
    if path.is_symlink():
        raise ValueError(f"Refusing to replace symlink {path}; pass the resolved path explicitly")
    existed = path.exists()
    original = path.read_bytes() if existed else None
    old = original.decode("utf-8") if existed else ""
    if old == new:
        print(f"UNCHANGED: {path}")
        return 0
    show_diff(old, new, path)
    if dry_run:
        print("DRY RUN: no changes or backups")
        return 0
    if not force:
        try:
            approval = input(f"Apply changes to {path}? [y/N] ")
        except EOFError:
            approval = ""
        if approval.strip().lower() not in {"y", "yes"}:
            print("CANCELLED: no changes or backups")
            return 1
    if path.is_symlink() or (path.read_bytes() if path.exists() else None) != original:
        raise ValueError("Destination changed during review; rerun to review the current file")
    if not path.parent.is_dir():
        raise ValueError(f"Destination directory does not exist: {path.parent}")
    mode = stat.S_IMODE(path.stat().st_mode) if existed else 0o600
    if existed:
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        backup = path.with_name(f"{path.name}.{stamp}.bak")
        with backup.open("xb") as stream:
            os.chmod(backup, 0o600)
            stream.write(original)
        print(f"BACKUP: {backup}")
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    print(f"WROTE: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    cli = parser()
    args = cli.parse_args(argv)
    if args.input and args.action != "merge":
        cli.error("--input is only valid for merge")
    if args.on_collision != "error" and args.action != "merge":
        cli.error("--on-collision is only valid for merge")
    if args.action == "merge" and not args.input:
        cli.error("merge requires at least one --input JSON")
    if args.json_path is None:
        candidates = list(Path.cwd().glob("*.hdlforge.json"))
        if len(candidates) != 1:
            cli.error("Specify --json: expected exactly one *.hdlforge.json in cwd")
        args.json_path = candidates[0]
    args.json_path = args.json_path.expanduser().absolute()
    args.ssh_config = args.ssh_config.expanduser().absolute()
    try:
        document = read_document(args.json_path) if args.json_path.exists() else {}
        selected = get_inventory(document, args.local_host, args.local_user)
        if args.action in {"export", "verify"} and selected is None:
            raise ValueError(f"No SSH inventory for {args.local_host}/{args.local_user} in {args.json_path}; import first")
        if args.action == "import":
            inventory = parse_config(args.ssh_config.read_bytes().decode("utf-8"))
            report(inventory, str(args.ssh_config))
            set_inventory(document, args.local_host, args.local_user, inventory)
        elif args.action == "merge":
            inventories = []
            if selected is not None:
                inventories.append((str(args.json_path), selected))
            for path in args.input:
                source = read_document(path.expanduser())
                incoming = get_inventory(source, args.local_host, args.local_user)
                if incoming is None:
                    raise ValueError(f"No SSH inventory for {args.local_host}/{args.local_user} in {path}")
                inventories.append((str(path), incoming))
            inventory, unresolved = merge(inventories, args.on_collision)
            if unresolved:
                print("Unresolved collisions: no files changed. Select --on-collision keep|incoming.")
                return 2
            set_inventory(document, args.local_host, args.local_user, inventory)
        else:
            inventory = selected
            collisions = report(inventory, str(args.json_path))
            new = render(inventory)
            if args.action == "export":
                return write_reviewed(args.ssh_config, new, args.dry_run, args.force)
            old = args.ssh_config.read_bytes().decode("utf-8")
            actual = parse_config(old)
            collisions |= report(actual, str(args.ssh_config))
            expected_hosts = {host.casefold(): signature(options) for host, options in inventory.items()}
            actual_hosts = {host.casefold(): signature(options) for host, options in actual.items()}
            for host, options in actual_hosts.items():
                if host in expected_hosts and options != expected_hosts[host]:
                    print(f"COLLISION: host {host}: JSON vs SSH config")
                    collisions = True
            show_diff(old, new, args.ssh_config)
            matches = actual_hosts == expected_hosts
            print(f"{'PASS' if matches and not collisions else 'FAIL'}: SSH configuration {'matches' if matches else 'differs'}; collisions={collisions}")
            return 0 if matches and not collisions else 1
        new = json.dumps(document, indent=2, ensure_ascii=False) + "\n"
        return write_reviewed(args.json_path, new, args.dry_run, args.force)
    except (OSError, ValueError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
