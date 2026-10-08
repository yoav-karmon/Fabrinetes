"""Common defaults for known and future fields, through real startup as well."""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
import unittest

import environment_defaults as defaults
from env_settings_model import propose
from hdlforge_json import normalize
import test_hdlforge_environment


class EnvironmentDefaultsTest(unittest.TestCase):
    def setUp(self):
        self.data = {'settings': {'env': {
            'default': {'path': ['/global'], 'pythonpath': ['/modules'],
                        'variables': {'A': 'global', 'B': 'global'},
                        'tools': {'vivado': '/global/vivado', 'verilator': '/global/verilator'},
                        'python_settings': {'version': '3.12', 'packages': ['example==1']},
                        'future_option': {'deep': {'a': 1, 'b': 2}}},
            'server': {'default': {'variables': {'A': 'server'}, 'python_settings': {'version': '3.12.3'}},
                       'user.name': {'tools': {'vivado': '/user/vivado'},
                                     'future_option': {'deep': {'b': 3}}}}}}}

    def test_nested_objects_inherit_missing_fields_for_all_types(self):
        original = deepcopy(self.data)
        value, sources = defaults.resolve(self.data, 'server', 'user.name')
        self.assertEqual(value['tools'], {'vivado': '/user/vivado', 'verilator': '/global/verilator'})
        self.assertEqual(value['variables'], {'A': 'server', 'B': 'global'})
        self.assertEqual(value['python_settings'], {'version': '3.12.3', 'packages': ['example==1']})
        self.assertEqual(value['future_option'], {'deep': {'a': 1, 'b': 3}})
        self.assertEqual(sources['future_option.deep.b'], 'settings.env.server.user.name.future_option.deep.b')
        self.assertEqual(self.data, original)

    def test_missing_user_uses_server_and_global(self):
        value, _ = defaults.resolve(self.data, 'server', 'absent')
        self.assertEqual(value['variables'], {'A': 'server', 'B': 'global'})
        self.assertEqual(value['path'], ['/global'])

    def test_missing_server_uses_global(self):
        value, _ = defaults.resolve(self.data, 'absent', 'absent')
        self.assertEqual(value, self.data['settings']['env']['default'])

    def test_list_override_including_empty_is_explicit(self):
        self.data['settings']['env']['server']['user.name']['path'] = []
        value, _ = defaults.resolve(self.data, 'server', 'user.name')
        self.assertEqual(value['path'], [])
        self.assertEqual(value['pythonpath'], ['/modules'])

    def test_new_global_field_is_visible_without_user_updates(self):
        self.data['settings']['env']['default']['new_setting'] = {'option': True}
        value, _ = defaults.resolve(self.data, 'server', 'user.name')
        self.assertEqual(value['new_setting'], {'option': True})
        self.assertNotIn('new_setting', self.data['settings']['env']['server']['user.name'])

    def test_schema_update_does_not_materialize_defaults_in_users(self):
        result, _ = normalize(self.data, 'paths', 'server', 'user.name')
        self.assertEqual(result['settings']['env']['server']['user.name'], self.data['settings']['env']['server']['user.name'])
        self.assertEqual(result['settings']['env']['server']['default'], self.data['settings']['env']['server']['default'])

    def test_path_merge_keeps_inherited_paths(self):
        result = propose(self.data, 'path', 'server', 'user.name', ['/new'], True, 'error')
        self.assertEqual(result['settings']['env']['server']['user.name']['path'], ['/global', '/new'])

    def test_global_path_write_targets_user_shaped_default(self):
        result = propose(self.data, 'path', 'default', 'ignored', ['/new'], False, 'error')
        self.assertEqual(result['settings']['env']['default']['path'], ['/new'])
        self.assertNotIn('ignored', result['settings']['env']['default'])

    def test_legacy_python_table_fails_with_migration_message(self):
        self.data['settings']['env']['python_settings'] = {}
        with self.assertRaisesRegex(ValueError, 'Move settings.env.python_settings'):
            defaults.resolve(self.data, 'server', 'user.name')


