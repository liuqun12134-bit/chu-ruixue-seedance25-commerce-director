#!/usr/bin/env python3
"""Update the installed skill from its public GitHub package; preserve local edits."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import uuid
from urllib.request import Request, urlopen

NAME = 'chu-ruixue-seedance25-commerce-director'
REPOSITORY = 'https://github.com/liuqun12134-bit/' + NAME + '.git'
BRANCH = 'main'
SKILL_PATH = 'skills/' + NAME
DERIVED = {'library-review.html', 'performance-library/review.html'} | {
    kind + '-library/index.json' for kind in ('demo', 'performance', 'product', 'script', 'action')}
sys.dont_write_bytecode = True


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def inventory(root):
    result = {}
    for folder, dirs, files in os.walk(root, followlinks=False):
        parent = Path(folder)
        for name in dirs + files:
            path = parent / name
            if path.is_symlink() or (hasattr(path, 'is_junction') and path.is_junction()):
                raise ValueError('Linked path is not supported: ' + str(path))
        if '.git' in dirs or '.git' in files:
            raise ValueError('Installed skill is a Git checkout; update that checkout separately.')
        dirs[:] = [d for d in dirs if d != '__pycache__']
        for name in files:
            path = parent / name
            if path.suffix not in {'.pyc', '.pyo'}:
                result[path.relative_to(root).as_posix()] = digest(path)
    return result


def safe_name(name):
    if not isinstance(name, str) or not name or '\\' in name or ':' in name:
        raise ValueError('Unsafe manifest path')
    path = PurePosixPath(name)
    if path.is_absolute() or any(p in {'.', '..', '.git', '__pycache__'} for p in path.parts) or str(path) != name:
        raise ValueError('Unsafe manifest path: ' + name)
    return name


def manifest_hashes(repo):
    manifest = json.loads((repo / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    if manifest.get('skill_name') != NAME or manifest.get('skill_path') != SKILL_PATH:
        raise ValueError('Repository package identity mismatch')
    result = {}
    folded = set()
    for item in manifest['files']:
        name = safe_name(item['path'])
        if name.casefold() in folded or not re.fullmatch('[a-f0-9]{64}', item['sha256']):
            raise ValueError('Invalid or duplicate manifest entry: ' + name)
        folded.add(name.casefold())
        result[name] = item['sha256']
    if 'SKILL.md' not in result or 'scripts/catalog.py' not in result:
        raise ValueError('Incomplete skill manifest')
    return result, manifest.get('skill_version', 'unknown')


def fetch_manifest(folder, commit):
    url = 'https://raw.githubusercontent.com/liuqun12134-bit/' + NAME + '/' + commit + '/package-manifest.json'
    folder.mkdir()
    with urlopen(Request(url, headers={'User-Agent': NAME + '-updater'}), timeout=90) as response:
        (folder / 'package-manifest.json').write_bytes(response.read())


def plan_changes(base, local, remote):
    """Whole-file three-way merge; ambiguity stops the entire update."""
    writes, deletes, conflicts = [], [], []
    for name in sorted(set(base) | set(local) | set(remote)):
        old, ours, theirs = base.get(name), local.get(name), remote.get(name)
        if name in DERIVED:
            # These are rebuilt from preserved source records in the staging copy.
            if ours != theirs:
                (deletes if theirs is None else writes).append(name)
            continue
        if ours == theirs or theirs == old:
            continue
        if ours == old:
            (deletes if theirs is None else writes).append(name)
        else:
            conflicts.append(name)
    # Detect file/directory collisions and case-only collisions before copying.
    final_names = (set(local) - set(deletes)) | set(writes)
    folded = {}
    for name in sorted(final_names):
        key = name.casefold()
        if key in folded:
            conflicts.extend([name, folded[key]])
        folded[key] = name
    for name in final_names:
        for parent in PurePosixPath(name).parents:
            if str(parent).casefold() in folded:
                conflicts.extend([name, folded[str(parent).casefold()]])
    return {'writes': writes, 'deletes': deletes, 'conflicts': sorted(set(conflicts))}


def run(args, cwd=None, env=None):
    process = subprocess.Popen([str(x) for x in args], cwd=cwd, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               encoding='utf-8', errors='replace', start_new_session=os.name != 'nt')
    try:
        stdout, stderr = process.communicate(timeout=1800 if 'lfs' in args else 600)
    except subprocess.TimeoutExpired:
        if os.name == 'nt':
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True)
        else:
            os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise RuntimeError(f'{args[0]} timed out; original installation was not replaced.')
    if process.returncode:
        raise RuntimeError(f'{args[0]} failed ({process.returncode}):\n{stderr[-4000:]}\n{stdout[-4000:]}')
    return stdout.strip()


def validate(root):
    for action in ('reindex', 'validate', 'review'):
        run([sys.executable, '-B', root / 'scripts/catalog.py', action], cwd=root)


def atomic_json(path, value):
    temp = path.with_name(path.name + '.tmp-' + uuid.uuid4().hex)
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def install(target, remote_root, changes, local_hashes, validate_fn=validate):
    """Prepare/validate a full copy, then swap; the prior directory is the backup."""
    stage = Path(tempfile.mkdtemp(prefix='.' + NAME + '-stage-', dir=target.parent))
    backup = target.with_name(target.name + '.backup-' + datetime.now().strftime('%Y%m%d-%H%M%S') + '-' + uuid.uuid4().hex[:8])
    try:
        shutil.copytree(target, stage, dirs_exist_ok=True)
        for name in changes['deletes']:
            (stage / name).unlink()
        # Empty folders from removed upstream files may block new files.
        for folder, _, _ in os.walk(stage, topdown=False):
            path = Path(folder)
            if path != stage and not any(path.iterdir()):
                path.rmdir()
        for name in changes['writes']:
            dest = stage / name
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(remote_root / name, dest)
        validate_fn(stage)
        if inventory(target) != local_hashes:
            raise RuntimeError('Local files changed during update; stopped before replacement.')
        target.rename(backup)
        try:
            stage.rename(target)
        except BaseException:
            backup.rename(target)
            raise
        return backup
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def execute(args):
    target = args.skill_dir.absolute()
    if target.is_symlink() or (hasattr(target, 'is_junction') and target.is_junction()):
        raise ValueError('The installed directory must not be a link or junction.')
    target = target.resolve()
    if not (target / 'SKILL.md').is_file():
        raise ValueError('Missing installed SKILL.md: ' + str(target))
    state_root = args.state_dir.expanduser().resolve()
    if state_root == target or target in state_root.parents:
        raise ValueError('Update state must be outside the skill directory.')
    state_root.mkdir(parents=True, exist_ok=True)
    state_path = state_root / (hashlib.sha256(str(target).casefold().encode()).hexdigest()[:16] + '.json')
    lock = target.with_name('.' + target.name + '.update.lock')
    try:
        lock_file = lock.open('x', encoding='utf-8')
    except FileExistsError:
        raise RuntimeError('Update lock exists; check the recorded process before removing: ' + str(lock))
    try:
        with lock_file:
            lock_file.write(json.dumps({'pid': os.getpid(), 'target': str(target)}))
        local = inventory(target)
        state = json.loads(state_path.read_text(encoding='utf-8')) if state_path.exists() else None
        if state and (state.get('repository') != REPOSITORY or state.get('target') != str(target)):
            raise ValueError('Update baseline belongs to another installation/source.')
        run(['git', '--version'])
        env = dict(os.environ, GIT_LFS_SKIP_SMUDGE='1', GIT_TERMINAL_PROMPT='0', GCM_INTERACTIVE='Never')
        with tempfile.TemporaryDirectory(prefix='crx-download-', dir=state_root) as download:
            repo = Path(download) / 'repo'
            print('Fetching public GitHub main (without video downloads)...', file=sys.stderr, flush=True)
            ref = run(['git', 'ls-remote', REPOSITORY, 'refs/heads/' + BRANCH], env=env)
            commit = ref.split()[0] if ref else ''
            if not re.fullmatch('[a-f0-9]{40}', commit):
                raise ValueError('Cannot resolve remote main commit')
            metadata = Path(download) / 'metadata'
            fetch_manifest(metadata, commit)
            remote, version = manifest_hashes(metadata)
            # The baseline records the upstream snapshot, not the merged local files.
            base = state['files'] if state else {}
            changes = plan_changes(base, local, remote)
            report = {'status': 'conflicts' if changes['conflicts'] else 'available',
                      'repository': REPOSITORY, 'commit': commit, 'version': version,
                      'target': str(target), 'baseline_missing': state is None, **changes}
            if not changes['writes'] and not changes['deletes'] and not changes['conflicts']:
                report['status'] = 'up_to_date'
            if args.check or changes['conflicts']:
                return report, 2 if changes['conflicts'] else 0
            if report['status'] == 'up_to_date' and all(local.get(name) == value for name, value in remote.items()):
                # Register a complete installation without downloading its media again.
                run([sys.executable, '-B', target / 'scripts/catalog.py', 'validate'], cwd=target)
                if inventory(target) != local:
                    raise RuntimeError('Local files changed while verifying the update.')
                atomic_json(state_path, {'schema_version': 1, 'repository': REPOSITORY,
                            'target': str(target), 'commit': commit, 'version': version,
                            'updated_at': datetime.now(timezone.utc).isoformat(), 'files': remote})
                report['state_file'] = str(state_path)
                return report, 0
            remote_root = repo / SKILL_PATH
            run(['git', 'lfs', 'version'])
            print('Downloading and verifying library media...', file=sys.stderr, flush=True)
            run(['git', '-c', 'core.autocrlf=false', '-c', 'http.lowSpeedLimit=1024', '-c', 'http.lowSpeedTime=60',
                 'clone', '--depth', '1', '--branch', BRANCH, '--single-branch', REPOSITORY, repo], env=env)
            if run(['git', 'rev-parse', 'HEAD'], cwd=repo) != commit:
                raise RuntimeError('Remote main changed during update; run again to check the new revision.')
            run(['git', 'lfs', 'pull'], cwd=repo, env=env)
            run(['git', 'lfs', 'fsck'], cwd=repo, env=env)
            if inventory(remote_root) != remote:
                raise ValueError('Package SHA-256 verification failed; publish a current manifest and all LFS objects.')
            # Validate the pristine release before composing it with local additions.
            run([sys.executable, '-B', remote_root / 'scripts/catalog.py', 'validate'], cwd=remote_root)
            backup = None
            if changes['writes'] or changes['deletes']:
                backup = install(target, remote_root, changes, local)
                report['status'] = 'updated'
                report['backup'] = str(backup)
            else:
                if inventory(target) != local:
                    raise RuntimeError('Local files changed while verifying the update.')
                run([sys.executable, '-B', target / 'scripts/catalog.py', 'validate'], cwd=target)
            previous_state = state_path.read_bytes() if state_path.exists() else None
            try:
                if backup and previous_state is not None:
                    state_path.with_name(state_path.stem + '.before-' + backup.name + '.json').write_bytes(previous_state)
                atomic_json(state_path, {'schema_version': 1, 'repository': REPOSITORY,
                            'target': str(target), 'commit': commit, 'version': version,
                            'updated_at': datetime.now(timezone.utc).isoformat(), 'files': remote})
            except BaseException:
                # State and installed files must never silently diverge.
                if backup:
                    failed = target.with_name(target.name + '.failed-' + uuid.uuid4().hex[:8])
                    target.rename(failed)
                    backup.rename(target)
                raise
            report['state_file'] = str(state_path)
            return report, 0
    finally:
        lock.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Check only; no media download or installed-file changes')
    parser.add_argument('--skill-dir', type=Path, default=Path(__file__).resolve().parents[1])
    runtime = Path(os.environ.get('CRX_RUNTIME_DIR', str(Path.home() / '.codex/runtimes' / NAME)))
    parser.add_argument('--state-dir', type=Path, default=runtime / 'updates')
    args = parser.parse_args()
    try:
        report, code = execute(args)
    except Exception as exc:
        report, code = {'status': 'failed', 'error': str(exc)}, 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return code


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
