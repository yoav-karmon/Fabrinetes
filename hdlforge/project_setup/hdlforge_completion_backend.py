#!/usr/bin/env python3

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable


TOOLS = ["vivado", "Verilator", "network", "vcd_analyzer", "tsharkWrapper", "hw_server", "projects"]
NETWORK_COMMANDS = ["send_raw", "send_arp", "send_icmp", "send_udp"]
HW_SERVER_COMMANDS = ["program", "scan_ila", "scan_jtag", "read_dna"]
VERILATOR_STEPS = ["build", "sim", "lint"]
GLOBAL_ENV_FLAGS = ["--env-python", "--env-path", "--env-var"]
GLOBAL_FLAGS = [*GLOBAL_ENV_FLAGS, "--dry-run"]
GLOBAL_VALUE_FLAGS = {"--project", "--tool", "--env-python", "--env-path", "--env-var"}
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
    interactive: bool = False
    chain_mode: bool = False
    selected_vivado_action: str | None = None
    has_vcdfile: bool = False
    has_pcap: bool = False
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
            completions.append(f"{display_dir}{name}/")
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
        idx += 1
    return values


def detect_project_file(tokens: list[str], cwd: Path) -> Path | None:
    explicit = get_explicit_flag_values(tokens, "--project")
    if explicit:
        candidate = Path(os.path.expanduser(explicit[-1]))
        if not candidate.is_absolute():
            candidate = cwd / candidate
        if candidate.is_file():
            return candidate.resolve()

    for suffix in ("*.hdlforge.json", "*.hdlforge.toml"):
        matches = sorted(cwd.glob(suffix))
        if matches:
            return matches[0].resolve()
    return None


def project_json_data(state: ParsedState) -> dict | None:
    if not state.project_file or state.project_file.suffix != ".json":
        return None
    return load_json(state.project_file)


def get_vivado_runs(state: ParsedState) -> list[str]:
    data = project_json_data(state)
    if not data:
        return []

    runs: list[str] = []
    vivado_cfg = (((data.get("vivado") or {}).get("config")) or {})
    runs.extend(vivado_cfg.get("syth_list") or [])

    for item in vivado_cfg.get("runs_flow") or []:
        synth_run = (item or {}).get("synth_run")
        if synth_run:
            runs.append(synth_run)

    return unique([run for run in runs if isinstance(run, str)])


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
        if not isinstance(key, str):
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
        if not isinstance(key, str):
            continue
        path = f"{prefix}.{key}" if prefix else key
        out.extend(walk_string_paths_with_values(value, path))
    return out


def is_llm_leaf(project_file: Path | None, dotted: str) -> bool:
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
        if not path.startswith("LLM_orch.") and "hdlforge" in value
    )
    completions = sorted({entry for entry in candidates if entry.startswith(cur)})
    return CompletionResult(completions, nospace=any(entry.endswith(".") for entry in completions))


def parse_classic_state(tokens: list[str], cwd: Path) -> ParsedState:
    state = ParsedState(tokens=tokens, cwd=cwd, seen=set())
    state.project_file = detect_project_file(tokens, cwd)
    idx = 0

    while idx < len(tokens):
        token = tokens[idx]
        state.seen.add(token)

        if token == "--tool" and idx + 1 < len(tokens):
            state.tool = tokens[idx + 1]
            state.seen.add(tokens[idx + 1])
            idx += 2
            continue

        if token == "--cmd" and idx + 1 < len(tokens):
            state.cmd = tokens[idx + 1]
            state.seen.add(tokens[idx + 1])
            idx += 2
            continue

        if token in {"-i", "--interactive"}:
            state.interactive = True
        elif token in {"-ic", "--interactive-chain"}:
            state.chain_mode = True
        elif token in {
            "--syn",
            "--impl",
            "--bit",
            "--all",
            "--lint",
            "--list_runs",
            "--reset_run",
            "--generate_prj_with_external_tcl",
            "--write_tcl",
            "--file_add",
            "--file_remove",
            "--add_file_to_project_tcl",
            "--remove_file_from_project_tcl",
            "--add_run_to_project_tcl",
            "--remove_run_from_project_tcl",
            "--clean_logs",
        } and state.selected_vivado_action is None:
            state.selected_vivado_action = token
        elif token == "--vcdfilename" and idx + 1 < len(tokens):
            state.has_vcdfile = True
            idx += 2
            continue
        elif token == "--pcap" and idx + 1 < len(tokens):
            state.has_pcap = True
            idx += 2
            continue

        idx += 1

    return state


Handler = Callable[[str, ParsedState], CompletionResult]


