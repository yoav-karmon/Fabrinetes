"""Verify command startup without an interactive shell environment."""

import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest


class LauncherEnvironmentTest(unittest.TestCase):
    def test_json_license_environment(self):
        project_file = self.project / "sample.hdlforge.json"
        data = json.loads(project_file.read_text())
        license_path = str(self.root / "license folder" / "Xilinx.lic")
        data["settings"]["env"]["test-host"]["test-user"]["variables"] = {
            "XILINXD_LICENSE_FILE": license_path,
        }
        project_file.write_text(json.dumps(data))
        for command in ('printenv XILINXD_LICENSE_FILE',
                        "hdlforge --no-print eval-cmd 'printenv XILINXD_LICENSE_FILE'"):
            with self.subTest(command=command):
                result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd", command],
                                        cwd=self.project, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.strip(), license_path)

    def test_build_selector_is_not_a_shortcut(self):
        for arguments in (
            ["vivado.build.synth.synth_production.new"],
            ["vivado.build.synth.synth_production.new"],
            ["vivado.build.synth.synth_production.new"],
        ):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(self.wrapper), "--dry-run", *arguments],
                                        cwd=self.project, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertIn("--tool execution skipped", result.stdout)
                self.assertNotIn("--eval_json", result.stdout)

    def test_build_does_not_hide_a_conflicting_shortcut(self):
        result = subprocess.run([str(self.wrapper), "--dry-run", "vivado.build.synth.synth_production.new", "other.shortcut"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unexpected argument", result.stderr)

    def setUp(self):
        # Snap-installed jq has a private /tmp but can read user-owned home files.
        self.temporary = tempfile.TemporaryDirectory(dir=Path.home())
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.home = self.root / "home"
        self.home.mkdir()
        self.home.joinpath(".bashrc").write_text("echo UNEXPECTED_BASHRC >&2; exit 99\n")
        self.project = self.root / "project"
        self.project.mkdir()
        subprocess.run(["git", "init", "--quiet", str(self.project)], check=True)
        self.wrapper = Path(__file__).with_name("hdlforge").resolve()
        self.project.joinpath("sample.hdlforge.json").write_text(json.dumps({
            "LLM_orch": {"nested": "hdlforge --no-print eval-cmd 'command -v hdlforge'"},
            "settings": {"env": {"test-host": {"test-user": {
                "path": [str(Path(shutil.which("jq")).parent)],
                "path_import": [], "pythonpath": [], "pythonpath_import": [],
                "variables": {}, "variables_import": [],
            }}}},
        }))
        self.bin_dir = self.root / "vendor bin"
        self.bin_dir.mkdir()
        self.bin_dir.joinpath("vivado").write_text("#!/bin/sh\nexit 0\n")
        self.bin_dir.joinpath("vivado").chmod(0o755)
        self.settings = self.root / "settings.sh"
        self.settings.write_text(f'export PATH="{self.bin_dir}:$PATH"\necho TOOL_STARTUP\n')
        self.env = {"HOME": str(self.home), "USER": os.environ.get("USER", "test"),
                    "HOST_MACHINE": "test-host", "HDLFORGE_HOST_USER": "test-user",
                    "PATH": f"{Path(shutil.which('jq')).parent}:{os.defpath}",
                    "INIT_PATH": os.defpath, "INIT_PYTHONPATH": "",
                    "BASHRC_INITIALIZED": "1", "FABRINETES": "/stale/installation",
                    "VIVADO_SETTINGS": str(self.settings)}

    def test_json_is_read_before_path_reset(self):
        # jq exists only on the incoming PATH, not the configured base PATH.
        incoming_bin = self.root / "incoming bin"
        incoming_bin.mkdir()
        incoming_bin.joinpath("jq").symlink_to(shutil.which("jq"))
        self.env["PATH"] = f"{incoming_bin}:{os.defpath}"
        self.env["HDLFORGE_BASE_PATH"] = os.defpath
        self.env["HOST_MACHINE"] = "test-host"
        self.env["HDLFORGE_HOST_USER"] = "test-user"
        self.project.joinpath("sample.hdlforge.json").write_text(json.dumps({
            "settings": {"env": {"test-host": {"test-user": {
                "path": [str(self.bin_dir)], "pythonpath": [str(self.root)],
                "path_import": [], "pythonpath_import": [], "variables": {}, "variables_import": [],
            }}}},
        }))
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd",
                                 'command -v vivado; printf "%s\\n" "$PATH" "$PYTHONPATH"'],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines()[0], str(self.bin_dir / "vivado"))
        self.assertNotIn(str(incoming_bin), result.stdout)
        self.assertEqual(result.stdout.splitlines()[-1], str(self.root))
        self.assertEqual(result.stderr, "")

    def test_invalid_json_stops_before_command(self):
        self.project.joinpath("sample.hdlforge.json").write_text("{invalid")
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd", "echo SHOULD_NOT_RUN"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("SHOULD_NOT_RUN", result.stdout)

    def test_cold_shortcut_resolves_nested_launcher(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "project-shortcuts.nested"], cwd=self.project,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(self.wrapper)])
        self.assertEqual(result.stderr, "")

    def test_quiet_mode_preserves_command_output_and_exit_status(self):
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd",
                                 "printf 'result\\n'; printf 'command error\\n' >&2; exit 37"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 37)
        self.assertEqual(result.stdout, "result\n")
        self.assertEqual(result.stderr, "command error\n")

    def test_external_vivado_settings_do_not_override_host_user_selection(self):
        self.env["VIVADO_SETTINGS"] = str(self.root / "missing-settings.sh")
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd", "echo SHOULD_NOT_RUN"],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout, "SHOULD_NOT_RUN\n")

    def test_add_to_bashrc_path_inserts_repairs_and_is_idempotent(self):
        bashrc = self.home / ".bashrc"
        bashrc.write_text(
            "export PATH=\"/other/hdlforge/project_setup:$PATH\"\n"
            "export PATH=\"/wrong/path:$PATH\" # hdlforge-path\n"
        )

        first = subprocess.run([str(self.wrapper), "path_manager.install-shell"],
                               env=self.env, capture_output=True, text=True)
        self.assertEqual(first.returncode, 0, first.stderr)
        expected = (
            f'export PATH="{self.wrapper.parent}:$PATH" # hdlforge-path\n'
            f'[ -r "{self.wrapper.parent}/hdlforge_completion.bash" ] && '
            f'source "{self.wrapper.parent}/hdlforge_completion.bash" # hdlforge-completion\n'
        )
        self.assertEqual(bashrc.read_text(), expected)
        self.assertIn("Repaired HDLForge PATH entry", first.stdout)

        second = subprocess.run([str(self.wrapper), "path_manager.install-shell"],
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(bashrc.read_text(), expected)
        self.assertIn("already correct", second.stdout)

    def test_print_env_shows_path_provenance(self):
        result = subprocess.run([str(self.wrapper), "path_manager.show"], cwd=self.project,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("HDLForge selected environment", result.stdout)
        self.assertIn("PATH (lookup order):", result.stdout)
        self.assertIn("PYTHONPATH (lookup order):", result.stdout)
        self.assertIn("HDLForge launcher", result.stdout)

    def run_selection(self, cwd: Path, arguments: list[str] | None = None) -> subprocess.CompletedProcess:
        """Observe the actual command directory and authoritative project selection."""
        command = 'printf "%s\\n" "$PWD" "$ROOT_FOLDER" "$HDLFORGE_PROJECT_FILE"'
        return subprocess.run([str(self.wrapper), "--no-print", *(arguments or []), "eval-cmd", command],
                              cwd=cwd, env=self.env, capture_output=True, text=True)

    def make_selected_project(self) -> Path:
        """Create a project below the fixture repository's environment JSON."""
        selected = self.project / "design with spaces" / "selected.hdlforge.json"
        selected.parent.mkdir()
        selected.write_text('{"LLM_orch": {"where": "pwd"}}')
        return selected

    def test_discovery_from_project_subdirectory(self):
        # Select the closest project and execute in its containing directory.
        selected = self.make_selected_project()
        launch_dir = selected.parent / "sources"
        launch_dir.mkdir()
        result = self.run_selection(launch_dir)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(selected.parent), str(selected.parent), str(selected)])

    def test_explicit_project_overrides_launch_project(self):
        selected = self.make_selected_project()
        relative = str(selected.relative_to(self.project))
        for arguments in (["--project", relative], [f"--project={relative}"]):
            with self.subTest(arguments=arguments):
                result = self.run_selection(self.project, arguments)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(result.stdout.splitlines(), [str(selected.parent), str(selected.parent), str(selected)])

    def test_explicit_symlink_resolves_to_project_directory(self):
        selected = self.make_selected_project()
        link = self.project / "selected-link.json"
        link.symlink_to(selected)
        result = self.run_selection(self.project, ["--project", str(link)])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(selected.parent), str(selected.parent), str(selected)])

    def test_ambiguous_discovery_requires_explicit_project(self):
        selected = self.make_selected_project()
        selected.with_name("other.hdlforge.json").write_text("{}")
        result = self.run_selection(selected.parent)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("multiple", result.stderr.lower())
        self.assertIn("--project", result.stderr)
        self.assertEqual(result.stdout, "")

    def test_explicit_selection_resolves_ambiguity(self):
        selected = self.make_selected_project()
        selected.with_name("other.hdlforge.json").write_text("{}")
        result = self.run_selection(selected.parent, ["--project", selected.name])
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], str(selected))

    def test_nested_command_preserves_explicit_selection(self):
        selected = self.make_selected_project()
        selected.with_name("other.hdlforge.json").write_text("{}")
        command = "hdlforge --no-print eval-cmd 'printenv HDLFORGE_PROJECT_FILE'"
        result = subprocess.run([str(self.wrapper), "--no-print", "--project", str(selected), "eval-cmd", command],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), str(selected))

    def test_fresh_launch_ignores_stale_project_environment(self):
        selected = self.make_selected_project()
        self.env["HDLFORGE_PROJECT_FILE"] = str(self.project / "sample.hdlforge.json")
        result = self.run_selection(selected.parent)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines()[-1], str(selected))

    def test_missing_explicit_project_fails_before_command(self):
        result = self.run_selection(self.project, ["--project", "missing.hdlforge.json"])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("not found", result.stderr.lower())
        self.assertEqual(result.stdout, "")

    def test_empty_explicit_project_is_rejected(self):
        for arguments in (["--project", ""], ["--project="]):
            with self.subTest(arguments=arguments):
                result = self.run_selection(self.project, arguments)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("--project", result.stderr)

    def test_vcd_argument_keeps_original_launch_base(self):
        selected = self.make_selected_project()
        for arguments in (["--vcdfilename", "capture.vcd"], ["--vcdfilename=capture.vcd"]):
            with self.subTest(arguments=arguments):
                result = subprocess.run([str(self.wrapper), "--project", str(selected), "--dry-run",
                                         "vcd_analyzer.modules", *arguments], cwd=self.project,
                                        env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                command = next(line.removeprefix("[i] Command: ") for line in result.stdout.splitlines()
                               if line.startswith("[i] Command: "))
                tokens = shlex.split(command)
                self.assertIn(str(self.project / "capture.vcd"), tokens)
                self.assertEqual(tokens[tokens.index("--project") + 1], str(selected))
                self.assertIn(f"[i] Working directory: {selected.parent}", result.stdout)

    def test_selected_sources_keep_original_launch_base(self):
        selected = self.make_selected_project()
        for flag in ("--lint-file", "--file"):
            with self.subTest(flag=flag):
                result = subprocess.run([str(self.wrapper), "--project", str(selected), "--dry-run",
                                         "Verilator.lint", flag, "outside.sv,second.sv"],
                                        cwd=self.project, env=self.env, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                command = next(line.removeprefix("[i] Command: ") for line in result.stdout.splitlines()
                               if line.startswith("[i] Command: "))
                tokens = shlex.split(command)
                self.assertEqual(tokens[tokens.index(flag) + 1],
                                 f"{self.project}/outside.sv,{self.project}/second.sv")

    def test_project_free_command_outside_repository_is_rejected(self):
        command = f"cd {shlex.quote(str(self.home))} && hdlforge --no-print eval-cmd pwd"
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd", command],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("inside a Git repository", result.stderr)

    def test_discovery_does_not_escape_git_boundary(self):
        nested_repo = self.project / "nested-repo"
        nested_repo.mkdir()
        subprocess.run(["git", "init", "--quiet", str(nested_repo)], check=True)
        self.env["HDLFORGE_CALLED"] = "1"
        self.env["REPO_TOP"] = str(nested_repo)
        result = self.run_selection(nested_repo)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(nested_repo), str(nested_repo), ""])

    def test_nested_command_can_select_another_project(self):
        selected = self.make_selected_project()
        command = f"cd {shlex.quote(str(selected.parent))} && hdlforge --no-print eval-cmd 'printenv HDLFORGE_PROJECT_FILE'"
        result = subprocess.run([str(self.wrapper), "--no-print", "eval-cmd", command],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), str(selected))

    def test_anonymous_passthrough_is_rejected(self):
        result = subprocess.run([str(self.wrapper), 'Verilator.lint', '--', '--project', 'other.json'],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Unexpected argument', result.stderr)

    def test_project_leaf_uses_the_selected_file(self):
        selected = self.make_selected_project()
        selected.write_text(json.dumps({"env": {"values": [{"SELECTED_VALUE": "correct project"}]}}))
        launch_dir = selected.parent / "nested"
        launch_dir.mkdir()
        result = subprocess.run([str(self.wrapper), "--no-print", "--env-var", "env.values",
                                 "eval-cmd", "printenv SELECTED_VALUE"], cwd=launch_dir,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.strip(), "correct project")

    def test_explicit_project_uses_its_own_repository(self):
        external = self.root / "external-repo"
        external.mkdir()
        subprocess.run(["git", "init", "--quiet", str(external)], check=True)
        selected = external / "external.hdlforge.json"
        selected.write_text((self.project / "sample.hdlforge.json").read_text())
        result = subprocess.run([str(self.wrapper), "--no-print", "--project", str(selected),
                                 "eval-cmd", 'printf "%s\\n" "$PWD" "$REPO_TOP" "$HDLFORGE_PROJECT_FILE"'],
                                cwd=self.project, env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.splitlines(), [str(external), str(external), str(selected)])


if __name__ == "__main__":
    unittest.main()
