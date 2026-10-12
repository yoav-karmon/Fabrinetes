"""Verify immutable shared builds and exclusive simulation outputs."""

import fcntl
import hashlib
import tempfile
import unittest
from pathlib import Path

from verilator_build_guard import VerilatorBuildGuard


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.build = self.root / 'build'
        self.build.mkdir()
        self.project = self.root / 'test.json'
        self.project.write_text('{}')
        self.source = self.root / 'top.sv'
        self.source.write_text('module top; endmodule')
        self.header = self.root / 'include.svh'
        self.header.write_text('`define SIZE 1')
        self.request = dict(project=str(self.project), target='test', top_module='top', build_args=[])
        (self.build / 'top').write_bytes(b'executable')
        (self.build / 'Vtop__verFiles.dat').write_text(f'S 1 2 3 "{self.header}"\n')

    def guard(self, no_build=True, output='a', request=None):
        return VerilatorBuildGuard(self.build, request or self.request, [self.source], [],
                                   no_build, self.build / output)

    def record(self):
        with self.guard(False) as guard:
            guard.record_build()

    def test_no_manifest_is_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'run build'):
            with self.guard():
                self.fail('Missing build must not run')

    def test_changed_source_header_config_and_binary_are_rejected(self):
        for path in (self.source, self.header, self.project, self.build / 'top'):
            with self.subTest(path=path):
                self.record()
                path.write_bytes(path.read_bytes() + b'changed')
                with self.assertRaisesRegex(RuntimeError, 'changed; compilation disabled'):
                    with self.guard():
                        self.fail('Changed build must not run')

    def test_changed_flags_are_rejected(self):
        self.record()
        with self.assertRaisesRegex(RuntimeError, 'options changed'):
            with self.guard(request=dict(self.request, build_args=['-GCOUNT=2'])):
                self.fail('Different target must not share this build')

    def test_source_mutation_during_test_is_reported(self):
        self.record()
        with self.assertRaisesRegex(RuntimeError, 'changed; compilation disabled'):
            with self.guard():
                self.source.write_text('modified during test')

    def test_source_mutation_during_build_cannot_publish_manifest(self):
        with self.guard(False) as guard:
            self.source.write_text('modified during build')
            with self.assertRaisesRegex(RuntimeError, 'during compilation'):
                guard.record_build()
        self.assertFalse((self.build / '.hdlforge-build.json').exists())

    def test_combined_build_and_sim_also_checks_inputs_after_simulation(self):
        with self.assertRaisesRegex(RuntimeError, 'changed; compilation disabled'):
            with self.guard(False) as guard:
                guard.record_build()
                self.source.write_text('modified by simulation')

    def test_readers_share_executable_but_duplicate_output_is_rejected(self):
        self.record()
        with self.guard(output='a'), self.guard(output='b'):
            with self.assertRaisesRegex(RuntimeError, 'output already in use'):
                with self.guard(output='a'):
                    self.fail('Same output must not run twice')

    def test_build_writer_cannot_acquire_lock_while_simulation_reads(self):
        self.record()
        key = hashlib.sha256(str(self.build).encode()).hexdigest()[:20]
        with self.guard(), (self.root / f'.hdlforge-verilator-{key}.lock').open('a+') as stream:
            with self.assertRaises(BlockingIOError):
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with (self.root / f'.hdlforge-verilator-{key}.lock').open('a+') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)


if __name__ == '__main__':
    unittest.main()
