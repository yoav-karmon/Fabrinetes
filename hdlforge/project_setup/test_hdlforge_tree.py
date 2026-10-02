"""Prove argument anchors and declarative option changes in completion."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import hdlforge_completion_backend as completion


class CompletionTreeTest(unittest.TestCase):
    def complete(self, tokens: list[str], current: str = "") -> list[str]:
        return completion.complete_command(tokens, current, Path.cwd())[0].completions

    def test_tool_inline_assignment(self):
        self.assertIn("ssh.merge", self.complete([] , "ssh."))

    def test_action_limits_modifiers(self):
        self.assertIn("--input", self.complete(["ssh.merge"]))
        self.assertNotIn("--input", self.complete(["ssh.verify"]))

    def test_values_that_look_like_flags_do_not_change_anchors(self):
        result = self.complete(["ssh.merge", "--local-host", "--tool"])
        self.assertIn("--input", result)
        self.assertNotIn("--local-host", result)

    def test_inline_value_completion(self):
        self.assertEqual(self.complete(["ssh.merge"], "--on-collision=in"),
                         ["--on-collision=incoming"])

    def test_passthrough_ends_native_completion(self):
        with self.assertRaises(ValueError):
            self.complete(["ssh.merge", "--"])

    def test_repeatable_input_remains_available(self):
        self.assertIn("--input", self.complete(["ssh.merge", "--input", "one.json"]))

    def test_schema_extension_requires_no_engine_change(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        flags = catalog["tree"]["commands"]["ssh"]["commands"]["merge"]["flags"]
        flags["--fixture-option"] = {"arity": 0, "when": {"present": "--input"}}
        flags["#--fixture-option"] = "Fixture option after an input"
        with patch.object(completion.command_tree, "load_tree", return_value=catalog["tree"]):
            completion.command_tree.validate(catalog["tree"])
            self.assertNotIn("--fixture-option", self.complete(["ssh.merge"]))
            self.assertIn("--fixture-option", self.complete(["ssh.merge", "--input", "one.json"]))

    def test_undocumented_argument_is_rejected(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        catalog["tree"]["master_flags"]["--undocumented"] = {"arity": 0}
        with self.assertRaisesRegex(ValueError, "Missing command/flag description"):
            completion.command_tree.validate(catalog["tree"])

    def test_build_stage_limits_modifiers(self):
        synth = self.complete(["vivado.build.synth.synth.new"])
        impl = self.complete(["vivado.build.impl.synth.latest.impl.new"])
        self.assertIn("--auto_impl", synth)
        self.assertNotIn("--auto_impl", impl)
        self.assertIn("--refresh_impl_inputs", impl)

    def test_management_tools_do_not_offer_unhandled_environment_flags(self):
        self.assertIn("--env-var", self.complete(["path_manager.show"]))


if __name__ == "__main__":
    unittest.main()
