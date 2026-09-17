"""Verify copy-paste command quoting and explicit target/action dispatch."""

from contextlib import nullcontext, redirect_stdout
import io
import os
from pathlib import Path
import shlex
import unittest
from unittest.mock import Mock, patch

from test_live_run_groups import run
from vivado_console.build_options import available_options, command, print_options
from vivado_console import live_run_groups


class BuildOptionsTest(unittest.TestCase):
    def test_grouped_table_preserves_complete_commands_and_family_boundaries(self):
        runs = [run("synth_a"), run("impl_a", "synth_a"), run("synth_b")]
        with patch.dict(os.environ, {"HDLFORGE_JSON_COMMAND_PATH": "LLM_orch.vivado.project_console.build.get_build_options"}):
            options = available_options(Path("project.json"), runs)
        output = io.StringIO()
        with redirect_stdout(output):
            print_options(options)
        cells = [line.split("|")[1:-1] for line in output.getvalue().splitlines() if line.startswith("|")]
        self.assertEqual([row[0].strip() for row in cells if row[0].strip()], ["Synthesis group", "synth_a", "synth_b"])
        text = output.getvalue()
        self.assertEqual([cell.strip() for cell in cells[0]], ["Synthesis group", "Command", "Arguments", "Explanation"])
        expected = {item["command"]: item["description"] for item in options}
        self.assertEqual(len(cells), len(options) + 1)
        reconstructed = []
        current_command = ""
        for row in cells[1:]:
            current_command = row[1].strip() or current_command
            full_command = current_command + " " + row[2].strip()
            reconstructed.append(full_command)
            self.assertEqual(row[3].strip(), expected[full_command])
        self.assertCountEqual(reconstructed, [item["command"] for item in options])
        self.assertTrue(any(not row[1].strip() for row in cells[1:]))
        self.assertNotIn("Group:", text)
        self.assertNotIn("Run:", text)
        self.assertNotIn("--project", text)

    def test_get_build_options_queries_the_live_snapshot(self):
        with patch.object(live_run_groups, "load_xpr_path", return_value=Path("test.xpr")), \
                patch.object(live_run_groups, "ProjectConsole") as console, \
                patch.object(live_run_groups, "snapshot", return_value=[run("live_synth")]) as snapshot, \
                redirect_stdout(io.StringIO()) as output:
            self.assertEqual(live_run_groups.main(Path("project.json"), "get_build_options", []), 0)
        snapshot.assert_called_once_with(console.return_value)
        self.assertIn("live_synth", output.getvalue())

    def test_printed_shortcut_round_trips_names_and_custom_parent(self):
        with patch.dict(os.environ, {"HDLFORGE_JSON_COMMAND_PATH": "LLM_orch.custom.project_console.build.get_build_options"}):
            text = command(Path("project.json"), "build_run", ["--run", "name with $vars; [brackets] 'quote'", "--reset"])
        words = shlex.split(text)
        self.assertEqual(words[:3], ["hdlforge", "custom.project_console.build.build_run", "--append"])
        self.assertNotIn("--project", words)
        self.assertEqual(shlex.split(words[3]), ["--run", "name with $vars; [brackets] 'quote'", "--reset"])

    def test_options_include_real_targets_but_no_build_for_disabled_entries(self):
        parent, child = run("synth"), run("impl", "synth")
        child["enabled"] = False
        options = available_options(Path("project.json"), [parent, child])
        disabled = [item for item in options if item["name"] == "impl"]
        self.assertTrue(any("enable_run" in item["command"] for item in disabled))
        self.assertFalse(any("build_run" in item["command"] for item in disabled))
        self.assertTrue(any("build_group" in item["command"] and "--reset" in item["command"] for item in options))

    def test_availability_commands_use_runs_namespace_from_build_options(self):
        with patch.dict(os.environ, {"HDLFORGE_JSON_COMMAND_PATH": "LLM_orch.custom.project_console.build.get_build_options"}):
            text = command(Path("project.json"), "enable_run", ["--run", "name with spaces"])
        words = shlex.split(text)
        self.assertEqual(words[:3], ["hdlforge", "custom.project_console.runs.enable_run", "--append"])
        self.assertEqual(shlex.split(words[3]), ["--run", "name with spaces"])

    def test_empty_build_commands_show_options_without_launching(self):
        for action in ("build_run", "build_group"):
            with patch.object(live_run_groups, "load_xpr_path", return_value=Path("test.xpr")), patch.object(live_run_groups, "snapshot", return_value=[run("synth")]), patch.object(live_run_groups, "print_options") as show, patch.object(live_run_groups.batch_build, "start") as start:
                self.assertEqual(live_run_groups.main(Path("project.json"), action, []), 0)
                show.assert_called_once()
                start.assert_not_called()

    def test_public_build_commands_submit_without_console_query(self):
        for action, args, target, kind in (
            ("build_group", ["--group", "synth"], "synth", "group"),
            ("build_run", ["--run", "impl"], "impl", "run"),
        ):
            with patch.object(live_run_groups, "load_xpr_path", return_value=Path("test.xpr")), patch.object(live_run_groups, "snapshot", side_effect=AssertionError("No console query")), patch.object(live_run_groups.batch_build, "start") as start:
                self.assertEqual(live_run_groups.main(Path("project.json"), action, args), 0)
                self.assertEqual(start.call_args.args[1:3], (target, kind))

    def test_disable_is_available_while_a_worker_holds_its_build_lock(self):
        console = Mock()
        console.locked.side_effect = lambda filename="command.lock": nullcontext() if filename == "command.lock" else self.fail("Disable must not wait for build.lock")
        with patch.object(live_run_groups, "load_xpr_path", return_value=Path("test.xpr")), \
                patch.object(live_run_groups, "ProjectConsole", return_value=console), \
                patch.object(live_run_groups, "snapshot", return_value=[run("synth")]):
            self.assertEqual(live_run_groups.main(Path("project.json"), "disable_group", ["--group", "synth"]), 0)
        self.assertIn("HDLForge:disabled", console.request.call_args.args[0])


if __name__ == "__main__":
    unittest.main()
