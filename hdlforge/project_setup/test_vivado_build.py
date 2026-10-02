"""Offline native build and completion contracts; never starts Vivado."""

import contextlib
from concurrent.futures import ThreadPoolExecutor
import io
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile

from vivado_build import execute, main, select_run
from vivado_build_artifacts import manage_artifacts
from vivado_build_config import synthesis_timestamps
from vivado_build_layout import CONFIG, metadata_path, find_run, read_run, write_run, new_identity
from vivado_build_selector import selector_choices
from vivado_build_registry import BuildRegistry
from vivado_build_tools import initialize_example, lint_project

STAGES = {"impl": ["init_design", "opt_design", "place_design", "phys_opt_design", "route_design",
                   "post_route_phys_opt_design", "write_bitstream"]}


class NativeBuildTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="hdlforge build ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / "sample.hdlforge.json"
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        (self.root / ".gitignore").write_text("_*/\n")
        for name in ("source $literal [brackets].sv", "static.xdc", "core.xcix"):
            (self.root / name).write_text("")
        with zipfile.ZipFile(self.root / "core.xcix", "w") as archive:
            archive.writestr("core/core.xci", "")
            archive.writestr("core/constraints/impl.xdc", "")
        scripts = self.root / "results/synth_one"
        scripts.mkdir(parents=True)
        bootstrap = Path(__file__).with_name("vivado_build_example_synth.tcl").read_text().split("##############################################################################")[0]
        (scripts / "run.tcl").write_text(bootstrap +
            "::hdlforge::design design test-part\n"
            "create_project -in_memory -part test-part\n"
            "read_verilog -sv [::hdlforge::source_path {source $literal [brackets].sv}]\n"
            "read_ip [::hdlforge::source_path core.xcix]\n"
            "set_property used_in_synthesis false /ip/constraints/impl.xdc\n"
            "read_xdc [::hdlforge::source_path static.xdc]\n"
            "synth_design -top design -part test-part -directive AreaOptimized_high -no_lc -flatten_hierarchy none -verilog_define TEST=1\n"
            "write_checkpoint -force -noxdef design.dcp\n"
            "generate_parallel_reports -reports {{report_utilization -file design_utilization_synth.rpt}}\n")
        for name in ("impl_one", "impl_two"):
            template = Path(__file__).with_name("vivado_build_example_impl.tcl").read_text()
            tail = template[template.index("link_design -top"):]
            (scripts / f"{name}.tcl").write_text(bootstrap +
                "set top design\nset part test-part\n::hdlforge::design $top $part\n"
                "create_project -in_memory -part $part\n"
                "add_files -quiet [dict get $::hdlforge_config input_dcp]\n"
                "read_ip [::hdlforge::source_path core.xcix]\n"
                "read_xdc [::hdlforge::source_path static.xdc]\n"
                "set ::ACTIVE_STEP init_design\n" + tail)
        self.impl = dict(script="results/synth_one/impl_one.tcl", sources=["core.xcix", "static.xdc"])
        self.synth = dict(script="results/synth_one/run.tcl",
                          sources=["source $literal [brackets].sv", "core.xcix", "static.xdc"],
                          impl_runs={"impl_one": self.impl, "impl_two": {**self.impl, "script": "results/synth_one/impl_two.tcl"}})
        self.data = {"vivado": {"non_project": {"output_root": "results", "vivado_version": "2025.1",
                                                "runs": {"synth_one": self.synth}}}}
        self.project.write_text(json.dumps(self.data))
        self.executable = self.root / "fake_vivado"
        shutil.copyfile(Path(__file__).with_name("test_fixtures") / "vivado_stub.py", self.executable)
        self.executable.chmod(0o755)

    def build_synthesis(self) -> dict:
        config = select_run(self.project, 'synth_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            result = execute(self.project, config, str(self.executable))
        self.assertEqual(result, 0, (Path(config['output']) / 'build.log').read_text())
        return config

    def test_latest_uses_metadata_after_rename(self) -> None:
        first = self.build_synthesis()
        second = self.build_synthesis()
        older = Path(first['output']).with_name('_zzz_old')
        newer = Path(second['output']).with_name('_aaa_new')
        Path(first['output']).rename(older)
        Path(second['output']).rename(newer)
        self.assertEqual(find_run(newer.parent, 'latest'), newer)
        implementation = select_run(self.project, 'synth_one.latest.impl_one.run')
        self.assertEqual(implementation['parent_run_id'], second['run_id'])
        self.assertEqual(Path(implementation['input_dcp']).parent.parent, newer)
        explicit = select_run(self.project, f"synth_one.{first['run_id']}.impl_one.run")
        self.assertEqual(Path(explicit['input_dcp']).parent.parent, older)

    def test_snapshots_preserve_repository_paths_for_sibling_inputs(self) -> None:
        # Put the project below the repo root and declare a sibling input.
        repository = self.root
        nested = repository / 'project'
        nested.mkdir()
        for path in list(repository.iterdir()):
            if path.name not in {'.git', '.gitignore', 'project'}:
                shutil.move(str(path), nested / path.name)
        self.root = nested
        self.project = nested / self.project.name
        self.executable = nested / self.executable.name
        shared = repository / 'shared'
        shared.mkdir()
        (shared / 'timing.xdc').write_text('# sibling constraint\n')
        self.synth['sources'].append('../shared/timing.xdc')
        self.impl['sources'].append('../shared/timing.xdc')
        self.project.write_text(json.dumps(self.data))
        parent = self.build_synthesis()
        snapshot = Path(parent['output']) / 'snapshot'
        self.assertTrue((snapshot / 'project' / self.project.name).is_file())
        self.assertTrue((snapshot / 'project/static.xdc').is_file())
        self.assertTrue((snapshot / 'shared/timing.xdc').is_file())
        self.assertFalse((snapshot / '_external').exists())
        child = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, child, str(self.executable)), 0)
        child_snapshot = Path(child['output']) / 'snapshot'
        self.assertTrue((child_snapshot / 'project/results/synth_one/impl_one.tcl').is_file())
        self.assertEqual((child_snapshot / 'shared/timing.xdc').read_text(), '# sibling constraint\n')

    def test_completion_uses_attempt_folder_names(self) -> None:
        config = self.build_synthesis()
        choices = selector_choices(self.project, self.data, '')
        self.assertIn(f"synth_one.{Path(config['output']).name}.status", choices)
        self.assertIn(f"synth_one.{Path(config['output']).name}.impl_one.run", choices)

    def test_discovery_lists_implementations_before_checkpoint_exists(self) -> None:
        parent = self.build_synthesis()
        folder = Path(parent['output'])
        invalid = folder.parent / 'notes'
        invalid.mkdir()
        (invalid / 'manifest.json').write_text('{broken')
        choices = selector_choices(self.project, self.data, '')
        self.assertFalse(any('notes' in value for value in choices))
        write_run(folder, {'status': 'failed', 'exit_code': 1})
        (folder / 'artifacts/design.dcp').unlink()
        choices = selector_choices(self.project, self.data, '')
        self.assertIn(f'synth_one.{folder.name}.status', choices)
        self.assertIn(f'synth_one.{folder.name}.impl_one.run', choices)
        with self.assertRaisesRegex(ValueError, 'Missing synthesis checkpoint'):
            select_run(self.project, f'synth_one.{folder.name}.impl_one.run')

    def test_status_and_stop_resolve_renamed_attempt_without_relaunch(self) -> None:
        parent = self.build_synthesis()
        output = Path(parent['output'])
        renamed = output.with_name('baseline')
        output.rename(renamed)
        with contextlib.redirect_stdout(io.StringIO()) as response:
            self.assertEqual(main(['--project', str(self.project), '--build', 'synth_one.baseline.status']), 0)
        self.assertEqual(json.loads(response.getvalue())['attempt'], 'baseline')
        with patch.object(BuildRegistry, 'stop_all') as stop:
            self.assertEqual(main(['--project', str(self.project), '--build', 'synth_one.baseline.stop']), 0)
            stop.assert_called_once_with(str(renamed))
        self.assertEqual(read_run(renamed)['run_id'], parent['run_id'])

    def test_saved_project_owns_implementation_definition(self) -> None:
        original = self.project.read_bytes()
        parent = self.build_synthesis()
        folder = Path(parent['output'])
        saved_project = folder / 'snapshot' / self.project.name
        self.assertEqual(saved_project.read_bytes(), original)
        # Live project changes must not remove or redirect the saved implementation.
        self.data['vivado']['non_project']['runs']['synth_one']['impl_runs'] = {}
        self.project.write_text(json.dumps(self.data))
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        self.assertEqual(config['project_file'], str(saved_project))
        self.assertEqual([entry['name'] for entry in config['sources']], ['core.xcix', 'static.xdc'])
        # The saved JSON controls selection, even when manifest indexes more inputs.
        document = json.loads(saved_project.read_text())
        document['vivado']['non_project']['runs']['synth_one']['impl_runs']['impl_one']['sources'] = ['static.xdc']
        saved_project.write_text(json.dumps(document))
        selected = select_run(self.project, 'synth_one.latest.impl_one.run')
        self.assertEqual([entry['name'] for entry in selected['sources']], ['static.xdc'])
        # Only the synthesis JSON selects the script; metadata does not override it.
        script = Path(selected['script'])
        renamed = script.with_name('timing_trial.tcl')
        script.rename(renamed)
        document['vivado']['non_project']['runs']['synth_one']['impl_runs']['impl_one']['script'] = 'results/synth_one/timing_trial.tcl'
        saved_project.write_text(json.dumps(document))
        self.assertEqual(select_run(self.project, 'synth_one.latest.impl_one.run')['script'], str(renamed))
        renamed.unlink()
        (self.root / 'results/synth_one/timing_trial.tcl').write_text('# live source must never be used\n')
        with self.assertRaisesRegex(ValueError, 'Missing prepared implementation script'):
            select_run(self.project, 'synth_one.latest.impl_one.run')

    def test_implementation_cannot_borrow_a_siblings_snapshot(self) -> None:
        # Remove one implementation's indexed input while its sibling retains it.
        parent = self.build_synthesis()
        folder = Path(parent['output'])
        saved = read_run(folder)
        saved['implementation_configs']['impl_one']['sources'] = []
        write_run(folder, saved)
        with self.assertRaisesRegex(ValueError, 'absent from its prepared snapshot'):
            select_run(self.project, 'synth_one.latest.impl_one.run')
        self.assertTrue(select_run(self.project, 'synth_one.latest.impl_two.run')['sources'])

    def test_synthesis_preserves_implementation_scripts(self) -> None:
        config = self.build_synthesis()
        folder = Path(config['output'])
        saved = json.loads((folder / CONFIG).read_text())
        for name in ('impl_one', 'impl_two'):
            implementation_folder = folder / 'impl_runs' / name
            self.assertTrue(implementation_folder.is_dir())
            self.assertTrue((implementation_folder / 'snapshot').is_dir())
            for child in ('work', 'artifacts'):
                self.assertFalse((implementation_folder / child).exists())
                self.assertFalse((folder.parent / child).exists())
                self.assertTrue((folder / child).is_dir())
            self.assertEqual((implementation_folder / 'snapshot' / self.project.name).read_bytes(), self.project.read_bytes())
            self.assertFalse((folder / 'snapshot/scripts' / f'{name}.json').exists())
            definition = saved['implementation_configs'][name]
            self.assertEqual(definition['script'], f'impl_runs/{name}/snapshot/results/synth_one/{name}.tcl')
            source = self.root / 'results/synth_one' / f'{name}.tcl'
            snapshot = folder / 'snapshot/results/synth_one' / f'{name}.tcl'
            self.assertEqual(snapshot.read_bytes(), source.read_bytes())
            source.write_text('# changed after synthesis\n')
            self.assertNotEqual(snapshot.read_bytes(), source.read_bytes())
        renamed = folder.with_name('_renamed')
        folder.rename(renamed)
        for definition in read_run(renamed)['implementation_configs'].values():
            self.assertTrue(Path(definition['script']).is_file())

    def test_implementation_defaults_to_frozen_declared_inputs(self) -> None:
        original = '# original implementation constraint\n'
        (self.root / 'static.xdc').write_text(original)
        parent = self.build_synthesis()
        (self.root / 'static.xdc').write_text('# live edit\n')
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        self.assertEqual(Path(config['sources'][1]['path']).read_text(), original)
        self.assertTrue(Path(config['script']).is_relative_to(Path(parent['output'])))
        self.assertTrue(Path(config['sources'][1]['path']).is_relative_to(Path(parent['output']) / 'impl_runs/impl_one/snapshot'))
        self.assertFalse((Path(parent['output']) / 'impl_runs/impl_one/constraints').exists())
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        saved = read_run(Path(config['output']))
        self.assertEqual(Path(saved['sources'][1]['path']).read_text(), original)

    def test_attempts_have_independent_manifests_preserving_parent(self) -> None:
        parent = self.build_synthesis()
        folder = Path(parent['output'])
        before = json.loads((folder / CONFIG).read_text())
        identities = []
        for name in ('impl_one', 'impl_two'):
            config = select_run(self.project, f'synth_one.latest.{name}.run')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(execute(self.project, config, str(self.executable)), 0)
            identities.append(config['run_id'])
            self.assertTrue((Path(config['output']) / CONFIG).exists())
            self.assertEqual(read_run(Path(config['output']))['run_id'], config['run_id'])
        after = json.loads((folder / CONFIG).read_text())
        self.assertEqual(after, before)
        self.assertEqual(after['implementation_configs'], before['implementation_configs'])
        self.assertEqual(len(list(folder.rglob('manifest.json'))), 3)

    def test_concurrent_attempt_metadata_updates_are_not_lost(self) -> None:
        parent = self.build_synthesis()
        attempts = [select_run(self.project, 'synth_one.latest.impl_one.run') for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda config: write_run(Path(config['output']), config), attempts))
        self.assertEqual({read_run(Path(c['output']))['run_id'] for c in attempts},
                         {c['run_id'] for c in attempts})

    def test_completed_attempt_refuses_overwrite(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        folder = Path(parent['output'])
        before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        with self.assertRaisesRegex(ValueError, 'Attempt already exists'):
            execute(self.project, parent, str(self.executable))
        after = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_real_tcl_synth_then_impl_and_no_overwrite(self) -> None:
        #######################################################################
        # Execute the production driver against fake Vivado commands in Tcl.   #
        #######################################################################
        config = select_run(self.project, "synth_one.run")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config["output"])
        self.assertTrue((output / "artifacts/design.dcp").is_file())
        self.assertTrue((output / "artifacts/design_utilization_synth.rpt").is_file())
        calls = (output / "work/calls.log").read_text()
        self.assertIn("-directive AreaOptimized_high -no_lc -flatten_hierarchy none", calls)
        self.assertIn("-verilog_define TEST=1", calls)
        self.assertIn("source $literal [brackets].sv", calls)
        self.assertIn("set_property used_in_synthesis false /ip/constraints/impl.xdc", calls)
        with self.assertRaisesRegex(ValueError, "Attempt already exists"):
            execute(self.project, config, str(self.executable))
        implementation = select_run(self.project, "synth_one.latest.impl_one.run")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, implementation, str(self.executable)), 0)
        impl_output = Path(implementation["output"])
        stages = read_run(impl_output)["stages"]
        self.assertEqual([entry["stage"] for entry in stages if entry["event"] == "done"], STAGES["impl"])
        self.assertTrue((impl_output / "artifacts/design_postroute_physopt.dcp").is_file())
        self.assertTrue((impl_output / "artifacts/design.bit").is_file())
        self.assertTrue((impl_output / "artifacts/design_timing_summary_routed.rpt").is_file())
        self.assertTrue((impl_output / 'build.log').is_file())
        self.assertFalse((impl_output / 'logs').exists())
        self.assertNotIn('attempts', read_run(output))

    def test_failed_stage_stops_and_preserves_checkpoint(self) -> None:
        self.build_synthesis()
        config = select_run(self.project, "synth_one.latest.impl_one.run")
        with patch.dict(os.environ, {"FAIL_STAGE": "route_design"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 1)
        output = Path(config["output"])
        self.assertEqual(read_run(output)["status"], "failed")
        self.assertTrue((output / "artifacts/design_physopt.dcp").is_file())
        self.assertFalse((output / "artifacts/design.bit").exists())
        self.assertIn("injected route_design failure", read_run(output)["failure"])

    def test_invalid_inputs_do_not_create_output(self) -> None:
        (self.root / "static.xdc").unlink()
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one.run")
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_empty_artifacts_and_unknown_runs(self) -> None:
        self.assertEqual(synthesis_timestamps(self.project, self.data, "synth_one.impl_one"), [])
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one.latest.impl_one.run")
        with self.assertRaises(ValueError):
            select_run(self.project, "unknown")

    def test_example_injection_preserves_existing_settings(self) -> None:
        before = json.loads(self.project.read_text())
        initialize_example(self.project)
        after = json.loads(self.project.read_text())
        after["vivado"]["non_project"]["runs"].pop("ip_example")
        example = after["vivado"]["non_project"]["runs"].pop("synth_example")
        self.assertEqual(after, before)
        self.assertIn("impl_example", example["impl_runs"])
        self.assertNotIn("steps", example["impl_runs"]["impl_example"])
        self.assertTrue(all(isinstance(path, str) for path in example["sources"]))
        self.assertNotIn("part", example)
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

    def test_lint_reports_invalid_ip_archive(self) -> None:
        (self.root / "core.xcix").write_text("invalid archive")
        self.assertTrue(any("invalid XCIX" in error for error in lint_project(self.project)))

    def test_json_steps_are_rejected_before_output(self) -> None:
        self.synth["steps"] = {"synth_design": {}}
        self.project.write_text(json.dumps(self.data))
        with self.assertRaises(ValueError):
            select_run(self.project, "synth_one.run")
        self.assertFalse((self.root / "results/synth_one/artifacts").exists())

    def test_design_settings_in_json_are_rejected(self) -> None:
        for field in ("stage", "part", "top", "defines", "parameters", "ips",
                      "constraints", "input_files", "project_properties"):
            with self.subTest(field=field):
                data = json.loads(self.project.read_text())
                data["vivado"]["non_project"]["runs"]["synth_one"][field] = "obsolete"
                self.project.write_text(json.dumps(data))
                with self.assertRaisesRegex(ValueError, "design settings belong in run.tcl"):
                    select_run(self.project, "synth_one.run")
                self.project.write_text(json.dumps(self.data))

    def test_implementation_tcl_identity_must_match_parent(self) -> None:
        script = self.root / self.impl["script"]
        script.write_text(script.read_text().replace("set top design", "set top different"))
        self.build_synthesis()
        config = select_run(self.project, "synth_one.latest.impl_one.run")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 1)
        self.assertIn("Implementation top differs", read_run(Path(config["output"]))["failure"])

    def test_tcl_identity_is_recorded_after_build(self) -> None:
        self.assertNotIn("top", self.synth)
        config = self.build_synthesis()
        saved = read_run(Path(config["output"]))
        self.assertEqual((saved["top"], saved["part"]), ("design", "test-part"))
        self.assertEqual(saved["stage"], "synth")

    def test_missing_tcl_identity_is_a_failed_run(self) -> None:
        script = self.root / self.synth["script"]
        script.write_text(script.read_text().replace("::hdlforge::design design test-part\n", ""))
        config = select_run(self.project, "synth_one.run")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 1)
        self.assertIn("Run Tcl must declare its identity", read_run(Path(config["output"]))["failure"])
        self.assertEqual(read_run(Path(config["output"]))["status"], "failed")
        self.assertEqual(read_run(Path(config["output"]))["exit_code"], 1)

    def test_public_cli_uses_selected_json_from_another_directory(self) -> None:
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        executable = self.root / "vivado"
        shutil.copyfile(self.executable, executable)
        executable.chmod(0o755)
        wrapper = Path(__file__).with_name("hdlforge")
        env = {**os.environ, "PATH": str(self.root) + os.pathsep + os.environ["PATH"]}
        env.pop("HDLFORGE_CALLED", None)
        self.data["settings"] = {"env": {"test-host": {"test-user": {
            "path": os.environ["PATH"].split(os.pathsep), "path_import": [],
            "pythonpath": os.environ.get("PYTHONPATH", "").split(os.pathsep),
            "pythonpath_import": [], "variables": {}, "variables_import": []}}}}
        self.data["settings"]["env"]["test-host"]["test-user"]["pythonpath"] = [
            p for p in self.data["settings"]["env"]["test-host"]["test-user"]["pythonpath"] if p]
        self.project.write_text(json.dumps(self.data))
        env.update(HOST_MACHINE="test-host", HDLFORGE_HOST_USER="test-user")
        result = subprocess.run([str(wrapper), "--project", str(self.project), "--env-path", json.dumps([str(self.root)]), "vivado.build.synth_one.run", "--auto_impl", "impl_one"], cwd=self.root, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout.count("HDLFORGE_BUILD_COMPLETE"), 2)
        self.assertEqual(len(synthesis_timestamps(self.project, self.data, "synth_one", completed_only=True)), 1)
        parent = find_run(self.root / 'results/synth_one', 'latest')
        child = find_run(parent / 'impl_runs/impl_one', 'latest')
        self.assertEqual(read_run(child)['status'], 'complete')
        self.assertFalse((self.root / 'results/_launch_logs').exists())
        registry = json.loads((self.root / 'results/_run_registry.json').read_text())
        self.assertTrue(all(isinstance(location, str) for location in registry['runs'].values()))


    def test_generated_json_is_relative_and_script_is_unchanged(self) -> None:
        config = self.build_synthesis()
        output = Path(config['output'])
        saved = json.loads((output / CONFIG).read_text())
        self.assertEqual(saved['output'], '.')
        self.assertEqual(saved['script'], 'snapshot/results/synth_one/run.tcl')
        self.assertEqual(saved['work_dir'], 'work')
        self.assertTrue((output / 'snapshot/static.xdc').is_file())
        self.assertFalse((output / 'snapshot/scripts').exists())
        self.assertFalse((output / 'snapshot/source').exists())
        self.assertEqual((output / 'snapshot/results/synth_one/run.tcl').read_bytes(), Path(config['script']).read_bytes())
        self.assertFalse((output / '.gitignore').exists())
        self.assertFalse((output / 'logs/config.tcl').exists())
        self.assertTrue(output.name.startswith('_'))
        self.assertIn('-source ' + str(output / 'snapshot/results/synth_one/run.tcl'),
                      shlex.join(saved['command']).replace("'", ""))

    def test_implementation_uses_parent_checkpoint_and_only_declared_inputs(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        self.assertEqual(output.parent, Path(parent['output']) / 'impl_runs' / 'impl_one')
        saved = read_run(output)
        self.assertEqual(saved['input_dcp'], str(Path(parent['output']) / 'artifacts/design.dcp'))
        self.assertEqual(Path(saved['script']), output / 'snapshot/results/synth_one/impl_one.tcl')
        self.assertIn(str(output / 'snapshot/results/synth_one/impl_one.tcl'), saved['command'])
        self.assertFalse(list((output / 'snapshot').rglob('*.sv')))
        self.assertFalse(list((output / 'snapshot').rglob('*.dcp')))
        self.assertEqual(saved['parent_run_id'], parent['run_id'])

    def test_selected_checkpoint_change_refuses_new_attempt(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        (Path(parent['output']) / 'artifacts/design.dcp').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'checkpoint missing or changed'):
            execute(self.project, config, str(self.executable))

    def test_renamed_parent_and_attempt_keep_identity_and_inputs(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        renamed = Path(parent['output']).with_name('timing_trial_1')
        Path(parent['output']).rename(renamed)
        child = renamed / 'impl_runs' / 'impl_one' / Path(config['output']).name
        moved = child.with_name('best_placement')
        child.rename(moved)
        saved = read_run(moved)
        self.assertEqual(saved['run_id'], config['run_id'])
        self.assertTrue(Path(saved['input_dcp']).is_file())
        self.assertTrue(Path(saved['script']).is_file())
        choices = selector_choices(self.project, self.data, '')
        self.assertIn('synth_one.timing_trial_1.impl_one.best_placement.status', choices)
        self.assertNotIn(parent['run_id'], ' '.join(choices))

    def test_editable_template_is_frozen_for_each_fresh_attempt(self) -> None:
        parent = self.build_synthesis()
        editable = Path(read_run(Path(parent['output']))['implementation_configs']['impl_one']['script'])
        constraints = Path(read_run(Path(parent['output']))['implementation_configs']['impl_one']['sources'][1]['path'])
        configs = []
        for marker in ('first settings', 'second settings'):
            with editable.open('a') as stream:
                stream.write('\n# ' + marker + '\n')
            constraints.write_text('# ' + marker + '\n')
            config = select_run(self.project, 'synth_one.latest.impl_one.run')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(execute(self.project, config, str(self.executable)), 0)
            configs.append(read_run(Path(config['output'])))
        self.assertNotEqual(configs[0]['run_id'], configs[1]['run_id'])
        self.assertNotIn('second settings', Path(configs[0]['script']).read_text())
        self.assertIn('second settings', Path(configs[1]['script']).read_text())
        self.assertIn('first settings', Path(configs[0]['sources'][1]['path']).read_text())
        self.assertNotIn('second settings', Path(configs[0]['sources'][1]['path']).read_text())
        self.assertIn('second settings', Path(configs[1]['sources'][1]['path']).read_text())

    def test_bitstream_regeneration_uses_parent_hash_and_original_epoch(self) -> None:
        parent = self.build_synthesis()
        implementation = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, implementation, str(self.executable)), 0)
        config = select_run(self.project, f"synth_one.{parent['run_id']}.impl_one.bitstream.{implementation['run_id']}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        self.assertTrue((output / 'artifacts/design.bit').is_file())
        self.assertEqual(read_run(output)['bitstream_epoch'], implementation['launch_epoch'])
        self.assertFalse(list((output / 'snapshot').rglob('*.dcp')))

    def test_fresh_ip_attempts_have_private_work_inputs(self) -> None:
        scripts = self.root / 'results/ip_one'
        scripts.mkdir()
        bootstrap = Path(__file__).with_name('vivado_build_example_ip.tcl').read_text().split('##############################################################################')[0]
        (scripts / 'run.tcl').write_text(bootstrap +
            '::hdlforge::design ip test-part\ncreate_project -in_memory -part test-part\nsynth_ip core\n'
            'set ip_path [dict get [lindex [dict get $::hdlforge_config sources] 0] path]\n'
            'set stream [open $ip_path w]\nputs $stream modified\nclose $stream\n')
        self.data['vivado']['non_project']['runs']['ip_one'] = dict(
            kind='ip', script='results/ip_one/run.tcl', sources=['core.xcix'])
        self.project.write_text(json.dumps(self.data))
        config = select_run(self.project, 'ip_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        frozen = Path(read_run(output)['sources'][0]['path'])
        self.assertEqual(frozen.read_bytes(), (self.root / 'core.xcix').read_bytes())
        rerun = select_run(self.project, 'ip_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, rerun, str(self.executable)), 0)
        self.assertEqual(frozen.read_bytes(), (self.root / 'core.xcix').read_bytes())
        self.assertEqual((output / 'work/ip_sources/0/core.xcix').read_text(), 'modified\n')

    def test_incomplete_latest_never_falls_back(self) -> None:
        self.build_synthesis()
        newest = self.build_synthesis()
        write_run(Path(newest['output']), {'status': 'failed'})
        (Path(newest['output']) / 'artifacts/design.dcp').unlink()
        with self.assertRaisesRegex(ValueError, 'Missing synthesis checkpoint'):
            select_run(self.project, 'synth_one.latest.impl_one.run')

    def test_direct_tcl_launch_refuses_changed_checkpoint(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        (Path(parent['output']) / 'artifacts/design.dcp').write_text('changed')
        command = read_run(output)['command']
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Parent checkpoint changed', result.stderr)
        self.assertEqual(read_run(output)['status'], 'complete')  # Direct Tcl cannot rewrite the manifest.

    def test_only_declared_sibling_tcl_helpers_are_snapshotted(self) -> None:
        script = self.root / self.synth['script']
        helper = script.parent / 'helper.tcl'
        helper.write_text('set ::declared_helper_loaded 1\n')
        (script.parent / 'unrelated.tcl').write_text('error must_not_run\n')
        with script.open('a') as stream:
            stream.write('source [::hdlforge::source_path {results/synth_one/helper.tcl}]\n')
        self.synth['sources'].append(str(helper.relative_to(self.root)))
        self.project.write_text(json.dumps(self.data))
        config = self.build_synthesis()
        scripts = Path(config['output']) / 'snapshot/results/synth_one'
        self.assertTrue(list((Path(config['output']) / 'snapshot').rglob('helper.tcl')))
        self.assertFalse((scripts / 'unrelated.tcl').exists())

    def test_registry_finds_renamed_run_by_id(self) -> None:
        config = self.build_synthesis()
        output = Path(config['output'])
        renamed = output.with_name('_arbitrary label')
        output.rename(renamed)
        rows = BuildRegistry(Path(config['output_root'])).refresh()
        row = next(row for row in rows if row['run_id'] == config['run_id'])
        self.assertEqual(row['output'], str(renamed))
        self.assertEqual(row['run_log'], str(renamed / 'build.log'))

    def test_tracked_implementation_protects_entire_synthesis_cleanup(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.latest.impl_one.run')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        bitstream = Path(config['output']) / 'artifacts/design.bit'
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', str(bitstream)], check=True)
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manage_artifacts(self.project, 'synth_one', '--clean_ignore_artifacts'), 0)
        self.assertTrue(bitstream.is_file())
        self.assertTrue((Path(parent['output']) / 'artifacts/design.dcp').is_file())


if __name__ == '__main__':
    unittest.main()
