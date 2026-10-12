"""Tests for operating-system and system-package environment settings."""

import unittest
from unittest.mock import patch

import env_settings_system as system


class SystemSettingsTest(unittest.TestCase):
    def test_package_validation_and_merge(self):
        self.assertEqual(system.validate_packages(['git=1:2.43', 'jq'], 'test'), ['git=1:2.43', 'jq'])
        with self.assertRaisesRegex(ValueError, 'repeats git'):
            system.validate_packages(['git=1', 'git=2'], 'test')
        with self.assertRaisesRegex(ValueError, 'conflict'):
            system.merge_packages(['git=1'], ['git=2'], 'error')
        self.assertEqual(system.merge_packages(['git=1'], ['git=2'], 'incoming'), ['git=2'])

    def test_os_validation_and_merge(self):
        old = dict(id='ubuntu', version_id='24.04', architecture='x86_64')
        system.validate_os(old, 'test')
        with self.assertRaisesRegex(ValueError, 'OS setting conflict'):
            system.merge_os(old, {**old, 'version_id': '26.04'}, 'error')

    @patch.object(system, 'installed_packages', return_value=['git=1', 'jq=2'])
    def test_package_verification(self, _installed):
        rows = system.verify_packages(['git=1', 'jq=3', 'missing'])
        self.assertEqual([row['status'] for row in rows], ['PASS', 'FAIL', 'FAIL'])

    @patch.object(system, 'os_release', return_value=dict(id='ubuntu', version_id='24.04', architecture='x86_64'))
    def test_os_verification(self, _release):
        rows = system.verify_os(dict(id='ubuntu', version_id='24.04', architecture='aarch64'))
        self.assertEqual([row['status'] for row in rows], ['PASS', 'PASS', 'FAIL'])


if __name__ == '__main__':
    unittest.main()
