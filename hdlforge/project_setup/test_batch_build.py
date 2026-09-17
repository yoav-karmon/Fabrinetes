"""Batch history, process identity, fresh logs and process-group stopping."""

from contextlib import nullcontext
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

from vivado_console import batch_build, build_jobs


class BatchBuildTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.console = Mock(xpr=self.root / 'chip.xpr', logs_directory=self.root)
        self.console.locked.side_effect = lambda *args: nullcontext()

    def entry(self):
        path = self.root / 'build.log'
        path.write_text('Starting synthesis\n')
        return {'id': 'test', 'pid': os.getpid(), 'process': build_jobs.identity(os.getpid()),
                'target': 'synth', 'submitted_at': time.time(), 'log': str(path)}

    def test_status_reads_log_again_and_records_quiet_duration(self):
        entry = self.entry()
        build_jobs.write_history(self.console, {'submissions': [entry]})
        path = Path(entry['log'])
        old = time.time() - 120
        os.utime(path, (old, old))
        self.assertEqual(build_jobs.refresh(self.console)[0]['last_status']['status'], 'Quiet')
        path.write_text('New stage\n')
        fresh = build_jobs.refresh(self.console)[0]['last_status']
        self.assertEqual(fresh['status'], 'Running')
        self.assertEqual(fresh['tail'], ['New stage'])
        self.console.request.assert_not_called()

    def test_reused_pid_does_not_count_as_alive(self):
        entry = self.entry()
        entry['process']['start_ticks'] = 'invalid'
        self.assertFalse(build_jobs.alive(entry))

    def test_exit_results_come_from_log_not_saved_status(self):
        entry = self.entry()
        entry['process'] = None
        for text, expected in [('HDLFORGE_BATCH_COMPLETED\n', 'Completed'),
                               ('ERROR: launch rejected\n', 'Failed / interrupted'),
                               ('still working\n', 'Exited; result unknown')]:
            Path(entry['log']).write_text(text)
            self.assertEqual(build_jobs.observe(entry)['status'], expected)

    def test_multiple_submissions_keep_history_without_liveness_gate(self):
        process = Mock(pid=123)
        process.wait.side_effect = subprocess.TimeoutExpired('vivado', .5)
        with patch.object(batch_build.subprocess, 'Popen', return_value=process), patch.object(build_jobs, 'identity', return_value=None):
            first = batch_build.start(self.console, 'synth')
            second = batch_build.start(self.console, 'impl')
        self.assertNotEqual(first['id'], second['id'])
        self.assertEqual(len(build_jobs.read_history(self.console)['submissions']), 2)
        self.console.open.assert_not_called()

    def test_immediate_failure_is_recorded(self):
        process = Mock(pid=123)
        process.wait.return_value = 1
        with patch.object(batch_build.subprocess, 'Popen', return_value=process), patch.object(build_jobs, 'identity', return_value=None):
            entry = batch_build.start(self.console, 'missing')
        self.assertEqual(entry['exit_code'], 1)

    def test_stop_refuses_reused_pid(self):
        entry = self.entry()
        entry['process']['start_ticks'] = 'invalid'
        build_jobs.write_history(self.console, {'submissions': [entry]})
        with patch.object(build_jobs.os, 'killpg') as kill:
            build_jobs.stop(self.console, 'test')
            kill.assert_not_called()

    def test_stop_real_batch_and_child(self):
        child_file = self.root / 'child.pid'
        code = "import subprocess,time,pathlib; p=subprocess.Popen(['sleep','60']); pathlib.Path(" + repr(str(child_file)) + ").write_text(str(p.pid)); time.sleep(60)"
        process = subprocess.Popen([sys.executable, '-c', code], start_new_session=True)
        try:
            for _ in range(100):
                if child_file.exists(): break
                time.sleep(.01)
            entry = self.entry()
            entry.update(pid=process.pid, process=build_jobs.identity(process.pid))
            build_jobs.write_history(self.console, {'submissions': [entry]})
            build_jobs.stop(self.console, 'test')
            process.wait(timeout=5)
            child = int(child_file.read_text())
            for _ in range(100):
                if build_jobs.identity(child) is None: break
                time.sleep(.01)
            self.assertIsNone(build_jobs.identity(child))
            self.assertFalse(build_jobs.alive(entry))
        finally:
            if process.poll() is None:
                os.killpg(process.pid, 9)
                process.wait()
