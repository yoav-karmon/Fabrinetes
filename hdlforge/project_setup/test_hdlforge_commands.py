"""Public command-tree and nested environment behavior."""
import json
from pathlib import Path
import shlex
import subprocess
import sys
import unittest

from hdlforge_command_tree import parse
import test_hdlforge_environment


class DottedCommandsTest(unittest.TestCase):
    setUp = test_hdlforge_environment.LauncherEnvironmentTest.setUp

    def run_command(self, *args):
        return subprocess.run([str(self.wrapper), '--no-print', *args], cwd=self.project,
                              env=self.env, capture_output=True, text=True)

    def test_incomplete_build_prints_help_without_launching(self):
        result = self.run_command('vivado.build')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('vivado.build.status', result.stdout)
        self.assertIn('--allow-env-overwrite', result.stdout)
        self.assertNotIn('TOOL_STARTUP', result.stderr)

    def test_eval_dry_run_does_not_execute_payload(self):
        marker = self.root / 'must-not-exist'
        result = self.run_command('--dry-run', 'eval-cmd', 'touch '+shlex.quote(str(marker)))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('execution skipped', result.stdout)
        self.assertFalse(marker.exists())

    def test_missing_console_payload_prints_contextual_help(self):
        result = self.run_command('vivado.console.send')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('--cmd VALUE', result.stdout)
        self.assertNotIn('TOOL_STARTUP', result.stderr)

    def test_eval_payload_is_opaque(self):
        result = self.run_command('eval-cmd', 'printf "%s" "--project --tool --allow-env-overwrite"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '--project --tool --allow-env-overwrite')

    def test_eval_multiple_command_parts_are_joined_by_bash(self):
        result = self.run_command('eval-cmd', 'printf "%s|%s"', 'first', 'second')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'first|second')

    def test_eval_argv_runs_script_with_exact_argument_boundaries(self):
        script = self.root / 'eval-target.sh'
        script.write_text('#!/bin/bash\nprintf "%s|%s" "$1" "$2"\n')
        script.chmod(0o755)
        launcher = ('wrapper=$1; script_path=$2; shift 2; '
                    'exec "$wrapper" --no-print eval-cmd-argv "$script_path" "$@"')
        result = subprocess.run(
            ['bash', '-c', launcher, 'launcher', str(self.wrapper), str(script),
             'hello world', 'a|b;*'],
            cwd=self.project,
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'hello world|a|b;*')

    def test_eval_argv_dry_run_quotes_argument_boundaries(self):
        result = self.run_command('--dry-run', 'eval-cmd-argv', 'printf', '%s', 'hello world')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn(r'printf %s hello\ world', result.stdout)
        self.assertIn('execution skipped', result.stdout)

    def test_eval_argv_warns_about_misplaced_hdlforge_flags(self):
        for argument in ('--env-python', '--project=child.hdlforge.json'):
            with self.subTest(argument=argument):
                result = self.run_command('eval-cmd-argv', 'printf', '%s', argument)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout, argument)
                self.assertIn(f'warning: {argument.partition("=")[0]} appears after eval-cmd-argv',
                              result.stderr)
                self.assertIn('will be passed to the program', result.stderr)

    def test_eval_argv_allows_common_child_help_flag_without_warning(self):
        result = self.run_command('eval-cmd-argv', 'printf', '%s', '--help')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '--help')
        self.assertEqual(result.stderr, '')

    def test_eval_owns_master_looking_command_parts(self):
        result = self.run_command('eval-cmd', 'printf "%s|%s"', '--project', 'child-value')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, '--project|child-value')

    def test_legacy_action_flags_are_rejected(self):
        for args in [('--tool', 'vivado'), ('--cmd', 'true'), ('--eval_json', 'nested'),
                     ('nested',)]:
            with self.subTest(args=args):
                result = self.run_command(*args)
                self.assertNotEqual(result.returncode, 0)

    def test_nested_values_are_preserved_by_default(self):
        child = shlex.join(['hdlforge', '--env-var', '[{"VALUE":"child"},{"ADDED":"new"}]',
                            'eval-cmd', 'printf "%s|%s" "$VALUE" "$ADDED"'])
        result = self.run_command('--env-var', '[{"VALUE":"parent"}]', 'eval-cmd', child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'parent|new')
        self.assertIn('preserving inherited environment variable VALUE', result.stderr)

    def test_nested_overwrite_requires_explicit_permission(self):
        child = shlex.join(['hdlforge', '--allow-env-overwrite', '--env-var', '[{"VALUE":"child"}]',
                            'eval-cmd', 'printf "%s" "$VALUE"'])
        result = self.run_command('--env-var', '[{"VALUE":"parent"}]', 'eval-cmd', child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'child')

    def test_overwrite_permission_is_not_inherited(self):
        child = shlex.join(['hdlforge', '--env-var', '[{"VALUE":"child"}]',
                            'eval-cmd', 'printf "%s" "$VALUE"'])
        result = self.run_command('--allow-env-overwrite', '--env-var', '[{"VALUE":"parent"}]',
                                  'eval-cmd', child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'parent')

    def test_master_flags_exist_on_every_leaf(self):
        for command in ('settings.show', 'vivado.console.start', 'sim-verilator.sim',
                        'eval-cmd', 'eval-cmd-argv'):
            with self.subTest(command=command):
                result = self.run_command(command+'.help')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--allow-env-overwrite', result.stdout)
                self.assertIn('--env-python', result.stdout)

    def test_explicit_shortcut_executes_only_its_leaf(self):
        result = self.run_command('aliases.nested')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.wrapper))

    def test_alias_forwards_literal_arguments_through_nested_execution(self):
        # Child-looking master flags must never change the HDLForge invocation.
        script = self.root / 'capture arguments.py'
        script.write_text('import json, sys\nprint(json.dumps(sys.argv[1:]))\n')
        project = self.project / 'sample.hdlforge.json'
        data = json.loads(project.read_text())
        base = shlex.join([sys.executable, str(script)])
        data['LLM_orch'].update(capture=base, relay='hdlforge eval-cmd-argv '+base)
        project.write_text(json.dumps(data))
        marker = self.root / 'must not execute'
        arguments = ['--implementation', 'path with spaces', '', 'line1\nline2',
                     '--help', '--project', 'not-a-project', '--dry-run', '--tool', 'git_config',
                     '--env-var', '[{"VALUE":"child"}]', '--file', 'relative path',
                     '--', '*', 'a;b|c', '"quotes"', '\\backslash',
                     '$(touch '+shlex.quote(str(marker))+')', '`touch '+shlex.quote(str(marker))+'`']
        for alias in ('capture', 'relay'):
            with self.subTest(alias=alias):
                result = self.run_command('aliases.'+alias, *arguments)
                self.assertEqual(result.returncode, 0, result.stdout+result.stderr)
                self.assertEqual(json.loads(result.stdout), arguments)
                self.assertEqual(result.stderr, '')
                self.assertFalse(marker.exists())
        preview = self.run_command('--dry-run', 'aliases.capture', *arguments)
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertIn('execution skipped', preview.stdout)

    def test_action_modifiers_cannot_select_another_action(self):
        result = self.run_command('vivado.console.start', '--project_console', 'stop')
        self.assertNotEqual(result.returncode, 0)

    def test_permitted_project_overlay_replaces_parent_cli_value(self):
        child_dir = self.project / 'child'
        child_dir.mkdir()
        child_project = child_dir / 'child.hdlforge.json'
        child_project.write_text(json.dumps({'settings': {'env': {'test-host': {'test-user': {
            'variables': {'VALUE': 'child-project'},
        }}}}}))
        child = shlex.join(['hdlforge', '--project', str(child_project), '--allow-env-overwrite',
                            'eval-cmd', 'printf "%s" "$VALUE"'])
        result = self.run_command('--env-var', '[{"VALUE":"parent"}]', 'eval-cmd', child)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'child-project')

    def test_master_option_before_eval_payload_selects_project(self):
        child = self.project / 'other'
        child.mkdir()
        selected = child / 'other.hdlforge.json'
        selected.write_text('{}')
        result = self.run_command('--project', str(selected), 'eval-cmd',
                                  'printf "%s" "$HDLFORGE_PROJECT_FILE"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(selected))

    def test_build_cleanup_modifier_is_valid_on_its_leaf(self):
        state = parse(['vivado.build.clean_ignore_artifacts'], self.project)
        self.assertIn('--build_clean_ignore_artifacts', state['args'])

    def test_hardware_command_payload_preserves_spaces_and_dots(self):
        state = parse(['hw-server.chain', '--commands', '["open device", "program path/file.bit", "q"]'], self.project)
        self.assertEqual(state['args'][-4:], ['--interactive-chain', 'open device', 'program path/file.bit', 'q'])


if __name__ == '__main__':
    unittest.main()
