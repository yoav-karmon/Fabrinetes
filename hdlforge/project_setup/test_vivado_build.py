"""Offline native build and completion contracts; never starts Vivado."""

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from hdlforge_completion_backend import complete_classic
from vivado_build import execute, select_run
from vivado_build_config import synthesis_timestamps
from vivado_build_tools import initialize_example, lint_project

STAGES = {"impl": ["init_design", "opt_design", "place_design", "phys_opt_design", "route_design",
                   "post_route_phys_opt_design", "write_bitstream"]}


class NativeBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hdlforge build ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "sample.hdlforge.json"
        for name in ("source $literal [brackets].sv", "static.xdc", "core.xcix"):
            (self.root / name).write_text("")
        with zipfile.ZipFile(self.root / "core.xcix", "w") as archive:
            archive.writestr("core/core.xci", "")
            archive.writestr("core/constraints/impl.xdc", "")
        scripts = self.root / "results/synth_one"
        scripts.mkdir(parents=True)
        (scripts / "run.tcl").write_text(
            "::hdlforge::initialize_design\n"
            "synth_design -top design -part test-part -directive AreaOptimized_high -no_lc -flatten_hierarchy none -verilog_define TEST=1\n"
            "write_checkpoint -force -noxdef design.dcp\n"
            "generate_parallel_reports -reports {{report_utilization -file design_utilization_synth.rpt}}\n")
        for name in ("impl_one", "impl_two"):
            (scripts / name).mkdir()
            template = Path(__file__).with_name("vivado_build_example_impl.tcl").read_text()
            (scripts / name / "run.tcl").write_text(template)
        self.impl = dict(stage="impl", script="results/synth_one/impl_one/run.tcl", part="test-part", top="design",
                         ips=["core.xcix"], constraints=["static.xdc"])
        self.synth = dict(stage="synth", script="results/synth_one/run.tcl", part="test-part", top="design",
                          sources=["source $literal [brackets].sv"],
                          ips=[{"path": "core.xcix", "file_properties": {
                              "constraints/impl.xdc": {"used_in_synthesis": False}}}],
                          constraints=["static.xdc"], defines=["TEST=1"],
                          impl_runs={"impl_one": self.impl, "impl_two": {**self.impl, "script": "results/synth_one/impl_two/run.tcl"}})
        self.data = {"vivado": {"non_project": {"output_root": "results", "vivado_version": "2025.1",
                                                "runs": {"synth_one": self.synth}}}}
        self.project.write_text(json.dumps(self.data))
        self.executable = self.root / "fake_vivado"
        shutil.copyfile(Path(__file__).with_name("test_fixtures") / "vivado_stub.py", self.executable)
        self.executable.chmod(0o755)

    def saved_synth(self, stamp: str, status: str = "complete", checkpoint: bool = True) -> Path:
        directory = self.root / "results/synth_one/artifacts" / stamp
        (directory / "info").mkdir(parents=True)
        (directory / "info/status").write_text(status)
        if checkpoint:
            (directory / "checkpoints").mkdir()
            (directory / "checkpoints/design.dcp").write_text("checkpoint")
        return directory

    def test_latest_complete_and_explicit_selection(self) -> None:
        self.saved_synth("2026-09-28T120000Z")
        self.saved_synth("2026-09-28T130000Z")
        self.saved_synth("2026-09-28T140000Z", "running:synth_design")
        self.saved_synth("2026-09-28T150000Z", checkpoint=False)
        config = select_run(self.project, "synth_one.impl_one")
        self.assertEqual(config["timestamp"], "2026-09-28T130000Z")
        self.assertTrue(config["output"].endswith("2026-09-28T130000Z/impl_runs/impl_one"))
        explicit = select_run(self.project, "synth_one.impl_one", "2026-09-28T120000Z")
        self.assertIn("2026-09-28T120000Z/checkpoints/design.dcp", explicit["input_dcp"])
        for invalid in ("../escape", "2026-09-28T140000Z", "2026-09-28T150000Z"):
            with self.assertRaises(ValueError):
                select_run(self.project, "synth_one.impl_one", invalid)
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one", "2026-09-28T120000Z")

    def test_dynamic_completion_chain_and_prefix(self) -> None:
        self.saved_synth("2026-09-28T120000Z")
        self.saved_synth("2026-09-28T140000Z", "failed")
        tokens = ["--project", str(self.project), "--tool", "vivado", "--build"]
        self.assertEqual(complete_classic(tokens, "synth_one.", Path("/tmp")).completions,
                         ["synth_one.impl_one", "synth_one.impl_two"])
        self.assertIn("--synth_timestamp", complete_classic(tokens + ["synth_one.impl_one"], "", self.root).completions)
        self.assertNotIn("--synth_timestamp", complete_classic(tokens + ["synth_one"], "", self.root).completions)
        arguments = tokens + ["synth_one.impl_one", "--synth_timestamp"]
        self.assertEqual(complete_classic(arguments, "2026-09-28T1", self.root).completions,
                         ["2026-09-28T120000Z", "2026-09-28T140000Z"])
        self.assertEqual(complete_classic(arguments, "2026-09-28T12", self.root).completions,
                         ["2026-09-28T120000Z"])
        self.assertNotIn("--synth_timestamp", complete_classic(arguments + ["2026-09-28T120000Z"], "", self.root).completions)

    def test_real_tcl_synth_then_impl_and_no_overwrite(self) -> None:
        #######################################################################
        # Execute the production driver against fake Vivado commands in Tcl.   #
        #######################################################################
        config = select_run(self.project, "synth_one")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config["output"])
        self.assertTrue((output / "checkpoints/design.dcp").is_file())
        self.assertTrue((output / "reports/design_utilization_synth.rpt").is_file())
        calls = (output / "work/calls.log").read_text()
        self.assertIn("-directive AreaOptimized_high -no_lc -flatten_hierarchy none", calls)
        self.assertIn("-verilog_define TEST=1", calls)
        self.assertIn("source $literal [brackets].sv", calls)
        self.assertIn("set_property used_in_synthesis 0 /ip/constraints/impl.xdc", calls)
        with self.assertRaises(FileExistsError):
            execute(self.project, config, str(self.executable))
        implementation = select_run(self.project, "synth_one.impl_one")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, implementation, str(self.executable)), 0)
        impl_output = Path(implementation["output"])
        stages = (impl_output / "info/stages.tsv").read_text().splitlines()[1:]
        self.assertEqual([line.split("\t")[2] for line in stages if "\tdone\t" in line], STAGES["impl"])
        self.assertTrue((impl_output / "checkpoints/design_postroute_physopt.dcp").is_file())
        self.assertTrue((impl_output / "bitstream/design.bit").is_file())
        self.assertTrue((impl_output / "reports/design_timing_summary_routed.rpt").is_file())
        logs = [impl_output / name for name in ("runme.log", "vivado.log", "vivado.jou")]
        self.assertEqual(len({path.stat().st_ino for path in logs}), 3)
        self.assertTrue(all(path.stat().st_nlink == 1 and not path.is_symlink() for path in logs))

    def test_failed_stage_stops_and_preserves_checkpoint(self) -> None:
        self.saved_synth("2026-09-28T120000Z")
        config = select_run(self.project, "synth_one.impl_one")
        with patch.dict(os.environ, {"FAIL_STAGE": "route_design"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 1)
        output = Path(config["output"])
        self.assertEqual((output / "info/status").read_text().strip(), "failed")
        self.assertTrue((output / "checkpoints/design_physopt.dcp").is_file())
        self.assertFalse((output / "bitstream/design.bit").exists())
        self.assertIn("injected route_design failure", (output / "info/failure.txt").read_text())

    def test_invalid_inputs_do_not_create_output(self) -> None:
        (self.root / "static.xdc").unlink()
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one")
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_empty_artifacts_and_unknown_runs(self) -> None:
        self.assertEqual(synthesis_timestamps(self.project, self.data, "synth_one.impl_one"), [])
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one.impl_one")
        with self.assertRaises(ValueError):
            select_run(self.project, "unknown")

    def test_example_injection_preserves_existing_settings(self) -> None:
        before = json.loads(self.project.read_text())
        initialize_example(self.project)
        after = json.loads(self.project.read_text())
        example = after["vivado"]["non_project"]["runs"].pop("synth_example")
        self.assertEqual(after, before)
        self.assertIn("impl_example", example["impl_runs"])
        self.assertNotIn("steps", example["impl_runs"]["impl_example"])
        self.assertIn("file_properties", example["ips"][0])
        contents = self.project.read_text()
        with self.assertRaises(ValueError):
            initialize_example(self.project)
        self.assertEqual(self.project.read_text(), contents)
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_lint_collects_missing_paths_and_scoped_ip_files(self) -> None:
        self.assertEqual(lint_project(self.project), [])
        (self.root / "static.xdc").unlink()
        (self.root / "source $literal [brackets].sv").unlink()
        errors = lint_project(self.project)
        self.assertTrue(any("static.xdc" in error for error in errors))
        self.assertTrue(any("source $literal" in error for error in errors))
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_lint_reports_missing_ip_archive_member(self) -> None:
        self.synth["ips"][0]["file_properties"]["missing.xdc"] = {"used_in_synthesis": False}
        self.project.write_text(json.dumps(self.data))
        self.assertTrue(any("missing IP member missing.xdc" in error for error in lint_project(self.project)))

    def test_json_steps_are_rejected_before_output(self) -> None:
        self.synth["steps"] = {"synth_design": {}}
        self.project.write_text(json.dumps(self.data))
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one")
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_public_cli_uses_selected_json_from_another_directory(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        executable = self.root / "vivado"
        shutil.copyfile(self.executable, executable)
        executable.chmod(0o755)
        wrapper = Path(__file__).with_name("hdlforge")
        env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"]}
        result = subprocess.run([str(wrapper), "--project", str(self.project), "--env-path", json.dumps([str(self.root)]), "--tool", "vivado",
                                 "--build", "synth_one"], cwd=wrapper.parent, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("HDLFORGE_BUILD_COMPLETE", result.stdout)
        self.assertEqual(len(synthesis_timestamps(self.project, self.data, "synth_one", completed_only=True)), 1)

    def test_bash_tab_tab_after_implementation_and_timestamp_flag(self) -> None:
        self.saved_synth("2026-09-28T120000Z")
        runtime = Path(__file__).with_name("hdlforge_completion_runtime.bash")
        script = '''
source "$1"
COMP_WORDS=(hdlforge --project "$2" --tool vivado --build synth_one.impl_one)
if [[ "$3" == timestamps ]]; then COMP_WORDS+=(--synth_timestamp); fi
COMP_WORDS+=("")
COMP_CWORD=$((${#COMP_WORDS[@]} - 1))
COMP_TYPE=63
_hdlforge_runtime_complete
printf '%s\\n' "${COMPREPLY[@]}"
'''
        for mode, expected in (("flags", "--synth_timestamp"), ("timestamps", "2026-09-28T120000Z")):
            result = subprocess.run(["bash", "--noprofile", "--norc", "-c", script, "test", str(runtime),
                                     str(self.project), mode], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(expected, result.stdout)


if __name__ == "__main__":
    unittest.main()
