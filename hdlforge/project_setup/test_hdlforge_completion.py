"""Check display-only descriptions without changing inserted command tokens."""

import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from hdlforge_completion_backend import completion_description, complete_llm_path


class CompletionDisplayTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "sample.hdlforge.json"
        self.project.write_text(json.dumps({
            "LLM_orch": {"demo": {"alpha": "echo alpha", "beta": "echo beta"}},
            "LLM_orch_help": {"demo.alpha": "Read saved JSON", "demo.beta": {"description": "Query live console"}},
        }))

    def complete(self, kind: int, word: str) -> list[str]:
        runtime = Path(__file__).with_name("hdlforge_completion_runtime.bash")
        script = '''
source "$1"
COMP_WORDS=(hdlforge "$2")
COMP_CWORD=1
COMP_TYPE="$3"
_hdlforge_runtime_complete
printf '%s\\0' "${COMPREPLY[@]}"
'''
        result = subprocess.run(["bash", "--noprofile", "--norc", "-c", script, "completion-test", str(runtime), word, str(kind)],
                                cwd=self.project.parent, capture_output=True, check=True, env={**os.environ, "COLUMNS": "100"})
        return result.stdout.decode().rstrip("\0").split("\0")

    def test_normal_and_menu_completion_insert_only_commands(self):
        for kind in (9, 37):
            self.assertEqual(self.complete(kind, "demo."), ["demo.alpha", "demo.beta"])

    def test_double_tab_has_one_column_with_descriptions(self):
        rows = self.complete(63, "demo.")
        self.assertIn("Read saved JSON", rows[0])
        self.assertIn("Query live console", rows[1])
        self.assertTrue(all(len(row) > 50 and "\n" not in row for row in rows))

    def test_single_match_is_never_annotated(self):
        self.assertEqual(self.complete(63, "demo.al"), ["demo.alpha"])

    def test_long_paths_keep_descriptions_without_changing_inserted_paths(self):
        group = "long_group_" * 8
        self.project.write_text(json.dumps({
            "LLM_orch": {group: {"alpha": "echo alpha", "beta": "echo beta"}},
            "LLM_orch_help": {f"{group}.alpha": "Read JSON"},
        }))
        rows = self.complete(63, group + ".")
        self.assertTrue(rows[0].startswith("..."))
        self.assertIn("Read JSON", rows[0])
        self.assertTrue(all(len(row) < 100 for row in rows))
        self.assertEqual(self.complete(9, group + "."), [f"{group}.alpha", f"{group}.beta"])

    def test_help_metadata_is_not_a_command(self):
        self.assertEqual(complete_llm_path(self.project, "").completions, ["demo."])

    def test_description_handles_explicit_json_paths_and_controls(self):
        data = {"LLM_orch_help": {"demo.alpha": {"help": "Read\nJSON\x1b"}}}
        self.assertEqual(completion_description(data, "LLM_orch.demo.alpha"), "Read JSON")
        self.assertEqual(completion_description(data, "demo.beta"), "")


if __name__ == "__main__":
    unittest.main()
