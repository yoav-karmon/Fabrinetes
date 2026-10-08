"""Requirement inheritance, package failures and real launcher integration."""

from copy import deepcopy
from importlib import metadata
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

import env_verification as verification
import hdlforge_completion_backend as completion
from hdlforge_command_tree import parse
from hdlforge_json import normalize
import test_hdlforge_environment


class PythonRequirementsTest(unittest.TestCase):
    def setUp(self):
        self.settings = {'settings': {'env': {'default': {'python_settings': {'version': '3.12', 'packages': ['example==1.0']}},
                         'server': {'default': {'python_settings': {'version': '3.12.3'}},
                                    'user.name': {'python_settings': {'packages': ['other==2.0']}}}}}}

    def test_user_then_server_then_global_per_field(self):
        before = deepcopy(self.settings)
        values, sources = verification.resolve_settings(self.settings, 'server', 'user.name')
        self.assertEqual(values, dict(version='3.12.3', packages=['other==2.0']))
        self.assertTrue(sources['version'].endswith('server.default.python_settings.version'))
        self.assertTrue(sources['packages'].endswith('server.user.name.python_settings.packages'))
        self.assertEqual(self.settings, before)

    def test_missing_user_or_server_inherits_defaults(self):
        for server, user, version in [('server', 'unknown', '3.12.3'), ('unknown', 'unknown', '3.12')]:
            with self.subTest(server=server):
                values, _ = verification.resolve_settings(self.settings, server, user)
                self.assertEqual(values, dict(version=version, packages=['example==1.0']))

    def test_explicit_empty_packages_replaces_default_list(self):
        self.settings['settings']['env']['server']['user.name']['python_settings']['packages'] = []
        values, _ = verification.resolve_settings(self.settings, 'server', 'user.name')
        self.assertEqual(values['packages'], [])

    def test_missing_policy_cannot_pass(self):
        for value in ({}, {'default': {'version': '3.12'}}):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, 'missing'):
                verification.resolve_settings({'settings': {'env': {'default': {'python_settings': value.get('default', {})}}}}, 'server', 'user')

    def test_invalid_layers_and_duplicate_names_are_rejected(self):
        for layer in (None, [], {'version': '3'}, {'version': 3.12}, {'packages': None},
                      {'packages': ['name>=1']}, {'packages': ['a_b==1', 'A-b==2']},
                      {'packages': [42]}, {'pakages': []}):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                verification.validate_settings({'settings': {'env': {'default': {'python_settings': layer}}}})

    def test_python_minor_and_patch_precision(self):
        for expected, actual, status in [('3.12', '3.12.9', 'PASS'), ('3.12.3', '3.12.3', 'PASS'),
                                         ('3.12.3', '3.12.4', 'FAIL'), ('3.12', '3.13.0', 'FAIL')]:
            with self.subTest(expected=expected, actual=actual):
                rows = verification.verify(dict(version=expected, packages=[]), actual)
                self.assertEqual(rows[0]['status'], status)

    def test_missing_mismatched_and_unpinned_packages(self):
        def lookup(name):
            if name == 'missing':
                raise metadata.PackageNotFoundError(name)
            return '2.0'
        rows = verification.verify(dict(version='3.12', packages=['good==2.0', 'wrong==1.0', 'missing', 'any']), '3.12.3', lookup)
        self.assertEqual([row['status'] for row in rows], ['PASS', 'PASS', 'FAIL', 'FAIL', 'PASS'])
        self.assertIsNone(rows[3]['actual'])

    def test_path_schema_preserves_python_requirements(self):
        data = self.settings
        result, _ = normalize(data, 'paths', 'server', 'user')
        self.assertEqual(result['settings']['env']['default']['python_settings'], self.settings['settings']['env']['default']['python_settings'])
        self.assertNotIn('path', result['settings']['env']['default']['python_settings'])

    def test_command_routing_help_and_completion(self):
        result = parse(['settings.python.verify', '--json'], Path.cwd())
        self.assertEqual(result['args'], ['--tool', 'env_settings', 'python', 'verify', '--json'])
        matches = completion.complete_command([], 'settings.python.', Path.cwd())[0].completions
        self.assertIn('settings.python.verify', matches)


class PythonVerificationLauncherTest(unittest.TestCase):
    setUp = test_hdlforge_environment.LauncherEnvironmentTest.setUp

    def configure(self, packages=None, version=None):
        path = self.project / 'sample.hdlforge.json'
        data = json.loads(path.read_text())
        data['settings']['env']['default'] = {'python_settings': {
            'version': version or '.'.join(platform.python_version().split('.')[:2]),
            'packages': [] if packages is None else packages}}
        path.write_text(json.dumps(data))

    def invoke(self, *args):
        return subprocess.run([str(self.wrapper), '--no-print', *args], cwd=self.project,
                              env=self.env, capture_output=True, text=True)

    def test_verifies_root_policy_in_selected_project_environment(self):
        self.configure(['fixture-dist==7.2'])
        packages = self.root / 'package folder'
        info = packages / 'fixture_dist-7.2.dist-info'
        info.mkdir(parents=True)
        (info / 'METADATA').write_text('Metadata-Version: 2.1\nName: fixture-dist\nVersion: 7.2\n')
        child = self.project / 'child'
        child.mkdir()
        project = child / 'child.hdlforge.json'
        # Root policy applies, while the selected project's import paths do apply.
        project.write_text(json.dumps({'settings': {'env': {
            'test-host': {'test-user': {'pythonpath': [str(packages)]}},
            'default': {'python_settings': {'version': '0.0', 'packages': ['absent']}}}}}))
        result = self.invoke('--project', str(project), 'settings.python.verify', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report['status'], 'PASS')
        self.assertEqual(report['checks'][1]['actual'], '7.2')
        self.assertEqual(report['repository'], str(self.project / 'sample.hdlforge.json'))
        self.assertEqual((report['server'], report['user']), ('test-host', 'test-user'))

    def test_reports_mismatch_without_installing_or_editing(self):
        self.configure(['hdlforge-definitely-missing-package==1.0'], '0.0')
        path = self.project / 'sample.hdlforge.json'
        before = path.read_bytes()
        result = self.invoke('settings.python.verify', '--json')
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual([row['status'] for row in json.loads(result.stdout)['checks']], ['FAIL', 'FAIL'])
        self.assertEqual(path.read_bytes(), before)
        # Explicit verification does not introduce automatic checks on other commands.
        self.assertEqual(self.invoke('eval-cmd', 'true').returncode, 0)

    def test_missing_policy_and_dry_run(self):
        result = self.invoke('settings.python.verify', '--json')
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(json.loads(result.stdout)['status'], 'ERROR')
        self.configure()
        result = self.invoke('--dry-run', 'settings.python.verify')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('Result: PASS', result.stdout)

    def test_requirements_are_not_listed_as_a_server(self):
        self.configure()
        script = self.wrapper.with_name('hdlforge_environment.bash')
        result = subprocess.run(['bash', '-c', 'source "$1"; hdlforge_list_host_and_users "$2"',
                                 'bash', str(script), str(self.project / 'sample.hdlforge.json')],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'test-host:test-user')

    def test_uses_interpreter_selected_by_cli_path(self):
        self.configure()
        self.bin_dir.joinpath('python3').symlink_to(sys.executable)
        result = self.invoke('--env-path', json.dumps([str(self.bin_dir)]), 'settings.python.verify', '--json')
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)['active']['interpreter'], str(self.bin_dir / 'python3'))


if __name__ == '__main__':
    unittest.main()
