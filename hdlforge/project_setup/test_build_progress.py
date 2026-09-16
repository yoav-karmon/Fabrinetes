"""Worker plans preserve progress and label artifacts without claiming timing closure."""

from contextlib import nullcontext
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from test_live_run_groups import run
from vivado_console import build_jobs, live_run_groups
from vivado_console.build_progress import plan_entry


class BuildProgressTest(unittest.TestCase):
    def test_legacy_worker_status_is_enriched_without_rewriting_state(self):
        parent = run("synth", status="synth_design Complete!")
        parent["properties"]["PROGRESS"] = "100%"
        child = run("impl", "synth", status="place_design Running")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.json"
            original = json.dumps({"pid": 123, "status": "running", "action": "build.synth.continue"})
            path.write_text(original)
            with patch.object(build_jobs, "readable_state_path", return_value=path), patch.object(build_jobs, "alive", return_value=True), patch.object(build_jobs, "table"), patch.object(build_jobs, "show_plan") as show:
                build_jobs.monitor(Mock(), read_runs=lambda: [parent, child])
            state = show.call_args.args[0]
            self.assertEqual([item["state"] for item in state["runs"]], ["current results", "running"])
            self.assertIn("place_design Running", state["phase"])
            self.assertEqual(path.read_text(), original)

    def test_closed_console_preserves_saved_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build.json"
            path.write_text(json.dumps({"pid": 123, "status": "running", "phase": "Building synth", "runs": [plan_entry(run("synth"))]}))
            with patch.object(build_jobs, "readable_state_path", return_value=path), patch.object(build_jobs, "alive", return_value=True), patch.object(build_jobs, "table"), patch.object(build_jobs, "show_plan") as show:
                build_jobs.monitor(Mock(), read_runs=Mock(side_effect=RuntimeError("Console closed")))
            self.assertEqual(show.call_args.args[0]["phase"], "Building synth")
            self.assertIn("Console closed", show.call_args.args[0]["observation"])

    def test_ip_plan_stops_at_routing(self):
        child = run("ip_impl", "ip_synth")
        child["properties"]["HDLFORGE_IS_IP"] = "1"
        item = plan_entry(child)
        self.assertEqual(item["stages"][-1], "route_design")
        self.assertNotIn("*.bit", item["outputs"])

    def test_worker_reports_order_and_disabled_child(self):
        parent = run("synth", status="Complete")
        child = dict(run("impl", "synth"), enabled=False)
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        reports = []
        with patch.object(live_run_groups, "snapshot", return_value=[parent, child]):
            live_run_groups.build(console, "build.synth.continue", 1, 10,
                                  lambda phase, plan: reports.append((phase, copy.deepcopy(plan))))
        final = reports[-1][1]
        self.assertEqual([item["name"] for item in final], ["synth", "impl"])
        self.assertEqual([item["state"] for item in final], ["reused", "skipped: disabled"])
        console.request.assert_not_called()

    def test_failure_keeps_remaining_plan_pending(self):
        parent, child = run("synth"), run("impl", "synth")
        failed = run("synth", status="synth_design ERROR")
        console = Mock()
        console.locked.side_effect = lambda *args: nullcontext()
        reports = []
        with patch.object(live_run_groups, "snapshot", side_effect=[[parent, child]] * 3 + [[failed, child]]):
            with self.assertRaisesRegex(RuntimeError, "remaining runs"):
                live_run_groups.build(console, "build.synth.continue", 1, 10,
                                      lambda phase, plan: reports.append((phase, copy.deepcopy(plan))))
        self.assertEqual([item["state"] for item in reports[-1][1]], ["failed", "pending"])


if __name__ == "__main__":
    unittest.main()
