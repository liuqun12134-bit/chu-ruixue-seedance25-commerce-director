import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('skill_update', Path(__file__).resolve().parents[1] / 'scripts/update.py')
up = importlib.util.module_from_spec(spec)
spec.loader.exec_module(up)


class UpdateTests(unittest.TestCase):
    def test_upstream_change_and_delete(self):
        result = up.plan_changes({'a': 'old', 'b': 'old'}, {'a': 'old', 'b': 'old'}, {'a': 'new'})
        self.assertEqual(result, {'writes': ['a'], 'deletes': ['b'], 'conflicts': []})

    def test_local_only_change_and_addition_survive(self):
        self.assertEqual(up.plan_changes({'a': 'old'}, {'a': 'local', 'personal': 'x'}, {'a': 'old'}),
                         {'writes': [], 'deletes': [], 'conflicts': []})

    def test_two_sided_change_and_delete_conflict(self):
        result = up.plan_changes({'a': 'old', 'b': 'old'}, {'a': 'ours', 'b': 'ours'}, {'a': 'theirs'})
        self.assertEqual(result['conflicts'], ['a', 'b'])

    def test_local_deletion_is_preserved_unless_upstream_changes(self):
        self.assertFalse(up.plan_changes({'a': 'old'}, {}, {'a': 'old'})['writes'])
        self.assertEqual(up.plan_changes({'a': 'old'}, {}, {'a': 'new'})['conflicts'], ['a'])

    def test_first_install_never_overwrites_unknown_changes(self):
        result = up.plan_changes({}, {'a': 'mine', 'b': 'same'}, {'a': 'remote', 'b': 'same', 'c': 'new'})
        self.assertEqual(result['writes'], ['c'])
        self.assertEqual(result['conflicts'], ['a'])

    def test_derived_indexes_rebuilt_without_losing_source_records(self):
        result = up.plan_changes({'product-library/index.json': 'old'},
                                 {'product-library/index.json': 'ours', 'product-library/mine.json': 'x'},
                                 {'product-library/index.json': 'theirs'})
        self.assertFalse(result['conflicts'])
        self.assertEqual(result['writes'], ['product-library/index.json'])
        self.assertFalse(result['deletes'])

    def test_path_and_case_collisions(self):
        self.assertTrue(up.plan_changes({}, {'a': 'local'}, {'a/b': 'new'})['conflicts'])
        self.assertTrue(up.plan_changes({}, {'A': 'local'}, {'a': 'new'})['conflicts'])

    def test_manifest_traversal_rejected(self):
        for name in ('../outside', '/absolute', 'C:/outside', 'a\\b', 'a/../b', '.git/config'):
            with self.assertRaises(ValueError):
                up.safe_name(name)

    def test_staged_install_preserves_local_and_backup(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target, remote = root / 'installed', root / 'remote'
            target.mkdir(); remote.mkdir()
            (target / 'a').write_text('old')
            (target / 'mine').write_text('keep')
            (remote / 'a').write_text('new')
            before = up.inventory(target)
            backup = up.install(target, remote, {'writes': ['a'], 'deletes': []}, before, lambda p: None)
            self.assertEqual((target / 'a').read_text(), 'new')
            self.assertEqual((target / 'mine').read_text(), 'keep')
            self.assertEqual(up.inventory(backup), before)

    def test_invalid_candidate_keeps_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'installed'; target.mkdir()
            (target / 'a').write_text('original')
            before = up.inventory(target)
            def fail(path):
                raise ValueError('bad references')
            with self.assertRaises(ValueError):
                up.install(target, root, {'writes': [], 'deletes': []}, before, fail)
            self.assertEqual(up.inventory(target), before)
            self.assertEqual(list(root.iterdir()), [target])

    def test_concurrent_edit_cancels_swap(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'installed'; target.mkdir()
            (target / 'a').write_text('old')
            def concurrent_edit(path):
                (target / 'a').write_text('new local work')
            with self.assertRaises(RuntimeError):
                up.install(target, root, {'writes': [], 'deletes': []}, up.inventory(target), concurrent_edit)
            self.assertEqual((target / 'a').read_text(), 'new local work')

    def test_swap_failure_restores_original(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            target = root / 'installed'; target.mkdir()
            (target / 'a').write_text('original')
            rename = Path.rename
            def fail_stage(path, destination):
                if '-stage-' in path.name:
                    raise OSError('file is in use')
                return rename(path, destination)
            with patch.object(Path, 'rename', fail_stage), self.assertRaises(OSError):
                up.install(target, root, {'writes': [], 'deletes': []}, up.inventory(target), lambda p: None)
            self.assertEqual((target / 'a').read_text(), 'original')


class LifecycleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.repo = self.root / 'upstream'
        self.source = self.repo / up.SKILL_PATH
        (self.source / 'scripts').mkdir(parents=True)
        (self.source / 'SKILL.md').write_text('test skill')
        (self.source / 'scripts/catalog.py').write_text('import sys\nsys.exit(0)\n')
        (self.source / 'library.txt').write_text('initial')
        self.write_manifest()
        self.target = self.root / 'installed'
        shutil.copytree(self.source, self.target)
        self.args = type('Args', (), {'skill_dir': self.target, 'state_dir': self.root / 'state', 'check': False})()
        self.calls = []
        self.real_run = up.run
        self.manifest_patch = patch.object(up, 'fetch_manifest', self.fake_manifest)
        self.manifest_patch.start()

    def tearDown(self):
        self.manifest_patch.stop()
        self.temp.cleanup()

    def fake_manifest(self, folder, commit):
        folder.mkdir()
        shutil.copy2(self.repo / 'package-manifest.json', folder / 'package-manifest.json')

    def write_manifest(self):
        (self.repo / 'package-manifest.json').write_text(json.dumps({
            'skill_name': up.NAME, 'skill_path': up.SKILL_PATH, 'skill_version': '2.1.0',
            'files': [{'path': p, 'sha256': h} for p, h in up.inventory(self.source).items()]}))

    def fake_git(self, args, cwd=None, env=None):
        self.calls.append([str(a) for a in args])
        if args[0] != 'git':
            return self.real_run(args, cwd, env)
        if 'clone' in args:
            shutil.copytree(self.repo, args[-1])
        return 'a' * 40 if 'rev-parse' in args or 'ls-remote' in args else ''

    def test_bootstrap_then_upgrade_then_noop(self):
        with patch.object(up, 'run', self.fake_git):
            report, code = up.execute(self.args)
            self.assertEqual((report['status'], code), ('up_to_date', 0))
            self.assertTrue(Path(report['state_file']).exists())
            (self.source / 'library.txt').write_text('remote upgrade')
            self.write_manifest()
            (self.target / 'my-private-record.txt').write_text('keep locally')
            report, code = up.execute(self.args)
            self.assertEqual((report['status'], code), ('updated', 0))
            self.assertEqual((self.target / 'library.txt').read_text(), 'remote upgrade')
            self.assertEqual((self.target / 'my-private-record.txt').read_text(), 'keep locally')
            self.assertEqual((Path(report['backup']) / 'library.txt').read_text(), 'initial')
            self.assertEqual(up.execute(self.args)[0]['status'], 'up_to_date')

    def test_check_does_not_download_media_or_write_baseline(self):
        self.args.check = True
        with patch.object(up, 'run', self.fake_git):
            report, code = up.execute(self.args)
        self.assertEqual(code, 0)
        self.assertFalse(list(self.args.state_dir.glob('*.json')))
        self.assertFalse(any('lfs' in call for call in self.calls))
        self.assertFalse(any('clone' in call for call in self.calls))
        self.assertEqual(up.inventory(self.source), up.inventory(self.target))

    def test_conflict_stops_whole_upgrade(self):
        with patch.object(up, 'run', self.fake_git):
            up.execute(self.args)
            (self.target / 'library.txt').write_text('local change')
            (self.source / 'library.txt').write_text('remote change')
            (self.source / 'new.txt').write_text('new')
            self.write_manifest()
            before = up.inventory(self.target)
            report, code = up.execute(self.args)
            self.assertEqual(code, 2)
            self.assertEqual(report['conflicts'], ['library.txt'])
            self.assertEqual(up.inventory(self.target), before)

    def test_bad_download_rejected_before_install(self):
        with patch.object(up, 'run', self.fake_git):
            up.execute(self.args)
        (self.source / 'library.txt').write_text('intended new version')
        self.write_manifest()
        (self.source / 'library.txt').write_text('tampered')
        before = up.inventory(self.target)
        with patch.object(up, 'run', self.fake_git), self.assertRaisesRegex(ValueError, 'SHA-256'):
            up.execute(self.args)
        self.assertEqual(up.inventory(self.target), before)

    def test_state_write_failure_rolls_back_install(self):
        with patch.object(up, 'run', self.fake_git):
            up.execute(self.args)
            (self.source / 'library.txt').write_text('new')
            self.write_manifest()
            before = up.inventory(self.target)
            with patch.object(up, 'atomic_json', side_effect=OSError('disk full')), self.assertRaises(OSError):
                up.execute(self.args)
            self.assertEqual(up.inventory(self.target), before)


if __name__ == '__main__':
    unittest.main()
