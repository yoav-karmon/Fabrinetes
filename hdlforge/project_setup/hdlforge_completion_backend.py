#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from table_formatter import create_matrix_table_from_data
from vivado_build_selector import parse_selector, selector_choices
from vivado_build_config import ARTIFACT_FLAGS, build_names, synthesis_timestamps

SCHEMA_ERROR = None
try:
    NATIVE_HELP = json.loads(Path(__file__).with_name("native_command_help.json").read_text())
    if not isinstance(NATIVE_HELP, dict):
        raise ValueError("Native completion catalog must be an object")
    for required_group in ("tree", "flags", "values", "project_console", "monitor"):
        if not isinstance(NATIVE_HELP.get(required_group), dict):
            raise ValueError(f"Missing native completion group: {required_group}")
    for required_group in ("tools", "flags"):
        if not isinstance(NATIVE_HELP["tree"].get(required_group), dict):
            raise ValueError(f"Missing tree group: {required_group}")
except (OSError, ValueError, TypeError) as error:
    SCHEMA_ERROR = str(error)
    NATIVE_HELP = {"tree": {"tools": {}, "flags": {}}, "flags": {}, "values": {}, "project_console": {}, "monitor": {}}
CONSOLE_ACTIONS = {("help" if value == "--help" else value): NATIVE_HELP["project_console"].get("#" + name, "")
                   for name, value in NATIVE_HELP["project_console"].items() if not name.startswith("#")}

TOOLS = [name for name in NATIVE_HELP["tree"]["tools"] if not name.startswith("#")]
GLOBAL_FLAGS = [name for name in NATIVE_HELP["tree"]["flags"] if not name.startswith("#") and name not in {"--project", "--tool"}]
GLOBAL_VALUE_FLAGS = {"--project", "--tool", "--cmd", "--env-python", "--env-path", "--env-var"}
REPEATABLE_GLOBAL_ENV_FLAGS = {"--env-python", "--env-path", "--env-var"}


@dataclass
class CompletionResult:
    completions: list[str]
    filenames: bool = False
    nospace: bool = False


@dataclass
class ParsedState:
    tokens: list[str]
    cwd: Path
    tool: str | None = None
    cmd: str | None = None
    project_file: Path | None = None
    seen: set[str] | None = None
    has_llm_path: bool = False
    llm_path: str | None = None
    eval_json: bool = False
    has_append: bool = False


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
    explicit = get_explicit_flag_values(tokens, "--project")
    if explicit:
        candidate = Path(os.path.expanduser(explicit[-1]))
        candidate = candidate if candidate.is_absolute() else cwd / candidate
        return candidate.resolve() if candidate.is_file() else None
    for directory in (cwd, *cwd.parents):
        candidates = sorted([*directory.glob("*.hdlforge.json"), *directory.glob("*.hdlforge.toml")])
        if candidates:
            return candidates[0].resolve() if len(candidates) == 1 else None
        if (directory / ".git").exists():
            break
    return None


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


def walk_llm_paths(node: object, prefix: str = "") -> list[str]:
    if not isinstance(node, dict):
        return [prefix] if prefix else []

    out: list[str] = []
    for key, value in node.items():
        if not isinstance(key, str) or key.startswith("#"):
            continue
        path = f"{prefix}.{key}" if prefix else key
        out.append(path)
        out.extend(walk_llm_paths(value, path))
    return out


def walk_string_paths_with_values(node: object, prefix: str = "") -> list[tuple[str, str]]:
    if isinstance(node, str):
        return [(prefix, node)] if prefix else []
    if not isinstance(node, dict):
        return []

    out: list[tuple[str, str]] = []
    for key, value in node.items():
        if not isinstance(key, str) or key.startswith("#"):
            continue
        path = f"{prefix}.{key}" if prefix else key
        out.extend(walk_string_paths_with_values(value, path))
    return out


def is_llm_leaf(project_file: Path | None, dotted: str) -> bool:
    if any(part.startswith("#") for part in dotted.split(".")):
        return False
    if not project_file or project_file.suffix != ".json":
        return False
    data = load_json(project_file)
    if not data:
        return False

    cursor: object = data.get("LLM_orch")
    for part in dotted.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return False
        cursor = cursor[part]
    return isinstance(cursor, str)


def is_json_string_leaf(project_file: Path | None, dotted: str) -> bool:
    if any(part.startswith("#") for part in dotted.split(".")):
        return False
    if not project_file or project_file.suffix != ".json":
        return False
    data = load_json(project_file)
    if not data:
        return False

    candidates = [dotted]
    if not dotted.startswith("LLM_orch."):
        candidates.append(f"LLM_orch.{dotted}")

    for candidate in candidates:
        cursor: object = data
        for part in candidate.split("."):
            if not isinstance(cursor, dict) or part not in cursor:
                break
            cursor = cursor[part]
        else:
            if isinstance(cursor, str):
                return True
    return False


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
        parent_prefix = cur.rsplit(".", 1)[0]
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
            next_seg = remainder.split(".", 1)[0]
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


