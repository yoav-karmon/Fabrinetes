"""Offline example initialization and extensible non-project build lint."""

import argparse
import copy
import json
import os
from pathlib import Path
import re
import shlex
import tempfile
import sys
import zipfile

from vivado_build import file_path, normalize_run
from vivado_build_config import BUILD_HELP, RUN_NAME


def lint_layout(project: Path, output_root: Path, selector: str, run: dict) -> list[str]:
    """Check named run folders and all directly configured Tcl script paths."""
    errors = []
    names = selector.split(".")
    expected = output_root / names[0]
    resolved_root = output_root.resolve()
    resolved_synth = (output_root / names[0]).resolve()
    resolved_run = expected.resolve()
    if resolved_synth.parent != resolved_root:
        errors.append(f"{selector}: synthesis folder escapes output_root: {resolved_synth}")
    if not expected.is_dir():
        errors.append(f"{selector}: missing run folder: {expected}")
    script = run.get("script")
    if isinstance(script, str) and script:
        path = (project.parent / script).resolve()
        if path.parent != resolved_run:
            errors.append(f"{selector}: script must be directly in {expected}: {path}")
        if not path.is_relative_to(resolved_root):
            errors.append(f"{selector}: script is outside output_root: {path}")
    return errors


def lint_run(project: Path, selector: str, run: dict, stage: str) -> list[str]:
    ###########################################################################
    # Collect path defects together; schema checks can grow without Vivado.    #
    ###########################################################################
    errors = []
    paths = [("script", run.get("script"))]
    for field in ("sources",):
        for index, entry in enumerate(run.get(field, [])):
            paths.append((f"{field}[{index}]", entry if isinstance(entry, str) else entry.get("path")))
    for location, value in paths:
        if not isinstance(value, str) or not value:
            errors.append(f"{selector}: {location}: expected a file path")
        else:
            try:
                file_path(project.parent, value)
            except (OSError, ValueError) as error:
                errors.append(f"{selector}: {location}: {error}")
    if errors:
        return errors
    try:
        config = normalize_run(project, run, stage)
    except (KeyError, ValueError, TypeError, AttributeError) as error:
        return [f"{selector}: {error}"]
    for entry in config["sources"]:
        path = Path(entry["path"])
        if path.suffix.lower() == ".xcix":
            try:
                with zipfile.ZipFile(path) as archive:
                    if not any(name.endswith(".xci") for name in archive.namelist()):
                        errors.append(f"{selector}: no XCI in {path}")
            except (OSError, zipfile.BadZipFile) as error:
                errors.append(f"{selector}: invalid XCIX {path}: {error}")
    # Check literal runtime lookups against the JSON-owned input list. Dynamic
    # Tcl expressions remain runtime-validated; lint never evaluates run Tcl.
    declared = set(run.get('sources', []))
    scripts = [Path(config['script']), *[Path(entry['path']) for entry in config['sources']
                                       if Path(entry['path']).suffix == '.tcl']]
    pattern = r'::hdlforge::source_path\s+(?:"([^"\n]+)"|\{([^}\n]+)\}|([^\s\]]+))'
    for script in scripts:
        for number, line in enumerate(script.read_text().splitlines(), 1):
            if line.lstrip().startswith('#'):
                continue
            for match in re.findall(pattern, line):
                name = next(value for value in match if value)
                if '$' not in name and '[' not in name and name not in declared:
                    errors.append(f'{selector}: {script}:{number}: source_path input not declared in sources: {name}')
    return errors


