"""Registry cleanup must preserve active or unobservable launch chains."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vivado_build_registry import BuildRegistry, artifact_protection


class RegistryCleanupTest(unittest.TestCase):
    def test_protection_follows_git_ignore_exceptions(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            output = root / 'artifacts' / 'run'
            output.mkdir(parents=True)
            (output / 'runme.log').write_text('complete')
            rules = root / '.gitignore'
            rules.write_text('/artifacts/**\n!/artifacts/**/\n')
            self.assertEqual(artifact_protection(str(output)), 'No')
            subprocess.run(['git', '-C', str(root), 'add', '-f', 'artifacts/run/runme.log'], check=True)
            self.assertEqual(artifact_protection(str(output)), 'Yes')
            # The index still protects a tracked file missing from the worktree.
            (output / 'runme.log').unlink()
            self.assertEqual(artifact_protection(str(output)), 'Yes')
            subprocess.run(['git', '-C', str(root), 'rm', '--cached', '-q', 'artifacts/run/runme.log'], check=True)
            (output / 'runme.log').write_text('complete')
            rules.write_text('/artifacts/**\n!/artifacts/**/\n!/artifacts/run/runme.log\n')
            self.assertEqual(artifact_protection(str(output)), 'Yes')
            self.assertEqual(artifact_protection(str(root / 'missing')), 'Missing')
            with patch('vivado_build_registry.cleanable', side_effect=ValueError('Git failed')):
                self.assertEqual(artifact_protection(str(output)), 'Unknown')

    def test_completed_unavailable_run_is_history_not_starting(self):
        registry = BuildRegistry(Path('/tmp/registry-display-test'))
        base = dict(selector='synth', synth_timestamp='2026-09-29T203905.608934Z',
                    stage='synth', output='/tmp/run', host={}, active=False,
                    pid_state='unavailable', engine=None, engine_pid=None)
        for status in ('complete', 'failed', 'stopped'):
            with self.subTest(status=status), \
                 patch.object(registry, 'refresh', return_value=[dict(base, status=status)]), \
                 patch('vivado_build_registry.enrich', return_value={}), \
                 patch('vivado_build_registry.create_matrix_table_from_data', return_value='table') as table, \
                 patch('builtins.print') as output:
                registry.status()
                output.assert_called_once_with('No active builds')
                table.assert_not_called()
                registry.status(all_runs=True)
                self.assertEqual(table.call_args.args[1][0][4], 'Exited')

    def test_unfinished_unavailable_run_remains_visible(self):
        registry = BuildRegistry(Path('/tmp/registry-display-test'))
        row = dict(selector='synth', stage='synth', output='/tmp/run', host={},
                   active=False, pid_state='unavailable', status='running', engine=None)
        with patch.object(registry, 'refresh', return_value=[row]), \
             patch('vivado_build_registry.enrich', return_value={}), \
             patch('vivado_build_registry.create_matrix_table_from_data', return_value='table') as table, \
             patch('builtins.print'):
            registry.status()
            self.assertEqual(table.call_args.args[1][0][4], 'Unavailable')

    def test_missing_outputs_prune_only_known_inactive_runs(self):
        with tempfile.TemporaryDirectory() as folder:
            registry = BuildRegistry(Path(folder))
            local = dict(host='host', boot_id='current', pid_namespace=1, uid=1000)
            old = dict(local, boot_id='previous')
            remote = dict(local, host='remote')
            hidden = dict(local, pid_namespace=2)
            rows = {}
            for name, host, state in [
                ('deleted', local, 'dead'), ('rebooted', old, 'unavailable'),
                ('remote', remote, 'unavailable'), ('hidden', hidden, 'unavailable'),
                ('active', local, 'R'), ('existing', local, 'dead'),
                ('parent', local, 'dead'), ('child', local, 'R'),
                ('engine_alive', local, 'dead'), ('denied', local, 'unavailable'),
            ]:
                output = registry.root / name
                rows[name] = dict(launch_id=name, host=host, process={'state': state},
                                  launcher=None, output=str(output), status_file=str(output / 'info/status'),
                                  status='complete', finished_at='2026-09-29T00:00:00+00:00')
            rows['child']['parent_launch_id'] = 'parent'
            rows['engine_alive']['engine'] = {'state': 'R'}
            (registry.root / 'existing').mkdir()
            registry.path.write_text(json.dumps({'version': 1, 'runs': rows}))
            with patch('vivado_build_registry.local_identity', return_value=local), \
                 patch('vivado_build_registry.probe_process', side_effect=lambda process, host: process['state'] if process else 'not_started'), \
                 patch('vivado_build_registry.vivado_engine', return_value=None):
                remaining = {row['launch_id'] for row in registry.refresh()}
            self.assertEqual(remaining, set(rows) - {'deleted', 'rebooted'})
            self.assertEqual(set(json.loads(registry.path.read_text())['runs']), remaining)


if __name__ == '__main__':
    unittest.main()