def complete_project_files(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_path(cur, _state.cwd, suffixes=(".hdlforge.json", ".hdlforge.toml"))


def complete_tools(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_words(cur, TOOLS)


def complete_network_cmds(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_words(cur, NETWORK_COMMANDS)


def complete_hw_server_cmds(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_words(cur, HW_SERVER_COMMANDS)


def complete_interfaces(cur: str, _state: ParsedState) -> CompletionResult:
    return complete_words(cur, list_interfaces())


def complete_static_words(words: list[str]) -> Handler:
    return lambda cur, _state: complete_words(cur, words)


def complete_vivado_run_names(cur: str, state: ParsedState) -> CompletionResult:
    return complete_csv_words(cur, get_vivado_runs(state))


def complete_sim_target_names(cur: str, state: ParsedState) -> CompletionResult:
    return complete_words(cur, get_sim_targets(state))


VALUE_HANDLER_TREE: dict[str, dict[str, Handler]] = {
    "root": {
        "--project": complete_project_files,
        "--tool": complete_tools,
        "--env-python": lambda _cur, _state: CompletionResult([]),
        "--env-path": lambda _cur, _state: CompletionResult([]),
        "--env-var": lambda _cur, _state: CompletionResult([]),
    },
    "tool:vivado": {
        "--syn": complete_vivado_run_names,
        "--impl": complete_vivado_run_names,
        "--bit": complete_vivado_run_names,
        "--all": complete_vivado_run_names,
        "--reset_run": complete_vivado_run_names,
        "--file_path": lambda cur, _state: complete_path(cur, _state.cwd),
        "--project_tcl_json_file": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".json",)),
    },
    "tool:Verilator": {
        "--step": complete_static_words(VERILATOR_STEPS),
        "--SimTargetName": complete_sim_target_names,
        "--flags": complete_verilator_flags,
        "--lint-file": lambda cur, _state: complete_path(
            cur,
            _state.cwd,
            suffixes=(".sv", ".v", ".svh", ".vh"),
        ),
    },
    "tool:network": {
        "--cmd": complete_network_cmds,
        "--interface": complete_interfaces,
        "--arp_op": complete_static_words(["1", "2"]),
        "--icmp_type": complete_static_words(["0", "8"]),
        "--icmp_code": complete_static_words(["0"]),
        "--src_ip": complete_static_words(["192.168.1.1", "192.168.1.2", "192.168.1.100"]),
        "--dst_ip": complete_static_words(["192.168.1.1", "192.168.1.2", "192.168.1.100"]),
        "--src_mac": complete_static_words(["FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"]),
        "--dst_mac": complete_static_words(["FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"]),
        "--eth_src_mac": complete_static_words(["FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"]),
        "--eth_dst_mac": complete_static_words(["FF:FF:FF:FF:FF:FF", "00:00:00:00:00:00"]),
        "--src_port": complete_static_words(["53", "80", "443", "8080", "12345"]),
        "--dst_port": complete_static_words(["53", "80", "443", "8080", "12345"]),
        "--identifier": complete_static_words(["0", "1"]),
        "--sequence": complete_static_words(["0", "1"]),
    },
    "tool:vcd_analyzer": {
        "--vcdfilename": lambda cur, _state: complete_path(cur, _state.cwd),
    },
    "tool:tsharkWrapper": {
        "--pcap": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".pcap",)),
        "--format": complete_static_words(["to_plain_text"]),
    },
    "tool:hw_server": {
        "--cmd": complete_hw_server_cmds,
        "--server_ip": complete_static_words(["10.1.130.74", "192.168.1.100", "localhost"]),
        "--bitstream": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".bit",)),
        "--probes": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".ltx",)),
        "--hw-config": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".json",)),
        "-c": lambda cur, _state: complete_path(cur, _state.cwd, suffixes=(".json",)),
        "-ic": complete_static_words(["1", "2", "3", "program", "scan_ila", "scan_jtag", "i1", "i2", "v1", "v2", "s1", "w1", "c1", "q"]),
        "--interactive-chain": complete_static_words(["1", "2", "3", "program", "scan_ila", "scan_jtag", "i1", "i2", "v1", "v2", "s1", "w1", "c1", "q"]),
    },
}


def branch_keys(state: ParsedState) -> list[str]:
    keys = ["root"]
    if state.tool:
        keys.append(f"tool:{state.tool}")
        if state.tool == "network" and state.cmd:
            keys.append(f"tool:network/cmd:{state.cmd}")
        if state.tool == "hw_server":
            if state.interactive:
                keys.append("tool:hw_server/interactive")
            if state.chain_mode:
                keys.append("tool:hw_server/chain")
            if state.cmd:
                keys.append(f"tool:hw_server/cmd:{state.cmd}")
    return keys


