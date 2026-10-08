"""Prove marker discovery and nested selectors through the saved build flow."""

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from hdlforge_command_tree import help_text, parse
from hdlforge_completion_backend import complete_command
from hdlforge_json import normalize
import test_vivado_build
from vivado_build import execute, prepare_run_config
from vivado_build_config import build_names, project_attempts
from vivado_build_artifacts import selected_folders
from vivado_build_hash import hash_source, verify_source_hashes
from vivado_build_layout import read_run
from vivado_build_selector import parse_selector, selected_run_folder, selector_choices
from vivado_build_registry import run_selection
from vivado_build_tools import initialize_run_defaults, lint_project
from vivado_run_tree import discover_runs, run_tree


class RunTreeTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / 'test.hdlforge.json'
        self.run = {'is_hdlforge_run': 'true', 'script': 'not-created/run.tcl',
                    'impl_runs': {'route': {'script': 'not-created/impl.tcl'}}}
        self.tree = {'chip': {'lab': {'synth': self.run},
                              'prod': {'synth': copy.deepcopy(self.run)}},
                     'empty': {'notes': {}}, 'unmarked': {'script': 'not-a-run.tcl'},
                     'disabled': {'is_hdlforge_run': 'false', 'script': 'disabled.tcl'}}
        self.data = {'vivado': {'non_project': {'runs': self.tree}}}
        self.project.write_text(json.dumps(self.data))

    def test_recursive_discovery_stops_at_marker_and_ignores_unmarked_branches(self):
        self.run['metadata'] = {'child': {'is_hdlforge_run': 'true'}}
        self.assertEqual(list(discover_runs(self.tree)), ['chip.lab.synth', 'chip.prod.synth'])
        self.assertEqual(build_names(self.data), ['chip.lab.synth', 'chip.lab.synth.route',
                                                'chip.prod.synth', 'chip.prod.synth.route'])

    def test_marker_values_and_dotted_keys(self):
        for flag in (True, 'true', False, 'false', 'yes', 1):
            with self.subTest(flag=flag):
                tree = {'run': {'is_hdlforge_run': flag}}
                if flag == 'yes' or type(flag) is int:
                    with self.assertRaises(ValueError):
                        discover_runs(tree)
                else:
                    self.assertEqual(bool(discover_runs(tree)), flag is True or flag == 'true')
        with self.assertRaisesRegex(ValueError, 'Invalid run path'):
            discover_runs({'literal.dot': self.run})

    def test_completion_and_help_follow_only_groups_with_marked_descendants(self):
        tokens = ['--project', str(self.project)]
        for prefix, expected in (
            ('', ['chip.']), ('chip.', ['lab.', 'prod.']), ('chip.lab.', ['synth.'])):
            stem = 'vivado.build.runs.' + prefix
            result = complete_command(tokens, stem, self.root)[0].completions
            self.assertEqual([name for name in result if not name.endswith('.help')],
                             [stem + child for child in expected])
        state = parse([*tokens, 'vivado.build.runs.chip.lab'], self.root)
        self.assertFalse(state['ready'])
        self.assertIn('vivado.build.runs.chip.lab.synth', help_text(state))
        with self.assertRaisesRegex(ValueError, 'Unknown synthesis'):
            parse([*tokens, 'vivado.build.runs.unmarked.run'], self.root)

    def test_dispatch_preserves_nested_path_and_timestamp_fraction(self):
        stamp = '_2026-10-08T123456.123456Z'
        command = f'vivado.build.runs.chip.lab.synth.{stamp}.impl.route.saved.status'
        state = parse(['--project', str(self.project), command], self.root)
        selector = f'chip.lab.synth.{stamp}.route.saved.status'
        self.assertEqual(state['args'][-1], selector)
        parsed = parse_selector(selector, discover_runs(self.tree))
        self.assertEqual((parsed['run'], parsed['synth'], parsed['impl'], parsed['attempt']),
                         ('chip.lab.synth', stamp, 'route', 'saved'))
        options = complete_command(['--project', str(self.project),
                                    'vivado.build.runs.chip.lab.synth.run', '--auto_impl'], '', self.root)[0]
        self.assertEqual(options.completions, ['route'])

    def test_marker_discovers_command_before_script_is_authored(self):
        self.run.pop('script')
        self.project.write_text(json.dumps(self.data))
        result = complete_command(['--project', str(self.project)],
                                  'vivado.build.runs.chip.lab.synth.', self.root)[0]
        self.assertIn('vivado.build.runs.chip.lab.synth.run', result.completions)

    def test_schema_initialization_adds_markers_without_turning_groups_into_runs(self):
        self.run.pop('is_hdlforge_run')
        result, changes = normalize(self.data, 'vivado.build', 'host', 'user')
        tree = run_tree(result)
        self.assertNotIn('is_hdlforge_run', tree['chip'])
        self.assertNotIn('script', tree['chip']['lab'])
        self.assertEqual(tree['chip']['lab']['synth']['is_hdlforge_run'], 'true')
        self.assertNotIn('is_hdlforge_run', tree['chip']['lab']['synth']['impl_runs']['route'])
        self.assertEqual(tree['disabled']['is_hdlforge_run'], 'false')
        self.assertEqual(normalize(result, 'vivado.build', 'host', 'user'), (result, []))
        self.project.write_text(json.dumps(self.data))
        with contextlib.redirect_stdout(io.StringIO()):
            initialize_run_defaults(self.project, 'chip.lab.synth')
        self.assertIn('chip.lab.synth', discover_runs(run_tree(json.loads(self.project.read_text()))))

    def test_marker_alone_does_not_invalidate_legacy_producer_fingerprint(self):
        source = self.root / 'source.sv'
        source.write_text('module example; endmodule')
        previous = dict(self.run)
        previous.pop('is_hdlforge_run')
        producer = self.root / 'producer'
        producer.mkdir()
        (producer / 'manifest.json').write_text(json.dumps({'source_hashes': {
            'version': 1, 'project': str(self.project), 'run': 'chip.lab.synth',
            'definition': previous, 'sources': {str(source): hash_source(source)}}}))
        verify_source_hashes(producer)
        # Moving an unchanged definition into different groups keeps the IP valid.
        self.data['vivado']['non_project']['runs'] = {'cme': {'cancel_fire': {'synth': self.run}}}
        self.project.write_text(json.dumps(self.data))
        verify_source_hashes(producer)
        source.write_text('module changed; endmodule')
        with self.assertRaisesRegex(ValueError, 'source changed'):
            verify_source_hashes(producer)


