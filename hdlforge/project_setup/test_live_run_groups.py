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
from vivado_console.build_jobs import state_path
from vivado_console.project_console import ProjectConsole
from vivado_console.project_console_commands import hdlforge_commands
from vivado_console.run_enable import blocked, is_enabled


def run(name, parent=None, status="Not started", eligible=True):
    return {"name": name, "parent_run": parent, "eligible": eligible,
            "properties": {"IS_SYNTHESIS": "0" if parent else "1", "IS_IMPLEMENTATION": "1" if parent else "0",
                           "STATUS": status, "PROGRESS": "100%" if status == "Complete" else "0%", "NEEDS_REFRESH": "0"}}


class LiveRunGroupsTest(unittest.TestCase):
    def test_cached_current_ip_synthesis_is_reused(self):
        cached = run("ip_synth", status="Complete")
        cached["properties"]["STATUS"] = "Using cached IP results"
        self.assertTrue(live_run_groups.finished(cached))
        cached["properties"]["NEEDS_REFRESH"] = "1"
        self.assertFalse(live_run_groups.finished(cached))

    def test_disabled_group_blocks_direct_child_and_reset_and_build(self):
        parent, child = run("synth"), run("impl", "synth")
        parent["enabled"] = False
        self.assertTrue(blocked(child, [parent, child]))
        self.assertIn("build.synth.enable", live_run_groups.choices([parent, child]))
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", return_value=[parent, child]):
            for path in ("build.synth.reset_and_build", "build.synth.implementations.impl.continue"):
                live_run_groups.build(console, path, 1, 10)
        console.request.assert_not_called()

    def test_disabled_child_is_skipped_without_launching_or_resetting(self):
        parent, child = run("synth", status="Complete"), run("impl", "synth")
        child["enabled"] = False
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", return_value=[parent, child]):
            live_run_groups.build(console, "build.synth.continue", 1, 10)
        console.request.assert_not_called()

    def test_disable_between_selection_and_launch_prevents_launch(self):
        enabled = [run("synth")]
        disabled = [dict(enabled[0], enabled=False)]
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", side_effect=[enabled, enabled, disabled]):
            live_run_groups.build(console, "build.synth.continue", 1, 10)
        console.request.assert_not_called()

    def test_continue_implementation_resumes_to_bitstream_without_resetting_synthesis(self):
        parent = run("synth", status="Complete")
        child = run("impl", "synth", status="route_design Complete!")
        done = run("impl", "synth", status="Complete")
        done["properties"]["STATUS"] = "write_bitstream Complete!"
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", side_effect=[[parent, child]] * 3 + [[parent, done]]):
            live_run_groups.build(console, "build.synth.implementations.impl.continue", 1, 10)
        console.request.assert_called_once_with('launch_runs "impl" -jobs 1 -to_step write_bitstream')

    def test_reset_individual_implementation_does_not_reset_siblings_or_synthesis(self):
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", return_value=[run("synth"), run("impl", "synth"), run("other", "synth")]):
            live_run_groups.build(console, "build.synth.implementations.impl.reset", 1, 10)
        console.request.assert_called_once_with('reset_runs "impl"')

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
                self.assertIn("--action", flags.completions)
                result = complete_classic(["--tool", "vivado", "--project_mng", "build", "--action"], "", project.parent)
                self.assertEqual(set(result.completions), {"continue", "disable", "enable", "reset", "reset_and_build"})

    def test_projects_sharing_a_build_directory_have_separate_worker_state(self):
        a = ProjectConsole(Path("/example/_vivado/a/a.xpr"))
        b = ProjectConsole(Path("/example/_vivado/b/b.xpr"))
        self.assertNotEqual(state_path(a), state_path(b))
        self.assertNotEqual(a.logs_directory, b.logs_directory)

    def test_log_streaming_does_not_repeat_bytes_and_handles_truncation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "runme.log"
            path.write_text("first\n")
            with patch("builtins.print") as output:
                offset = live_run_groups.relay_log(path, 0)
                live_run_groups.relay_log(path, offset)
                output.assert_called_once_with("first\n", end="", flush=True)
                path.write_text("new\n")
                self.assertEqual(live_run_groups.relay_log(path, offset), 4)
                self.assertEqual(output.call_args.args, ("new\n",))

    def test_exact_parent_and_selected_child_determine_sequence(self):
        runs = [run("synth.a"), run("impl_a", "synth.a"), run("impl_b", "synth.a"),
                run("idr", "synth.a", eligible=False), run("other"), run("unrelated", "other")]
        sequence, action = live_run_groups.selected_runs("build.synth%2Ea.implementations.impl_b.continue", runs)
        self.assertEqual([item["name"] for item in sequence], ["impl_b"])
        self.assertEqual(action, "continue")
        sequence, _ = live_run_groups.selected_runs("build.synth%2Ea.reset_and_build", runs)
        self.assertEqual([item["name"] for item in sequence], ["synth.a", "impl_a", "impl_b"])
        with self.assertRaises(ValueError):
            live_run_groups.selected_runs("build.synth%2Ea.implementations.idr.continue", runs)

    def test_native_completion_is_static_without_a_project(self):
        state = ParsedState([], Path.cwd())
        with patch.object(live_run_groups, "snapshot", side_effect=AssertionError("No discovery on Tab")):
            self.assertEqual(complete_project_management("build.", state).completions, [])
            self.assertIn("get_groups", complete_project_management("get_", state).completions)

    def test_failure_stops_before_any_implementation_launch(self):
        initial = [run("synth"), run("impl", "synth")]
        failed = [run("synth", status="synth_design ERROR"), run("impl", "synth")]
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", side_effect=[initial, initial, initial, failed]):
            with self.assertRaisesRegex(RuntimeError, "remaining runs were not launched"):
                live_run_groups.build(console, "build.synth.continue", 1, 10)
        console.request.assert_called_once_with('launch_runs "synth" -jobs 1')

    def test_reset_targets_synthesis_parent_only(self):
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        with patch.object(live_run_groups, "snapshot", return_value=[run("synth"), run("impl", "synth"), run("idr", "synth", eligible=False)]):
            live_run_groups.build(console, "build.synth.reset", 1, 10)
        console.request.assert_called_once_with('reset_runs "synth"')


if __name__ == "__main__":
    unittest.main()
