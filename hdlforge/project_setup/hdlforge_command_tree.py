"""Shared dotted-command resolution for launch, help and completion."""
import json
import os
from pathlib import Path
import sys

from vivado_build_selector import first_path_component, parse_selector, selector_choices
from vivado_run_tree import discover_runs, run_tree, selected_run

CATALOG = Path(__file__).with_name('native_command_help.json')
TAIL_COMMANDS = {'eval-cmd', 'eval-cmd-argv'}
COMMON_CHILD_FLAGS = {'--help', '-h'}


def entries(mapping: dict) -> dict:
    return {key: value for key, value in mapping.items() if not key.startswith('#')}


def load_tree() -> dict:
    tree = json.loads(CATALOG.read_text())['tree']
    validate(tree)
    return tree


def validate(tree: dict) -> None:
    """Reject malformed declarative routes before dispatch or completion."""
    for group in ('master_flags', 'master_commands', 'flags', 'commands', 'values'):
        mapping = tree.get(group, {})
        if not isinstance(mapping, dict):
            raise ValueError(f'{group} must be an object')
        for name, node in entries(mapping).items():
            if not isinstance(node, dict) or not mapping.get('#'+name):
                raise ValueError(f'Missing command/flag description: {name}')
            if node.get('arity', 0) not in (0, 1, '?', '+'):
                raise ValueError(f'Invalid arity: {name}')
            validate(node)
    if tree.get('provider') and tree['provider'] not in {
        'shortcuts', 'build_runs', 'word', 'init_builds',
        'project_files', 'environment_arrays', 'files', 'builds', 'auto_impl',
        'synth_timestamps', 'interfaces', 'sim_targets', 'verilator_flags',
    }:
        raise ValueError(f"Unknown provider: {tree['provider']}")


def project_file(tokens: list[str], cwd: Path) -> Path | None:
    """Select a project without initializing or modifying its environment."""
    for index, token in enumerate(tokens):
        if token == '--project' and index+1 < len(tokens):
            return (cwd / os.path.expanduser(tokens[index+1])).resolve()
        if token.startswith('--project='):
            return (cwd / os.path.expanduser(token.split('=', 1)[1])).resolve()
    inherited = os.environ.get('HDLFORGE_PROJECT_FILE', '')
    while True:
        if os.environ.get('HDLFORGE_CALLED') == '1' and inherited:
            path = Path(inherited)
            if path.parent == cwd and path.is_file():
                return path
        choices = sorted([*cwd.glob('*.hdlforge.json'), *cwd.glob('*.hdlforge.toml')])
        if len(choices) == 1:
            return choices[0]
        if len(choices) > 1 or (cwd / '.git').exists() or cwd.parent == cwd:
            return None
        cwd = cwd.parent


def project_data(project: Path | None) -> dict:
    if not project or project.suffix != '.json':
        return {}
    try:
        return json.loads(project.read_text())
    except (OSError, ValueError):
        return {}


def shortcut_node(data: dict, path: str) -> object:
    node = data.get('LLM_orch', {})
    for part in path.split('.') if path else []:
        if part.startswith('#') or not isinstance(node, dict):
            return None
        node = node.get(part)
    return node


def dynamic_choices(provider: str, data: dict, project: Path | None) -> dict:
    if provider == 'shortcuts':
        choices = {}
        def walk(node, prefix=''):
            for name, value in entries(node).items():
                path = prefix+name
                description = node.get('#'+name, data.get('LLM_orch_help', {}).get(path, 'Project shortcut '+path))
                if isinstance(description, dict):
                    description = description.get('description', description.get('help', 'Project shortcut '+path))
                choices[path] = description
                if isinstance(value, dict):
                    walk(value, path+'.')
        walk(data.get('LLM_orch', {}))
        return choices
    if provider == 'build_runs' and project:
        result = {}
        for value in selector_choices(project, data, ''):
            parsed = parse_selector(value, discover_runs(run_tree(data)))
            if parsed and parsed.get('impl'):
                stem = f"{parsed['run']}.{parsed['synth']}."
                value = stem + 'impl.' + value[len(stem):]
            result[value] = 'Non-project build '+value
        return result
    if provider == 'init_builds':
        return {name: 'Initialize build '+name for name in ['all', *discover_runs(run_tree(data))]}
    return {}


