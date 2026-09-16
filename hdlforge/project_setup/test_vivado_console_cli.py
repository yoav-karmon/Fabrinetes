"""Exercise reusable console installation and native path discovery via HDLForge."""

import json
from pathlib import Path
import subprocess
import tempfile
import unittest


WRAPPER = Path(__file__).with_name("hdlforge")


class NativeConsoleTest(unittest.TestCase):
    def test_install_and_resolve_explicit_json_in_an_independent_repository(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            project = root / "custom.json"
            project.write_text(json.dumps({"vivado": {"config": {"project_name": "example", "build_dir": "generated"}},
                                           "LLM_orch": {"tools": {"keep": "echo keep", "project_console": {"obsolete": "exit 99"}}}}))
            # Automatic discovery would pick the wrong file; selection must survive recursion.
            (root / "wrong.hdlforge.json").write_text(json.dumps({"vivado": {"config": {"project_name": "wrong"}}}))

            def invoke(*arguments):
                result = subprocess.run([str(WRAPPER), "--no-print", "--project", str(project), *arguments],
                                        cwd=root, capture_output=True, text=True, timeout=30)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return result.stdout

            expected = root / "generated/example/example.xpr"
            self.assertEqual(invoke("--tool", "vivado", "--get_xpr_path"), str(expected) + "\n")
            self.assertFalse(expected.exists())
            invoke("--tool", "vivado", "--project_mng", "install-json",
                   "--json-file", str(project), "--key", "LLM_orch.tools", "--overwrite")
            installed = json.loads(project.read_text())["LLM_orch"]["tools"]
            self.assertEqual(installed["keep"], "echo keep")
            self.assertNotIn("obsolete", installed["project_console"])
            self.assertNotIn("REPO_TOP", json.dumps(installed))
            self.assertIn(str(expected), invoke("tools.project_console.management.name"))
            self.assertFalse(expected.exists())
            # Static build help works even before an XPR exists; targets are explicit appended options.
            action = "build_run"
            shortcut = "tools.project_console.build." + action
            for arguments in ((shortcut,), ("--eval_json", "LLM_orch." + shortcut)):
                output = invoke(*arguments, "--dry-run", "--append", "--run impl_1 --reset --jobs 2")
                self.assertIn("--project_mng " + action + " --run impl_1 --reset --jobs 2", output)
                self.assertIn("execution skipped", output)
            self.assertFalse(expected.exists())
            self.assertIn("--run", invoke(shortcut, "--append", "--help"))
            self.assertNotIn("commands", installed["project_console"])
            self.assertIn("get_build_options", installed["project_console"]["build"])
            installed["project_console"]["obsolete"] = "exit 99"
            config = json.loads(project.read_text())
            config["LLM_orch"]["tools"] = installed
            config["LLM_orch"]["second"] = {"project_console": {**installed["project_console"], "keep": "echo keep"}}
            project.write_text(json.dumps(config))
            invoke("tools.project_console.management.update-json")
            updated = json.loads(project.read_text())
            self.assertNotIn("obsolete", updated["LLM_orch"]["tools"]["project_console"])
            self.assertIn("keep", updated["LLM_orch"]["second"]["project_console"])


if __name__ == "__main__":
    unittest.main()
