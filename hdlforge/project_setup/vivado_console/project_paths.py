"""Discover the project JSON identifying a persistent Tcl console."""
from pathlib import Path

def discover_project_json(project_dir: Path) -> Path:
    """Find the one HDLForge project JSON owned by the current directory."""
    candidates = sorted(project_dir.glob("*.hdlforge.json"))
    if len(candidates) != 1:
        raise ValueError(
            f"expected exactly one *.hdlforge.json in {project_dir}, "
            f"found {len(candidates)}"
        )
    return candidates[0].resolve()

