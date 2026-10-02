"""SSH inventory CLI regression tests use temporary files, never real SSH settings."""

from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ssh_config_cli import main
from ssh_config_inventory import merge, parse_config, read_document, render, get_inventory, set_inventory
from hdlforge_completion_backend import complete_command


class SSHInventoryTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.config = self.root / "config"
        self.project = self.root / "repo.json"
        self.config.write_text("# original\nHost lab\n  HostName server.example\n  User alice\n  IdentityFile ~/.ssh/one\n  IdentityFile ~/.ssh/two\n")
        self.project.write_text('{"settings": {"project_name": "test"}}\n')

    def run_cli(self, action, *arguments):
        output = io.StringIO()
        with redirect_stdout(output):
            result = main([action, "--json", str(self.project), "--ssh-config", str(self.config), "--local-host", "local", "--local-user", "owner", *arguments])
        return result, output.getvalue()

    def test_structured_round_trip(self):
        inventory = parse_config(self.config.read_text())
        self.assertEqual(inventory["lab"]["User"], "alice")
        self.assertEqual(inventory["lab"]["IdentityFile"], ["~/.ssh/one", "~/.ssh/two"])
        self.assertEqual(parse_config(render(inventory)), inventory)
        self.assertNotIn("version", inventory)
        self.assertNotIn("preamble", inventory)

    def test_local_host_and_user_isolation(self):
        document = read_document(self.project)
        set_inventory(document, "another-host", "owner", {"untouched": {"User": "other"}})
        set_inventory(document, "local", "another-user", {"private": {"Port": 2200}})
        self.project.write_text(json.dumps(document))
        self.assertEqual(self.run_cli("import", "--force")[0], 0)
        updated = read_document(self.project)
        self.assertEqual(get_inventory(updated, "another-host", "owner"), {"untouched": {"User": "other"}})
        self.assertEqual(get_inventory(updated, "local", "another-user"), {"private": {"Port": 2200}})
        self.assertEqual(get_inventory(updated, "local", "owner")["lab"]["User"], "alice")
        self.assertIsNone(get_inventory(updated, "missing", "owner"))

    def test_verify_ignores_formatting_and_option_name_case(self):
        self.run_cli("import", "--force")
        self.config.write_text(self.config.read_text().replace("User alice", "user = alice").replace("  ", "\t"))
        self.assertEqual(self.run_cli("verify")[0], 0)

    def test_import_export_backup_and_unrelated_fields(self):
        original_project = self.project.read_bytes()
        original_config = self.config.read_text()
        self.assertEqual(self.run_cli("import", "--force")[0], 0)
        self.assertEqual(read_document(self.project)["settings"]["project_name"], "test")
        self.assertEqual(next(self.root.glob("repo.json.*.bak")).read_bytes(), original_project)
        self.config.write_text("Host old\n User other\n")
        self.assertEqual(self.run_cli("export", "--force")[0], 0)
        self.assertEqual(parse_config(self.config.read_text()), parse_config(original_config))
        self.assertEqual(len(list(self.root.glob("config.*.bak"))), 1)
        self.assertEqual(self.run_cli("verify")[0], 0)

    def test_dry_run_and_decline_never_write(self):
        before = self.project.read_bytes()
        self.assertEqual(self.run_cli("import", "--dry-run", "--force")[0], 0)
        with patch("builtins.input", return_value="no"):
            self.assertEqual(self.run_cli("import")[0], 1)
        self.assertEqual(self.project.read_bytes(), before)
        self.assertEqual(list(self.root.glob("*.bak")), [])

    def test_approval_and_eof(self):
        with patch("builtins.input", side_effect=EOFError):
            self.assertEqual(self.run_cli("import")[0], 1)
        with patch("builtins.input", return_value="yes"):
            self.assertEqual(self.run_cli("import")[0], 0)

    def test_collision_is_host_alias_not_hostname(self):
        left = parse_config("Host lab\n User alice\nHost alias\n HostName same\n")
        right = parse_config("Host LAB\n User bob\nHost other\n HostName same\n")
        with redirect_stdout(io.StringIO()) as output:
            result, unresolved = merge([("left", left), ("right", right)], "error")
        self.assertTrue(unresolved)
        self.assertIn("COLLISION: host lab", output.getvalue())
        self.assertEqual(len(result), 3)
        with redirect_stdout(io.StringIO()):
            incoming, unresolved = merge([("left", left), ("right", right)], "incoming")
            kept, _ = merge([("left", left), ("right", right)], "keep")
        self.assertFalse(unresolved)
        self.assertIn("bob", incoming["lab"]["User"])
        self.assertIn("alice", kept["lab"]["User"])

    def test_duplicate_and_repeated_json_keys(self):
        inventory = parse_config("Host lab\n User alice\n")
        with redirect_stdout(io.StringIO()) as output:
            merged, unresolved = merge([("one", inventory), ("two", inventory)], "error")
        self.assertFalse(unresolved)
        self.assertEqual(len(merged), 1)
        self.assertIn("DUPLICATE", output.getvalue())
        self.project.write_text('{"ssh_config": {}, "ssh_config": {}}')
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            read_document(self.project)

    def test_force_does_not_resolve_collision(self):
        self.run_cli("import", "--force")
        source = self.root / "other.json"
        source_document = {}
        set_inventory(source_document, "local", "owner", parse_config("Host lab\n User bob\n"))
        source.write_text(json.dumps(source_document))
        before = self.project.read_bytes()
        self.assertEqual(self.run_cli("merge", "--input", str(source), "--force")[0], 2)
        self.assertEqual(self.project.read_bytes(), before)
        self.assertEqual(self.run_cli("merge", "--input", str(source), "--on-collision", "incoming", "--force")[0], 0)

    def test_concurrent_edit_during_approval(self):
        def edit(_prompt):
            self.project.write_text('{"external": true}\n')
            return "yes"
        with patch("builtins.input", side_effect=edit):
            self.assertEqual(self.run_cli("import")[0], 2)
        self.assertEqual(json.loads(self.project.read_text()), {"external": True})
        self.assertEqual(list(self.root.glob("*.bak")), [])

    def test_unsafe_merge_refused_and_malformed_inventory(self):
        for text in ("Include other\nHost lab\n User a\n", "Host *\n User a\n", "Host a b\n User a\n", "Host lab\n Match all\n User a\n"):
            with self.assertRaises(ValueError):
                merge([("unsafe", parse_config(text))], "incoming")
        inventory = parse_config("Host lab\n User a\n")
        inventory["lab"]["User"] = "bad\nHost injected"
        with self.assertRaises(ValueError):
            render(inventory)

    def test_verify_cross_file_collision(self):
        self.run_cli("import", "--force")
        self.config.write_text("Host lab\n User bob\n")
        result, output = self.run_cli("verify")
        self.assertEqual(result, 1)
        self.assertIn("COLLISION: host lab: JSON vs SSH", output)

    def test_wrapper_help_and_dry_run(self):
        wrapper = Path(__file__).with_name("hdlforge")
        for action in ("import", "export", "verify", "merge"):
            result = subprocess.run([str(wrapper), "ssh."+action, "-h"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--allow-env-overwrite", result.stdout)
        result = subprocess.run([str(wrapper), "ssh.import", "--json", str(self.project), "--ssh-config", str(self.config), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("DRY RUN", result.stdout)
        self.assertNotIn("ssh_config", self.project.read_text())

    def test_completion_actions_policies_and_files(self):
        actions = complete_command([], "ssh.", self.root)[0].completions
        self.assertTrue(set(("ssh.import", "ssh.export", "ssh.verify", "ssh.merge")).issubset(actions))
        policies = complete_command(["ssh.merge", "--on-collision"], "", self.root)[0].completions
        self.assertEqual(policies, ["error", "keep", "incoming"])
        files = complete_command(["ssh.import", "--ssh-config"], str(self.config), self.root)[0].completions
        self.assertIn(str(self.config), files)

    def test_new_files_permissions_symlinks_and_crlf(self):
        self.config.write_bytes(b"Host lab\r\n User alice\r\n")
        self.run_cli("import", "--force")
        expected = self.config.read_bytes()
        self.config.unlink()
        self.assertEqual(self.run_cli("export", "--force")[0], 0)
        self.assertEqual(parse_config(self.config.read_text()), parse_config(expected.decode()))
        self.assertEqual(self.config.stat().st_mode & 0o777, 0o600)
        self.assertEqual(list(self.root.glob("config.*.bak")), [])
        target = self.root / "target"
        self.config.rename(target)
        self.config.symlink_to(target)
        self.assertEqual(self.run_cli("export", "--force")[0], 2)
        self.assertTrue(self.config.is_symlink())

    def test_repeated_backups_and_noop(self):
        self.run_cli("import", "--force")
        self.run_cli("import", "--force")
        self.assertEqual(len(list(self.root.glob("repo.json.*.bak"))), 1)
        self.config.write_text("Host changed\n User alice\n")
        self.run_cli("import", "--force")
        self.assertEqual(len(list(self.root.glob("repo.json.*.bak"))), 2)


if __name__ == "__main__":
    unittest.main()
