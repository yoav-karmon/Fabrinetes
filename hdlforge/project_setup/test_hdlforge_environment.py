"""Verify command startup without an interactive shell environment."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class LauncherEnvironmentTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.home.joinpath(".bashrc").write_text("echo UNEXPECTED_BASHRC >&2; exit 99\n")
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.project)], check=True)
        self.wrapper = Path(__file__).with_name("hdlforge").resolve()
        self.project.joinpath("sample.hdlforge.json").write_text(json.dumps({
            "LLM_orch": {"nested": "hdlforge --no-print --cmd 'command -v hdlforge; command -v vivado'"},
        }))
        self.bin_dir = self.root / "vendor bin"
        self.bin_dir.mkdir()
        self.bin_dir.joinpath("vivado").write_text("#!/bin/sh\nexit 0\n")
        self.bin_dir.joinpath("vivado").chmod(0o755)
        self.settings = self.root / "settings.sh"
        self.settings.write_text(f'export PATH="{self.bin_dir}:$PATH"\necho TOOL_STARTUP\n')
        self.env = {"HOME": str(self.home), "USER": os.environ.get("USER", "test"),
                    "PATH": os.defpath, "INIT_PATH": os.defpath, "INIT_PYTHONPATH": "",
                    "BASHRC_INITIALIZED": "1", "FABRINETES": "/stale/installation",
                    "VIVADO_SETTINGS": str(self.settings)}

    def test_cold_shortcut_resolves_nested_launcher_and_configured_tool(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "nested"], cwd=self.project,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.wrapper), str(self.bin_dir / "vivado")])
        self.assertEqual(result.stderr, "")

    def test_quiet_mode_preserves_command_output_and_exit_status(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "--cmd",
                                 "printf 'result\\n'; printf 'command error\\n' >&2; exit 37"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 37)
        self.assertEqual(result.stdout, "result\n")
        self.assertEqual(result.stderr, "command error\n")

    def test_missing_settings_reports_startup_failure(self):
        self.env["VIVADO_SETTINGS"] = str(self.root / "missing-settings.sh")
        result = subprocess.run([str(self.wrapper), "--no-print", "--cmd", "echo SHOULD_NOT_RUN"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SHOULD_NOT_RUN", result.stdout)
        self.assertIn("Vivado settings file is not readable", result.stderr)


if __name__ == "__main__":
    unittest.main()
