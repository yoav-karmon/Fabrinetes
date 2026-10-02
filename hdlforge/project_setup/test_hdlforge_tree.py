"""Prove argument anchors and declarative option changes in completion."""

from copy import deepcopy
from pathlib import Path
import unittest
from unittest.mock import patch

import hdlforge_completion_backend as completion


class CompletionTreeTest(unittest.TestCase):
    def complete(self, tokens: list[str], current: str = "") -> list[str]:
        return completion.complete_classic(tokens, current, Path.cwd()).completions

    def test_tool_inline_assignment(self):
        self.assertIn("merge", self.complete(["--tool=ssh"]))

    def test_action_limits_modifiers(self):
        self.assertIn("--input", self.complete(["--tool", "ssh", "merge"]))
        self.assertNotIn("--input", self.complete(["--tool", "ssh", "verify"]))

    def test_values_that_look_like_flags_do_not_change_anchors(self):
        result = self.complete(["--tool", "ssh", "merge", "--local-host", "--tool"])
        self.assertIn("--input", result)
        self.assertNotIn("--local-host", result)

    def test_inline_value_completion(self):
        self.assertEqual(self.complete(["--tool", "ssh", "merge"], "--on-collision=in"),
                         ["--on-collision=incoming"])

    def test_passthrough_ends_native_completion(self):
        self.assertEqual(self.complete(["--tool", "ssh", "merge", "--"]), [])

    def test_repeatable_input_remains_available(self):
        self.assertIn("--input", self.complete(["--tool", "ssh", "merge", "--input", "one.json"]))

    def test_schema_extension_requires_no_engine_change(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        flags = catalog["tree"]["tools"]["ssh"]["actions"]["merge"]["flags"]
        flags["--fixture-option"] = {"arity": 0, "when": {"present": "--input"}}
        flags["#--fixture-option"] = "Fixture option after an input"
        with patch.object(completion, "NATIVE_HELP", catalog):
            completion.validate_tree(catalog["tree"])
            self.assertNotIn("--fixture-option", self.complete(["--tool", "ssh", "merge"]))
            self.assertIn("--fixture-option", self.complete(["--tool", "ssh", "merge", "--input", "one.json"]))

    def test_undocumented_argument_is_rejected(self):
        catalog = deepcopy(completion.NATIVE_HELP)
        catalog["tree"]["flags"]["--undocumented"] = {"arity": 0}
        with self.assertRaisesRegex(ValueError, "Missing completion description"):
            completion.validate_tree(catalog["tree"])

    def test_build_stage_limits_modifiers(self):
        synth = self.complete(["--tool", "vivado", "--build", "synth.new"])
        impl = self.complete(["--tool", "vivado", "--build", "synth.latest.impl.new"])
        self.assertIn("--auto_impl", synth)
        self.assertNotIn("--auto_impl", impl)
        self.assertIn("--refresh_impl_inputs", impl)

    def test_management_tools_do_not_offer_unhandled_environment_flags(self):
        self.assertNotIn("--env-var", self.complete(["--tool", "path_manager", "show"]))


if __name__ == "__main__":
    unittest.main()