def resolve_path(tree: dict, command: str, data: dict) -> tuple[dict, str, str, bool]:
    """Walk static anchors, then the owning provider's dynamic suffix."""
    node = tree
    prefix = []
    parts = command.rstrip('.').split('.') if command else []
    for index, part in enumerate(parts):
        if part == 'help' and index == len(parts)-1:
            return node, '.'.join(prefix), '', False
        if node.get('provider') and part not in entries(node.get('commands', {})):
            value = '.'.join(parts[index:])
            if node['provider'] == 'shortcuts':
                selected = shortcut_node(data, value)
                if selected is None:
                    raise ValueError('Unknown project shortcut: '+value)
                return node, '.'.join(prefix), value, isinstance(selected, str)
            if node['provider'] == 'build_runs':
                runs = discover_runs(run_tree(data))
                run_name = selected_run(value, runs)
                if runs or data:
                    if run_name is None:
                        if any(name.startswith(value + '.') for name in runs):
                            return node, '.'.join(prefix), value, False
                        raise ValueError('Unknown synthesis run or group: ' + value)
                    suffix = value[len(run_name):]
                    selected = run_name + suffix.replace('.impl.', '.', 1)
                else:
                    if value.startswith('impl.'):
                        raise ValueError('Select a synthesis run before its implementation')
                    selected = value.replace('.impl.', '.', 1)
                parsed = parse_selector(selected, runs if (runs or data) else None)
                suffix = value[len(run_name):] if run_name else value
                if parsed and parsed.get('impl') and '.impl.' not in suffix:
                    raise ValueError('Implementation belongs under SYNTH.TIMESTAMP.impl.IMPL')
                return node, '.'.join(prefix), value, bool(parsed)
            return node, '.'.join(prefix), value, bool(value)
        if part not in entries(node.get('commands', {})):
            raise ValueError('Unknown command: '+'.'.join([*prefix, part]))
        node = node['commands'][part]
        prefix.append(part)
    return node, '.'.join(prefix), '', bool(node.get('dispatch') and not node.get('provider'))


def condition_matches(condition: dict, seen: set, values: dict) -> bool:
    if not condition:
        return True
    if 'all' in condition:
        return all(condition_matches(item, seen, values) for item in condition['all'])
    if 'any' in condition:
        return any(condition_matches(item, seen, values) for item in condition['any'])
    if 'not' in condition:
        return not condition_matches(condition['not'], seen, values)
    if 'present' in condition:
        return condition['present'] in seen
    if 'equals' in condition:
        key, value = condition['equals']
        return values.get(key) == value
    raise ValueError('Unknown condition: '+str(condition))


def parse(tokens: list[str], cwd: Path, *, partial: bool = False) -> dict:
    """Consume master options, one command anchor and its owned arguments."""
    tree = load_tree()
    master = entries(tree['master_flags'])
    index = 0
    command = ''
    # Master options may precede the command. Local options follow its anchor.
    while index < len(tokens):
        flag, sep, value = tokens[index].partition('=')
        if not flag.startswith('-'):
            command = tokens[index]
            break
        if flag not in master:
            raise ValueError('Unknown master flag: '+flag)
        index += 1 + (int(bool(master[flag].get('arity'))) if not sep else 0)
    command_index = index if command else -1
    # Alias leaves, like evaluation commands, own their complete argument tail.
    alias_path = command.startswith('aliases.') and command.split('.')[1] not in entries(tree['commands']['aliases'].get('commands', {}))
    owns_tail = command in TAIL_COMMANDS or alias_path
    project_tokens = tokens[:command_index] if owns_tail else []
    scan = 0
    while not owns_tail and scan < len(tokens):
        if scan == command_index:
            scan += 1
            continue
        flag, separator, value = tokens[scan].partition('=')
        if flag in master:
            project_tokens.append(tokens[scan])
            if master[flag].get('arity') and not separator and scan+1 < len(tokens):
                scan += 1
                project_tokens.append(tokens[scan])
        scan += 1
    project = project_file(project_tokens, cwd)
    data = project_data(project)
    node, prefix, value, ready = resolve_path(tree, command, data)
    specs = {**master, **entries(node.get('flags', {}))}
    seen, values, forwarded, master_args, payload = set(), {}, [], [], []
    pending = None
    index = 0
    while index < len(tokens):
        if index == command_index:
            index += 1
            continue
        if owns_tail and command_index >= 0 and index > command_index:
            payload.extend(tokens[index:])
            break
        token = tokens[index]
        flag, sep, flag_value = token.partition('=')
        spec = specs.get(flag)
        if spec is None:
            if node.get('payload') and (not token.startswith('-') or payload):
                payload.append(token)
                index += 1
                continue
            raise ValueError('Unexpected argument for '+(command or 'hdlforge')+': '+token)
        if flag in seen and not spec.get('repeatable'):
            raise ValueError('Repeated option: '+flag)
        seen.add(flag)
        if spec.get('arity'):
            if not sep:
                index += 1
                if index >= len(tokens):
                    if partial:
                        pending = (flag, spec)
                        break
                    raise ValueError(flag+' requires a value')
                flag_value = tokens[index]
        elif sep:
            raise ValueError(flag+' does not take a value')
        values[flag] = flag_value
        target = master_args if flag in master else forwarded
        target.append(spec.get('target', flag))
        if spec.get('arity'):
            if spec.get('expand') == 'json_array':
                array = json.loads(flag_value)
                if not isinstance(array, list) or not array or not all(isinstance(item, str) for item in array):
                    raise ValueError(flag+' requires a nonempty JSON array of strings')
                target.extend(array)
            else:
                target.append(flag_value)
            if spec.get('arity') == '+':
                while index+1 < len(tokens) and not tokens[index+1].startswith('-'):
                    index += 1
                    target.append(tokens[index])
                if partial and index+1 == len(tokens):
                    pending = (flag, spec)
        index += 1
    if node.get('payload') and not payload:
        ready = False
    if any(flag not in seen for flag in node.get('required_flags', [])):
        ready = False
    dispatch_value = value
    if node.get('provider') == 'build_runs':
        run_name = selected_run(value, discover_runs(run_tree(data))) or ''
        dispatch_value = run_name + value[len(run_name):].replace('.impl.', '.', 1)
    internal = []
    for part in node.get('dispatch', []):
        if part == '{value}' and node.get('split_value'):
            internal.extend(dispatch_value.split(node['split_value']))
        elif part == '{payload}':
            internal.extend(payload)
        else:
            internal.append(part.replace('{value}', dispatch_value))
    if alias_path and ready:
        internal.extend(payload)
    if not owns_tail:
        for offset, item in enumerate(internal[:-1]):
            if item.startswith('--'):
                seen.add(item)
                values[item] = internal[offset+1]
    if '--build' in values:
        runs = discover_runs(run_tree(data))
        parsed = parse_selector(values['--build'], runs if (runs or data) else None)
        values.update(build_action=parsed.get("action") if parsed else None, build_valid=bool(parsed), build_stage='impl' if parsed and parsed.get('impl') else 'synth',
                      build_bitstream=bool(parsed and parsed.get('bitstream')),
                      build_new_impl=bool(parsed and parsed.get('impl') and parsed.get('attempt') == 'new'))
    for flag in seen & specs.keys():
        if not partial and not condition_matches(specs[flag].get('when', {}), seen - {flag}, values):
            raise ValueError(flag+' is unavailable for this command state')
    return dict(tree=tree, node=node, command=command, prefix=prefix, value=value,
                ready=ready, specs=specs, seen=seen, values=values, pending=pending,
                master=master_args, args=internal+forwarded, project=project, data=data,
                payload=payload, owns_tail=owns_tail)


