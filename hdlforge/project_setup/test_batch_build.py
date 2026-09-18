"""Batch launcher starts independently without maintaining PID history."""

from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from vivado_console import batch_build, live_run_groups


class BatchBuildTest(unittest.TestCase):
    def test_launches_twice_without_console_or_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            xpr = Path(directory)/"chip"/"chip.xpr"
            process = Mock()
            process.wait.side_effect = subprocess.TimeoutExpired("vivado", 0.5)
            with patch.object(batch_build.subprocess, "Popen", return_value=process) as launch:
                first = batch_build.start(xpr, "synth_production")
                second = batch_build.start(xpr, "synth_production")
            self.assertEqual(launch.call_count, 2)
            self.assertNotEqual(first["log"], second["log"])
            self.assertNotIn("pid", first)
            self.assertFalse((Path(directory)/"submissions.json").exists())

    def test_reports_immediate_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            xpr = Path(directory)/"chip"/"chip.xpr"
            with patch.object(batch_build.subprocess, "Popen", return_value=Mock(wait=Mock(return_value=1))):
                self.assertEqual(batch_build.start(xpr, "synth_production")["exit_code"], 1)

    def test_command_propagates_failure_without_constructing_console(self):
        with patch.object(live_run_groups, "load_xpr_path", return_value=Path("/tmp/chip.xpr")), \
             patch.object(live_run_groups, "ProjectConsole", side_effect=AssertionError("No console")), \
             patch.object(batch_build, "start", return_value={"exit_code": 7}):
            self.assertEqual(live_run_groups.main(Path("chip.json"), "build_run", ["--run", "synth_1"]), 7)
