"""Registry cleanup must preserve active or unobservable launch chains."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vivado_build_registry import BuildRegistry


class RegistryCleanupTest(unittest.TestCase):
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
