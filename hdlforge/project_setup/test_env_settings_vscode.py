"""Tests for repository VS Code environment settings."""

import unittest

import env_settings
import env_settings_vscode as vscode


class VSCodeSettingsTest(unittest.TestCase):
    def test_extensions_are_normalized_and_duplicates_rejected(self):
        value = dict(extensions=['Publisher.Tool@1'], settings={})
        self.assertEqual(vscode.extension(value['extensions'][0]), ('publisher.tool', '1'))
        with self.assertRaisesRegex(ValueError, 'repeats extension publisher.tool'):
            vscode.validate(dict(extensions=['Publisher.Tool', 'publisher.tool@2'], settings={}), 'test')

    def test_import_filters_by_required_id_and_preserves_manual_extras(self):
        captured = dict(extensions=['wanted.tool@2', 'ignored.tool@3'], settings={})
        required = dict(extensions=['Wanted.Tool@1'], settings={})
        current = dict(extensions=['manual.tool@4'])
        self.assertEqual(vscode.filter_required(captured, required, current),
                         dict(extensions=['wanted.tool@2', 'manual.tool@4']))

    def test_comparison_ignores_extension_and_setting_list_order(self):
        current = dict(extensions=['b.tool@2', 'a.tool@1'], settings={'includes': ['b', 'a', 'a']})
        incoming = dict(extensions=['a.tool@1', 'b.tool@2'], settings={'includes': ['a', 'b']})
        rows = env_settings.value_comparisons('vscode', current, incoming)
        self.assertTrue(all(row[2] == '==' for row in rows))
        self.assertEqual(len(rows), 4)

    def test_merge_uses_extension_id_not_list_position(self):
        existing = dict(extensions=['a.tool@1'], settings={'one': True})
        incoming = dict(extensions=['b.tool@2'], settings={'two': False})
        self.assertEqual(vscode.merge(existing, incoming, 'error'), dict(
            extensions=['a.tool@1', 'b.tool@2'], settings={'one': True, 'two': False}))


if __name__ == '__main__':
    unittest.main()
