"""Settings management through real HDLForge launches in disposable repositories."""

from argparse import Namespace
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import env_settings
import env_settings_model as model
import env_settings_ssh as ssh
from hdlforge_command_tree import parse
from hdlforge_completion_backend import complete_command
import test_hdlforge_environment


class SettingsLauncherTest(unittest.TestCase):
    def setUp(self):
        test_hdlforge_environment.LauncherEnvironmentTest.setUp(self)
        self.config = self.project / 'sample.hdlforge.json'
        self.input_file = self.root / 'incoming.json'

    def invoke(self, *args):
        return subprocess.run([str(self.wrapper), '--no-print', *args], cwd=self.project,
                              env=self.env, text=True, capture_output=True)

    def read_entry(self):
        return json.loads(self.config.read_text())['settings']['env']['test-host']['test-user']

    def test_show_includes_all_groups_and_active_identity(self):
        before = self.config.read_bytes()
        result = self.invoke('settings.show', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(set(report['settings']), set(model.SCOPES))
        self.assertEqual(report['server'], 'test-host')
        self.assertEqual(report['repository'], str(self.config))
        self.assertIn('active', report['settings']['path'])
        self.assertEqual(self.config.read_bytes(), before)

    def test_path_import_changes_only_selected_field(self):
        before = json.loads(self.config.read_text())
        self.input_file.write_text(json.dumps(['/usr/bin', '/bin', '/usr/bin']))
        result = self.invoke('settings.path.import', '--input', str(self.input_file), '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        expected = deepcopy(before)
        expected['settings']['env']['test-host']['test-user']['path'] = ['/usr/bin', '/bin']
        self.assertEqual(json.loads(self.config.read_text()), expected)
        self.assertEqual(json.loads(result.stdout)['status'], 'UPDATED')

    def test_path_dry_run_never_writes(self):
        self.input_file.write_text('["/new/path"]')
        before = self.config.read_bytes()
        for action in ('import-dry-run', 'merge-dry-run'):
            with self.subTest(action=action):
                result = self.invoke('settings.path.' + action, '--input', str(self.input_file), '--json')
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn('/new/path', json.loads(result.stdout)['diff'])
                self.assertEqual(self.config.read_bytes(), before)

    def test_global_dry_run_previews_mutation(self):
        self.input_file.write_text('["/new/path"]')
        before = self.config.read_bytes()
        result = self.invoke('--dry-run', 'settings.pythonpath.import', '--input', str(self.input_file), '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'DRY RUN')
        self.assertEqual(self.config.read_bytes(), before)

    def test_pythonpath_merge_deduplicates_and_keeps_imports(self):
        data = json.loads(self.config.read_text())
        env = data['settings']['env']['test-host']['test-user']
        env['pythonpath'] = ['/existing']
        env['pythonpath_import'] = ['shared.pythonpath']
        data['shared'] = {'pythonpath': ['/inherited']}
        self.config.write_text(json.dumps(data))
        self.input_file.write_text('["/existing", "/incoming"]')
        result = self.invoke('settings.pythonpath.merge', '--input', str(self.input_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_entry()['pythonpath'], ['/existing', '/incoming'])
        self.assertEqual(self.read_entry()['pythonpath_import'], ['shared.pythonpath'])

    def test_invalid_path_input_does_not_write(self):
        self.input_file.write_text('[3]')
        before = self.config.read_bytes()
        result = self.invoke('settings.path.import', '--input', str(self.input_file))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(self.config.read_bytes(), before)

    def test_relative_input_uses_launch_directory_with_explicit_project(self):
        child = self.project / 'child'
        child.mkdir()
        project = child / 'child.hdlforge.json'
        project.write_text('{}')
        self.project.joinpath('input.json').write_text('["/usr/bin"]')
        result = self.invoke('--project', str(project), 'settings.path.import', '--input', 'input.json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.read_entry()['path'], ['/usr/bin'])
        self.assertEqual(project.read_text(), '{}')

    def test_python_global_defaults_import_and_user_inheritance(self):
        requirements = dict(version='3.12', packages=['scapy==2.7.0'])
        self.input_file.write_text(json.dumps(requirements))
        result = self.invoke('settings.python.import', '--server', 'default', '--input', str(self.input_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.invoke('settings.python.print-as-json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['effective'], requirements)
        self.assertEqual(report['sources']['version'], 'settings.env.default.python_settings.version')

    def test_new_dotted_user_entry_and_list_json(self):
        self.input_file.write_text('["/usr/bin"]')
        result = self.invoke('settings.path.import', '--server', 'another-host', '--user', 'user.name', '--input', str(self.input_file))
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self.invoke('settings.path.list-json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['path']['another-host']['user.name']['path'], ['/usr/bin'])
        data = json.loads(self.config.read_text())
        self.assertEqual(data['settings']['env']['another-host']['user.name'], {'path': ['/usr/bin'], 'path_import': []})

    def test_path_verify_fails_for_missing_directory(self):
        data = json.loads(self.config.read_text())
        data['settings']['env']['test-host']['test-user']['path'].append(str(self.root / 'missing'))
        self.config.write_text(json.dumps(data))
        result = self.invoke('settings.path.verify', '--json')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(json.loads(result.stdout)['checks'][-1]['status'], 'FAIL')

    def test_ssh_import_previews_then_copies_config_only(self):
        source = self.home / '.ssh/config'
        source.parent.mkdir()
        source.write_text('Host example\n  HostName example.internal\n')
        source.parent.joinpath('id_private').write_text('PRIVATE-KEY-NOT-TO-COPY')
        before = self.config.read_bytes()
        result = self.invoke('settings.ssh-config.import-dry-run', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('example.internal', json.loads(result.stdout)['diff'])
        self.assertFalse(self.project.joinpath('environment').exists())
        self.assertEqual(self.config.read_bytes(), before)
        result = self.invoke('settings.ssh-config.import')
        self.assertEqual(result.returncode, 0, result.stderr)
        target = self.project / self.read_entry()['ssh_config_file']
        self.assertEqual(target.read_text(), source.read_text())
        self.assertEqual([path.name for path in target.parent.iterdir()], ['config'])
        result = self.invoke('settings.ssh-config.verify', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'PASS')

    def test_ssh_merge_conflict_does_not_change_either_file(self):
        source = self.root / 'ssh.conf'
        source.write_text('Host example\n HostName original\n')
        self.assertEqual(self.invoke('settings.ssh-config.import', '--input', str(source)).returncode, 0)
        target = self.project / self.read_entry()['ssh_config_file']
        before, ssh_before = self.config.read_bytes(), target.read_bytes()
        source.write_text('Host example\n HostName incoming\n')
        result = self.invoke('settings.ssh-config.merge', '--input', str(source))
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn('conflict', result.stderr)
        self.assertEqual(self.config.read_bytes(), before)
        self.assertEqual(target.read_bytes(), ssh_before)

    def test_ssh_file_rolls_back_when_json_publish_fails(self):
        source = self.root / 'ssh.conf'
        source.write_text('Host example\n HostName example.internal\n')
        before = self.config.read_text()
        args = Namespace(scope='ssh-config', input=source, action='import', dry_run=False,
                         repository=self.config, server='test-host', user='test-user', on_collision='error')
        with patch.object(env_settings, 'write_update', side_effect=ValueError('Concurrent edit')):
            with self.assertRaisesRegex(ValueError, 'Concurrent edit'):
                env_settings.update(args, json.loads(before), before)
        self.assertEqual(self.config.read_text(), before)
        self.assertFalse(self.project.joinpath('environment/ssh-configs/test-host/test-user/config').exists())

    def test_python_merge_writes_new_package_and_preserves_default(self):
        data = json.loads(self.config.read_text())
        defaults = dict(version='3.12', packages=['old==1'])
        data['settings']['env']['default'] = {'python_settings': defaults}
        self.config.write_text(json.dumps(data))
        self.input_file.write_text(json.dumps(dict(version='3.12', packages=['new==2'])))
        result = self.invoke('settings.python.merge', '--input', str(self.input_file))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        settings = json.loads(self.config.read_text())['settings']['env']
        self.assertEqual(settings['default']['python_settings'], defaults)
        self.assertEqual(settings['test-host']['test-user']['python_settings']['packages'], ['old==1', 'new==2'])

    def test_local_capture_dry_run_is_explicit_and_read_only(self):
        before = self.config.read_bytes()
        result = self.invoke('settings.pythonpath.import-dry-run', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'DRY RUN')
        self.assertEqual(self.config.read_bytes(), before)


class SettingsModelTest(unittest.TestCase):
    def test_merge_includes_inherited_python_packages(self):
        data = {'settings': {'env': {'default': {'python_settings': {'version': '3.12', 'packages': ['old==1']}}}}}
        result = model.propose(data, 'python', 'host', 'user', {'version': '3.12', 'packages': ['new==2']}, True, 'error')
        self.assertEqual(result['settings']['env']['host']['user']['python_settings']['packages'], ['old==1', 'new==2'])
        self.assertNotIn('host', data['settings']['env'])

    def test_python_collision_policy(self):
        old = dict(version='3.12', packages=['Some_pkg==1'])
        new = dict(version='3.12', packages=['some-pkg==2'])
        with self.assertRaisesRegex(ValueError, 'Package conflict'):
            model.merge_python(old, new, 'error')
        self.assertEqual(model.merge_python(old, new, 'existing')['packages'], ['Some_pkg==1'])
        self.assertEqual(model.merge_python(old, new, 'incoming')['packages'], ['some-pkg==2'])

    def test_ssh_literal_hosts_merge_and_collision_policy(self):
        old = 'Host old\n HostName old.internal\n'
        new = 'Host new\n HostName new.internal\n'
        merged = ssh.merge(old, new, 'error')
        self.assertIn(old.strip(), merged)
        self.assertIn(new.strip(), merged)
        changed = 'Host old\n HostName changed.internal\n'
        self.assertNotIn('changed', ssh.merge(old, changed, 'existing'))
        self.assertIn('changed', ssh.merge(old, changed, 'incoming'))

    def test_ssh_complex_rules_are_not_silently_rewritten(self):
        for content in ('Host *\n User me\n', 'Match exec "touch /tmp/never"\n User me\n', 'Include other.conf\n'):
            with self.subTest(content=content), self.assertRaises(ValueError):
                ssh.merge(content, 'Host new\n User me\n', 'incoming')

    def test_ssh_input_rejects_key_material(self):
        with self.assertRaisesRegex(ValueError, 'expected SSH config'):
            ssh.blocks('-----BEGIN OPENSSH PRIVATE KEY-----\nnot-a-config\n')

    def test_settings_actions_are_real_routes_with_matching_completion(self):
        actions = ('show', 'import', 'import-dry-run', 'merge', 'merge-dry-run', 'print-as-json', 'lint-user-settings', 'list-json', 'verify')
        for scope in model.SCOPES:
            with self.subTest(scope=scope):
                candidates = complete_command([], 'settings.' + scope + '.', Path.cwd())[0].completions
                self.assertTrue(all('settings.' + scope + '.' + action in candidates for action in actions))
                self.assertEqual(parse(['settings.' + scope + '.merge'], Path.cwd())['args'], ['--tool', 'env_settings', scope, 'merge'])
                self.assertIn('--input', complete_command(['settings.' + scope + '.import'], '--', Path.cwd())[0].completions)
                self.assertNotIn('--input', complete_command(['settings.' + scope + '.verify'], '--', Path.cwd())[0].completions)


if __name__ == '__main__':
    unittest.main()
