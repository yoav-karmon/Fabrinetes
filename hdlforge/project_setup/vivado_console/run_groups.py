"""Reusable run families and inventory comparisons for project-console views."""


def group_runs(runs: list) -> list:
    """Return named families, ordered parent first, without dropping any runs."""
    by_name = {run["name"]: run for run in runs}
    children = {}
    for run in runs:
        children.setdefault(run.get("parent_run"), []).append(run["name"])
    displayed = set()
    groups = []

    def append_family(name: str, family: list) -> None:
        if name in displayed:
            return
        displayed.add(name)
        family.append(by_name[name])
        for child in sorted(children.get(name, [])):
            append_family(child, family)

    roots = sorted(run["name"] for run in runs
                   if not run.get("parent_run") or run["parent_run"] not in by_name)
    # The second pass also retains malformed cycles and incomplete selections.
    for name in roots + sorted(by_name):
        if name in displayed:
            continue
        parent = by_name[name].get("parent_run")
        missing_parent = parent and parent not in by_name
        title = f"{parent} (not in this selection)" if missing_parent else name
        family = []
        append_family(name, family)
        if missing_parent:
            for sibling in sorted(children[parent]):
                append_family(sibling, family)
        groups.append((title, family))
    return groups


def changed_runs(previous: dict, current: dict) -> dict:
    """Describe each changed run once, including parent and error changes."""
    old_runs = {run["name"]: run for run in previous.get("runs", [])}
    changes = {}
    for run in current["runs"]:
        name = run["name"]
        old = old_runs.pop(name, None)
        if old is None:
            changes[name] = ("Added", "-")
            continue
        count = int(old.get("parent_run") != run.get("parent_run"))
        for group in ("properties", "property_errors"):
            before, after = old.get(group, {}), run.get(group, {})
            count += sum(key not in before or key not in after or before[key] != after[key]
                         for key in before.keys() | after.keys())
        if count:
            changes[name] = ("Updated", count)
    changes.update((name, ("Removed", "-")) for name in sorted(old_runs))
    return changes
