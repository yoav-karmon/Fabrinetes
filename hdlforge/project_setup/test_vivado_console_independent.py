"""Keep interactive Tcl independent of XPRs and compilation workflows."""

from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from vivado_console.project_console import main, parser
from vivado_console.project_console_commands import COMMANDS


class IndependentConsoleTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "console.hdlforge.json"
        self.project.write_text("{}")

    def test_start_without_xpr_or_export_configuration(self):
        with patch("vivado_console.project_console.ProjectConsole") as factory, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["start", "--project-json", str(self.project)]), 0)
        factory.return_value.open.assert_called_once()
        factory.return_value.request.assert_called_once_with("lvp_status")

    def test_arbitrary_tcl_is_submitted_verbatim(self):
        command = "open_checkpoint design.dcp; puts [get_cells *]"
        with patch("vivado_console.project_console.ProjectConsole") as factory, redirect_stdout(io.StringIO()):
            self.assertEqual(main(["send", "--project-json", str(self.project), "--cmd", command]), 0)
        factory.return_value.request.assert_called_once_with(command)

    def test_restart_never_prompts_for_export(self):
        with patch("vivado_console.project_console.ProjectConsole") as factory, \
                patch("builtins.input", side_effect=AssertionError("Unexpected prompt")), redirect_stdout(io.StringIO()):
            factory.return_value.exists.return_value = True
            self.assertEqual(main(["restart", "--project-json", str(self.project)]), 0)
        factory.return_value.close.assert_called_once_with(force=True)
        factory.return_value.request.assert_called_once_with("lvp_status")

    def test_retired_actions_absent(self):
        retired = {"build_run", "build_group", "build_bitstream", "reset_run", "reset_group",
                   "export_open_project_to_tcl", "generate_project_from_tcl", "regenerate_project", "close_project", "follow", "get_groups", "get_runs",
                   "group_info", "group_status", "reuse_status", "run_info", "run_status", "set_run_property"}
        self.assertTrue(retired.isdisjoint(COMMANDS))
        with self.assertRaises(SystemExit), patch("sys.stderr", new=io.StringIO()):
            parser().parse_args(["build_run"])


if __name__ == "__main__":
    unittest.main()
