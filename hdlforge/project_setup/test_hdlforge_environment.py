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
            "LLM_orch": {"nested": "hdlforge --no-print --cmd 'command -v hdlforge'"},
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

    def test_cold_shortcut_resolves_nested_launcher(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "nested"], cwd=self.project,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.wrapper)])
        self.assertEqual(result.stderr, "")

    def test_quiet_mode_preserves_command_output_and_exit_status(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "--cmd",
                                 "printf 'result\\n'; printf 'command error\\n' >&2; exit 37"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 37)
        self.assertEqual(result.stdout, "result\n")
        self.assertEqual(result.stderr, "command error\n")

    def test_external_vivado_settings_do_not_override_host_user_selection(self):
        self.env["VIVADO_SETTINGS"] = str(self.root / "missing-settings.sh")
        result = subprocess.run([str(self.wrapper), "--no-print", "--cmd", "echo SHOULD_NOT_RUN"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "SHOULD_NOT_RUN\n")

    def test_add_to_bashrc_path_inserts_repairs_and_is_idempotent(self):
        bashrc = self.home / ".bashrc"
        bashrc.write_text(
            "export PATH=\"/other/hdlforge/project_setup:$PATH\"\n"
            "export PATH=\"/wrong/path:$PATH\" # hdlforge-path\n"
        )

        first = subprocess.run([str(self.wrapper), "--add-to-bashrc-path"],
                               env=self.env, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = (
            f'export PATH="{self.wrapper.parent}:$PATH" # hdlforge-path\n'
            f'[ -r "{self.wrapper.parent}/hdlforge_completion.bash" ] && '
            f'source "{self.wrapper.parent}/hdlforge_completion.bash" # hdlforge-completion\n'
        )
        self.assertEqual(bashrc.read_text(), expected)
        self.assertIn("Repaired HDLForge PATH entry", first.stdout)

        second = subprocess.run([str(self.wrapper), "--add-to-bashrc-path"],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(bashrc.read_text(), expected)
        self.assertIn("already correct", second.stdout)

    def test_print_env_shows_path_provenance(self):
        result = subprocess.run([str(self.wrapper), "--print-env"], cwd=self.project,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HDLForge prepared environment", result.stdout)
        self.assertIn("PATH (lookup order):", result.stdout)
        self.assertIn("PYTHONPATH (lookup order):", result.stdout)
        self.assertIn("HDLForge launcher", result.stdout)


if __name__ == "__main__":
    unittest.main()
