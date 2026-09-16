"""Live synthesis groups, individual run scopes, and their described actions."""

from urllib.parse import quote

from .project_console_commands import CATALOG
from .run_enable import blocked


ACTIONS = {name: CATALOG["run_group_actions"]["#" + name]
           for name in CATALOG["run_group_actions"] if not name.startswith("#")}


def run_key(name: str) -> str:
    return quote(name, safe="_-").replace(".", "%2E")


def children_of(synth: dict, runs: list) -> list:
    return sorted((run for run in runs if run["parent_run"] == synth["name"] and run["eligible"]
                   and run["properties"].get("IS_IMPLEMENTATION") in {"1", "true"}), key=lambda run: run["name"])


def choices(runs: list) -> dict:
    result = {"build.": "Live synthesis groups and individual runs; disabled entries remain available to enable."}
    for synth in runs:
        if synth["properties"].get("IS_SYNTHESIS") not in {"1", "true"} or not synth["eligible"]:
            continue
        prefix = "build." + run_key(synth["name"]) + "."
        state = "disabled" if blocked(synth, runs) else "enabled"
        scopes = {"": f"Group {synth['name']} [{state}]: synthesis, then enabled implementations",
                  "synthesis.": f"Synthesis only [{state}]: {synth['properties']['STATUS']}"}
        children = children_of(synth, runs)
        if children:
            result[prefix + "implementations."] = "Choose an individual implementation; its synthesis must already be complete."
        for child in children:
            state = "disabled" if blocked(child, runs) else "enabled"
            scopes["implementations." + run_key(child["name"]) + "."] = f"{child['name']} only [{state}]: {child['properties']['STATUS']}"
        for scope, description in scopes.items():
            result[prefix + scope] = description
            for action, help_text in ACTIONS.items():
                result[prefix + scope + action] = description + ". " + help_text
    return result


def canonical_path(path: str) -> str:
    """Retain old native spellings while advertising only the live build tree."""
    if path.startswith("run_groups."):
        path = "build." + path[len("run_groups."):]
        path = path.replace(".all_implementations.", ".")
        if path.endswith(".build"):
            path = path[:-len("build")] + "continue"
    return path


def selected_runs(path: str, runs: list) -> tuple[list, str]:
    path = canonical_path(path)
    if path not in choices(runs) or path.endswith("."):
        raise ValueError("Use get_groups/get_runs, then build with --group or --run and --action")
    parts = path.split(".")
    synth = next(run for run in runs if run_key(run["name"]) == parts[1])
    children = children_of(synth, runs)
    if parts[2] == "synthesis":
        return [synth], parts[-1]
    if parts[2] == "implementations":
        return [run for run in children if run_key(run["name"]) == parts[3]], parts[-1]
    return [synth, *children], parts[-1]
