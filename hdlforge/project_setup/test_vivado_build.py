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

from vivado_build import execute, select_run
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
            "::hdlforge::initialize_design\n"
            "synth_design -top design -part test-part -directive AreaOptimized_high -no_lc -flatten_hierarchy none -verilog_define TEST=1\n"
            "write_checkpoint -force -noxdef design.dcp\n"
            "generate_parallel_reports -reports {{report_utilization -file design_utilization_synth.rpt}}\n")
        for name in ("impl_one", "impl_two"):
            template = Path(__file__).with_name("vivado_build_example_impl.tcl").read_text()
            (scripts / f"{name}.tcl").write_text(template)
        self.impl = dict(stage="impl", script="results/synth_one/impl_one.tcl", part="test-part", top="design",
                         ips=["core.xcix"], constraints=["static.xdc"])
        self.synth = dict(stage="synth", script="results/synth_one/run.tcl", part="test-part", top="design",
                          sources=["source $literal [brackets].sv"],
                          ips=[{"path": "core.xcix", "file_properties": {
                              "constraints/impl.xdc": {"used_in_synthesis": False}}}],
                          constraints=["static.xdc"], defines=["TEST=1"],
                          impl_runs={"impl_one": self.impl, "impl_two": {**self.impl, "script": "results/synth_one/impl_two.tcl"}})
        self.data = {"vivado": {"non_project": {"output_root": "results", "vivado_version": "2025.1",
                                                "runs": {"synth_one": self.synth}}}}
        self.project.write_text(json.dumps(self.data))
        self.executable = self.root / "fake_vivado"
        shutil.copyfile(Path(__file__).with_name("test_fixtures") / "vivado_stub.py", self.executable)
        self.executable.chmod(0o755)

    def build_synthesis(self) -> dict:
        config = select_run(self.project, 'synth_one')
        with contextlib.redirect_stdout(io.StringIO()):
            result = execute(self.project, config, str(self.executable))
        self.assertEqual(result, 0, (Path(config['output']) / 'logs/runme.log').read_text())
        return config

    def test_latest_uses_metadata_after_rename(self) -> None:
        first = self.build_synthesis()
        second = self.build_synthesis()
        older = Path(first['output']).with_name('_zzz_old')
        newer = Path(second['output']).with_name('_aaa_new')
        Path(first['output']).rename(older)
        Path(second['output']).rename(newer)
        self.assertEqual(find_run(newer.parent, 'latest'), newer)
        implementation = select_run(self.project, 'synth_one.impl_one')
        self.assertEqual(implementation['parent_run_id'], second['run_id'])
        self.assertEqual(Path(implementation['input_dcp']).parent.parent, newer)
        explicit = select_run(self.project, 'synth_one.impl_one', first['run_id'])
        self.assertEqual(Path(explicit['input_dcp']).parent.parent, older)

    def test_completion_uses_stable_ids(self) -> None:
        config = self.build_synthesis()
        choices = selector_choices(self.project, self.data, '')
        self.assertIn(f"synth_one.rerun.{config['run_id']}", choices)
        self.assertIn(f"synth_one.{config['run_id']}.impl_one.new", choices)

    def test_synthesis_preserves_implementation_scripts(self) -> None:
        config = self.build_synthesis()
        folder = Path(config['output'])
        saved = json.loads((folder / CONFIG).read_text())
        for name in ('impl_one', 'impl_two'):
            implementation_folder = folder / 'impl_runs' / name
            self.assertTrue(implementation_folder.is_dir())
            self.assertEqual(list(implementation_folder.iterdir()), [])
            self.assertFalse((folder / 'snapshot/scripts' / f'{name}.json').exists())
            definition = saved['implementation_configs'][name]
            self.assertEqual(definition['script'], f'{name}.tcl')
            source = self.root / 'results/synth_one' / f'{name}.tcl'
            snapshot = folder / 'snapshot/scripts' / f'{name}.tcl'
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
        config = select_run(self.project, 'synth_one.impl_one')
        self.assertEqual(Path(config['constraints'][0]['path']).read_text(), original)
        self.assertTrue(Path(config['script']).is_relative_to(Path(parent['output'])))
        refreshed = select_run(self.project, 'synth_one.impl_one', refresh_impl_inputs=True)
        self.assertEqual(Path(refreshed['constraints'][0]['path']).read_text(), '# live edit\n')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        saved = read_run(Path(config['output']))
        self.assertEqual(Path(saved['constraints'][0]['path']).read_text(), original)

    def test_attempts_share_one_json_and_preserve_previous_entries(self) -> None:
        parent = self.build_synthesis()
        folder = Path(parent['output'])
        before = json.loads((folder / CONFIG).read_text())
        identities = []
        for name in ('impl_one', 'impl_two'):
            config = select_run(self.project, f'synth_one.{name}')
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(execute(self.project, config, str(self.executable)), 0)
            identities.append(config['run_id'])
            self.assertFalse((Path(config['output']) / CONFIG).exists())
            self.assertEqual(read_run(Path(config['output']))['run_id'], config['run_id'])
        after = json.loads((folder / CONFIG).read_text())
        self.assertEqual(set(after['attempts']), set(identities))
        self.assertEqual(after['implementation_configs'], before['implementation_configs'])
        self.assertEqual(list(folder.rglob('run.json')), [folder / CONFIG])

    def test_concurrent_attempt_metadata_updates_are_not_lost(self) -> None:
        parent = self.build_synthesis()
        attempts = [select_run(self.project, 'synth_one.impl_one') for _ in range(8)]
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda config: write_run(Path(config['output']), config), attempts))
        document = json.loads((Path(parent['output']) / CONFIG).read_text())
        self.assertEqual(set(document['attempts']), {config['run_id'] for config in attempts})

    def test_synthesis_rerun_refuses_implementation_history(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        folder = Path(parent['output'])
        before = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        rerun = select_run(self.project, f"synth_one.rerun.{parent['run_id']}")
        with self.assertRaisesRegex(ValueError, 'implementation history'):
            execute(self.project, rerun, str(self.executable))
        after = {str(p.relative_to(folder)): p.read_bytes() for p in folder.rglob('*') if p.is_file()}
        self.assertEqual(before, after)

    def test_real_tcl_synth_then_impl_and_no_overwrite(self) -> None:
        #######################################################################
        # Execute the production driver against fake Vivado commands in Tcl.   #
        #######################################################################
        config = select_run(self.project, "synth_one")
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
        with self.assertRaises(FileExistsError):
            execute(self.project, config, str(self.executable))
        implementation = select_run(self.project, "synth_one.impl_one")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, implementation, str(self.executable)), 0)
        impl_output = Path(implementation["output"])
        stages = (impl_output / "logs/stages.tsv").read_text().splitlines()[1:]
        self.assertEqual([line.split("\t")[2] for line in stages if "\tdone\t" in line], STAGES["impl"])
        self.assertTrue((impl_output / "artifacts/design_postroute_physopt.dcp").is_file())
        self.assertTrue((impl_output / "artifacts/design.bit").is_file())
        self.assertTrue((impl_output / "artifacts/design_timing_summary_routed.rpt").is_file())
        logs = [impl_output / "logs" / name for name in ("runme.log", "vivado.log", "vivado.jou")]
        self.assertEqual(len({path.stat().st_ino for path in logs}), 3)
        self.assertTrue(all(path.stat().st_nlink == 1 and not path.is_symlink() for path in logs))

    def test_failed_stage_stops_and_preserves_checkpoint(self) -> None:
        self.build_synthesis()
        config = select_run(self.project, "synth_one.impl_one")
        with patch.dict(os.environ, {"FAIL_STAGE": "route_design"}), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 1)
        output = Path(config["output"])
        self.assertEqual((output / "logs/status").read_text().strip(), "failed")
        self.assertTrue((output / "artifacts/design_physopt.dcp").is_file())
        self.assertFalse((output / "artifacts/design.bit").exists())
        self.assertIn("injected route_design failure", (output / "logs/failure.txt").read_text())

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
        after["vivado"]["non_project"]["runs"].pop("ip_example")
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
        result = subprocess.run([str(wrapper), "--project", str(self.project), "--env-path", json.dumps([str(self.root)]), "vivado.build.synth.synth_one.continue"], cwd=wrapper.parent, env=env,
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("HDLFORGE_BUILD_COMPLETE", result.stdout)
        self.assertEqual(len(synthesis_timestamps(self.project, self.data, "synth_one", completed_only=True)), 1)


    def test_generated_json_is_relative_and_script_is_unchanged(self) -> None:
        config = self.build_synthesis()
        output = Path(config['output'])
        saved = json.loads((output / CONFIG).read_text())
        self.assertEqual(saved['output'], '../..')
        self.assertEqual(saved['script'], 'run.tcl')
        self.assertEqual(saved['work_dir'], '../../work')
        self.assertEqual((output / 'snapshot/scripts/run.tcl').read_bytes(), Path(config['script']).read_bytes())
        self.assertFalse((output / '.gitignore').exists())
        self.assertFalse((output / 'logs/config.tcl').exists())
        self.assertTrue(output.name.startswith('_'))
        self.assertIn('-source ' + str(output / 'snapshot/scripts/run.tcl'),
                      (output / 'logs/invocation.txt').read_text().replace("'", ""))

    def test_implementation_uses_parent_checkpoint_and_only_declared_inputs(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        self.assertEqual(output.parent, Path(parent['output']) / 'impl_runs' / 'impl_one')
        saved = read_run(output)
        self.assertEqual(saved['input_dcp'], str(Path(parent['output']) / 'artifacts/design.dcp'))
        self.assertFalse(list((output / 'snapshot/source').rglob('*.sv')))
        self.assertFalse(list((output / 'snapshot/source').rglob('*.dcp')))
        self.assertEqual(saved['parent_run_id'], parent['run_id'])

    def test_changed_checkpoint_refuses_rerun_without_changing_json(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        original = metadata_path(output).read_bytes()
        (Path(parent['output']) / 'artifacts/design.dcp').write_text('changed')
        with self.assertRaisesRegex(ValueError, 'checkpoint missing or changed'):
            select_run(self.project, f"synth_one.{parent['run_id']}.impl_one.rerun.{config['run_id']}")
        self.assertEqual(metadata_path(output).read_bytes(), original)

    def test_rerun_survives_renaming_both_parent_and_implementation(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        original = read_run(Path(config['output']))['run_id']
        renamed = Path(parent['output']).with_name('_renamed synthesis')
        Path(parent['output']).rename(renamed)
        child = renamed / 'impl_runs' / 'impl_one' / Path(config['output']).name
        moved = child.with_name('_renamed implementation')
        child.rename(moved)
        rerun = select_run(self.project, f"synth_one.{parent['run_id']}.impl_one.rerun.{config['run_id']}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, rerun, str(self.executable)), 0)
        self.assertEqual(read_run(moved)['run_id'], original)
        self.assertFalse((moved / CONFIG).exists())
        self.assertTrue((moved / 'artifacts/design.bit').is_file())

    def test_bitstream_regeneration_uses_parent_hash_and_original_epoch(self) -> None:
        parent = self.build_synthesis()
        implementation = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, implementation, str(self.executable)), 0)
        config = select_run(self.project, f"synth_one.{parent['run_id']}.impl_one.bitstream.{implementation['run_id']}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        self.assertTrue((output / 'artifacts/design.bit').is_file())
        self.assertEqual(read_run(output)['bitstream_epoch'], implementation['launch_epoch'])
        self.assertFalse(list((output / 'snapshot/source').rglob('*.dcp')))

    def test_ip_rerun_recreates_private_work_inputs(self) -> None:
        scripts = self.root / 'results/ip_one'
        scripts.mkdir()
        bootstrap = Path(__file__).with_name('vivado_build_example_ip.tcl').read_text().split('##############################################################################')[0]
        (scripts / 'run.tcl').write_text(bootstrap +
            '::hdlforge::initialize_design\nsynth_ip core\n'
            'set ip_path [dict get [lindex [dict get $::hdlforge_config ips] 0] path]\n'
            'set stream [open $ip_path w]\nputs $stream modified\nclose $stream\n')
        self.data['vivado']['non_project']['runs']['ip_one'] = dict(
            stage='ip', script='results/ip_one/run.tcl', part='test-part', ips=['core.xcix'])
        self.project.write_text(json.dumps(self.data))
        config = select_run(self.project, 'ip_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        frozen = Path(read_run(output)['ips'][0]['path'])
        self.assertEqual(frozen.read_bytes(), (self.root / 'core.xcix').read_bytes())
        rerun = select_run(self.project, f"ip_one.rerun.{config['run_id']}")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, rerun, str(self.executable)), 0)
        self.assertEqual(frozen.read_bytes(), (self.root / 'core.xcix').read_bytes())
        self.assertEqual((output / 'work/ip_sources/0/core.xcix').read_text(), 'modified\n')

    def test_incomplete_latest_never_falls_back(self) -> None:
        self.build_synthesis()
        newest = self.build_synthesis()
        (Path(newest['output']) / 'logs/status').write_text('failed\n')
        with self.assertRaisesRegex(ValueError, 'incomplete or unsuccessful'):
            select_run(self.project, 'synth_one.impl_one')

    def test_direct_tcl_launch_refuses_changed_checkpoint(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(execute(self.project, config, str(self.executable)), 0)
        output = Path(config['output'])
        (Path(parent['output']) / 'artifacts/design.dcp').write_text('changed')
        command = shlex.split((output / 'logs/invocation.txt').read_text())
        result = subprocess.run(command, cwd=self.root, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('Parent checkpoint changed', result.stderr)
        self.assertEqual((output / 'logs/status').read_text().strip(), 'failed')

    def test_only_declared_sibling_tcl_helpers_are_snapshotted(self) -> None:
        script = self.root / self.synth['script']
        helper = script.parent / 'helper.tcl'
        helper.write_text('set ::declared_helper_loaded 1\n')
        (script.parent / 'unrelated.tcl').write_text('error must_not_run\n')
        with script.open('a') as stream:
            stream.write('source [file join [file dirname [info script]] helper.tcl]\n')
        self.synth['input_files'] = [str(helper.relative_to(self.root))]
        self.project.write_text(json.dumps(self.data))
        config = self.build_synthesis()
        scripts = Path(config['output']) / 'snapshot/scripts'
        self.assertTrue((scripts / 'helper.tcl').is_file())
        self.assertFalse((scripts / 'unrelated.tcl').exists())

    def test_registry_finds_renamed_run_by_id(self) -> None:
        config = self.build_synthesis()
        output = Path(config['output'])
        renamed = output.with_name('_arbitrary label')
        output.rename(renamed)
        rows = BuildRegistry(Path(config['output_root'])).refresh()
        row = next(row for row in rows if row['run_id'] == config['run_id'])
        self.assertEqual(row['output'], str(renamed))
        self.assertEqual(row['run_log'], str(renamed / 'logs/runme.log'))

    def test_tracked_implementation_protects_entire_synthesis_cleanup(self) -> None:
        parent = self.build_synthesis()
        config = select_run(self.project, 'synth_one.impl_one')
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
