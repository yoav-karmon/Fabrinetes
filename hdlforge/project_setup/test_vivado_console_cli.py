"""Test the single console CLI without opening any production project."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, MagicMock, patch
from vivado_console.follow import follow

from vivado_console.project_console import confirm_close, display_response, main, parser, run_command
from vivado_console.project_console_commands import hdlforge_commands, install_commands
from vivado_console.tcl_arguments import tcl_word


class ConsoleTest(unittest.TestCase):
    def test_follow_queries_console_once_then_only_logs(self):
        console = MagicMock(xpr=Path('/tmp/test.xpr'))
        console.last_response = {'records': [{'NAME': 'impl_1', 'PARENT': 'synth_1', 'STATUS': 'Running'}]}
        ended = {'records': [{'NAME': 'impl_1', 'PARENT': 'synth_1', 'STATUS': 'RUN_PASS'}]}
        with patch('vivado_console.follow.enrich', return_value=ended) as analyze, redirect_stdout(io.StringIO()):
            self.assertEqual(follow(console), 0)
        console.request.assert_called_once()
        self.assertTrue(analyze.call_args.kwargs['log_only'])

    def test_terminate_kills_without_tcl_or_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'test.hdlforge.json'
            project.write_text(json.dumps({'vivado': {'external_config': {'filename': 'test.tcl'}}}))
            with patch('vivado_console.project_console.load_xpr_path', return_value=Path(directory)/'test.xpr'), \
                    patch('vivado_console.project_console.ProjectConsole') as factory, \
                    patch('builtins.input', side_effect=AssertionError('No prompt expected')), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['stop', '--project-json', str(project)]), 0)
            console = factory.return_value
            console.close.assert_called_once_with(force=True)
            console.request.assert_not_called()
            console.locked.assert_not_called()

    def test_declining_export_still_closes(self):
        console = Mock(xpr=Path('/tmp/target.xpr'))
        console.last_response = {'records': [{'PROJECT': 'target', 'XPR': '/tmp/target.xpr'}]}
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='n'):
            confirm_close(console, parser().parse_args(['stop']), Path('/tmp/project.tcl'))
        self.assertEqual([c.args[0] for c in console.request.call_args_list], ['lvp_status', 'lvp_close_project'])

    def test_cancel_keeps_project_open(self):
        console = Mock(xpr=Path('/tmp/target.xpr'))
        console.last_response = {'records': [{'PROJECT': 'target', 'XPR': '/tmp/target.xpr'}]}
        with patch('sys.stdin.isatty', return_value=True), patch('builtins.input', return_value='cancel'):
            with self.assertRaisesRegex(RuntimeError, 'Cancelled'):
                confirm_close(console, parser().parse_args(['stop']), Path('/tmp/project.tcl'))
        console.request.assert_called_once_with('lvp_status')

    def test_grouped_runs_keep_identifiers_unwrapped(self):
        name = 'i_impl_latency_test_1_ml_strat_1'
        rows = [{'NAME': 'synth_latency_test', 'PARENT': '', 'STATUS': 'Not started', 'PROGRESS': '0%', 'ENABLED': '1'},
                {'NAME': name, 'PARENT': 'synth_latency_test', 'STATUS': 'Running route_design...', 'PROGRESS': '80%', 'STATS.WNS': '-0.12', 'ENABLED': '1'},
                {'NAME': 'synth_production', 'PARENT': '', 'STATUS': 'Not started', 'ENABLED': '1'}]
        output = io.StringIO()
        with redirect_stdout(output):
            display_response(dict(request='r', command='lvp_get_runs', output='', result='', code=0, records=rows))
        text = output.getvalue()
        self.assertIn('Group: synth_latency_test', text)
        self.assertIn('Group: synth_production', text)
        self.assertIn(name, text)
        self.assertIn('Timing', text)
        self.assertNotIn('| Parent', text)
        self.assertEqual(text.count('| Run '), 2)
        self.assertIn('W/CW/E', text)

    def test_close_rejects_other_project_even_with_force(self):
        console = Mock(xpr=Path('/tmp/target.xpr'))
        console.last_response = {'records': [{'PROJECT': 'other', 'XPR': '/tmp/other.xpr'}]}
        with self.assertRaisesRegex(RuntimeError, 'Nothing was closed'):
            confirm_close(console, parser().parse_args(['stop', '--force']), Path('/tmp/project.tcl'))
        console.request.assert_called_once_with('lvp_status')

    def test_close_accepts_json_target(self):
        console = Mock(xpr=Path('/tmp/target.xpr'))
        console.last_response = {'records': [{'PROJECT': 'target', 'XPR': '/tmp/target.xpr'}]}
        confirm_close(console, parser().parse_args(['stop', '--force']), Path('/tmp/project.tcl'))
        self.assertEqual(console.request.call_args.args, ('lvp_close_project',))

    def test_run_property_commands(self):
        args = parser().parse_args(['set_run_property', '--run', 'synth_1', '--property', 'DESCRIPTION', '--value', 'test'])
        self.assertEqual(run_command(args), 'lvp_edit_run_property "synth_1" "DESCRIPTION" "test"')
        self.assertEqual(run_command(parser().parse_args(['incremental_off', '--run', 'impl_1'])), 'lvp_incremental "impl_1" 0')
        self.assertEqual(run_command(parser().parse_args(['set_run_property', '--run', 'impl_1'])), 'lvp_run_properties "impl_1"')

    def test_help_is_command_description_table(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['help']), 0)
        self.assertIn('| Command', output.getvalue())
        self.assertIn('Description', output.getvalue())
        self.assertNotIn('usage:', output.getvalue())

    def test_group_launch_is_one_tcl_call(self):
        args = parser().parse_args(['build_group', '--group', 'synth_1', '--jobs', '3'])
        self.assertEqual(run_command(args), 'lvp_build_group "synth_1" 3 1 0')

    def test_missing_target_lists_live_choices(self):
        self.assertEqual(run_command(parser().parse_args(['build_group'])), 'lvp_get_groups')
        self.assertEqual(run_command(parser().parse_args(['build_run'])), 'lvp_get_runs')

    @unittest.skipUnless(shutil.which("tclsh"), "Literal quoting is also covered by the live Vivado fixture")
    def test_tcl_arguments_are_literal(self):
        value = 'name [error injected]; $value { } " \\ newline\nend'
        script = 'set value ' + tcl_word(value) + '\nputs [binary encode hex [encoding convertto utf-8 $value]]\n'
        result = subprocess.run(['tclsh'], input=script, text=True, capture_output=True, check=True)
        self.assertEqual(bytes.fromhex(result.stdout.strip()).decode(), value)

    def test_complete_transcript_and_error_boundaries(self):
        response = dict(request='r1', command='bad_command', output='WARNING: first\nERROR: second\n', result='full error stack', code=1, records=[])
        output = io.StringIO()
        with redirect_stdout(output):
            display_response(response)
        text = output.getvalue()
        self.assertLess(text.index('OUTPUT BEGIN'), text.index('WARNING: first'))
        self.assertLess(text.index('full error stack'), text.index('OUTPUT END'))
        self.assertIn('result=ERROR', text)

    def test_json_contains_transcript_and_structured_data(self):
        response = dict(request='r1', command='status', output='native warning', result='', code=0, records=[{'STATUS':'Running'}])
        output = io.StringIO()
        with redirect_stdout(output):
            display_response(response, machine=True)
        self.assertEqual(json.loads(output.getvalue()), response)

    def test_installer_preserves_other_settings(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'fixture.json'
            path.write_text(json.dumps({'settings': {'keep': 17}, 'LLM_orch': {'vivado': {'other': 'keep'}}}))
            install_commands(path, 'LLM_orch.vivado', False)
            value = json.loads(path.read_text())
            self.assertEqual(value['settings']['keep'], 17)
            self.assertEqual(value['LLM_orch']['vivado']['other'], 'keep')
            commands = value['LLM_orch']['vivado']['project_console']
            self.assertIn('build_group', commands['build'])
            self.assertIn('inspect_console', commands['management'])
            self.assertIn('update-json', commands)
            self.assertNotIn('build_group', commands)

    def test_all_commands_have_descriptions(self):
        commands = hdlforge_commands()['project_console']
        def check(group):
            for name, value in group.items():
                if name.startswith('#'):
                    continue
                self.assertTrue(group['#'+name])
                if isinstance(value, dict):
                    check(value)
                else:
                    self.assertIn('--project_console ', value)
                    self.assertNotIn('--project_mng ', value)
        check(commands)

    def test_bad_jobs_rejected_without_console(self):
        with patch('vivado_console.project_console.ProjectConsole', side_effect=AssertionError('must not open')):
            self.assertEqual(main(['build_run','--run','synth_1','--jobs','0']), 1)


if __name__ == '__main__':
    unittest.main()
