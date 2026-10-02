"""Exercise fresh environments and literal project/CLI overlays."""

import json
import subprocess
import unittest

import test_hdlforge_environment


class EnvironmentLayersTest(unittest.TestCase):
    setUp = test_hdlforge_environment.LauncherEnvironmentTest.setUp

    def run_command(self, command: str, *arguments: str) -> subprocess.CompletedProcess:
        return subprocess.run([str(self.wrapper), "--no-print", *arguments, "--cmd", command],
                              cwd=self.project, env=self.env, capture_output=True, text=True)

    def test_fresh_launch_removes_caller_exports(self):
        self.env["STALE_CALLER_VARIABLE"] = "stale"
        self.env["SSH_AUTH_SOCK"] = "/example/agent"
        result = self.run_command('printf "%s|%s" "${STALE_CALLER_VARIABLE-unset}" "$SSH_AUTH_SOCK"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "unset|/example/agent")

    def test_nested_launch_retains_parent_runtime_values(self):
        result = self.run_command("export RUNTIME_VALUE=parent; hdlforge --no-print --cmd 'printenv RUNTIME_VALUE'")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "parent\n")

    def test_cli_preserves_literal_trailing_newlines(self):
        value = 'spaces "quotes" $dollar\n\n'
        result = self.run_command('printf "%s" "$LITERAL_VALUE"', "--env-var", json.dumps([{"LITERAL_VALUE": value}]))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, value)

    def test_project_then_cli_precedence_warns_on_stderr(self):
        project = self.project / "child"
        project.mkdir()
        selected = project / "child.hdlforge.json"
        selected.write_text(json.dumps({"settings": {"env": {"test-host": {"test-user": {
            "variables": {"LAYER_VALUE": "project"},
        }}}}}))
        result = self.run_command('printf "%s" "$LAYER_VALUE"', "--project", str(selected),
                                  "--env-var", '[{"LAYER_VALUE":"cli"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "cli")
        self.assertIn("command line overrides environment variable LAYER_VALUE", result.stderr)

    def test_identical_cli_values_are_quiet(self):
        result = self.run_command('printf "%s" "$LAYER_VALUE"', "--env-var",
                                  '[{"LAYER_VALUE":"same"},{"LAYER_VALUE":"same"}]')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "same")
        self.assertEqual(result.stderr, "")

    def test_reserved_cli_variable_rejected_before_child(self):
        result = self.run_command("echo CHILD_EXECUTED", "--env-var", '[{"HDLFORGE_CALLED":"0"}]')
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("CHILD_EXECUTED", result.stdout)
        self.assertIn("reserved environment variable", result.stderr)

    def test_duplicate_cli_paths_are_applied_once(self):
        paths = json.dumps([str(self.bin_dir), str(self.bin_dir)])
        result = self.run_command('printf "%s" "$PATH"', "--env-path", paths)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(":").count(str(self.bin_dir)), 1)

    def test_project_paths_use_project_directory(self):
        child = self.project / "child"
        child.mkdir()
        (child / "modules").mkdir()
        selected = child / "child.hdlforge.json"
        selected.write_text(json.dumps({"settings": {"env": {"test-host": {"test-user": {
            "pythonpath": ["modules"],
        }}}}}))
        result = self.run_command('printf "%s" "$PYTHONPATH"', "--project", str(selected))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, str(child / "modules"))

    def test_zero_marker_rebuilds_environment(self):
        self.env["HDLFORGE_CALLED"] = "0"
        self.env["STALE_CALLER_VARIABLE"] = "stale"
        result = self.run_command('printf "%s" "${STALE_CALLER_VARIABLE-unset}"')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "unset")


if __name__ == "__main__":
    unittest.main()
