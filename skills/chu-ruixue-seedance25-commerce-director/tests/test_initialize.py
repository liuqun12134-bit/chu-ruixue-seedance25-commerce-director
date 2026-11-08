"""No network: verify missing/ready/failed transitions and archive boundaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import initialize as init
from runtime_config import read_config, write_json, runtime_root


class RuntimeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='.crx-init-test-', dir=Path.cwd())
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.args = argparse.Namespace(runtime_dir=self.root, search_root=self.root,
                                       check_only=False, python_installed=False, model_dir=None)

    def test_ready_reuses_all_without_installing(self):
        with patch.object(init, 'find_python', return_value=(Path(sys.executable), {})), \
             patch.object(init, 'find_tool', side_effect=lambda name, *_: Path(name + '.exe')), \
             patch.object(init, 'media_smoke'), \
             patch.object(init, 'find_model', return_value=self.root / 'model'), \
             patch.object(init, 'install_python_packages') as packages, \
             patch.object(init, 'install_ffmpeg') as ffmpeg, \
             patch.object(init, 'install_model') as model:
            for _ in range(2):
                report = init.initialize(self.args)
                self.assertEqual(report['status'], 'ready')
                self.assertEqual(report['installed'], [])
            packages.assert_not_called()
            ffmpeg.assert_not_called()
            model.assert_not_called()
            self.assertEqual(read_config(self.root / 'runtime.json')['python'], sys.executable)

    def test_check_only_preserves_config_and_does_not_install(self):
        previous = {'schema_version': 1, 'python': 'old-python'}
        write_json(self.root / 'runtime.json', previous)
        self.args.check_only = True
        with patch.object(init, 'find_python', return_value=(None, None)), \
             patch.object(init, 'find_tool', return_value=None), \
             patch.object(init, 'install_python_packages') as packages, \
             patch.object(init, 'install_ffmpeg') as ffmpeg, \
             patch.object(init, 'install_model') as model:
            report = init.initialize(self.args)
            self.assertFalse(report['ok'])
            self.assertEqual(report['status'], 'missing')
            self.assertEqual(len(report['missing_before']), 4)
            self.assertEqual(read_config(self.root / 'runtime.json'), previous)
            packages.assert_not_called()
            ffmpeg.assert_not_called()
            model.assert_not_called()

    def test_missing_components_installed_and_verified_before_config(self):
        python = Path(sys.executable)
        with patch.object(init, 'find_python', return_value=(None, None)), \
             patch.object(init, 'install_python_packages', return_value=(python, {})) as packages, \
             patch.object(init, 'find_tool', return_value=None), \
             patch.object(init, 'install_ffmpeg', return_value={'sha256': 'example', 'ffmpeg': 'ffmpeg.exe', 'ffprobe': 'ffprobe.exe'}) as ffmpeg, \
             patch.object(init, 'media_smoke') as smoke, \
             patch.object(init, 'find_model', return_value=None), \
             patch.object(init, 'install_model', return_value=self.root / 'model') as model:
            report = init.initialize(self.args)
            self.assertTrue(report['ok'])
            self.assertEqual(report['status'], 'installed')
            self.assertEqual(len(report['installed']), 3)
            packages.assert_called_once()
            ffmpeg.assert_called_once()
            smoke.assert_called_once()
            model.assert_called_once()
            self.assertTrue((self.root / 'runtime.json').is_file())

    def test_install_failure_never_overwrites_last_good_config(self):
        previous = {'schema_version': 1, 'python': 'preserve-this'}
        write_json(self.root / 'runtime.json', previous)
        with patch.object(init, 'find_python', return_value=(None, None)), \
             patch.object(init, 'install_python_packages', side_effect=RuntimeError('network failed')):
            with self.assertRaisesRegex(RuntimeError, 'network failed'):
                init.initialize(self.args)
        self.assertEqual(read_config(self.root / 'runtime.json'), previous)

    def test_broken_media_pair_uses_new_download(self):
        with patch.object(init, 'find_python', return_value=(Path(sys.executable), {})), \
             patch.object(init, 'find_tool', side_effect=lambda name, *_: Path('old') / name), \
             patch.object(init, 'media_smoke', side_effect=[RuntimeError('bad codec'), None]) as smoke, \
             patch.object(init, 'install_ffmpeg', return_value={'ffmpeg': 'new/ffmpeg.exe', 'ffprobe': 'new/ffprobe.exe'}), \
             patch.object(init, 'find_model', return_value=self.root / 'model'):
            report = init.initialize(self.args)
            self.assertEqual(report['status'], 'installed')
            self.assertEqual(smoke.call_args.args[:2], (Path('new/ffmpeg.exe'), Path('new/ffprobe.exe')))

    def test_corrupt_model_triggers_repair(self):
        with patch.object(init, 'find_python', return_value=(Path(sys.executable), {})), \
             patch.object(init, 'find_tool', side_effect=lambda name, *_: Path(name + '.exe')), \
             patch.object(init, 'media_smoke'), \
             patch.object(init, 'find_model', return_value=None), \
             patch.object(init, 'install_model', return_value=self.root / 'new-model') as model, \
             patch.object(init, 'install_python_packages') as packages, \
             patch.object(init, 'install_ffmpeg') as ffmpeg:
            report = init.initialize(self.args)
            self.assertEqual(report['installed'], ['Whisper small 模型'])
            model.assert_called_once()
            packages.assert_not_called()
            ffmpeg.assert_not_called()

    def test_usable_python_import_is_required(self):
        with patch.object(init, 'run', side_effect=RuntimeError('DLL load failed')):
            self.assertIsNone(init.probe_python(sys.executable))

    def archive(self, member):
        archive = self.root / 'bundle.zip'
        with zipfile.ZipFile(archive, 'w') as file:
            file.writestr(member, b'example')
        return archive, hashlib.sha256(archive.read_bytes()).hexdigest()

    def test_archive_hash_must_match(self):
        archive, _ = self.archive('ffmpeg/bin/ffmpeg.exe')
        with self.assertRaisesRegex(RuntimeError, 'checksum'):
            init.extract_verified_zip(archive, self.root / 'unpack', '0' * 64)
        self.assertFalse((self.root / 'unpack').exists())

    def test_archive_cannot_escape_runtime(self):
        archive, checksum = self.archive('../outside.exe')
        with self.assertRaisesRegex(RuntimeError, 'Unsafe'):
            init.extract_verified_zip(archive, self.root / 'unpack', checksum)
        self.assertFalse((self.root / 'outside.exe').exists())

    def test_verified_archive_extracts(self):
        archive, checksum = self.archive('ffmpeg/bin/ffmpeg.exe')
        init.extract_verified_zip(archive, self.root / 'unpack', checksum)
        self.assertEqual((self.root / 'unpack/ffmpeg/bin/ffmpeg.exe').read_bytes(), b'example')

    def test_stale_or_corrupt_config_is_not_trusted(self):
        config = self.root / 'runtime.json'
        config.write_text('broken', encoding='utf-8')
        self.assertEqual(read_config(config), {})
        config.write_text(json.dumps({'schema_version': 999}), encoding='utf-8')
        self.assertEqual(read_config(config), {})

    def test_runtime_path_survives_sandbox_appdata_redirection(self):
        with patch.dict(os.environ, {'CRX_RUNTIME_DIR': '', 'LOCALAPPDATA': 'sandbox-a'}):
            first = runtime_root()
        with patch.dict(os.environ, {'CRX_RUNTIME_DIR': '', 'LOCALAPPDATA': 'sandbox-b'}):
            self.assertEqual(runtime_root(), first)
        self.assertTrue(first.is_relative_to(Path.home() / '.codex/runtimes'))


if __name__ == '__main__':
    unittest.main()