class EnvironmentDefaultsLauncherTest(unittest.TestCase):
    def setUp(self):
        test_hdlforge_environment.LauncherEnvironmentTest.setUp(self)
        self.config = self.project / 'sample.hdlforge.json'
        data = json.loads(self.config.read_text())
        base = data['settings']['env']['test-host']['test-user']
        base['variables'] = {'VALUE': 'global', 'OTHER': 'inherited'}
        data['settings']['env'] = {'default': base, 'test-host': {
            'default': {'variables': {'VALUE': 'server'}},
            'test-user': {'variables': {'VALUE': 'user'}}}}
        self.config.write_text(json.dumps(data))

    def invoke(self, *args):
        return subprocess.run([str(self.wrapper), '--no-print', *args], cwd=self.project,
                              env=self.env, text=True, capture_output=True)

    def test_startup_uses_user_override_and_global_missing_field(self):
        result = self.invoke('eval-cmd', 'printf "%s|%s" "$VALUE" "$OTHER"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'user|inherited')

    def test_startup_unknown_user_uses_server_default(self):
        self.env['HDLFORGE_HOST_USER'] = 'absent'
        result = self.invoke('eval-cmd', 'printf "%s|%s" "$VALUE" "$OTHER"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'server|inherited')

    def test_startup_unknown_server_uses_global_default(self):
        self.env['HOST_MACHINE'] = 'absent'
        result = self.invoke('eval-cmd', 'printf "%s|%s" "$VALUE" "$OTHER"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'global|inherited')

    def test_empty_configured_path_uses_shell_path_including_nested_launch(self):
        data = json.loads(self.config.read_text())
        data['settings']['env']['default']['path'] = []
        self.config.write_text(json.dumps(data))
        self.env['PATH'] = str(self.bin_dir) + ':' + self.env['PATH']
        for command in ('command -v vivado', "hdlforge --no-print eval-cmd 'command -v vivado'"):
            with self.subTest(command=command):
                result = self.invoke('eval-cmd', command)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), str(self.bin_dir / 'vivado'))

    def test_imported_path_prevents_shell_fallback(self):
        data = json.loads(self.config.read_text())
        data['shared'] = {'path': data['settings']['env']['default']['path']}
        data['settings']['env']['default'].update(path=[], path_import=['shared.path'])
        self.config.write_text(json.dumps(data))
        self.env['PATH'] = str(self.bin_dir) + ':' + self.env['PATH']
        result = self.invoke('eval-cmd', 'printf "%s" "$PATH"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn(str(self.bin_dir), result.stdout)

    def test_inherited_tools_are_applied_by_startup(self):
        data = json.loads(self.config.read_text())
        data['settings']['env']['default']['tools'] = {'vivado': str(self.settings)}
        self.config.write_text(json.dumps(data))
        result = self.invoke('eval-cmd', 'command -v vivado')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.bin_dir / 'vivado'))
        self.assertIn('TOOL_STARTUP', result.stderr)

    def test_project_overlay_resolves_its_own_defaults(self):
        child = self.project / 'child'
        child.mkdir()
        project = child / 'child.hdlforge.json'
        project.write_text(json.dumps({'settings': {'env': {'default': {'variables': {'PROJECT_ONLY': 'yes'}}}}}))
        result = self.invoke('--project', str(project), 'eval-cmd', 'printf "%s|%s" "$VALUE" "$PROJECT_ONLY"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, 'user|yes')

    def test_inherited_path_imports_expand_before_local(self):
        data = json.loads(self.config.read_text())
        data['shared'] = {'pythonpath': ['shared']}
        data['settings']['env']['default']['pythonpath_import'] = ['shared.pythonpath']
        data['settings']['env']['test-host']['test-user']['pythonpath'] = ['user']
        self.config.write_text(json.dumps(data))
        result = self.invoke('eval-cmd', 'printf "%s" "$PYTHONPATH"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(self.project / 'user') + ':' + str(self.project / 'shared'))

    def test_server_default_can_be_edited_by_settings_manager(self):
        source = self.project / 'paths.json'
        source.write_text('["/usr/bin"]')
        result = self.invoke('settings.path.import', '--user', 'default', '--input', str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(self.config.read_text())['settings']['env']
        self.assertEqual(data['test-host']['default']['path'], ['/usr/bin'])
        self.assertNotIn('path', data['test-host']['test-user'])

    def test_show_reports_inherited_arbitrary_keys(self):
        data = json.loads(self.config.read_text())
        data['settings']['env']['default']['future_setting'] = {'a': 9}
        self.config.write_text(json.dumps(data))
        result = self.invoke('settings.show', '--json')
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['effective_environment']['future_setting'], {'a': 9})
        self.assertEqual(report['sources']['future_setting.a'], 'settings.env.default.future_setting.a')


if __name__ == '__main__':
    unittest.main()
