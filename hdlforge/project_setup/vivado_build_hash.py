"""Content fingerprints for saved producer inputs and consumer freshness checks."""

import hashlib
import json
from pathlib import Path

from vivado_run_tree import discover_runs, run_definition, run_tree


def hash_source(path: Path) -> str:
    """SHA-256 of a file or a sorted directory tree, independent of timestamps."""
    path = Path(path)
    digest = hashlib.sha256()
    if path.is_file():
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    elif path.is_dir():
        for child in sorted(path.rglob("*")):
            relative = child.relative_to(path).as_posix().encode()
            digest.update(len(relative).to_bytes(8, "big") + relative)
            digest.update(b"D" if child.is_dir() else b"F")
            if child.is_file():
                digest.update(bytes.fromhex(hash_source(child)))
    else:
        raise ValueError(f"Missing source: {path}")
    return digest.hexdigest()


def record_source_hashes(project: Path, config: dict) -> None:
    """Record hashes of frozen inputs, before Vivado can modify its work copies."""
    data = json.loads(project.read_text())
    selector = config["selector"]
    config['source_hashes'] = {
        "version": 1, "project": str(project.resolve()), "run": selector,
        "definition": run_definition(run_tree(data), selector),
        "sources": {entry['original']: entry['sha256'] for entry in config['inputs']},
    }


def verify_source_hashes(producer: Path) -> None:
    """Reject producer runs with missing metadata or changed producer inputs."""
    manifest = producer / 'manifest.json'
    if manifest.is_file():
        record = json.loads(manifest.read_text()).get('source_hashes', {})
    else:
        manifest = producer / 'logs/source_hashes.json'
        record = json.loads(manifest.read_text())
    if record.get("version") != 1 or not record.get("sources"):
        raise ValueError(f"Invalid source hashes: {manifest}; regenerate the producer IP")
    project = Path(record["project"])
    tree = run_tree(json.loads(project.read_text()))
    try:
        current = dict(run_definition(tree, record["run"]))
    except ValueError:
        # Grouping is CLI organization, not an IP input change. Locate a moved
        # definition by its unchanged script, never by a possibly shared leaf.
        matches = [run for run in discover_runs(tree).values()
                   if run.get('script') == record['definition'].get('script')]
        if len(matches) != 1:
            raise ValueError(f"Cannot identify moved producer run: {record['run']}; expected one matching script") from None
        current = dict(matches[0])
    previous = dict(record["definition"])
    previous.pop("publish_latest", None)  # Ignore the retired copying switch in historical metadata.
    # The discovery marker does not change producer inputs or the generated IP.
    current.pop("is_hdlforge_run", None)
    previous.pop("is_hdlforge_run", None)
    # Release placement is metadata, independent of the produced design.
    current.pop("release_root", None)
    previous.pop("release_root", None)
    if current != previous:
        raise ValueError(f"Producer JSON run changed: {project}: {record['run']}; regenerate the IP")
    for source, expected in record["sources"].items():
        if hash_source(Path(source)) != expected:
            raise ValueError(f"Stale IP run {producer}: source changed: {source}; regenerate the IP")
