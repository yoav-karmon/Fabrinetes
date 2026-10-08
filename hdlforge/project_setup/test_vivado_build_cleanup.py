"""Recursive cleanup eligibility against real Git ignore rules and indexes."""

import contextlib
import fcntl
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from vivado_build_artifacts import cleanable, cleanup_orphan_locks, manage_artifacts
from vivado_build_layout import read_run, write_run, new_identity


class RecursiveCleanupTest(unittest.TestCase):
    def test_internal_run_lock_blocks_cleanup_then_is_deleted_with_attempt(self):
        lock = self.run / '.run.lock'
        with lock.open('a') as handle:
            fcntl.flock(handle, fcntl.LOCK_SH | fcntl.LOCK_NB)
            with patch('vivado_build_artifacts.selected_folders', return_value=[self.run]):
                manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts')
            self.assertTrue(self.run.exists())
        with patch('vivado_build_artifacts.selected_folders', return_value=[self.run]):
            manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts')
        self.assertFalse(self.run.exists())

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix='hdlforge cleanup ')
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        self.run = self.root / '_run'
        self.deep = self.run / 'impl' / '_attempt' / 'snapshot' / 'source'
        self.deep.mkdir(parents=True)
        self.rules = self.root / '.gitignore'
        self.rules.write_text('/_run/**\n!/_run/**/\n')
        self.payload = self.deep / 'design.dcp'
        self.payload.write_text('checkpoint')
        write_run(self.run, {**new_identity(), 'selector': 'synth'})
        self.project = self.root / 'sample.hdlforge.json'
        self.project.write_text(json.dumps({'vivado': {'non_project': {
            'output_root': '.', 'runs': {'synth': {'is_hdlforge_run': 'true', 'script': 'synth/run.tcl'}}}}}))

    def test_all_descendants_ignored_allows_cleanup(self) -> None:
        allowed, _ = cleanable(self.run)
        self.assertTrue(allowed)

    def test_one_deep_exception_protects_entire_run(self) -> None:
        with self.rules.open('a') as rules:
            rules.write('!/_run/impl/_attempt/snapshot/source/design.dcp\n')
        allowed, reason = cleanable(self.run)
        self.assertFalse(allowed)
        self.assertIn('not ignored', reason)
        self.assertTrue(self.payload.is_file())

    def test_forced_tracked_descendant_protects_entire_run(self) -> None:
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', str(self.payload)], check=True)
        allowed, reason = cleanable(self.run)
        self.assertFalse(allowed)
        self.assertIn('tracked by Git', reason)

    def test_missing_tracked_descendant_still_protects_run(self) -> None:
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', str(self.payload)], check=True)
        self.payload.unlink()
        self.assertFalse(cleanable(self.run)[0])

    def test_unreadable_descendant_does_not_authorize_cleanup(self) -> None:
        # Model the OS error even when tests execute with elevated permissions.
        with patch('vivado_build_artifacts.os.scandir', side_effect=PermissionError('cannot inspect')):
            with self.assertRaises(PermissionError):
                cleanable(self.run)

    def test_nested_repository_is_protected(self) -> None:
        subprocess.run(['git', 'init', '-q', str(self.deep)], check=True)
        self.assertFalse(cleanable(self.run)[0])

    def test_symlink_root_is_protected(self) -> None:
        alias = self.root / '_alias'
        alias.symlink_to(self.run, target_is_directory=True)
        self.assertFalse(cleanable(alias)[0])

    def test_hidden_descendant_exception_is_protected(self) -> None:
        hidden = self.deep / '.hidden'
        hidden.mkdir()
        (hidden / 'keep.txt').write_text('keep')
        with self.rules.open('a') as rules:
            rules.write('!keep.txt\n')
        self.assertFalse(cleanable(self.run)[0])

    def test_cleanup_preserves_whole_tree_for_one_visible_file(self) -> None:
        sibling = self.run / 'ignored.log'
        sibling.write_text('also preserve')
        with self.rules.open('a') as rules:
            rules.write('!design.dcp\n')
        with patch('vivado_build_artifacts.selected_folders', return_value=[self.run]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts'), 0)
        self.assertTrue(self.payload.is_file())
        self.assertTrue(sibling.is_file())

    def test_cleanup_deletes_tree_only_when_every_file_is_ignored(self) -> None:
        with self.rules.open('a') as rules:
            rules.write('*.run.lock\n')
        lock = self.run.parent / f'_{read_run(self.run)["run_id"]}.run.lock'
        with patch('vivado_build_artifacts.selected_folders', return_value=[self.run]), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts'), 0)
        self.assertFalse(self.run.exists())
        self.assertFalse(lock.exists())

    def orphan_lock(self) -> Path:
        with self.rules.open('a') as rules:
            rules.write('*.run.lock\n')
        lock = self.root / ('_' + 'a' * 32 + '.run.lock')
        lock.touch()
        return lock

    def test_cleanup_removes_preexisting_orphan(self) -> None:
        lock = self.orphan_lock()
        cleanup_orphan_locks(self.root)
        self.assertFalse(lock.exists())

    def test_cleanup_finds_orphan_without_any_remaining_attempt(self) -> None:
        lock = self.orphan_lock()
        container = self.root / 'synth'
        container.mkdir()
        moved = container / lock.name
        lock.rename(moved)
        manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts')
        self.assertFalse(moved.exists())

    def test_cleanup_preserves_running_attempt_and_its_lock(self) -> None:
        self.orphan_lock()
        lock = self.root / f'_{read_run(self.run)["run_id"]}.run.lock'
        with lock.open('w') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with patch('vivado_build_artifacts.selected_folders', return_value=[self.run]):
                manage_artifacts(self.project, 'synth', '--clean_ignore_artifacts')
        self.assertTrue(self.payload.is_file())
        self.assertTrue(lock.is_file())

    def test_cleanup_preserves_symlink_lock(self) -> None:
        lock = self.orphan_lock()
        lock.unlink()
        lock.symlink_to(self.payload)
        cleanup_orphan_locks(self.root)
        self.assertTrue(lock.is_symlink())
        self.assertTrue(self.payload.is_file())

    def test_dry_run_preserves_orphan(self) -> None:
        lock = self.orphan_lock()
        with contextlib.redirect_stdout(io.StringIO()) as output:
            cleanup_orphan_locks(self.root, dry_run=True)
        self.assertTrue(lock.exists())
        self.assertIn('Would delete orphan run lock', output.getvalue())

    def test_cleanup_preserves_held_orphan(self) -> None:
        lock = self.orphan_lock()
        with lock.open('r') as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            cleanup_orphan_locks(self.root)
            self.assertTrue(lock.exists())
        cleanup_orphan_locks(self.root)
        self.assertFalse(lock.exists())

    def test_cleanup_preserves_existing_attempt_lock(self) -> None:
        self.orphan_lock()
        lock = self.root / f'_{read_run(self.run)["run_id"]}.run.lock'
        lock.touch()
        cleanup_orphan_locks(self.root)
        self.assertTrue(lock.exists())

    def test_cleanup_preserves_tracked_orphan(self) -> None:
        lock = self.orphan_lock()
        subprocess.run(['git', '-C', str(self.root), 'add', '-f', str(lock)], check=True)
        cleanup_orphan_locks(self.root)
        self.assertTrue(lock.exists())

    def test_cleanup_preserves_nonignored_orphan(self) -> None:
        lock = self.orphan_lock()
        with self.rules.open('a') as rules:
            rules.write('!' + lock.name + '\n')
        cleanup_orphan_locks(self.root)
        self.assertTrue(lock.exists())

    def test_cleanup_preserves_locks_when_manifest_is_unreadable(self) -> None:
        lock = self.orphan_lock()
        (self.run / 'manifest.json').write_text('{broken')
        cleanup_orphan_locks(self.root)
        self.assertTrue(lock.exists())


if __name__ == '__main__':
    unittest.main()
