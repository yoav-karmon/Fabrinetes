"""Protect a built Verilator executable while isolated simulations share it."""

import fcntl
import hashlib
import json
import re
from contextlib import ExitStack
from pathlib import Path


def fingerprints(paths: list[Path]) -> dict[str, str]:
    return {str(path.resolve()): hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(paths))}


class VerilatorBuildGuard:
    """Exclusive compilation; shared immutable executable with exclusive test output."""

    def __init__(self, build_dir: Path, request: dict, sources: list[Path], includes: list[Path],
                 no_build: bool, output: Path | None = None):
        self.build_dir = Path(build_dir).resolve()
        self.request = request
        self.sources = list(sources)
        self.includes = list(includes)
        self.no_build = no_build
        self.output = output
        self.manifest = self.build_dir / '.hdlforge-build.json'
        self.stack = ExitStack()

    def lock(self, name: str, shared: bool, nonblocking: bool = False) -> None:
        key = hashlib.sha256(name.encode()).hexdigest()[:20]
        path = self.build_dir.parent / f'.hdlforge-verilator-{key}.lock'
        stream = self.stack.enter_context(path.open('a+'))
        mode = fcntl.LOCK_SH if shared else fcntl.LOCK_EX
        try:
            fcntl.flock(stream, mode | (fcntl.LOCK_NB if nonblocking else 0))
        except BlockingIOError:
            raise RuntimeError(f'Simulation output already in use: {self.output}') from None

    def declared_files(self) -> list[Path]:
        paths = self.sources + [Path(self.request['project'])]
        for directory in self.includes:
            paths.extend(path for path in directory.rglob('*') if path.suffix in {'.v', '.sv', '.vh', '.svh'} and path.is_file())
        return paths

    def __enter__(self):
        self.build_dir.parent.mkdir(parents=True, exist_ok=True)
        try:
            print('[i] Acquiring shared simulation lock' if self.no_build else '[i] Acquiring exclusive build lock', flush=True)
            self.lock(str(self.build_dir), self.no_build)
            if self.output is not None:
                self.lock(str(self.output.resolve()), False, nonblocking=True)
            self.before = fingerprints(self.declared_files())
            if self.no_build:
                self.validate()
                print('[i] Verified build: simulation only, compilation disabled', flush=True)
            else:
                self.manifest.unlink(missing_ok=True)
            return self
        except BaseException:
            self.stack.close()
            raise

    def record_build(self) -> None:
        #######################################################################
        # Retain actual Verilator input dependencies, including included HDL. #
        # Hash contents so a timestamp-only cache cannot hide source changes. #
        #######################################################################
        if fingerprints(self.declared_files()) != self.before:
            raise RuntimeError('Build inputs changed during compilation; rerun build')
        paths = self.declared_files()
        for dependency_file in self.build_dir.glob('*__verFiles.dat'):
            for name in re.findall(r'^S\s+[^\n]*?"([^"]+)"\s*$', dependency_file.read_text(), re.M):
                path = Path(name)
                paths.append(path if path.is_absolute() else self.build_dir / path)
        executable = self.build_dir / self.request['top_module']
        paths.append(executable)
        record = dict(request=self.request, files=fingerprints(paths))
        self.manifest.write_text(json.dumps(record, indent=2) + '\n')

    def validate(self) -> None:
        try:
            record = json.loads(self.manifest.read_text())
            if record['request'] != self.request:
                raise RuntimeError('Build target/options changed; run build before --no-build')
            actual = fingerprints([Path(path) for path in record['files']])
            changed = [path for path, digest in actual.items() if record['files'][path] != digest]
            if changed:
                raise RuntimeError('Build input or executable changed; compilation disabled: ' + ', '.join(changed[:5]))
        except (OSError, ValueError, KeyError) as error:
            raise RuntimeError(f'No matching verified build; run build before --no-build: {error}') from error

    def __exit__(self, exc_type, exc, traceback):
        try:
            if self.no_build or self.output is not None and self.manifest.exists():
                self.validate()
                if fingerprints(self.declared_files()) != self.before:
                    raise RuntimeError('Build inputs changed during simulation; compilation disabled')
        finally:
            self.stack.close()