def complete_llm_path(project_file: Path | None, cur: str) -> CompletionResult:
    if not project_file or project_file.suffix != ".json":
        return CompletionResult([])

    data = load_json(project_file)
    if not data:
        return CompletionResult([])

    return complete_dotted_paths(walk_llm_paths(data.get("LLM_orch")), cur)


def complete_json_path(project_file: Path | None, cur: str) -> CompletionResult:
    if not project_file or project_file.suffix != ".json":
        return CompletionResult([])

    data = load_json(project_file)
    if not data:
        return CompletionResult([])

    if cur.startswith("LLM_orch"):
        return complete_dotted_paths(walk_llm_paths(data.get("LLM_orch"), "LLM_orch"), cur)

    candidates = ["LLM_orch."]
    candidates.extend(
        path
        for path, value in walk_string_paths_with_values(data)
        if not path.startswith(("LLM_orch.", "LLM_orch_help.")) and "hdlforge" in value
    )
    completions = sorted({entry for entry in candidates if entry.startswith(cur)})
    return CompletionResult(completions, nospace=any(entry.endswith(".") for entry in completions))


def is_deployment_program_file_path(dotted: str | None) -> bool:
    if not dotted:
        return False
    if dotted.startswith("LLM_orch."):
        dotted = dotted.removeprefix("LLM_orch.")

    parts = dotted.split(".")
    return (
        len(parts) == 6
        and parts[0] == "deployment"
        and parts[1] == "manager"
        and parts[2] == "program"
        and parts[-1] == "file"
    )


def parse_classic_state(tokens: list[str], cwd: Path) -> ParsedState:
    # Tool/value consumption belongs to tree_state; project lookup is read-only.
    return ParsedState(tokens=tokens, cwd=cwd, seen=set(), project_file=detect_project_file(tokens, cwd))




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


def build_selection_facts(value: str, state: ParsedState) -> dict:
    parsed = parse_selector(value)
    known = value in build_names(project_json_data(state) or {})
    stage = "impl" if parsed and parsed.get("impl") else "synth"
    return {"build_valid": bool(parsed or known), "build_stage": stage,
            "build_bitstream": bool(parsed and parsed.get("bitstream")),
            "build_new_impl": bool(parsed and parsed.get("impl") and parsed.get("attempt") == "new")}


STATE_PROVIDERS = {"build_selection": build_selection_facts}


def tree_entries(mapping: dict) -> dict:
    return {key: value for key, value in mapping.items() if not key.startswith("#")}


def validate_tree(node: dict) -> None:
    """Reject undocumented choices and unknown completion providers."""
    for group in ("flags", "tools", "actions", "values"):
        entries = node.get(group, {})
        if not isinstance(entries, dict):
            raise ValueError(f"Completion {group} must be an object")
        for name, spec in tree_entries(entries).items():
            if not isinstance(spec, dict):
                raise ValueError(f"Completion option must be an object: {name}")
            if not isinstance(entries.get("#" + name), str) or not entries["#" + name].strip():
                raise ValueError(f"Missing completion description: {name}")
            if spec.get("provider") and spec["provider"] not in PROVIDERS:
                raise ValueError(f"Unknown completion provider: {spec['provider']}")
            if spec.get("state_provider") and spec["state_provider"] not in STATE_PROVIDERS:
                raise ValueError(f"Unknown state provider: {spec['state_provider']}")
            if spec.get("arity", 0) not in (0, 1, "?"):
                raise ValueError(f"Invalid argument arity: {name}")
            validate_tree(spec)
    if "children" in node:
        validate_tree(node["children"])


def condition_matches(condition: dict, seen: set, values: dict) -> bool:
    if not condition:
        return True
    if "all" in condition:
        return all(condition_matches(item, seen, values) for item in condition["all"])
    if "any" in condition:
        return any(condition_matches(item, seen, values) for item in condition["any"])
    if "not" in condition:
        return not condition_matches(condition["not"], seen, values)
    if "present" in condition:
        return condition["present"] in seen
    if "equals" in condition:
        flag, value = condition["equals"]
        return values.get(flag) == value
    raise ValueError(f"Unknown completion condition: {condition}")