def resolve_value_handler(flag: str, state: ParsedState) -> Handler | None:
    for key in reversed(branch_keys(state)):
        handler = VALUE_HANDLER_TREE.get(key, {}).get(flag)
        if handler:
            return handler
    return None


def filter_single_use(flags: list[str], state: ParsedState, *, repeatable: set[str] | None = None) -> list[str]:
    used = state.seen or set()
    repeatable = (repeatable or set()) | REPEATABLE_GLOBAL_ENV_FLAGS
    return [flag for flag in flags if flag in repeatable or flag not in used]


def suggest_vivado_flags(state: ParsedState) -> list[str]:
    actions = [
        "--syn",
        "--impl",
        "--bit",
        "--all",
        "--lint",
        "--list_runs",
        "--reset_run",
        "--generate_prj_with_external_tcl",
        "--write_tcl",
        "--file_add",
        "--file_remove",
        "--add_file_to_project_tcl",
        "--remove_file_from_project_tcl",
        "--add_run_to_project_tcl",
        "--remove_run_from_project_tcl",
        "--clean_logs",
    ]

    selected = state.selected_vivado_action
    if not selected:
        return filter_single_use(actions + ["--project", *GLOBAL_FLAGS, "--verbose", "--help", "-h"], state)

    modifiers: list[str]
    if selected in {"--syn", "--impl", "--bit", "--all", "--lint", "--reset_run"}:
        modifiers = ["--clean"]
    elif selected == "--generate_prj_with_external_tcl":
        modifiers = ["--clean", "--force"]
    elif selected in {"--file_add", "--file_remove"}:
        modifiers = ["--file_path"]
    elif selected in {
        "--add_file_to_project_tcl",
        "--remove_file_from_project_tcl",
        "--add_run_to_project_tcl",
        "--remove_run_from_project_tcl",
    }:
        modifiers = ["--project_tcl_json", "--project_tcl_json_file"]
    elif selected == "--clean_logs":
        modifiers = ["--force", "--verbose"]
    else:
        modifiers = []

    return filter_single_use(modifiers + ["--project", *GLOBAL_FLAGS, "--verbose", "--help", "-h"], state)


def suggest_verilator_flags(state: ParsedState) -> list[str]:
    return filter_single_use(
        ["--step", "--SimTargetName", "--clean", "--verbose", "--flags", "--lint-file", "--extra-env", "--project", *GLOBAL_FLAGS, "--help", "-h"],
        state,
        repeatable={"--step", "--flags", "--lint-file"},
    )


