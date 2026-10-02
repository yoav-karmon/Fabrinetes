#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path

from table_formatter import create_matrix_table_from_data
from vivado_build_selector import first_path_component, parse_selector, selector_choices
from vivado_build_config import ARTIFACT_FLAGS, build_names, synthesis_timestamps

import hdlforge_command_tree as command_tree

SCHEMA_ERROR = None
try:
    NATIVE_HELP = json.loads(Path(__file__).with_name("native_command_help.json").read_text())
    command_tree.validate(NATIVE_HELP["tree"])
except (OSError, ValueError, KeyError, TypeError) as error:
    SCHEMA_ERROR = str(error)
    NATIVE_HELP = {"tree": {"commands": {}, "master_flags": {}}}

@dataclass
class CompletionResult:
    completions: list[str]
    filenames: bool = False
    nospace: bool = False


@dataclass
class ParsedState:
    tokens: list[str]
    cwd: Path
    project_file: Path | None = None
    seen: set[str] | None = None


def unique(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def complete_words(cur: str, words: list[str]) -> CompletionResult:
    return CompletionResult([word for word in words if word.startswith(cur)])


def complete_csv_words(cur: str, words: list[str]) -> CompletionResult:
    used = [part for part in cur.split(",")[:-1] if part]
    tail = cur.split(",")[-1] if cur else ""
    prefix = ",".join(used)
    out = []
    for word in words:
        if word in used:
            continue
        if not word.startswith(tail):
            continue
        out.append(f"{prefix},{word}" if prefix else word)
    return CompletionResult(out)


def _typed_dir_and_prefix(cur: str) -> tuple[str, str]:
    if "/" in cur:
        typed_dir, prefix = cur.rsplit("/", 1)
        return typed_dir, prefix
    return "", cur


def complete_path(cur: str, base_dir: Path, *, suffixes: tuple[str, ...] | None = None) -> CompletionResult:
    typed_dir, prefix = _typed_dir_and_prefix(cur)
    search_dir = Path(os.path.expanduser(typed_dir or "."))
    if not search_dir.is_absolute():
        search_dir = base_dir / search_dir
    display_dir = f"{typed_dir}/" if typed_dir else ""
    completions: list[str] = []

    try:
        entries = sorted(search_dir.iterdir(), key=lambda entry: entry.name)
    except OSError:
        return CompletionResult([], filenames=True)

    for entry in entries:
        name = entry.name
        if not name.startswith(prefix):
            continue
        if entry.is_dir():
            completions.append(f"{display_dir}{name}")
            continue
        if suffixes and not any(name.endswith(suffix) for suffix in suffixes):
            continue
        completions.append(f"{display_dir}{name}")

    return CompletionResult(completions, filenames=True)


def load_json(path: Path) -> dict | None:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def get_explicit_flag_values(tokens: list[str], flag: str) -> list[str]:
    values: list[str] = []
    idx = 0
    while idx < len(tokens):
        token = tokens[idx]
        if token == flag and idx + 1 < len(tokens):
            values.append(tokens[idx + 1])
            idx += 2
            continue
        if token.startswith(f"{flag}="):
            values.append(token.split("=", 1)[1])
        idx += 1
    return values


def detect_project_file(tokens: list[str], cwd: Path) -> Path | None:
    return command_tree.project_file(tokens, cwd)


def project_json_data(state: ParsedState) -> dict | None:
    if not state.project_file or state.project_file.suffix != ".json":
        return None
    return load_json(state.project_file)


def get_sim_targets(state: ParsedState) -> list[str]:
    data = project_json_data(state)
    if not data:
        return []

    verilator = data.get("verilator") or {}
    verilator_cfg = (verilator.get("config") or {})
    sim_targets = verilator_cfg.get("sim_targets") or verilator.get("sim_targets") or []
    out: list[str] = []

    if isinstance(sim_targets, dict):
        for name, target in sim_targets.items():
            if isinstance(name, str) and isinstance(target, dict):
                out.append(name)
        return unique(out)

    for target in sim_targets:
        name = (target or {}).get("name")
        if isinstance(name, str):
            out.append(name)
    return unique(out)


def get_verilator_flag_values(state: ParsedState) -> list[str]:
    data = project_json_data(state)
    if not data:
        return []

    verilator_cfg = ((data.get("verilator") or {}).get("config") or {})
    build_args = verilator_cfg.get("build_args") or {}
    flag_values = build_args.get("verilator_flags") or []
    return unique([str(flag) for flag in flag_values if isinstance(flag, (str, int, float))])


def complete_verilator_flags(cur: str, state: ParsedState) -> CompletionResult:
    return complete_words(cur, get_verilator_flag_values(state))


def list_interfaces() -> list[str]:
    try:
        result = subprocess.run(
            ["ip", "-o", "link", "show"],
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return []

    interfaces: list[str] = []
    for line in result.stdout.splitlines():
        parts = line.split(": ", 1)
        if len(parts) != 2:
            continue
        iface = parts[1].split("@", 1)[0].strip()
        if iface:
            interfaces.append(iface)
    return unique(interfaces)


def complete_dotted_paths(all_paths: list[str], cur: str) -> CompletionResult:
    if not all_paths:
        return CompletionResult([])

    exact_branch_prefix = ""
    if cur:
        for path in all_paths:
            if path.startswith(f"{cur}."):
                exact_branch_prefix = f"{cur}."
                break

    parent_prefix = ""
    base_prefix = ""
    if exact_branch_prefix:
        parent_prefix = cur
        base_prefix = exact_branch_prefix
    elif cur.endswith("."):
        parent_prefix = cur[:-1]
        base_prefix = f"{parent_prefix}." if parent_prefix else ""
    elif "." in cur:
        partial_stamp = re.search(r"(_?\d{4}-\d{2}-\d{2}T\d{6}\.\d{0,6}Z?)$", cur)
        parent_prefix = cur[:partial_stamp.start()].rstrip('.') if partial_stamp else cur.rsplit(".", 1)[0]
        base_prefix = f"{parent_prefix}."

    has_children: dict[str, bool] = {}
    for path in all_paths:
        if not path:
            continue
        if not base_prefix:
            candidate = path.split(".", 1)[0]
        else:
            if not path.startswith(base_prefix):
                continue
            remainder = path[len(base_prefix) :]
            next_seg = first_path_component(remainder)
            if not next_seg:
                continue
            candidate = f"{base_prefix}{next_seg}"

        if path.startswith(f"{candidate}."):
            has_children[candidate] = True
        else:
            has_children.setdefault(candidate, False)

    completions: list[str] = []
    if exact_branch_prefix:
        completions.append(exact_branch_prefix)
    for candidate, child in has_children.items():
        completions.append(f"{candidate}." if child else candidate)

    filtered = sorted({entry for entry in completions if entry.startswith(cur)})
    return CompletionResult(filtered, nospace=any(entry.endswith(".") for entry in filtered))


def complete_project_files(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_path(cur, _state.cwd, suffixes=(".hdlforge.json", ".hdlforge.toml"))


def complete_interfaces(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_words(cur, list_interfaces())


def complete_sim_target_names(cur: str, state: ParsedState) -> CompletionResult:
    return complete_words(cur, get_sim_targets(state))


def selected_build(state: ParsedState) -> str:
    values = get_explicit_flag_values(state.tokens, "--build")
    return values[-1] if values and not values[-1].startswith("--") else ""


def complete_builds(cur: str, state: ParsedState) -> CompletionResult:
    return complete_words(cur, (selector_choices(state.project_file, project_json_data(state) or {}, cur) if state.project_file else []))


def complete_auto_impl(cur: str, state: ParsedState) -> CompletionResult:
    synthesis = selected_build(state)
    parsed = parse_selector(synthesis)
    if parsed and not parsed["impl"]:
        synthesis = parsed["run"]
    if not synthesis or "." in synthesis:
        return CompletionResult([])
    used = get_explicit_flag_values(state.tokens, "--auto_impl")
    prefix = synthesis + "."
    children = [name[len(prefix):] for name in build_names(project_json_data(state) or {})
                if name.startswith(prefix) and name[len(prefix):] not in used]
    return complete_words(cur, children)


def complete_synth_timestamps(cur: str, state: ParsedState) -> CompletionResult:
    artifact_action = any(flag in state.tokens for flag in ARTIFACT_FLAGS)
    if not state.project_file or ("." not in selected_build(state) and not artifact_action):
        return CompletionResult([])
    values = synthesis_timestamps(state.project_file, project_json_data(state) or {}, selected_build(state))
    return complete_words(cur, values)


def complete_environment_arrays(cur: str, state: ParsedState) -> CompletionResult:
    """Offer data leaves without evaluating project commands."""
    pending = [("", project_json_data(state) or {})]
    choices = []
    while pending:
        path, value = pending.pop()
        if isinstance(value, dict):
            pending.extend((f"{path}.{key}" if path else key, child)
                           for key, child in value.items() if not key.startswith("#"))
        elif isinstance(value, list):
            choices.append(path)
    return complete_words(cur, sorted(choices))


# -- Declarative state traversal -------------------------------------------
PROVIDERS = {
    "project_files": complete_project_files,
    "sim_targets": complete_sim_target_names,
    "builds": complete_builds,
    "auto_impl": complete_auto_impl,
    "synth_timestamps": complete_synth_timestamps,
    "interfaces": complete_interfaces,
    "verilator_flags": complete_verilator_flags,
    "files": lambda cur, state: complete_path(cur, state.cwd),
    "init_builds": lambda cur, state: complete_words(cur, ["all", *build_names(project_json_data(state) or {})]),
    "environment_arrays": complete_environment_arrays,
}


def command_candidates(node: dict, state: dict, prefix: str = "") -> dict:
    """Describe static anchors and project-dependent choices without execution."""
    candidates = {}
    if prefix:
        candidates[prefix+'help'] = 'Show contextual help without executing.'
    mapping = node.get('commands', {})
    for name, child in command_tree.entries(mapping).items():
        path = prefix + name
        candidates[path] = mapping['#'+name]
        candidates.update(command_candidates(child, state, path+'.'))
    if node.get('provider'):
        candidates.update({prefix+name: description for name, description in
                          command_tree.dynamic_choices(node['provider'], state['data'], state['project']).items()})
    return candidates


def complete_command(tokens: list[str], cur: str, cwd: Path) -> tuple[CompletionResult, dict]:
    state = command_tree.parse(tokens, cwd, partial=True)
    descriptions = {}
    specs = state['specs']
    pending = state['pending']
    prefix = ''
    if cur.startswith('--') and '=' in cur:
        flag, cur = cur.split('=', 1)
        pending = (flag, specs.get(flag, {}))
        prefix = flag+'='
    if pending:
        flag, spec = pending
        provider_state = ParsedState(tokens, cwd, project_file=state['project'], seen=state['seen'])
        provider_state.tokens = state['args'] + tokens
        if spec.get('provider') in PROVIDERS:
            result = PROVIDERS[spec['provider']](cur, provider_state)
        else:
            result = complete_words(cur, list(command_tree.entries(spec.get('values', {}))))
        result.completions = [prefix+item for item in result.completions]
        descriptions.update({prefix+name: spec.get('values', {}).get('#'+name, 'Value for '+flag) for name in result.completions})
        return result, descriptions
    if not state['command'] and not cur.startswith('-'):
        candidates = command_candidates(state['tree'], state)
        result = complete_dotted_paths(list(candidates), cur)
        for index, item in enumerate(result.completions):
            node, _, _, ready = command_tree.resolve_path(state['tree'], item, state['data'])
            if ready and not node.get('provider'):
                result.completions[index] = item.rstrip('.')
        descriptions = {item: candidates.get(item.rstrip('.'), 'Command group') for item in result.completions}
        return result, descriptions
    flags = [flag for flag, spec in specs.items()
             if (flag not in state['seen'] or spec.get('repeatable'))
             and command_tree.condition_matches(spec.get('when', {}), state['seen'], state['values'])]
    for group in (state['tree']['master_flags'], state['node'].get('flags', {})):
        descriptions.update({flag: group.get('#'+flag, '') for flag in flags if flag in group})
    return complete_words(cur, flags), descriptions


def completion_description(data: dict, candidate: str) -> str:
    """Read optional display text; never execute a command to obtain help."""
    path = candidate.rstrip(".").removeprefix("LLM_orch.")
    native = data.get("__native_descriptions", {}).get(candidate)
    if native:
        return native
    descriptions = data.get("LLM_orch_help", {})
    value = descriptions.get(path, "") if isinstance(descriptions, dict) else ""
    parent = data.get("LLM_orch", {})
    parts = path.split(".")
    for part in parts[:-1]:
        parent = parent.get(part, {}) if isinstance(parent, dict) else {}
    if isinstance(parent, dict):
        value = parent.get("#" + parts[-1], value)
    if isinstance(value, dict):
        value = value.get("description") or value.get("help", "")
    if not isinstance(value, str):
        return ""
    return " ".join(re.sub(r"[\x00-\x1f\x7f-\x9f]", " ", value).split())


def completion_table(candidates: list[str], data: dict, columns: int) -> list[str]:
    """Render display-only choices with HDLForge's bundled table formatter."""
    columns = max(30, columns)
    labels = candidates
    command_width = max(len("Command"), max(len(item) for item in labels))
    description_width = columns - command_width - 7
    rows = [[label, completion_description(data, item)] for label, item in zip(labels, candidates)]
    # Command tokens must remain whole. On narrow terminals put descriptions
    # below them instead of splitting folder names across table cells.
    if description_width < 16:
        lines = []
        for label, description in rows:
            lines.append(label)
            lines.extend(textwrap.wrap('# ' + description, width=columns - 2,
                                       initial_indent='  ', subsequent_indent='  '))
    else:
        rendered = create_matrix_table_from_data(["Command", "Description"], rows,
                                                col_wrapped_limits={1: description_width})
        lines = rendered.splitlines()
    # Readline must not arrange the rendered lines in multiple columns.
    return [line.ljust(columns // 2 + 1) for line in lines]


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--comp-cword", type=int, required=True)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--display-table", action="store_true")
    parser.add_argument("--columns", type=int, default=80)
    parser.add_argument("words", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    try:
        if SCHEMA_ERROR:
            raise ValueError(SCHEMA_ERROR)
        command_tree.validate(NATIVE_HELP["tree"])
    except ValueError as error:
        if args.describe:
            print(str(error), file=sys.stderr)
        return 1

    words = args.words[1:] if args.words and args.words[0] == "--" else args.words
    comp_cword = args.comp_cword
    cwd = Path(args.cwd)

    if not words:
        print("__META__ filenames=0 nospace=0")
        return 0

    cur = words[comp_cword] if comp_cword < len(words) else ""
    tokens_before_current = words[1:comp_cword]

    try:
        result, native = complete_command(tokens_before_current, cur, cwd)
    except (ValueError, KeyError, TypeError) as error:
        if args.describe:
            print(f"Invalid command state: {error}", file=sys.stderr)
        return 1

    print(f"__META__ filenames={1 if result.filenames else 0} nospace={1 if result.nospace else 0}")
    for item in result.completions:
        print(item)
    if (args.describe or args.display_table) and not result.filenames:
        project_file = detect_project_file(tokens_before_current, cwd)
        data = load_json(project_file) if project_file and project_file.suffix == ".json" else {}
        data = {**(data or {}), "__native_descriptions": native}
        for item in result.completions:
            if not completion_description(data, item):
                native[item] = "Configured choice for " + (tokens_before_current[-1] if tokens_before_current else "this command")
        if args.describe:
            for item in result.completions:
                description = completion_description(data or {}, item)
                if description:
                    print(f"__DESC__\t{item}\t{description}")
        if args.display_table and result.completions:
            for line in completion_table(result.completions, data or {}, args.columns):
                print(f"__TABLE__\t{line}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
