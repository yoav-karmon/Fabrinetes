"""Prove argument anchors and declarative option changes in completion."""

from copy import deepcopy
from pathlib import Path
import unittest
import json
import tempfile
from unittest.mock import patch

import hdlforge_completion_backend as completion
from hdlforge_command_tree import parse
from vivado_build_layout import new_identity, write_run


class CompletionTreeTest(unittest.TestCase):
    def test_removed_ssh_tool_is_not_routable(self):
        with self.assertRaises(ValueError):
            parse(['remote-ssh.export'], Path.cwd())
        self.assertEqual(self.complete([], 'remote-ssh.'), [])

    def setUp(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        catalog['tree']['commands']['fixture'] = {
            'commands': {
                'merge': {'flags': {
                    '--input': {'arity': 1, 'repeatable': True}, '#--input': 'Input file',
                    '--local-host': {'arity': 1}, '#--local-host': 'Local host',
                    '--on-collision': {'arity': 1, 'values': {
                        'incoming': {}, '#incoming': 'Use incoming',
                        'existing': {}, '#existing': 'Keep existing'}},
                    '#--on-collision': 'Collision policy'},
                    'dispatch': ['--tool', 'fixture']},
                '#merge': 'Merge fixture inputs',
                'verify': {'dispatch': ['--tool', 'fixture']}, '#verify': 'Verify fixture'},
        }
        catalog['tree']['commands']['#fixture'] = 'Test-only command'
        self.catalog = catalog
        self.tree_patch = patch.object(completion.command_tree, 'load_tree', return_value=catalog['tree'])
        self.tree_patch.start()
        self.addCleanup(self.tree_patch.stop)

    def complete(self, tokens: list[str], current: str = "") -> list[str]:
        return completion.complete_command(tokens, current, Path.cwd())[0].completions

    def test_tool_inline_assignment(self):
        self.assertIn("fixture.merge", self.complete([] , "fixture."))

    def test_action_limits_modifiers(self):
        self.assertIn("--input", self.complete(["fixture.merge"]))
        self.assertNotIn("--input", self.complete(["fixture.verify"]))

    def test_values_that_look_like_flags_do_not_change_anchors(self):
        result = self.complete(["fixture.merge", "--local-host", "--tool"])
        self.assertIn("--input", result)
        self.assertNotIn("--local-host", result)

    def test_inline_value_completion(self):
        self.assertEqual(self.complete(["fixture.merge"], "--on-collision=in"),
                         ["--on-collision=incoming"])

    def test_passthrough_ends_native_completion(self):
        with self.assertRaises(ValueError):
            self.complete(["fixture.merge", "--"])

    def test_repeatable_input_remains_available(self):
        self.assertIn("--input", self.complete(["fixture.merge", "--input", "one.json"]))

    def test_schema_extension_requires_no_engine_change(self):
        catalog = deepcopy(self.catalog)
        flags = catalog["tree"]["commands"]["fixture"]["commands"]["merge"]["flags"]
        flags["--fixture-option"] = {"arity": 0, "when": {"present": "--input"}}
        flags["#--fixture-option"] = "Fixture option after an input"
        with patch.object(completion.command_tree, "load_tree", return_value=catalog["tree"]):
            completion.command_tree.validate(catalog["tree"])
            self.assertNotIn("--fixture-option", self.complete(["fixture.merge"]))
            self.assertIn("--fixture-option", self.complete(["fixture.merge", "--input", "one.json"]))

    def test_undocumented_argument_is_rejected(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        catalog["tree"]["master_flags"]["--undocumented"] = {"arity": 0}
        with self.assertRaisesRegex(ValueError, "Missing command/flag description"):
            completion.command_tree.validate(catalog["tree"])

    def test_build_stage_limits_modifiers(self):
        synth = self.complete(["vivado.build.synth.run"])
        impl = self.complete(["vivado.build.synth.latest.impl.impl.run"])
        self.assertIn("--auto_impl", synth)
        self.assertNotIn("--auto_impl", impl)
        self.assertNotIn("--refresh_impl_inputs", impl)

    def test_nested_build_dispatch_and_old_root_rejection(self):
        state = parse(["vivado.build.demo.latest.impl.route.run"], Path.cwd())
        self.assertEqual(state["args"][:4], ["--tool", "vivado", "--build", "demo.latest.route.run"])
        self.assertEqual(state["values"]["build_stage"], "impl")
        with self.assertRaises(ValueError):
            parse(["vivado.build.impl.demo.latest.route.run"], Path.cwd())
        with self.assertRaises(ValueError):
            parse(["vivado.build.demo.latest.route.run"], Path.cwd())

    def test_nested_completion_lists_only_parent_implementations(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            project = root / "demo.hdlforge.json"
            project.write_text(json.dumps({"vivado": {"non_project": {
                "output_root": "compilation", "runs": {
                    "demo": {"impl_runs": {"route": {}}},
                    "other": {"impl_runs": {"other_route": {}}}}}}}))
            output = root / "compilation/demo/_attempt"
            write_run(output, dict(new_identity(), stage="synth", selector="demo", output=str(output),
                                   status="complete", exit_code=0, top="top", project_file=str(project), implementation_configs={"route": {"script": str(output / "run.tcl")}}))
            (output / 'run.tcl').touch()
            (output / 'artifacts').mkdir()
            (output / 'artifacts/top.dcp').touch()
            (output / 'impl_runs/route').mkdir(parents=True)
            (output / 'impl_runs/route/run.tcl').touch()
            def candidates(current):
                return completion.complete_command(["--project", str(project)], current, root)[0].completions
            self.assertIn("vivado.build.demo.", candidates("vivado.build."))
            self.assertNotIn("vivado.build.impl.", candidates("vivado.build."))
            self.assertEqual(candidates("vivado.build.demo.latest."), ["vivado.build.demo.latest.impl."])
            self.assertEqual(candidates("vivado.build.demo.latest.impl."), ["vivado.build.demo.latest.impl.route."])

    def test_timestamp_precision_survives_nested_dispatch(self):
        stamp = "_2026-10-02T123456.123456Z"
        state = parse([f"vivado.build.demo.{stamp}.impl.route.saved.status"], Path.cwd())
        self.assertEqual(state["args"][3], f"demo.{stamp}.route.saved.status")

    def test_attempt_actions_have_no_build_modifiers(self):
        for action in ('status', 'stop'):
            flags = self.complete(['vivado.build.synth.saved.' + action])
            self.assertNotIn('--auto_impl', flags)
            self.assertNotIn('--refresh_impl_inputs', flags)

    def test_attempt_folder_timestamp_is_one_completion_component(self):
        stamp = '_2026-10-02T191758.567616Z'
        paths = [f'vivado.build.demo.{stamp}.status', f'vivado.build.demo.{stamp}.stop']
        result = completion.complete_dotted_paths(paths, 'vivado.build.demo.')
        self.assertEqual(result.completions, [f'vivado.build.demo.{stamp}.'])

    def test_management_tools_do_not_offer_unhandled_environment_flags(self):
        self.assertIn("--env-var", self.complete(["paths.show"]))

    def test_completion_display_keeps_full_attempt_names(self):
        candidates = [
            'vivado.build.synth_fast._2026-10-02T191758.567616Z.',
            'vivado.build.synth_fast._2026-10-02T191758.567616Z.impl.impl_fast._2026-10-02T200252.962792Z.status',
        ]
        data = {'__native_descriptions': {name: 'Select this attempt' for name in candidates}}
        for columns in (40, 80, 160, 240):
            with self.subTest(columns=columns):
                lines = completion.completion_table(candidates, data, columns)
                for name in candidates:
                    self.assertTrue(any(name in line for line in lines))


if __name__ == "__main__":
    unittest.main()