def tree_state(state: ParsedState) -> tuple:
    """Consume tokens once; values cannot accidentally select another anchor."""
    tree = NATIVE_HELP["tree"]
    nodes = [tree]
    if state.tool:
        nodes.append(tree["tools"].get(state.tool, {}))
    seen, values, exclusive = set(), {}, set()
    pending = None
    passthrough = False
    action_selected = False

    def flags():
        allowed_globals = nodes[1].get("globals") if len(nodes) > 1 else None
        return {key: value for index, node in enumerate(nodes)
                for key, value in tree_entries(node.get("flags", {})).items()
                if index != 0 or allowed_globals is None or key in allowed_globals}

    def consume(flag, spec, value):
        nonlocal nodes
        seen.add(flag)
        values[flag] = value
        if spec.get("state_provider"):
            values.update(STATE_PROVIDERS[spec["state_provider"]](value, state))
        if spec.get("exclusive"):
            exclusive.add(spec["exclusive"])
        if flag == "--tool":
            state.tool = value
            nodes = [tree, tree["tools"].get(value, {})]
        if "children" in spec:
            nodes.append(spec["children"])
        if value in spec.get("values", {}):
            nodes.append(spec["values"][value])

    for token in state.tokens:
        if passthrough:
            break
        if pending:
            flag, spec = pending
            pending = None
            if spec["arity"] != "?" or not token.startswith("-"):
                consume(flag, spec, token)
                continue
            consume(flag, spec, "")
        if token == "--":
            passthrough = True
            continue
        flag, separator, value = token.partition("=")
        available = flags()
        if flag in available:
            spec = available[flag]
            if spec.get("arity", 0) and not separator:
                pending = (flag, spec)
            else:
                consume(flag, spec, value)
            continue
        for node in list(nodes):
            if token in node.get("actions", {}) and not action_selected:
                nodes.append(node["actions"][token])
                values["action"] = token
                action_selected = True
                break
    state.seen = seen
    return nodes, flags(), seen, values, exclusive, pending, passthrough, action_selected


def suggest_flags(state: ParsedState) -> list[str]:
    nodes, flags, seen, values, exclusive, pending, passthrough, action_selected = tree_state(state)
    if passthrough:
        return []
    return [flag for flag, spec in flags.items()
            if (flag not in seen or spec.get("repeatable"))
            and (not spec.get("exclusive") or spec["exclusive"] not in exclusive)
            and condition_matches(spec.get("when", {}), seen, values)]


def filter_single_use(flags: list[str], state: ParsedState, *, repeatable: set[str] | None = None) -> list[str]:
    repeatable = (repeatable or set()) | REPEATABLE_GLOBAL_ENV_FLAGS
    return [flag for flag in flags if flag in repeatable or flag not in (state.seen or set())]


def complete_classic(tokens_before_current: list[str], cur: str, cwd: Path) -> CompletionResult:
    state = parse_classic_state(tokens_before_current, cwd)
    nodes, flags, seen, values, exclusive, pending, passthrough, action_selected = tree_state(state)
    if passthrough:
        return CompletionResult([])
    prefix = ""
    if cur.startswith("--") and "=" in cur:
        flag, cur = cur.split("=", 1)
        if flag not in flags:
            return CompletionResult([])
        pending = (flag, flags[flag])
        prefix = flag + "="
    if pending and (pending[1].get("arity") != "?" or not cur.startswith("-")):
        flag, spec = pending
        if spec.get("anchor") == "tools":
            result = complete_words(cur, list(tree_entries(NATIVE_HELP["tree"]["tools"])))
        elif spec.get("provider"):
            result = PROVIDERS[spec["provider"]](cur, state)
        else:
            result = complete_words(cur, list(tree_entries(spec.get("values", {}))))
        result.completions = [prefix + item for item in result.completions]
        return result
    candidates = suggest_flags(state)
    if not action_selected:
        candidates += [name for node in nodes for name, spec in tree_entries(node.get("actions", {})).items()
                       if condition_matches(spec.get("when", {}), seen, values)]
    return complete_words(cur, unique(candidates))


def tree_descriptions(node: dict) -> dict:
    descriptions = {}
    for key, value in node.items():
        if key.startswith("#") and isinstance(value, str):
            descriptions[key[1:]] = value
        elif isinstance(value, dict):
            descriptions.update(tree_descriptions(value))
    return descriptions


def parse_llm_mode(tokens_before_current: list[str], cwd: Path) -> ParsedState:
    state = ParsedState(tokens=tokens_before_current, cwd=cwd, seen=set(tokens_before_current))
    state.project_file = detect_project_file(tokens_before_current, cwd)

    expecting_value_flag: str | None = None
    expecting_append_value = False
    for token in tokens_before_current:
        if expecting_value_flag:
            if expecting_value_flag == "--cmd":
                state.cmd = token
            expecting_value_flag = None
            continue
        if expecting_append_value:
            expecting_append_value = False
            continue
        if token in GLOBAL_VALUE_FLAGS:
            expecting_value_flag = token
            continue
        if token == "--eval_json":
            state.eval_json = True
            continue
        if token == "--append":
            state.has_append = True
            expecting_append_value = True
            continue
        if token == "--":
            break
        if not token.startswith("-") and not state.has_llm_path:
            state.has_llm_path = True
            state.llm_path = token

    return state