def lint_project(project: Path) -> list[str]:
    project = project.resolve()
    data = json.loads(project.read_text())
    config = data.get("vivado", {}).get("non_project", {})
    errors = []
    output_root = None
    if not isinstance(config.get("output_root"), str) or not config["output_root"]:
        errors.append("vivado.non_project.output_root must be a nonempty path")
    else:
        output_root = (project.parent / config["output_root"]).resolve()
        if not output_root.is_dir():
            errors.append(f"output_root is not an existing directory: {output_root}")
    runs = config.get("runs", {})
    if not isinstance(runs, dict) or not runs:
        return errors + ["vivado.non_project.runs must contain a synthesis run"]
    for name, synthesis in runs.items():
        if not RUN_NAME.fullmatch(name):
            errors.append(f"Invalid synthesis run name: {name}")
            continue
        try:
            if output_root is not None:
                errors.extend(lint_layout(project, output_root, name, synthesis))
            errors.extend(lint_run(project, name, synthesis, synthesis.get("kind", "synth")))
            for child, implementation in synthesis.get("impl_runs", {}).items():
                if not RUN_NAME.fullmatch(child):
                    errors.append(f"Invalid implementation run name: {child}")
                    continue
                if output_root is not None:
                    errors.extend(lint_layout(project, output_root, f"{name}.{child}", implementation))
                errors.extend(lint_run(project, f"{name}.{child}", implementation, "impl"))
        except (AttributeError, TypeError, KeyError) as error:
            errors.append(f"{name}: malformed run configuration: {error}")
    return errors


