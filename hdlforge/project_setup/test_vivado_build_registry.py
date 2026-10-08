"""Attempt-local worker discovery, cancellation and concurrent manifest updates."""

from concurrent.futures import ThreadPoolExecutor
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vivado_build_layout import edit_run, new_identity, read_run, write_run
from vivado_build_registry import BuildRegistry, BuildStopped, artifact_protection, run_selection


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

    def test_log_analysis_uses_recorded_log_directory_for_completed_runs(self):
        registry = BuildRegistry(Path('/tmp/registry-display-test'))
        for log in ('/tmp/run/build.log', '/tmp/run/logs/runme.log'):
            row = dict(selector='synth.impl', stage='impl', output='/tmp/run', host={},
                       active=False, pid_state='dead', status='complete', run_log=log, engine=None)
            with self.subTest(log=log), \
                 patch.object(registry, 'refresh', return_value=[row]), \
                 patch('vivado_build_registry.enrich', return_value={}) as analyze, \
                 patch('vivado_build_registry.create_matrix_table_from_data', return_value='table'), \
                 patch('builtins.print'):
                registry.status(all_runs=True)
                self.assertEqual(analyze.call_args.args[0]['records'][0]['DIRECTORY'], str(Path(log).parent))

    def test_status_all_reports_log_analyzer_failure(self):
        registry = BuildRegistry(Path('/tmp/registry-display-test'))
        row = dict(selector='synth', stage='synth', output='/tmp/run', host={},
                   active=False, pid_state='dead', status='complete', engine=None)
        with patch.object(registry, 'refresh', return_value=[row]), \
             patch('vivado_build_registry.enrich', return_value={'analysis_error': 'Missing analyzer dependency'}), \
             patch('vivado_build_registry.create_matrix_table_from_data', return_value='table'), \
             patch('builtins.print') as output:
            registry.status(all_runs=True)
            output.assert_any_call('Log analysis unavailable: Missing analyzer dependency')


class AttemptManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix='attempt-state-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.project = self.root / 'test.hdlforge.json'
        self.project.write_text(json.dumps({'vivado': {'non_project': {'runs': {
            'first': {'is_hdlforge_run': 'true', 'script': 'one/nested/run.tcl'},
            'second': {'is_hdlforge_run': 'true', 'script': 'elsewhere/run.tcl'},
        }}}}))
        self.registry = BuildRegistry(self.project)

    def launch(self, name: str, parent: dict | None = None) -> dict:
        config = new_identity()
        folder = (Path(parent['output']) / 'impl_runs/impl' if parent else
                  self.root / ('one/nested' if name == 'first' else 'elsewhere'))
        config.update(selector=name, stage='impl' if parent else 'synth',
                      output=str(folder / ('_' + config['run_id'])),
                      synthesis_run_id=parent['run_id'] if parent else config['run_id'])
        if parent:
            config['parent_launch_id'] = parent['launch_id']
        config['launch_id'] = self.registry.register(self.project, config)
        return config

    def test_discovery_without_index_is_scoped_and_read_only(self) -> None:
        first, second = self.launch('first'), self.launch('second')
        child = self.launch('first.impl', first)
        unrelated = self.root / 'unconfigured/_attempt'
        write_run(unrelated, dict(read_run(Path(first['output'])), execution={'launch_id': 'unrelated'}))
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in self.root.rglob('manifest.json')}
        with patch('vivado_build_registry.probe_process', return_value='unavailable'), \
             patch('vivado_build_registry.vivado_engine', return_value=None):
            rows = BuildRegistry(self.project).refresh()
        self.assertEqual({row['launch_id'] for row in rows}, {run['launch_id'] for run in (first, second, child)})
        self.assertTrue(all(row['pid_state'] == 'unavailable' for row in rows))
        self.assertEqual(before, {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in before})
        self.assertFalse(list(self.root.rglob('_run_registry*')))
        for run in (first, second, child):
            self.assertTrue((Path(run['output']) / '.manifest.lock').is_file())

    def test_status_uses_current_json_hierarchy_without_rewriting_history(self) -> None:
        parent = self.launch('first')
        child = self.launch('first.impl', parent)
        bitstream = self.launch('first.impl', child)
        with edit_run(Path(bitstream['output'])) as config:
            config['stage'] = config['execution']['stage'] = 'bitstream'
            config['execution']['build_selection'] = f"first.{parent['run_id']}.impl.bitstream.{child['run_id']}"
        before = {path: path.read_bytes() for path in self.root.rglob('manifest.json')}
        data = json.loads(self.project.read_text())
        runs = data['vivado']['non_project']['runs']
        runs['cme'] = {'cancel_fire': {'first': runs.pop('first')}}
        self.project.write_text(json.dumps(data))

        rows = {row['launch_id']: row for row in BuildRegistry(self.project).records()}
        stem = f"cme.cancel_fire.first.{parent['run_id']}"
        self.assertEqual(run_selection(rows[parent['launch_id']]), stem)
        self.assertEqual(run_selection(rows[child['launch_id']]), f"{stem}.impl.{child['run_id']}")
        self.assertEqual(run_selection(rows[bitstream['launch_id']]), f"{stem}.impl.bitstream.{child['run_id']}")
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_concurrent_edits_preserve_other_fields_and_cancellation(self) -> None:
        run = self.launch('first')
        folder = Path(run['output'])
        def increment(index: int) -> None:
            with edit_run(folder) as record:
                record['count'] = record.get('count', 0) + 1
            self.registry.update(run['launch_id'], **{f'field_{index}': index})
        self.registry.update(run['launch_id'], stop_requested=True)
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(increment, range(40)))
        record = read_run(folder)
        self.assertEqual(record['count'], 40)
        self.assertTrue(record['execution']['stop_requested'])
        self.assertEqual([record['execution'][f'field_{index}'] for index in range(40)], list(range(40)))

    def test_parent_cancellation_blocks_register_and_attach(self) -> None:
        parent = self.launch('first')
        child = self.launch('first.impl', parent)
        self.registry.update(parent['launch_id'], stop_requested=True)
        with self.assertRaises(BuildStopped):
            self.launch('first.impl', parent)
        with patch('vivado_build_registry.process_info', return_value={'pid': 123}), self.assertRaises(BuildStopped):
            self.registry.attach(child['launch_id'], 123)
        self.assertTrue(read_run(Path(child['output']))['execution']['stop_requested'])

    def test_stop_all_uses_manifests_and_marks_before_signalling(self) -> None:
        first, second = self.launch('first'), self.launch('second')
        child = self.launch('first.impl', first)
        rows = self.registry.records()
        live = True
        def probe(process: dict | None, host: dict) -> str:
            return 'R' if process and live else 'dead'
        def signal(process: dict | None, host: dict, number: int, **kwargs) -> None:
            nonlocal live
            self.assertTrue(all(read_run(Path(row['output']))['execution']['stop_requested'] for row in rows))
            live = False
        with patch('vivado_build_registry.probe_process', side_effect=probe), \
             patch('vivado_build_registry.signal_process', side_effect=signal) as signals, \
             patch('vivado_build_registry.group_members', return_value=[]), \
             patch.object(self.registry, 'discover'), contextlib.redirect_stdout(io.StringIO()):
            self.registry.stop_all()
        self.assertTrue(signals.called)
        for run in (first, second, child):
            record = read_run(Path(run['output']))
            self.assertEqual(record['status'], 'stopped')
            self.assertEqual(record['exit_code'], 130)
        with self.assertRaises(BuildStopped):
            self.launch('first.impl', first)

    def test_scoped_stop_leaves_other_run_unchanged(self) -> None:
        first, second = self.launch('first'), self.launch('second')
        second_folder = Path(second['output'])
        before = (second_folder / 'manifest.json').read_bytes()
        live = True
        def probe(process: dict | None, host: dict) -> str:
            return 'R' if process and live else 'dead'
        def signal(*args, **kwargs) -> None:
            nonlocal live
            live = False
        with patch('vivado_build_registry.probe_process', side_effect=probe), \
             patch('vivado_build_registry.signal_process', side_effect=signal), \
             patch('vivado_build_registry.group_members', return_value=[]), \
             patch.object(self.registry, 'discover'), contextlib.redirect_stdout(io.StringIO()):
            self.registry.stop_all(first['output'])
        self.assertEqual((second_folder / 'manifest.json').read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
