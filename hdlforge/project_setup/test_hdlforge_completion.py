"""Check display-only descriptions without changing inserted command tokens."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from hdlforge_completion_backend import completion_description, complete_llm_path, complete_json_path, is_llm_leaf


class CompletionDisplayTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.project = Path(self.temporary.name) / "sample.hdlforge.json"
        self.project.write_text(json.dumps({
            "LLM_orch": {"#demo": "Demo commands", "demo": {
                "#alpha": "Read saved JSON", "alpha": "echo alpha",
                "#beta": "Query live console", "beta": "echo beta",
                "#notes": {"nested": "hdlforge must not run this"},
            }},
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
        self.assertTrue(rows[0].startswith("+"))
        self.assertIn("Command", rows[1])
        self.assertIn("Description", rows[1])
        self.assertIn("Read saved JSON", "\n".join(rows))
        self.assertIn("Query live console", "\n".join(rows))
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
        self.assertTrue(rows[0].startswith("+"))
        self.assertIn("Read JSON", "\n".join(rows))
        self.assertTrue(all(len(row) <= 100 for row in rows))
        self.assertEqual(self.complete(9, group + "."), [f"{group}.alpha", f"{group}.beta"])

    def test_table_completion_works_without_the_fpga_repository(self):
        standalone = self.project.parent / "standalone_hdlforge"
        standalone.mkdir()
        for filename in ("hdlforge_completion_backend.py", "table_formatter.py"):
            shutil.copyfile(Path(__file__).with_name(filename), standalone / filename)
        result = subprocess.run(["python3", "-E", "-s", str(standalone / "hdlforge_completion_backend.py"),
                                 "--cwd", str(self.project.parent), "--comp-cword", "1", "--display-table",
                                 "--", "hdlforge", "demo."], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("__TABLE__\t+", result.stdout)
        self.assertIn("Read saved JSON", result.stdout)

    def test_help_metadata_is_not_a_command(self):
        self.assertEqual(complete_llm_path(self.project, "").completions, ["demo."])
        self.assertEqual(complete_json_path(self.project, "LLM_orch.demo.").completions,
                         ["LLM_orch.demo.alpha", "LLM_orch.demo.beta"])
        self.assertFalse(is_llm_leaf(self.project, "demo.#alpha"))

    def test_wrapper_rejects_direct_metadata_execution(self):
        wrapper = Path(__file__).with_name("hdlforge")
        subprocess.run(["git", "init", "--quiet", str(self.project.parent)], check=True)
        for path in ("demo.#alpha", "LLM_orch.demo.#notes.nested"):
            result = subprocess.run(["bash", str(wrapper), "--project", str(self.project), "--eval_json", path],
                                    capture_output=True, text=True)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Description metadata cannot be executed", result.stdout)

    def test_description_handles_explicit_json_paths_and_controls(self):
        data = {"LLM_orch_help": {"demo.alpha": {"help": "Read\nJSON\x1b"}}}
        self.assertEqual(completion_description(data, "LLM_orch.demo.alpha"), "Read JSON")
        self.assertEqual(completion_description(data, "demo.beta"), "")


if __name__ == "__main__":
    unittest.main()
