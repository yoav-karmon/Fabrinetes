"""Publish finished artifact trees, including failed runs, as real directories."""

import ctypes
import datetime
import fcntl
import os
from pathlib import Path
import shutil
import tempfile


def clear_latest(config: dict) -> None:
    """Replace the previous latest tree with an empty directory at run start."""
    _replace_latest(config, empty=True)


def publish_latest(config: dict) -> None:
    """Copy completed artifacts into latest unless a newer run has started."""
    _replace_latest(config, empty=False)


def _replace_latest(config: dict, *, empty: bool) -> None:
    """Serialize startup clearing and publication using the same launch stamp."""
    output = Path(config["output"])
    if not empty and (output / "info/status").read_text().strip() not in {"complete", "failed"}:
        raise ValueError("Only successful or failed finished runs can be published")
    launched = datetime.datetime.fromisoformat(config["launch_timestamp"])
    epoch = datetime.datetime(1970, 1, 1, tzinfo=datetime.timezone.utc)
    delta = launched - epoch
    stamp_ns = ((delta.days * 86400 + delta.seconds) * 1000000 + delta.microseconds) * 1000
    run_folder = Path(config["output_root"]).joinpath(*config["selector"].split("."))
    run_folder.mkdir(parents=True, exist_ok=True)
    latest = run_folder / "artifacts" / "latest"
    # An explicit rerun of the publication already writes here. Clearing it
    # would destroy its frozen inputs; copying onto itself would also deadlock
    # on the publication lock held across this rerun and its continuations.
    if output.resolve() == latest.resolve():
        return
    latest.parent.mkdir(parents=True, exist_ok=True)
    with (run_folder / ".publish.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if latest.is_symlink():
            raise ValueError(f"Refusing to replace a symlink: {latest}")
        if latest.exists() and latest.stat().st_mtime_ns > stamp_ns:
            return
        staging = Path(tempfile.mkdtemp(prefix=".publish-", dir=run_folder))
        try:
            # Dereference any links so the published tree contains real copies.
            if not empty:
                shutil.copytree(output, staging, dirs_exist_ok=True, symlinks=False)
            os.utime(staging, ns=(stamp_ns, stamp_ns))
            if latest.exists():
                # Linux renameat2 exchanges nonempty directories atomically.
                # A failure leaves the old latest tree intact; do not fall back
                # to deleting it or exposing a partly copied directory.
                libc = ctypes.CDLL(None, use_errno=True)
                exchange = libc.renameat2
                exchange.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
                exchange.restype = ctypes.c_int
                if exchange(-100, os.fsencode(staging), -100, os.fsencode(latest), 2):
                    error = ctypes.get_errno()
                    raise OSError(error, os.strerror(error), str(latest))
            else:
                os.replace(staging, latest)
        finally:
            # After exchange, staging holds the old published copy, never the
            # original timestamped artifacts. Cleanup does not invalidate latest.
            if staging.exists():
                shutil.rmtree(staging, ignore_errors=True)
