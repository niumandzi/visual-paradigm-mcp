"""Installer tests against temporary fake plugin files, not the installed VP plugin."""
from contextlib import redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from scripts import install as installer


class InstallTests(unittest.TestCase):
    def test_installs_metadata_refuses_overwrite_and_backs_up_replacement(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / 'bridge source'
            artifact = root / 'plugin/classes/local/codex/Bridge.class'
            artifact.parent.mkdir(parents=True)
            artifact.write_bytes(b'fixture-v1')
            (root / 'plugin/plugin.xml').write_text('<plugin/>')
            (root / 'jobs').mkdir()
            (root / 'jobs/Command.class').write_bytes(b'fixture')
            destination = Path(temp) / 'plugins'
            with patch.object(installer, 'ROOT', root), redirect_stdout(io.StringIO()):
                installer.install(destination)
                installed = destination / 'local-codex-bridge'
                self.assertIn('bridge\\ source', (installed / 'bridge.properties').read_text())
                with self.assertRaises(SystemExit):
                    installer.install(destination)
                artifact.write_bytes(b'fixture-v2')
                installer.install(destination, replace=True)
            backups = list((root / 'backups').glob('installed-plugin-*'))
            self.assertEqual(len(backups), 1)
            self.assertEqual((backups[0] / 'classes/local/codex/Bridge.class').read_bytes(), b'fixture-v1')
            self.assertEqual((installed / 'classes/local/codex/Bridge.class').read_bytes(), b'fixture-v2')


if __name__ == '__main__':
    unittest.main()