class NestedBuildTest(unittest.TestCase):
    def setUp(self):
        test_vivado_build.NativeBuildTest.setUp(self)
        # Groups deliberately use names from the selector grammar.
        self.name = 'chip.impl.status.synth_one'
        self.synth['release_root'] = 'release/chip'
        self.data['vivado']['non_project']['runs'] = {'chip': {'impl': {'status': {'synth_one': self.synth}}}}
        self.project.write_text(json.dumps(self.data))

    def test_nested_synthesis_implementation_bitstream_and_inventory(self):
        #######################################################################
        # Build with a fake Vivado, then consume only the saved parent inputs. #
        #######################################################################
        self.assertEqual(lint_project(self.project), [])
        with contextlib.redirect_stdout(io.StringIO()):
            synth = prepare_run_config(self.project, self.name + '.run')
            self.assertEqual(execute(self.project, synth, str(self.executable)), 0)
            child = prepare_run_config(self.project, self.name + '.latest.impl_one.run')
            self.assertEqual(execute(self.project, child, str(self.executable)), 0)
            bitstream = prepare_run_config(self.project, self.name + '.latest.impl_one.bitstream.latest')
            self.assertEqual(execute(self.project, bitstream, str(self.executable)), 0)
        self.assertEqual(read_run(Path(child['output']))['selector'], self.name + '.impl_one')
        saved_project = Path(read_run(Path(synth['output']))['project_file'])
        self.assertEqual(discover_runs(run_tree(json.loads(saved_project.read_text())))[self.name]['release_root'],
                         'release/chip')
        self.assertEqual(len(project_attempts(self.project, self.data)), 3)
        self.assertEqual(selected_folders(self.project, self.name + '.impl_one', None),
                         [Path(child['output'])])
        choices = selector_choices(self.project, self.data, '')
        self.assertIn(self.name + '.latest.impl_one.run', choices)
        self.assertEqual(self.project.read_text(), json.dumps(self.data))

    def test_public_nested_cli_auto_implementation(self):
        #######################################################################
        # Exercise dispatch, the detached worker and automatic implementation. #
        #######################################################################
        executable = self.root / 'vivado'
        shutil.copyfile(self.executable, executable)
        executable.chmod(0o755)
        self.data['settings'] = {'env': {'default': {
            'path': os.environ['PATH'].split(os.pathsep), 'path_import': [],
            'pythonpath': [value for value in os.environ.get('PYTHONPATH', '').split(os.pathsep) if value],
            'pythonpath_import': [], 'variables': {}, 'variables_import': []}}}
        self.project.write_text(json.dumps(self.data))
        env = {key: value for key, value in os.environ.items() if not key.startswith('HDLFORGE_')}
        result = subprocess.run([str(Path(__file__).with_name('hdlforge')), '--project', str(self.project),
                                 '--env-path', json.dumps([str(self.root)]),
                                 'vivado.build.runs.' + self.name + '.run', '--auto_impl', 'impl_one'],
                                cwd=self.root, env=env, capture_output=True, text=True, timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count('HDLFORGE_BUILD_COMPLETE'), 2)

    def test_regrouping_and_relocation_keep_saved_attempts_and_snapshot_inputs(self):
        #######################################################################
        # Move JSON groups and script folders without rewriting saved history. #
        #######################################################################
        with contextlib.redirect_stdout(io.StringIO()):
            synth = prepare_run_config(self.project, self.name + '.run')
            self.assertEqual(execute(self.project, synth, str(self.executable)), 0)
            child = prepare_run_config(self.project, self.name + '.latest.impl_one.run')
            self.assertEqual(execute(self.project, child, str(self.executable)), 0)
        attempts = project_attempts(self.project, self.data)
        manifests = {folder: (folder / 'manifest.json').read_bytes() for folder in attempts}
        self.data['vivado']['non_project']['runs'] = {'cme': {'cancel_fire': run_tree(self.data)}}
        # Relocate the entire run folder, including completed attempts.
        old_folder = self.root / 'results/synth_one'
        new_folder = self.root / 'vivado_builds/cme/cancel_fire/synth_one'
        new_folder.parent.mkdir(parents=True)
        old_folder.rename(new_folder)
        attempts = [new_folder / folder.relative_to(old_folder) for folder in attempts]
        manifests = {new_folder / folder.relative_to(old_folder): value
                     for folder, value in manifests.items()}
        for config in (synth, child):
            config['output'] = str(new_folder / Path(config['output']).relative_to(old_folder))
        self.data = json.loads(json.dumps(self.data).replace('results/synth_one/',
                              'vivado_builds/cme/cancel_fire/synth_one/'))
        self.project.write_text(json.dumps(self.data))
        new_name = 'cme.cancel_fire.' + self.name
        self.assertEqual(project_attempts(self.project, self.data), attempts)
        self.assertIn(new_name + '.latest.impl_one.run', selector_choices(self.project, self.data, ''))
        parsed = parse_selector(new_name + '.latest.impl_one.latest.status', discover_runs(run_tree(self.data)))
        self.assertEqual(selected_run_folder(self.project, parsed), Path(child['output']))
        with contextlib.redirect_stdout(io.StringIO()):
            # Bitstream selection can still use an implementation made before regrouping.
            bitstream = prepare_run_config(self.project, new_name + '.latest.impl_one.bitstream.latest')
            self.assertEqual(execute(self.project, bitstream, str(self.executable)), 0)
            retry = prepare_run_config(self.project, new_name + '.latest.impl_one.run')
            self.assertEqual(retry['input_dcp'], str(Path(synth['output']) / 'artifacts/design.dcp'))
            self.assertEqual(execute(self.project, retry, str(self.executable)), 0)
        for folder, original in manifests.items():
            self.assertEqual((folder / 'manifest.json').read_bytes(), original)
        self.assertEqual(run_selection({'selector': new_name + '.impl_one', 'stage': 'impl',
                                        'synth_timestamp': 'parent', 'run_id': 'child'}),
                         new_name + '.parent.impl_one.child')


if __name__ == '__main__':
    unittest.main()
