#!/usr/bin/env python3
"""
Static Vivado project Tcl editor for HDLForge.
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ProjectTclEditError(Exception):
    """Project Tcl edit failed with a user-facing message."""


@dataclass(frozen=True)
class EditResult:
    action: str
    count: int
    tcl_path: Path


def usage_text() -> str:
    return """Usage:
  hdlforge --tool vivado --add_file_to_project_tcl --project_tcl_json_file edits.json
  hdlforge --tool vivado --remove_file_from_project_tcl --project_tcl_json '{"files":["sources/RTL/foo.sv"]}'
  hdlforge --tool vivado --add_run_to_project_tcl --project_tcl_json_file runs.json
  hdlforge --tool vivado --remove_run_from_project_tcl --project_tcl_json '{"runs":["impl_extra"]}'

JSON examples:
  {"files":[{"path":"sources/RTL/foo/foo.sv","fileset":"sources_1"}]}
  {"files":["sources/RTL/foo/foo.sv"]}
  {"synth_runs":[{"name":"synth_debug","more_options":"{-generic DEBUG=1}"}]}
  {"impl_runs":[{"name":"impl_timing","parent_run":"synth_1","strategy":"Performance_Explore"}]}
  {"runs":["impl_timing"]}

If --project_tcl_json and --project_tcl_json_file are omitted, set this in the
project JSON:
  "vivado": {"external_config": {"project_tcl_edit_json": "project_tcl_edits.json"}}
