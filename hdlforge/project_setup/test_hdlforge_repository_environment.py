"""Repository identity, required environment fields and ordered imports."""

import json
import subprocess
import unittest

import test_hdlforge_environment


class RepositoryEnvironmentTest(unittest.TestCase):
    setUp = test_hdlforge_environment.LauncherEnvironmentTest.setUp

    def invoke(self):
        return subprocess.run([str(self.wrapper), "--no-print", "eval-cmd",
                               'printf "%s|%s" "${VALUE-unset}" "$PYTHONPATH"'],
                              cwd=self.project, env=self.env, capture_output=True, text=True)

    def configure(self, change):
        path = self.project / "sample.hdlforge.json"
        data = json.loads(path.read_text())
        change(data, data["settings"]["env"]["test-host"]["test-user"])
        path.write_text(json.dumps(data))

    def test_missing_user_fails_before_execution(self):
        self.env["HDLFORGE_HOST_USER"] = "unknown"
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing repository environment", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_missing_required_key_fails(self):
        self.configure(lambda data, env: env.pop("variables_import"))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires path", result.stderr)

    def test_imports_then_local_override_with_warning(self):
        self.configure(lambda data, env: (
            data.update(shared={"user.name": {"variables": {"VALUE": "imported"}}}),
            env.update(variables_import=["shared.user.name.variables"], variables={"VALUE": "local"})))
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "local|")
        self.assertIn("overrides environment variable VALUE", result.stderr)
        self.assertNotIn("imported", result.stderr)

    def test_recursive_path_imports_preserve_order_and_deduplicate(self):
        self.configure(lambda data, env: (
            data.update(shared={"base": {"pythonpath": ["base"]},
                                "next": {"pythonpath": ["next"], "pythonpath_import": ["shared.base.pythonpath"]}}),
            env.update(pythonpath_import=["shared.next.pythonpath"], pythonpath=["local", "base"])))
        result = self.invoke()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "unset|" + ":".join(str(self.project / item) for item in ["local", "next", "base"]))

    def test_import_cycle_is_rejected(self):
        self.configure(lambda data, env: env.update(path_import=["settings.env.test-host.test-user.path"]))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import cycle", result.stderr)

    def test_missing_import_is_rejected(self):
        self.configure(lambda data, env: env.update(path_import=["missing.path"]))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Missing environment import", result.stderr)

    def test_wrong_import_type_is_rejected(self):
        self.configure(lambda data, env: env.update(path_import=["settings.env.test-host.test-user.variables"]))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Invalid environment import type", result.stderr)

    def test_null_import_list_is_rejected(self):
        self.configure(lambda data, env: env.update(path_import=None))
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("import fields must be arrays", result.stderr)

    def test_imports_are_not_replayed_in_nested_launch(self):
        self.configure(lambda data, env: (
            data.update(shared={"variables": {"VALUE": "imported"}}),
            env.update(variables_import=["shared.variables"])))
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd",
                                 'export VALUE=runtime; hdlforge eval-cmd "printenv VALUE" --no-print'],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "runtime\n")
        self.assertEqual(result.stderr, "")

    def test_update_repo_from_child_initializes_root(self):
        self.configure(lambda data, env: env.pop("path_import"))
        child = self.project / "child"
        child.mkdir()
        selected = child / "child.hdlforge.json"
        selected.write_text("{}")
        result = subprocess.run([str(self.wrapper), "paths.update-repo"],
                                cwd=child, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(selected.read_text(), "{}")
        self.assertEqual(self.invoke().returncode, 0)

    def test_nested_launch_outside_repository_is_rejected(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd",
                                 'cd /tmp; hdlforge eval-cmd "echo SHOULD_NOT_RUN"'],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SHOULD_NOT_RUN", result.stdout)
        self.assertIn("inside a Git repository", result.stderr)


if __name__ == "__main__":
    unittest.main()
