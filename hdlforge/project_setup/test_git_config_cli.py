"""Exercise local Git writes and failure isolation in disposable repositories."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from git_config_cli import update, git


class GitConfigTest(unittest.TestCase):
    def test_local_update_preview_verify_and_missing_account(self):
        with tempfile.TemporaryDirectory(prefix='git config ') as folder:
            root = Path(folder)
            subprocess.run(['git', 'init', '-q', str(root)], check=True)
            config = root / 'ssh config'
            config.write_text('Host lab\n    User test\n')
            (root / 'test.hdlforge.json').write_text(json.dumps({
                'settings': {'env': {'host': {'user': {'ssh_config_file': config.name}}}}}))
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(update(root, 'update-dry-run', 'host', 'user'), 0)
                self.assertEqual(git(root, 'config', '--local', '--get', 'core.sshCommand').returncode, 1)
                self.assertEqual(update(root, 'verify', 'host', 'user'), 1)
                self.assertEqual(update(root, 'update', 'host', 'user'), 0)
                self.assertEqual(update(root, 'verify', 'host', 'user'), 0)
                before = (root / '.git/config').read_bytes()
                self.assertEqual(update(root, 'update', 'host', 'user'), 0)
                self.assertEqual((root / '.git/config').read_bytes(), before)
                with self.assertRaisesRegex(ValueError, 'Missing settings'):
                    update(root, 'update', 'host', 'other')
                self.assertEqual((root / '.git/config').read_bytes(), before)
                config.unlink()
                with self.assertRaisesRegex(ValueError, 'existing file'):
                    update(root, 'update', 'host', 'user')


if __name__ == '__main__':
    unittest.main()