"""


def fail(message: str) -> None:
    print(f"[!x!] {message}", file=sys.stderr)
    print(usage_text(), file=sys.stderr)
    raise SystemExit(1)


def load_edit_json(json_text: str | None, json_file: str | None, project_root: Path, default_json_file: str | None) -> dict[str, Any]:
    if json_text and json_file:
        fail("Use either --project_tcl_json or --project_tcl_json_file, not both.")

    if json_text:
        source = "--project_tcl_json"
        raw_text = json_text
    else:
        json_path_text = json_file or default_json_file
        if not json_path_text:
            fail("Project Tcl edit JSON was not provided.")
        json_path = Path(json_path_text)
        if not json_path.is_absolute():
            json_path = project_root / json_path
        source = str(json_path)
        if not json_path.exists():
            fail(f"Project Tcl edit JSON file not found: {json_path}")
        raw_text = json_path.read_text()

    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        fail(f"Invalid JSON in {source}: {exc}")

    if not isinstance(data, dict):
        fail("Project Tcl edit JSON must be a dictionary/object.")
    return data


def edit_project_tcl(action: str, tcl_path: Path, data: dict[str, Any]) -> EditResult:
    if not tcl_path.exists():
        fail(f"Project Tcl file not found: {tcl_path}")

    editor = ProjectTclEditor(tcl_path)
    if action == "add_file":
        count = editor.add_files(_extract_files(data))
    elif action == "remove_file":
        count = editor.remove_files(_extract_file_paths(data))
    elif action == "add_run":
        count = editor.add_runs(data)
    elif action == "remove_run":
        count = editor.remove_runs(_extract_run_names(data))
    else:
        fail(f"Unknown project Tcl edit action: {action}")

    editor.write()
    return EditResult(action=action, count=count, tcl_path=tcl_path)


class ProjectTclEditor:
    def __init__(self, tcl_path: Path):
        self.tcl_path = tcl_path
        self.text = tcl_path.read_text()

    def write(self) -> None:
        self.tcl_path.write_text(self.text)

    def add_files(self, files: list[dict[str, Any]]) -> int:
        count = 0
        for file_entry in files:
            path = _clean_project_path(file_entry.get("path") or file_entry.get("file"))
            fileset = str(file_entry.get("fileset", _default_fileset(path)))
            if _path_exists_in_tcl(self.text, path):
                print(f"[i] File already exists in project Tcl, skipping: {path}")
                continue
            self.text = _insert_file_in_add_list(self.text, path, fileset)
            self.text = _insert_file_property_block(self.text, path, fileset, file_entry)
            count += 1
        return count

    def remove_files(self, paths: list[str]) -> int:
        count = 0
        for path in paths:
            clean_path = _clean_project_path(path)
            before = self.text
            self.text = _remove_file_from_add_list(self.text, clean_path)
            self.text = _remove_file_property_block(self.text, clean_path)
            if self.text == before:
                print(f"[i] File was not found in project Tcl, skipping: {clean_path}")
                continue
            count += 1
        return count

    def add_runs(self, data: dict[str, Any]) -> int:
        count = 0
        for run in _extract_runs(data, "synth"):
            name = _required_name(run, "synth run")
            if _run_exists_in_tcl(self.text, name):
                print(f"[i] Run already exists in project Tcl, skipping: {name}")
                continue
            self.text = _insert_before_marker(self.text, "# set the current synth run", _render_synth_run(run))
            count += 1
        for run in _extract_runs(data, "impl"):
            name = _required_name(run, "implementation run")
            if _run_exists_in_tcl(self.text, name):
                print(f"[i] Run already exists in project Tcl, skipping: {name}")
                continue
            self.text = _insert_before_marker(self.text, "# set the current impl run", _render_impl_run(run))
            count += 1
        return count

    def remove_runs(self, run_names: list[str]) -> int:
        count = 0
        for run_name in run_names:
            before = self.text
            self.text = _remove_run_block(self.text, run_name)
            if self.text == before:
                print(f"[i] Run was not found in project Tcl, skipping: {run_name}")
                continue
            count += 1
        return count


def _extract_files(data: dict[str, Any]) -> list[dict[str, Any]]:
    raw_files = data.get("files")
    if raw_files is None:
        fail("JSON for file add must contain a 'files' list.")
    if not isinstance(raw_files, list):
        fail("'files' must be a list.")
    files = []
    for item in raw_files:
        if isinstance(item, str):
            files.append({"path": item})
        elif isinstance(item, dict):
            files.append(item)
        else:
            fail("Each file entry must be a string path or dictionary.")
    return files


def _extract_file_paths(data: dict[str, Any]) -> list[str]:
    return [_clean_project_path(item.get("path") if isinstance(item, dict) else item) for item in _extract_files(data)]


def _extract_runs(data: dict[str, Any], run_type: str) -> list[dict[str, Any]]:
    key = "synth_runs" if run_type == "synth" else "impl_runs"
    raw_runs = data.get(key, [])
    if not isinstance(raw_runs, list):
        fail(f"'{key}' must be a list.")

    typed_runs = []
    for item in raw_runs:
        if not isinstance(item, dict):
            fail(f"Each '{key}' entry must be a dictionary.")
        typed_runs.append(item)

    for item in data.get("runs", []):
        if isinstance(item, dict) and item.get("type") == run_type:
            typed_runs.append(item)
    return typed_runs


def _extract_run_names(data: dict[str, Any]) -> list[str]:
    raw_runs = data.get("runs")
    if raw_runs is None:
        raw_runs = data.get("run_names")
    if raw_runs is None:
        fail("JSON for run remove must contain 'runs' or 'run_names'.")
    if not isinstance(raw_runs, list):
        fail("'runs' must be a list.")
    names = []
    for item in raw_runs:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict):
            names.append(_required_name(item, "run"))
        else:
            fail("Each run entry must be a string name or dictionary.")
    return names


def _clean_project_path(path_value: Any) -> str:
    if not isinstance(path_value, str) or not path_value.strip():
        fail("File path must be a non-empty string.")
    path = path_value.strip()
    path = path.removeprefix("./")
    for prefix in ("${origin_dir}/", "$origin_dir/"):
        if path.startswith(prefix):
            path = path[len(prefix) :]
    return path


def _required_name(run: dict[str, Any], label: str) -> str:
    name = run.get("name")
    if not isinstance(name, str) or not name.strip():
        fail(f"{label} entry must contain a non-empty 'name'.")
    return name.strip()


def _default_fileset(path: str) -> str:
    return "constrs_1" if path.endswith(".xdc") else "sources_1"


def _tcl_quote(value: Any) -> str:
    if value is None:
        return '""'
    text = str(value)
    if text.startswith("{") and text.endswith("}"):
        return text
    return f'"{text}"'


def _path_exists_in_tcl(text: str, path: str) -> bool:
    return f"/{path}" in text or f'"$origin_dir/{path}"' in text or f'"${{origin_dir}}/{path}"' in text


def _run_exists_in_tcl(text: str, run_name: str) -> bool:
    return re.search(rf"create_run\s+-name\s+{re.escape(run_name)}(\s|$)", text) is not None


def _insert_before_marker(text: str, marker: str, block: str) -> str:
    index = text.find(marker)
    if index == -1:
        fail(f"Could not find project Tcl insertion marker: {marker}")
    return text[:index].rstrip() + "\n\n" + block.rstrip() + "\n\n" + text[index:]


def _insert_file_in_add_list(text: str, path: str, fileset: str) -> str:
    if fileset != "sources_1":
        return text

    fileset_marker = f"set obj [get_filesets {fileset}]"
    marker_index = text.find(fileset_marker)
    if marker_index == -1:
        fail(f"Could not find fileset in project Tcl: {fileset}")

    list_index = text.find("set files [list \\", marker_index)
    if list_index == -1:
        fail(f"Could not find add_files list for fileset: {fileset}")
    list_end = text.find("]\nadd_files -norecurse -fileset $obj $files", list_index)
    if list_end == -1:
        fail(f"Could not find end of add_files list for fileset: {fileset}")

    line = f' [file normalize "${{origin_dir}}/{path}"] \\\n'
    return text[:list_end] + line + text[list_end:]


def _insert_file_property_block(text: str, path: str, fileset: str, file_entry: dict[str, Any]) -> str:
    block = _render_file_property_block(path, fileset, file_entry)
    marker = "# Set 'sources_1' fileset file properties for local files"
    if fileset == "constrs_1":
        marker = "# Set 'constrs_1' fileset properties"
    return _insert_before_marker(text, marker, block)


def _remove_file_from_add_list(text: str, path: str) -> str:
    pattern = re.compile(rf"^ \[file normalize \"\$\{{?origin_dir\}}?/{re.escape(path)}\"\] \\\n", re.MULTILINE)
    return pattern.sub("", text)


def _remove_file_property_block(text: str, path: str) -> str:
    pattern = re.compile(
        rf"\n?(?:# Add/Import constrs file and set constrs file properties\n"
        rf"set file \"\[file normalize \"\$origin_dir/{re.escape(path)}\"\]\"\n"
        r"set file_added \[add_files -norecurse -fileset \$obj \[list \$file\]\]\n)?"
        rf"set file \"\$origin_dir/{re.escape(path)}\"\n"
        r"set file \[file normalize \$file\]\n"
        r"set file_obj \[get_files -of_objects \[get_filesets [^\]]+\] \[list \"\*\$file\"\]\]\n"
        r"(?:(?!\nset file \"\$origin_dir/|\n# Set '|\n# Create ').*\n)*",
        re.MULTILINE,
    )
    return pattern.sub("\n", text)


def _render_file_property_block(path: str, fileset: str, file_entry: dict[str, Any]) -> str:
    properties = dict(file_entry.get("properties", {}))
    file_type = file_entry.get("file_type") or _default_file_type(path)
    if file_type:
        properties.setdefault("file_type", file_type)

    if path.endswith(".xci"):
        properties.setdefault("generate_files_for_reference", "0")
        properties.setdefault("generate_synth_checkpoint", "1")
        properties.setdefault("synth_checkpoint_mode", "Singular")
        properties.setdefault("registered_with_manager", "1")

    properties.setdefault("is_enabled", "1")
    properties.setdefault("is_global_include", "0")
    properties.setdefault("path_mode", "RelativeFirst")
    if fileset == "sources_1":
        properties.setdefault("library", "xil_defaultlib")
        properties.setdefault("used_in", "synthesis implementation simulation")
        properties.setdefault("used_in_implementation", "1")
        properties.setdefault("used_in_simulation", "1")
        properties.setdefault("used_in_synthesis", "1")
    else:
        properties.setdefault("library", "xil_defaultlib")
        properties.setdefault("processing_order", "NORMAL")
        properties.setdefault("scoped_to_cells", "")
        properties.setdefault("scoped_to_ref", "")
        properties.setdefault("used_in", "synthesis implementation")
        properties.setdefault("used_in_implementation", "1")
        properties.setdefault("used_in_synthesis", "1")

    lines = [
        f'set file "$origin_dir/{path}"',
        "set file [file normalize $file]",
        f'set file_obj [get_files -of_objects [get_filesets {fileset}] [list "*$file"]]',
    ]
    if fileset == "constrs_1":
        lines = [
            "# Add/Import constrs file and set constrs file properties",
            f'set file "[file normalize "$origin_dir/{path}"]"',
            "set file_added [add_files -norecurse -fileset $obj [list $file]]",
            f'set file "$origin_dir/{path}"',
            "set file [file normalize $file]",
            f'set file_obj [get_files -of_objects [get_filesets {fileset}] [list "*$file"]]',
        ]
    for name, value in properties.items():
        if name == "generate_synth_checkpoint":
            lines.append('if { ![get_property "is_locked" $file_obj] } {')
            lines.append(f'  set_property -name "{name}" -value {_tcl_quote(value)} -objects $file_obj')
            lines.append("}")
        elif name == "synth_checkpoint_mode":
            lines.append('if { ![get_property "is_locked" $file_obj] } {')
            lines.append(f'  set_property -name "{name}" -value {_tcl_quote(value)} -objects $file_obj')
            lines.append("}")
        else:
            lines.append(f'set_property -name "{name}" -value {_tcl_quote(value)} -objects $file_obj')
    return "\n".join(lines)


def _default_file_type(path: str) -> str | None:
    suffix = Path(path).suffix.lower()
    if suffix == ".sv":
        return "SystemVerilog"
    if suffix in {".v", ".vh"}:
        return "Verilog"
    if suffix in {".vhd", ".vhdl"}:
        return "VHDL"
    if suffix == ".xdc":
        return "XDC"
    return None


def _render_synth_run(run: dict[str, Any]) -> str:
    name = _required_name(run, "synth run")
    part = run.get("part", "xcvu9p-fsgd2104-3-e")
    flow = run.get("flow", "Vivado Synthesis 2025")
    strategy = run.get("strategy", "Vivado Synthesis Defaults")
    constrset = run.get("constrset", "constrs_1")
    report_strategy = run.get("report_strategy", "No Reports")
    properties = {
        "constrset": constrset,
        "description": strategy,
        "flow": flow,
        "part": part,
        "srcset": run.get("srcset", "sources_1"),
        "strategy": strategy,
        "steps.synth_design.args.flatten_hierarchy": run.get("flatten_hierarchy", "rebuilt"),
        "steps.synth_design.args.gated_clock_conversion": run.get("gated_clock_conversion", "off"),
        "steps.synth_design.args.directive": run.get("directive", "Default"),
        "steps.synth_design.args.more options": run.get("more_options", ""),
    }
    properties.update(run.get("properties", {}))
    return _render_run_block(name, "synth", part, flow, strategy, report_strategy, constrset, None, properties)


def _render_impl_run(run: dict[str, Any]) -> str:
    name = _required_name(run, "implementation run")
    parent_run = run.get("parent_run", run.get("parent", "synth_1"))
    part = run.get("part", "xcvu9p-fsgd2104-3-e")
    flow = run.get("flow", "Vivado Implementation 2025")
    strategy = run.get("strategy", "Performance_Explore")
    constrset = run.get("constrset", "constrs_1")
    report_strategy = run.get("report_strategy", "No Reports")
    properties = {
        "constrset": constrset,
        "description": run.get("description", "Uses multiple algorithms for optimization, placement, and routing to get potentially better results."),
        "flow": flow,
        "part": part,
        "srcset": run.get("srcset", "sources_1"),
        "strategy": strategy,
        "steps.opt_design.is_enabled": run.get("opt_design_enabled", "1"),
        "steps.opt_design.args.directive": run.get("opt_directive", "Explore"),
        "steps.place_design.args.directive": run.get("place_directive", "Explore"),
        "steps.phys_opt_design.is_enabled": run.get("phys_opt_design_enabled", "1"),
        "steps.phys_opt_design.args.directive": run.get("phys_opt_directive", "Explore"),
        "steps.route_design.args.directive": run.get("route_directive", "Explore"),
        "steps.write_bitstream.args.verbose": run.get("write_bitstream_verbose", "0"),
    }
    properties.update(run.get("properties", {}))
    return _render_run_block(name, "impl", part, flow, strategy, report_strategy, constrset, parent_run, properties)


def _render_run_block(name: str, run_type: str, part: str, flow: str, strategy: str, report_strategy: str, constrset: str, parent_run: str | None, properties: dict[str, Any]) -> str:
    create_args = [
        f"create_run -name {name}",
        f"-part {part}",
        f"-flow {{{flow}}}",
        f'-strategy "{strategy}"',
        f"-report_strategy {{{report_strategy}}}",
        f"-constrset {constrset}",
    ]
    if parent_run:
        create_args.append(f"-parent_run {parent_run}")

    lines = [
        f"# Create '{name}' run (if not found)",
        f'if {{[string equal [get_runs -quiet {name}] ""]}} {{',
        "    " + " ".join(create_args),
        "} else {",
        f'  set_property strategy "{strategy}" [get_runs {name}]',
        f'  set_property flow "{flow}" [get_runs {name}]',
        "}",
        f"set obj [get_runs {name}]",
        "set_property set_report_strategy_name 1 $obj",
        f"set_property report_strategy {{{report_strategy.replace('No Reports', 'Vivado Synthesis Default Reports' if run_type == 'synth' else 'Vivado Implementation Default Reports')}}} $obj",
        "set_property set_report_strategy_name 0 $obj",
        f"set obj [get_runs {name}]",
    ]
    for prop_name, prop_value in properties.items():
        lines.append(f'set_property -name "{prop_name}" -value {_tcl_quote(prop_value)} -objects $obj')
    return "\n".join(lines)


def _remove_run_block(text: str, run_name: str) -> str:
    pattern = re.compile(
        rf"\n?# Create '{re.escape(run_name)}' run \(if not found\)\n"
        r"(?:(?!\n# Create '|\n# set the current (?:synth|impl) run).*\n)*",
        re.MULTILINE,
    )
    return pattern.sub("\n", text)
