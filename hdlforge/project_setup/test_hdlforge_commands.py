"""Public command-tree and nested environment behavior."""
import json
from pathlib import Path
import shlex
import subprocess
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
        result = self.run_command('eval-cmd', 'touch '+shlex.quote(str(marker)), '--dry-run')
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

    def test_legacy_action_flags_are_rejected(self):
        for args in [('--tool', 'vivado'), ('--cmd', 'true'), ('--eval_json', 'nested'),
                     ('nested',), ('eval-cmd', 'true', '--append', 'bad')]:
            with self.subTest(args=args):
                result = self.run_command(*args)
                self.assertNotEqual(result.returncode, 0)

    def test_nested_values_are_preserved_by_default(self):
        child = 'hdlforge eval-cmd '+shlex.quote('printf "%s|%s" "$VALUE" "$ADDED"')
        child += ' --env-var '+shlex.quote('[{"VALUE":"child"},{"ADDED":"new"}]')
        result = self.run_command('eval-cmd', child, '--env-var', '[{"VALUE":"parent"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'parent|new')
        self.assertIn('preserving inherited environment variable VALUE', result.stderr)

    def test_nested_overwrite_requires_explicit_permission(self):
        child = 'hdlforge eval-cmd '+shlex.quote('printf "%s" "$VALUE"')
        child += ' --allow-env-overwrite --env-var '+shlex.quote('[{"VALUE":"child"}]')
        result = self.run_command('eval-cmd', child, '--env-var', '[{"VALUE":"parent"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'child')

    def test_overwrite_permission_is_not_inherited(self):
        child = 'hdlforge eval-cmd '+shlex.quote('printf "%s" "$VALUE"')
        child += ' --env-var '+shlex.quote('[{"VALUE":"child"}]')
        result = self.run_command('eval-cmd', child, '--allow-env-overwrite', '--env-var', '[{"VALUE":"parent"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'parent')

    def test_master_flags_exist_on_every_leaf(self):
        for command in ('paths.show', 'vivado.console.start', 'sim-verilator.sim', 'eval-cmd'):
            with self.subTest(command=command):
                result = self.run_command(command+'.help')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('--allow-env-overwrite', result.stdout)
                self.assertIn('--env-python', result.stdout)

    def test_explicit_shortcut_executes_only_its_leaf(self):
        result = self.run_command('aliases.nested')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.wrapper))

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
        child = shlex.join(['hdlforge', 'eval-cmd', 'printf "%s" "$VALUE"',
                            '--project', str(child_project), '--allow-env-overwrite'])
        result = self.run_command('eval-cmd', child, '--env-var', '[{"VALUE":"parent"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'child-project')

    def test_master_option_after_eval_payload_selects_project(self):
        child = self.project / 'other'
        child.mkdir()
        selected = child / 'other.hdlforge.json'
        selected.write_text('{}')
        result = self.run_command('eval-cmd', 'printf "%s" "$HDLFORGE_PROJECT_FILE"', '--project', str(selected))
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
