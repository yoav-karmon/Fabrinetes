"""Host-keyed SSH dictionaries for a local host/user environment."""

import copy
import json
import re
import shlex
from pathlib import Path


def parse_config(text: str) -> dict:
    """Import literal Host blocks, rejecting constructs a host map cannot preserve."""
    result = {}
    current = None
    seen_hosts = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.fullmatch(r"([^\s=]+)(?:\s*=\s*|\s+)(.*)", line)
        if not match:
            raise ValueError(f"Invalid SSH directive: {line}")
        name, value = match.groups()
        tokens = shlex.split(value, comments=True)
        if name.lower() == "host":
            if len(tokens) != 1 or any(char in tokens[0] for char in "*?!"):
                raise ValueError("Inventory requires one literal connection Host per block")
            host = tokens[0]
            key = host.casefold()
            if key in seen_hosts:
                raise ValueError(f"DUPLICATION/COLLISION: repeated Host {host}; combine its blocks before import")
            seen_hosts[key] = host
            current = {}
            result[host] = current
        elif name.lower() in {"include", "match"} or current is None:
            raise ValueError(f"Host inventory cannot preserve global/conditional directive {name}; no files changed")
        else:
            if not tokens:
                raise ValueError(f"Missing value for {name}")
            # Keep quoting for commands and paths; Port alone has a numeric JSON type.
            stored = int(value) if name.lower() == "port" and value.isdigit() else value
            existing = next((key for key in current if key.lower() == name.lower()), None)
            if existing is None:
                current[name] = stored
            else:
                previous = current[existing]
                current[existing] = [*previous, stored] if isinstance(previous, list) else [previous, stored]
    render(result)
    return result


def render(inventory: dict) -> str:
    """Render ordered host/config dictionaries; arrays represent repeated directives."""
    if not isinstance(inventory, dict):
        raise ValueError("ssh_config must be a destination-host dictionary")
    lines = []
    for host, options in inventory.items():
        if not isinstance(host, str) or not re.fullmatch(r"[^\s#'\"=*?!\x00]+", host):
            raise ValueError(f"Invalid literal Host: {host}")
        if not isinstance(options, dict):
            raise ValueError(f"Host {host} requires a configuration dictionary")
        lines.append(f"Host {host}\n")
        seen_options = set()
        for name, values in options.items():
            if not re.fullmatch(r"[A-Za-z][A-Za-z0-9]*", name) or name.lower() in {"host", "match", "include"}:
                raise ValueError(f"Invalid host option: {name}")
            if name.lower() in seen_options:
                raise ValueError(f"Duplicate option {name} for {host}; use an array for repeated values")
            seen_options.add(name.lower())
            values = values if isinstance(values, list) else [values]
            if not values:
                raise ValueError(f"Empty values for {name}")
            for value in values:
                if not isinstance(value, (str, int)) or isinstance(value, bool) or not str(value) or any(char in str(value) for char in "\r\n\x00"):
                    raise ValueError(f"{name} requires a nonempty single-line string or integer")
                lines.append(f"    {name} {value}\n")
        lines.append("\n")
    return "".join(lines)


def unique_object(pairs: list) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_document(path: Path) -> dict:
    document = json.loads(path.read_text(), object_pairs_hook=unique_object)
    if not isinstance(document, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return document


def signature(options: dict) -> dict:
    """Compare option names case-insensitively, preserving repeated-value order."""
    return {name.lower(): [shlex.split(str(value), comments=True) for value in (values if isinstance(values, list) else [values])]
            for name, values in options.items()}


def report(inventory: dict, label: str) -> bool:
    render(inventory)
    seen = {}
    collision = False
    for host, options in inventory.items():
        key = host.casefold()
        value = signature(options)
        if key in seen:
            kind = "DUPLICATE" if value == seen[key] else "COLLISION"
            print(f"{kind}: {label}: host {host}")
            collision |= kind == "COLLISION"
        seen[key] = value
    return collision


def merge(inventories: list[tuple[str, dict]], resolution: str) -> tuple[dict, bool]:
    """Merge by connection Host and report all duplicates/conflicts with sources."""
    result = {}
    seen = {}
    unresolved = False
    for label, inventory in inventories:
        render(inventory)
        for host, options in inventory.items():
            key = host.casefold()
            if key in seen:
                previous_host, previous_label = seen[key]
                identical = signature(result[previous_host]) == signature(options)
                print(f"{'DUPLICATE' if identical else 'COLLISION'}: host {key}: {previous_label} vs {label}")
                if not identical:
                    unresolved |= resolution == "error"
                    if resolution == "incoming":
                        result[previous_host] = copy.deepcopy(options)
                        seen[key] = previous_host, label
            else:
                result[host] = copy.deepcopy(options)
                seen[key] = host, label
    return result, unresolved


def get_inventory(document: dict, local_host: str, local_user: str) -> dict | None:
    """Select exactly one local environment without falling back to another owner."""
    environment = document.get("settings", {}).get("env", {}).get(local_host, {}).get(local_user, {})
    inventory = environment.get("ssh_config")
    if inventory is not None:
        render(inventory)
    return inventory


def set_inventory(document: dict, local_host: str, local_user: str, inventory: dict) -> None:
    render(inventory)
    document.setdefault("settings", {}).setdefault("env", {}).setdefault(local_host, {}).setdefault(local_user, {})["ssh_config"] = inventory
