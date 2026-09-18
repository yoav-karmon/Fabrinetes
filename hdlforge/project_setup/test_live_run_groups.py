"""Check group selection, read-only completion, and failed-build handoff."""

from contextlib import nullcontext
import json
from pathlib import Path
import unittest
import tempfile
from unittest.mock import Mock, patch

from hdlforge_completion_backend import (ParsedState, complete_classic, complete_json_path,
                                        complete_llm_path, complete_project_management, is_llm_leaf)
from vivado_console import live_run_groups
from vivado_console.project_console import ConsoleUnavailable, ProjectConsole
from vivado_console.project_console_commands import hdlforge_commands
from vivado_console.run_enable import blocked, is_enabled


def run(name, parent=None, status="Not started", eligible=True):
    return {"name": name, "parent_run": parent, "eligible": eligible,
            "properties": {"IS_SYNTHESIS": "0" if parent else "1", "IS_IMPLEMENTATION": "1" if parent else "0",
                           "STATUS": status, "PROGRESS": "100%" if status == "Complete" else "0%", "NEEDS_REFRESH": "0"}}


class LiveRunGroupsTest(unittest.TestCase):
    def test_saved_options_need_no_vivado_and_exclude_idr(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test.xpr"
            path.write_text("""<Project><Runs>
              <Run Id="synth" Type="Ft3:Synth"/>
              <Run Id="impl" SynthRun="synth" Description="[HDLForge:disabled]"/>
              <Run Id="idr_child" SynthRun="synth" ParentHierarchy="idr:child"/>
              <Run Id="idr"><Strategy><StratHandle Flow="Vivado IDR Flow 2025"/></Strategy></Run>
            </Runs></Project>""")
            with patch.object(ProjectConsole, "open", side_effect=AssertionError("Must not open")):
                rows = live_run_groups.saved_run_options(path)
            self.assertEqual(rows[1]["parent_run"], "synth")
            self.assertFalse(rows[1]["enabled"])
            self.assertFalse(rows[2]["eligible"])
            self.assertFalse(rows[3]["eligible"])

    def test_all_read_only_run_commands_never_open_console(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/"test.xpr"
            path.write_text('<Project><Runs><Run Id="synth" Type="Ft3:Synth"/><Run Id="impl" SynthRun="synth"/></Runs></Project>')
            with patch.object(live_run_groups, "load_xpr_path", return_value=path), \
                 patch.object(ProjectConsole, "open", side_effect=AssertionError("No console")), \
                 patch.object(ProjectConsole, "pending_request", side_effect=AssertionError("No console access")), \
                 patch("builtins.print"):
                for action in ("runs", "get_runs", "get_groups", "get_build_options", "build_run", "build_group"):
                    self.assertEqual(live_run_groups.main(Path("project.json"), action, []), 0)
                for action in ("get_runs", "get_groups", "get_build_options"):
                    self.assertEqual(live_run_groups.main(Path("project.json"), action, ["--json", "--force"]), 0)

    def test_unavailable_console_requires_confirmation(self):
        console = ProjectConsole(Path('/tmp/recovery-test.xpr'))
        with patch.object(console, '_open', side_effect=ConsoleUnavailable('pending')), patch.object(console, 'exists', return_value=True), patch.object(console, 'close') as close:
            with self.assertRaisesRegex(ConsoleUnavailable, "--append '--force'"):
                console.open()
            close.assert_not_called()

    def test_force_recovers_unavailable_console_once(self):
        console = ProjectConsole(Path('/tmp/recovery-test.xpr'))
        console.force_recovery = True
        with patch.object(console, '_open', side_effect=[ConsoleUnavailable('pending'), None]) as opening, patch.object(console, 'exists', return_value=True), patch.object(console, 'close') as close:
            console.open()
            close.assert_called_once_with(force=True)
            self.assertEqual(opening.call_count, 2)

    def test_force_does_not_restart_for_tcl_error(self):
        console = ProjectConsole(Path('/tmp/recovery-test.xpr'))
        console.force_recovery = True
        with patch.object(console, '_open', side_effect=RuntimeError('Tcl error')), patch.object(console, 'close') as close:
            with self.assertRaisesRegex(RuntimeError, 'Tcl error'):
                console.open()
            close.assert_not_called()

    def test_snapshot_opens_console(self):
        console = Mock(project_file=None)
        console.locked.return_value = nullcontext()
        console.request.return_value = ""
        self.assertEqual(live_run_groups.snapshot(console), [])
        console.open.assert_called_once()

    def test_snapshot_recovers_exited_console_once(self):
        console = Mock(project_file=None)
        console.locked.return_value = nullcontext()
        console.request.side_effect = [RuntimeError("console exited"), ""]
        console.exists.return_value = False
        self.assertEqual(live_run_groups.snapshot(console), [])
        self.assertEqual(console.open.call_count, 2)

    def test_snapshot_does_not_restart_pending_console(self):
        console = Mock(project_file=None)
        console.locked.return_value = nullcontext()
        console.request.side_effect = RuntimeError("command pending")
        console.exists.return_value = True
        with self.assertRaisesRegex(RuntimeError, "pending"):
            live_run_groups.snapshot(console)
        console.open.assert_called_once()

    def test_native_marker_overrides_legacy_exclusion_and_preserves_disabled_state(self):
        self.assertFalse(is_enabled("User description\n[HDLForge:disabled]"))
        self.assertFalse(is_enabled("User description", legacy_disabled=True))
        self.assertTrue(is_enabled("User description\n[HDLForge:enabled]", legacy_disabled=True))

    def test_shortcut_completion_is_static_and_never_queries_the_console(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory) / "custom.json"
            project.write_text(json.dumps({"LLM_orch": {"anywhere": hdlforge_commands()}}))
            prefix = "anywhere.project_console.build.build_run"
            with patch.object(live_run_groups, "snapshot", side_effect=AssertionError("No discovery on Tab")):
                self.assertIn(prefix, complete_llm_path(project, prefix.rsplit(".", 1)[0] + ".").completions)
                self.assertTrue(is_llm_leaf(project, prefix))
                self.assertEqual(complete_llm_path(project, prefix + ".").completions, [])
                self.assertIn("LLM_orch." + prefix, complete_json_path(project, "LLM_orch." + prefix).completions)
                flags = complete_classic(["--tool", "vivado", "--project_mng", "build"], "--", project.parent)
                self.assertIn("--group", flags.completions)

    def test_projects_sharing_a_build_directory_have_separate_worker_state(self):
        a = ProjectConsole(Path("/example/_vivado/a/a.xpr"))
        b = ProjectConsole(Path("/example/_vivado/b/b.xpr"))
        self.assertNotEqual(a.logs_directory, b.logs_directory)

    def test_native_completion_is_static_without_a_project(self):
        state = ParsedState([], Path.cwd())
        with patch.object(live_run_groups, "snapshot", side_effect=AssertionError("No discovery on Tab")):
            self.assertEqual(complete_project_management("build.", state).completions, [])
            self.assertIn("get_groups", complete_project_management("get_", state).completions)



if __name__ == "__main__":
    unittest.main()
