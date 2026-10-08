"""Exercise schema repair without launching tools or changing user values."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from hdlforge_command_tree import load_tree, parse
from hdlforge_json import DEFAULTS, lint, main, normalize, write_update


class ProjectJsonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.project = self.root / "test.hdlforge.json"
        self.project.write_text("{}")
        self.output = io.StringIO()

    def run_json(self, scope, action, *args):
        with redirect_stdout(self.output):
            return main([scope, action, "--project", str(self.project), *args])

    def test_every_scope_is_non_destructive_and_idempotent(self):
        original = {"custom": {"keep": [17]}, "vivado": {"monitor": {"poll_seconds": 19}}}
        for scope in [*DEFAULTS, "vivado", "vivado.console"]:
            with self.subTest(scope=scope):
                value, added = normalize(original, scope, "host", "user")
                self.assertEqual(original["custom"], value["custom"])
                self.assertEqual(value["vivado"]["monitor"]["poll_seconds"], 19)
                self.assertTrue(added)
                self.assertEqual(normalize(value, scope, "host", "user"), (value, []))
                self.assertNotIn("settings", original)

    def test_environment_initialization_fills_empty_values_and_preserves_custom_fields(self):
        original = {'settings': {'env': {'default': {
            'path': ['/keep'], 'tools': {'vivado': '/custom'},
            'python_settings': {'version': '', 'packages': ['custom==1']},
            'future': {'keep': True}}, 'other': {'user': {'variables': {'X': 'Y'}}}}}, 'custom': 42}
        generated, changes = normalize(original, 'paths', 'host', 'user')
        default = generated['settings']['env']['default']
        self.assertTrue(default['python_settings']['version'])
        self.assertEqual(default['python_settings']['packages'], ['custom==1'])
        self.assertEqual(default['path'], ['/keep'])
        self.assertEqual(default['tools']['vivado'], '/custom')
        self.assertEqual(default['future'], {'keep': True})
        self.assertEqual(generated['custom'], 42)
        self.assertEqual(generated['settings']['env']['other']['default'], {})
        self.assertEqual(normalize(generated, 'paths', 'host', 'user'), (generated, []))
        self.assertEqual(original['settings']['env']['default']['python_settings']['version'], '')

    def test_dry_run_does_not_write_bytes_mode_or_mtime(self):
        self.project.chmod(0o640)
        before = self.project.stat()
        self.assertEqual(self.run_json("vivado.build", "update-json", "--dry-run"), 0)
        after = self.project.stat()
        self.assertEqual(self.project.read_text(), "{}")
        self.assertEqual((before.st_mode, before.st_mtime_ns), (after.st_mode, after.st_mtime_ns))
        self.assertEqual(list(self.root.iterdir()), [self.project])
        self.assertIn("Add vivado", self.output.getvalue())
        self.assertIn("no files changed", self.output.getvalue())

    def test_missing_keys_are_errors_until_repaired(self):
        self.assertEqual(self.run_json("vivado.build", "lint-json"), 1)
        self.assertEqual(self.run_json("vivado.build", "update-json"), 0)
        self.assertEqual(self.run_json("vivado.build", "lint-json"), 0)
        stamp = self.project.stat().st_mtime_ns
        self.assertEqual(self.run_json("vivado.build", "update-json"), 0)
        self.assertEqual(self.project.stat().st_mtime_ns, stamp)

    def test_bad_existing_type_is_preserved(self):
        self.project.write_text('{"vivado": "custom"}')
        self.assertEqual(self.run_json("vivado.build", "update-json"), 2)
        self.assertEqual(self.project.read_text(), '{"vivado": "custom"}')

    def test_atomic_update_rejects_concurrent_edit(self):
        self.project.write_text('{"changed":true}')
        with self.assertRaisesRegex(ValueError, "changed during update"):
            write_update(self.project, "{}", {"vivado": {}})
        self.assertEqual(json.loads(self.project.read_text()), {"changed": True})
        self.assertEqual(list(self.root.iterdir()), [self.project])

    def test_duplicate_keys_are_rejected_without_rewriting(self):
        self.project.write_text('{"vivado":{}, "vivado":{}}')
        self.assertEqual(self.run_json("vivado.build", "update-json"), 2)
        self.assertIn("Duplicate JSON key", self.output.getvalue())

    def test_build_lint_checks_nested_inputs_types_and_retired_fields(self):
        data = {"vivado": {"non_project": {"runs": {"synth": {
            "script": "run.tcl", "sources": ["source.sv"], "enabled_on_all": "yes",
            "impl_runs": {"impl": {"script": "impl.tcl", "part": "retired"}}}}}}}
        data, _ = normalize(data, "vivado.build", "host", "user")
        errors = lint(data, "vivado.build", self.project, "host", "user")
        self.assertTrue(any("run.tcl" in error for error in errors))
        self.assertTrue(any("impl.tcl" in error for error in errors))
        self.assertTrue(any("not a supported build key" in error for error in errors))
        self.assertTrue(any("retired" in error for error in errors))
        run = data["vivado"]["non_project"]["runs"]["synth"]
        run.pop("enabled_on_all")
        run["impl_runs"]["impl"].pop("part")
        for name in ("run.tcl", "source.sv", "impl.tcl"):
            (self.root / name).write_text("")
        self.assertEqual(lint(data, "vivado.build", self.project, "host", "user"), [])

    def test_simulation_arrays_and_missing_sources(self):
        data = {"verilator": {"config": {"sim_targets": [{"name": "sim", "python_file": "test.py"}]}}}
        data, _ = normalize(data, "sim-verilator", "host", "user")
        self.assertIsInstance(data["verilator"]["config"]["sim_targets"], list)
        self.assertTrue(any("test.py" in error for error in lint(data, "sim-verilator", self.project, "host", "user")))
        (self.root / "test.py").touch()
        self.assertEqual(lint(data, "sim-verilator", self.project, "host", "user"), [])

    def test_environment_import_cycle_is_reported(self):
        data, _ = normalize({}, "paths", "host", "user")
        env = data["settings"]["env"]["host"]["user"]
        env["path_import"] = ["settings.env.host.user.path"]
        self.project.write_text(json.dumps(data))
        self.assertTrue(any("cycle" in error for error in lint(data, "paths", self.project, "host", "user")))

    def test_roots_are_lowercase_with_expected_shared_initials(self):
        roots = [name for name in load_tree()["commands"] if not name.startswith("#")]
        self.assertTrue(all(name == name.lower() for name in roots))
        roots_by_initial = {}
        for name in roots:
            roots_by_initial.setdefault(name[0], []).append(name)
        repeated = {initial: names for initial, names in roots_by_initial.items() if len(names) > 1}
        self.assertEqual(repeated, {"e": ["eval-cmd", "eval-cmd-argv"], "s": ["sim-verilator", "settings"]})
        for scope in [*DEFAULTS, "vivado", "vivado.console"]:
            for action in ("update-json", "lint-json"):
                route = parse([("settings" if scope == "paths" else scope) + "." + action, "--project", str(self.project)], self.root)
                self.assertIn("--json-schema", str(route))

    def test_alias_lint_rejects_removed_commands_without_execution(self):
        self.project.write_text(json.dumps({"LLM_orch": {"bad": "hdlforge vivado.get_xpr_path"}}))
        self.assertEqual(self.run_json("aliases", "lint-json"), 1)
        self.assertIn("Unknown command", self.output.getvalue())

    def test_alias_data_arrays_are_preserved(self):
        self.project.write_text(json.dumps({"LLM_orch": {"env": {"vars": [{"FOO": "bar"}]}, "run": "hdlforge eval-cmd 'true'"}}))
        self.assertEqual(self.run_json("aliases", "lint-json"), 0)

    def test_monitor_update_fills_nested_entries_without_exposing_values(self):
        original = {"vivado": {"monitor": {"execution_targets": {"host": {"ssh": "server"}},
                    "event_tasks": {"closed": [{"name": "notify"}]},
                    "notify": {"outputs": {"slack": {"user_settings": {"login": {"token": "private-fixture"}}}}}}}}
        self.project.write_text(json.dumps(original))
        self.assertEqual(self.run_json("vivado.monitor", "update-json"), 0)
        monitor = json.loads(self.project.read_text())["vivado"]["monitor"]
        self.assertEqual(monitor["execution_targets"]["host"]["exec_prefix"], [])
        self.assertEqual(monitor["event_tasks"]["closed"][0]["command"], [])
        self.assertNotIn("private-fixture", self.output.getvalue())
        self.assertEqual(self.run_json("vivado.monitor", "lint-json"), 0)

    def test_paths_update_repo_dry_run_is_read_only(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        original = self.project.read_text()
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("HDLFORGE_") and key not in {"REPO_TOP", "PYTHONPATH"}}
        environment.update(HOST_MACHINE="test-host", HDLFORGE_HOST_USER="test-user")
        result = subprocess.run([str(Path(__file__).with_name("hdlforge")), "settings.update-repo",
                                 "--project", str(self.project), "--dry-run"],
                                cwd=self.root, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.project.read_text(), original)
        self.assertIn("Fill settings", result.stdout)
        self.assertIn("Dry run", result.stdout)

    def test_schema_maintenance_initializes_empty_repository(self):
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        launcher = Path(__file__).with_name("hdlforge")
        environment = {key: value for key, value in os.environ.items()
                       if not key.startswith("HDLFORGE_") and key != "REPO_TOP"}
        result = subprocess.run([str(launcher), "settings.update-json", "--project", str(self.project)],
                                cwd=self.root, env=environment, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        generated = json.loads(self.project.read_text())['settings']['env']['default']
        self.assertEqual(generated['path'], [])
        self.assertIn('python_settings', generated)


if __name__ == "__main__":
    unittest.main()