def initialize_example(project: Path) -> None:
    ###########################################################################
    # Add a complete schema example without replacing existing run settings.   #
    ###########################################################################
    original = project.read_text()
    data = json.loads(original)
    example = json.loads(Path(__file__).with_name("vivado_build_example.json").read_text())
    config = data.setdefault("vivado", {}).setdefault("non_project", {})
    runs = config.setdefault("runs", {})
    if any(name in runs for name in example["runs"]):
        raise ValueError("An example run already exists; existing examples are not overwritten")
    for key, value in example.items():
        if key != "runs":
            config.setdefault(key, value)
    sample = copy.deepcopy(example["runs"]["synth_example"])
    # Rebase example snapshot inputs and Tcl references to the chosen root.
    def rebase(run):
        run["script"] = run["script"].replace("compilation/", str(config["output_root"]) + "/", 1)
        run["sources"] = [path.replace("compilation/", str(config["output_root"]) + "/", 1)
                          if path.startswith("compilation/") else path for path in run["sources"]]
        for child in run.get("impl_runs", {}).values():
            rebase(child)
    rebase(sample)
    runs["synth_example"] = sample
    ip_sample = copy.deepcopy(example["runs"]["ip_example"])
    rebase(ip_sample)
    runs["ip_example"] = ip_sample
    destination = project.parent / config["output_root"] / "synth_example"
    ip_destination = destination.parent / "ip_example"
    for folder in (destination, ip_destination):
        if folder.exists() or folder.is_symlink():
            raise ValueError(f"Example folder already exists: {folder}")
    created_files = []
    created_folders = []
    temporary = None
    try:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.mkdir()
        created_folders.append(destination)
        implementation = destination / "impl_example"
        implementation.mkdir()
        created_folders.append(implementation)
        ip_destination.mkdir()
        created_folders.append(ip_destination)
        hierarchy = destination / "ip_keep_hierarchy.xdc"
        with hierarchy.open("x") as handle:
            created_files.append(hierarchy)
            handle.write(Path(__file__).with_name("vivado_build_example_ip_keep_hierarchy.xdc").read_text())
        for stage, folder in (("synth", destination), ("impl", implementation), ("ip", ip_destination)):
            script = destination / "impl_run_example.tcl" if stage == "impl" else folder / "run.tcl"
            with script.open("x") as handle:
                created_files.append(script)
                handle.write(Path(__file__).with_name(f"vivado_build_example_{stage}.tcl").read_text()
                             .replace("compilation/", str(config["output_root"]) + "/"))
            readme = folder / "README.md"
            content = Path(__file__).with_name("vivado_build_example_README.md").read_text()
            for token, value in {"STAGE": stage, "PROJECT": project.name,
                                 "PROJECT_ARG": shlex.quote(project.name),
                                 "OUTPUT_ROOT": str(config["output_root"])}.items():
                content = content.replace("{{" + token + "}}", value)
            with readme.open("x") as handle:
                created_files.append(readme)
                handle.write(content)
        with tempfile.NamedTemporaryFile(mode="w", dir=project.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.write("\n")
        temporary.chmod(project.stat().st_mode)
        if project.read_text() != original:
            raise ValueError("Project JSON changed during example initialization")
        os.replace(temporary, project)
    except BaseException:
        for script in reversed(created_files):
            script.unlink()
        for folder in reversed(created_folders):
            folder.rmdir()
        raise
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def initialize_run_defaults(project: Path, selector: str) -> None:
    """Fill missing optional run settings without overwriting authored values."""
    original = project.read_text()
    data = json.loads(original)
    runs = data["vivado"]["non_project"]["runs"]
    selected = {}
    for name, run in runs.items():
        selected[name] = run
        for child, implementation in run.get("impl_runs", {}).items():
            selected[f"{name}.{child}"] = implementation
    prefix = "vivado.non_project.runs."
    if selector.startswith(prefix):
        selector = selector[len(prefix):].replace(".impl_runs.", ".")
    if selector != "all":
        if selector not in selected:
            raise ValueError(f"Unknown run: {selector}")
        selected = {selector: selected[selector]}
    for name, run in selected.items():
        if not run.get("script"):
            raise ValueError(f"{name}: supply required script; initialization will not invent design inputs")
        run.setdefault("sources", [])
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", dir=project.parent, delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(data, handle, indent=2)
            handle.write("\n")
        temporary.chmod(project.stat().st_mode)
        if project.read_text() != original:
            raise ValueError("Project JSON changed during initialization")
        os.replace(temporary, project)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()
    print(f"Initialized missing settings for {len(selected)} runs in {project}; existing values preserved")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, epilog=BUILD_HELP, formatter_class=argparse.RawDescriptionHelpFormatter, allow_abbrev=False)
    parser.add_argument("--project")
    actions = parser.add_mutually_exclusive_group(required=True)
    actions.add_argument("--init_build_example", action="store_true")
    actions.add_argument("--init_build", metavar="RUN_OR_ALL", help="Fill missing settings in a run selector, JSON run path, or all runs")
    actions.add_argument("--create", choices=("syth_imp_example", "synth_impl_example"))
    actions.add_argument("--build_lint", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.project:
            project = Path(args.project).resolve()
        else:
            candidates = list(Path.cwd().glob("*.hdlforge.json"))
            if len(candidates) != 1:
                raise ValueError("Select a project with --project <file.hdlforge.json>")
            project = candidates[0].resolve()
        if args.init_build:
            initialize_run_defaults(project, args.init_build)
            return 0
        if args.init_build_example or args.create:
            initialize_example(project)
            print(f"Added synth_example, nested impl_example, and ip_example to {project}")
            print("Created all three run.tcl examples under output_root, including private-copy IP regeneration.")
            print("Each example folder includes a README.md with commands, settings and snapshots and logical latest selection.")
            print("Replace example input paths and select your FPGA part before building; no Vivado execution.")
            print("Then build ip_example first, synth_example second, and synth_example.impl_example last.")
            print("Synthesis snapshots inputs and implementation settings; implementation reuses that snapshot.")
            print("WARNING: Customize synth_example/ip_keep_hierarchy.xdc: replace the placeholder IP reference and uncomment KEEP_HIERARCHY SOFT assignments where needed. The template applies no hierarchy constraints until edited.")
            return 0
        errors = lint_project(project)
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        print(f"Build lint: {'FAIL' if errors else 'PASS'} ({len(errors)} defects); no Vivado execution")
        return 1 if errors else 0
    except (OSError, ValueError, TypeError, AttributeError) as error:
        print(f"Build configuration error: {error}", file=sys.stderr)
        return 1
