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

from vivado_console.project_console import display_response, main, parser
from vivado_console.project_console_commands import hdlforge_commands, install_commands
from vivado_console.tcl_arguments import tcl_word


class ConsoleTest(unittest.TestCase):
    def test_terminate_kills_without_tcl_or_prompt(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / 'test.hdlforge.json'
            project.write_text('{}')
            with patch('vivado_console.project_console.ProjectConsole') as factory, \
                    patch('builtins.input', side_effect=AssertionError('No prompt expected')), redirect_stdout(io.StringIO()):
                self.assertEqual(main(['stop', '--project-json', str(project)]), 0)
            console = factory.return_value
            console.close.assert_called_once_with(force=True)
            console.request.assert_not_called()
            console.locked.assert_not_called()



    def test_help_is_command_description_table(self):
        output = io.StringIO()
        with redirect_stdout(output):
            self.assertEqual(main(['help']), 0)
        self.assertIn('| Command', output.getvalue())
        self.assertIn('Description', output.getvalue())
        self.assertNotIn('usage:', output.getvalue())



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
            self.assertNotIn('build', commands)
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
                    self.assertIn('vivado.console.', value)
                    self.assertNotIn('--project_mng ', value)
        check(commands)



if __name__ == '__main__':
    unittest.main()