def complete_llm(tokens_before_current: list[str], cur: str, cwd: Path) -> CompletionResult:
    if any(token == "--tool" or token.startswith("--tool=") for token in tokens_before_current):
        return complete_classic(tokens_before_current, cur, cwd)
    if "--" in tokens_before_current:
        dd_index = tokens_before_current.index("--")
        passthrough_tokens = tokens_before_current[dd_index + 1 :]
        return complete_classic(passthrough_tokens, cur, cwd)

    state = parse_llm_mode(tokens_before_current, cwd)
    prev = tokens_before_current[-1] if tokens_before_current else ""
    if prev == "--project":
        return complete_project_files(cur, state)
    if prev in {"--env-python", "--env-path", "--env-var"}:
        return CompletionResult([])
    if prev == "--cmd":
        return CompletionResult([])
    if prev == "--eval_json":
        return complete_json_path(state.project_file, cur)
    if prev == "--append":
        if is_deployment_program_file_path(state.llm_path):
            return complete_path(cur, state.cwd, suffixes=(".bit",))
        return CompletionResult([])

    if state.cmd is not None:
        append_flags = [] if state.has_append else ["--append"]
        if cur.startswith("-") or not cur:
            return complete_words(cur, append_flags)
        return CompletionResult([])

    llm_flags = filter_single_use(["--eval_json", "--cmd", "--project", "--tool", *GLOBAL_FLAGS, "--help", "-h"], state)

    if (cur.startswith("-") or not cur) and not state.has_llm_path:
        merged = unique(complete_llm_path(state.project_file, cur).completions + [flag for flag in llm_flags if flag.startswith(cur)])
        return CompletionResult(merged)

    if not state.has_llm_path:
        llm_result = complete_llm_path(state.project_file, cur)
        merged = unique(llm_result.completions + [flag for flag in llm_flags if flag.startswith(cur)])
        return CompletionResult(merged, filenames=llm_result.filenames, nospace=llm_result.nospace)

    if cur == state.llm_path:
        if state.eval_json:
            return complete_json_path(state.project_file, cur)
        return complete_llm_path(state.project_file, cur)

    is_leaf = (
        is_json_string_leaf(state.project_file, state.llm_path)
        if state.eval_json and state.llm_path
        else is_llm_leaf(state.project_file, state.llm_path or "")
    )
    if state.llm_path and is_leaf:
        append_flags = [] if state.has_append else ["--append"]
        if cur.startswith("-") or not cur:
            return complete_words(cur, append_flags)
        return CompletionResult([])

    return CompletionResult([])


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
    command_width = min(max(len("Command"), max(len(item) for item in labels)), (columns - 7) // 2)
    description_width = columns - command_width - 7
    rows = [[label, completion_description(data, item)] for label, item in zip(labels, candidates)]
    rendered = create_matrix_table_from_data(["Command", "Description"], rows,
                                            col_wrapped_limits={0: command_width, 1: description_width})
    # Readline must not arrange the rendered lines in multiple columns.
    lines = rendered.splitlines()
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
        validate_tree(NATIVE_HELP["tree"])
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

    classic_mode = any(token == "--tool" or token.startswith("--tool=") for token in tokens_before_current)
    if os.environ.get("HDLFORGE_COMPLETION_DEBUG"):
        mode_name = "classic" if classic_mode else "llm_orch"
        print(
            f"[hdlforge completion] backend mode={mode_name} cwd={cwd} cur={cur!r}",
            file=sys.stderr,
        )
    try:
        result = complete_classic(tokens_before_current, cur, cwd) if classic_mode else complete_llm(tokens_before_current, cur, cwd)
    except (ValueError, KeyError, TypeError) as error:
        if args.describe:
            print(f"Invalid completion tree: {error}", file=sys.stderr)
        return 1

    print(f"__META__ filenames={1 if result.filenames else 0} nospace={1 if result.nospace else 0}")
    for item in result.completions:
        print(item)
    if (args.describe or args.display_table) and not result.filenames:
        project_file = detect_project_file(tokens_before_current, cwd)
        data = load_json(project_file) if project_file and project_file.suffix == ".json" else {}
        native = {name[1:]: value for group in (NATIVE_HELP["flags"], NATIVE_HELP["values"])
                  for name, value in group.items() if name.startswith("#")}
        if "--project_console" in tokens_before_current:
            native.update(CONSOLE_ACTIONS)
        if "--monitor" in tokens_before_current:
            native.update({name[1:]: value for name, value in NATIVE_HELP['monitor'].items() if name.startswith('#')})
        native.update(tree_descriptions(NATIVE_HELP["tree"]))
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