def suggest_network_flags(state: ParsedState) -> list[str]:
    if not state.cmd:
        return filter_single_use(["--cmd", "--verbose", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    per_cmd = {
        "send_raw": ["--interface", "--data", "--verbose"],
        "send_arp": ["--interface", "--arp_op", "--eth_dst_mac", "--eth_src_mac", "--src_mac", "--src_ip", "--dst_mac", "--dst_ip", "--verbose"],
        "send_icmp": ["--interface", "--eth_dst_mac", "--eth_src_mac", "--src_ip", "--dst_ip", "--icmp_type", "--icmp_code", "--identifier", "--sequence", "--data", "--verbose"],
        "send_udp": ["--interface", "--eth_dst_mac", "--eth_src_mac", "--src_ip", "--dst_ip", "--src_port", "--dst_port", "--data", "--verbose"],
    }
    return filter_single_use(per_cmd.get(state.cmd, []) + ["--project", *GLOBAL_FLAGS, "--help", "-h"], state)


def suggest_vcd_flags(state: ParsedState) -> list[str]:
    if not state.has_vcdfile:
        return filter_single_use(["--vcdfilename", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    if "--get_values_pins" in (state.seen or set()) or "--get_values_all" in (state.seen or set()):
        return filter_single_use(["--human", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    if "--get_modules_list" in (state.seen or set()):
        return filter_single_use(["--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    return filter_single_use(
        ["--get_modules_list", "--get_values_pins", "--get_values_all", "--project", *GLOBAL_FLAGS, "--help", "-h"],
        state,
    )


def suggest_tshark_flags(state: ParsedState) -> list[str]:
    if not state.has_pcap:
        return filter_single_use(["--pcap", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    return filter_single_use(
        [
            "--format",
            "--frame",
            "--frame_start",
            "--frame_end",
            "--frame_list",
            "--count",
            "--skip",
            "--tsharkArgsAppend",
            "--disable_heuristics",
            "--disable_protocols",
            "--verbose",
            "--project",
            *GLOBAL_FLAGS,
            "--help",
            "-h",
        ],
        state,
    )


def suggest_hw_server_flags(state: ParsedState) -> list[str]:
    if state.interactive:
        return filter_single_use(["--hw-config", "-c", "--server_ip", "--bitstream", "--probes", "--debug", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    if state.chain_mode:
        return filter_single_use(["--server_ip", "--hw-config", "-c", "--debug", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    if not state.cmd:
        return filter_single_use(["--cmd", "-i", "--interactive", "-ic", "--interactive-chain", "--hw-config", "-c", "--server_ip", "--debug", "--project", *GLOBAL_FLAGS, "--help", "-h"], state)

    per_cmd = {
        "program": ["--server_ip", "--bitstream", "--probes", "--hw-config", "-c", "--debug"],
        "scan_ila": ["--server_ip", "--probes", "--hw-config", "-c", "--debug"],
        "scan_jtag": ["--server_ip", "--hw-config", "-c", "--debug"],
        "read_dna": ["--server_ip", "--hw-config", "-c", "--debug"],
    }
    return filter_single_use(per_cmd.get(state.cmd, []) + ["--project", *GLOBAL_FLAGS, "--help", "-h"], state)


def suggest_project_flags(state: ParsedState) -> list[str]:
    return filter_single_use(["--list", *GLOBAL_FLAGS, "--help", "-h"], state)


def suggest_root_flags(state: ParsedState) -> list[str]:
    return filter_single_use(["--project", "--tool", *GLOBAL_FLAGS, "--verbose", "--help", "-h"], state)


def suggest_flags(state: ParsedState) -> list[str]:
    if state.tool == "vivado":
        return suggest_vivado_flags(state)
    if state.tool == "Verilator":
        return suggest_verilator_flags(state)
    if state.tool == "network":
        return suggest_network_flags(state)
    if state.tool == "vcd_analyzer":
        return suggest_vcd_flags(state)
    if state.tool == "tsharkWrapper":
        return suggest_tshark_flags(state)
    if state.tool == "hw_server":
        return suggest_hw_server_flags(state)
    if state.tool == "projects":
        return suggest_project_flags(state)
    return suggest_root_flags(state)


def complete_classic(tokens_before_current: list[str], cur: str, cwd: Path) -> CompletionResult:
    state = parse_classic_state(tokens_before_current, cwd)
    prev = tokens_before_current[-1] if tokens_before_current else ""
    handler = resolve_value_handler(prev, state)
    if handler:
        return handler(cur, state)

    if cur.startswith("-") or not cur:
        return complete_words(cur, suggest_flags(state))

    return CompletionResult([])


def parse_llm_mode(tokens_before_current: list[str], cwd: Path) -> ParsedState:
    state = ParsedState(tokens=tokens_before_current, cwd=cwd, seen=set(tokens_before_current))
    state.project_file = detect_project_file(tokens_before_current, cwd)

    expecting_project_value = False
    expecting_append_value = False
    for token in tokens_before_current:
        if expecting_project_value:
            expecting_project_value = False
            continue
        if expecting_append_value:
            expecting_append_value = False
            continue
        if token in GLOBAL_VALUE_FLAGS:
            expecting_project_value = True
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
    if prev == "--eval_json":
        return complete_json_path(state.project_file, cur)
    if prev == "--append":
        return CompletionResult([])

    llm_flags = filter_single_use(["--eval_json", "--project", "--tool", *GLOBAL_FLAGS, "--help", "-h"], state)

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


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--cwd", required=True)
    parser.add_argument("--comp-cword", type=int, required=True)
    parser.add_argument("words", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    words = args.words[1:] if args.words and args.words[0] == "--" else args.words
    comp_cword = args.comp_cword
    cwd = Path(args.cwd)

    if not words:
        print("__META__ filenames=0 nospace=0")
        return 0

    cur = words[comp_cword] if comp_cword < len(words) else ""
    tokens_before_current = words[1:comp_cword]

    classic_mode = "--tool" in tokens_before_current
    if os.environ.get("HDLFORGE_COMPLETION_DEBUG"):
        mode_name = "classic" if classic_mode else "llm_orch"
        print(
            f"[hdlforge completion] backend mode={mode_name} cwd={cwd} cur={cur!r}",
            file=sys.stderr,
        )
    result = complete_classic(tokens_before_current, cur, cwd) if classic_mode else complete_llm(tokens_before_current, cur, cwd)

    print(f"__META__ filenames={1 if result.filenames else 0} nospace={1 if result.nospace else 0}")
    for item in result.completions:
        print(item)
    return 0


if __name__ == "__main__":
    sys.exit(main())