def help_text(state: dict) -> str:
    node = state['node']
    prefix = state['prefix']
    if node.get('provider') == 'shortcuts' and state['ready']:
        lines = [f"Usage: hdlforge [master flags] {state['command']} [script arguments ...]",
                 'Everything after the alias name goes to its command, including --help.']
    elif node.get('payload'):
        suffix = 'PROGRAM [ARG ...]' if prefix == 'eval-cmd-argv' else 'COMMAND [COMMAND PART ...]'
        lines = [f'Usage: hdlforge [master flags] {prefix} {suffix}']
    else:
        lines = ['Usage: hdlforge '+(state['command'] or '<command>')+' [modifiers]']
    mapping = {} if state['value'] else node.get('commands', {})
    choices = {((prefix+'.') if prefix else '')+name: mapping['#'+name] for name in entries(mapping)}
    if node.get('provider'):
        dynamic = dynamic_choices(node['provider'], state['data'], state['project'])
        stem = state['value'].rstrip('.')+'.' if state['value'] else ''
        for name, description in dynamic.items():
            if not name.startswith(stem):
                continue
            child = stem+first_path_component(name[len(stem):])
            choices.setdefault(prefix+'.'+child, dynamic.get(child, 'Select '+child))
    if choices:
        lines.append('Commands:')
        lines.extend('  '+name+'  # '+description for name, description in choices.items())
    for label, group in [('Master flags', state['tree']['master_flags']), ('Command modifiers', node.get('flags', {}))]:
        lines.append(label+':')
        lines.extend('  '+name+(' VALUE' if spec.get('arity') else '')+'  # '+group['#'+name]
                     for name, spec in entries(group).items()
                     if not spec.get('hidden') and condition_matches(spec.get('when', {}), state['seen'], state['values']))
    return '\n'.join(lines)


def warn_misplaced_eval_argv_flags(state: dict) -> None:
    """Warn when argv payload tokens look like misplaced HDLForge flags."""
    if state['command'] != 'eval-cmd-argv':
        return
    if os.environ.get('HDLFORGE_JSON_COMMAND_PATH'):
        return  # An alias explicitly forwards its script arguments to this launcher.
    master_flags = entries(state['tree']['master_flags'])
    warned = set()
    for token in state['payload']:
        flag = token.partition('=')[0]
        if flag not in master_flags or flag in COMMON_CHILD_FLAGS or flag in warned:
            continue
        warned.add(flag)
        print(f'warning: {flag} appears after eval-cmd-argv; it will be passed to the program, '
              f'not processed by HDLForge; move it before eval-cmd-argv to use it as an HDLForge flag',
              file=sys.stderr)


def main() -> int:
    try:
        state = parse(sys.argv[1:], Path.cwd())
        warn_misplaced_eval_argv_flags(state)
        if not state['ready'] or {'--help', '-h'} & state['seen'] or state['command'].endswith('.help'):
            output = ['HELP', help_text(state)]
        else:
            output = ['RUN', str(len(state['master'])), *state['master'], *state['args']]
        sys.stdout.buffer.write(('\0'.join(output)+'\0').encode())
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print('error: '+str(error), file=sys.stderr)
        return 2


if __name__ == '__main__':
    sys.exit(main())
