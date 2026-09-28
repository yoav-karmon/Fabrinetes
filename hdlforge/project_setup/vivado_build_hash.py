"""Content fingerprints for saved producer inputs and consumer freshness checks."""

import hashlib
import json
from pathlib import Path


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
    info = Path(config["output"]) / "info"
    copied = json.loads((info / "input_manifest.json").read_text())
    data = json.loads((info / "project.json").read_text())
    selector = config["selector"]
    run = data["vivado"]["non_project"]["runs"][selector]
    record = {
        "version": 1, "project": str(project.resolve()), "run": selector,
        "definition": run,
        "sources": {source: hash_source(Path(saved)) for source, saved in copied.items()},
    }
    (info / "source_hashes.json").write_text(json.dumps(record, indent=2) + "\n")


def verify_source_hashes(latest: Path) -> None:
    """Reject publications with missing metadata or changed producer inputs."""
    manifest = latest / "info/source_hashes.json"
    if not manifest.is_file():
        raise ValueError(f"Missing source hashes in {latest}; regenerate the producer IP")
    record = json.loads(manifest.read_text())
    if record.get("version") != 1 or not record.get("sources"):
        raise ValueError(f"Invalid source hashes: {manifest}; regenerate the producer IP")
    project = Path(record["project"])
    current = json.loads(project.read_text())["vivado"]["non_project"]["runs"].get(record["run"])
    if current != record["definition"]:
        raise ValueError(f"Producer JSON run changed: {project}: {record['run']}; regenerate the IP")
    for source, expected in record["sources"].items():
        if hash_source(Path(source)) != expected:
            raise ValueError(f"Stale IP publication {latest}: source changed: {source}; regenerate the IP")
