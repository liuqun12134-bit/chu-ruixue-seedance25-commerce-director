#!/usr/bin/env python3
"""Verify every packaged asset, including real Git LFS contents, against its snapshot."""
import argparse
import hashlib
import json
from pathlib import Path
import sys


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    repo = args.root.resolve()
    manifest = json.loads((repo / 'package-manifest.json').read_text(encoding='utf-8-sig'))
    root = (repo / manifest['skill_path']).resolve()
    root.relative_to(repo)
    expected = set()
    errors = []
    total_bytes = 0
    for item in manifest['files']:
        name = item['path']
        if name in expected:
            errors.append(f'duplicate manifest entry: {name}')
        expected.add(name)
        path = (root / name).resolve()
        path.relative_to(root)
        if not path.is_file():
            errors.append(f'missing: {name}')
            continue
        size = path.stat().st_size
        total_bytes += size
        if size != item['size']:
            errors.append(f'size mismatch (run git lfs pull if this is a video): {name}')
        elif digest(path) != item['sha256']:
            errors.append(f'SHA-256 mismatch: {name}')
    actual = {
        path.relative_to(root).as_posix() for path in root.rglob('*')
        if path.is_file() and '__pycache__' not in path.relative_to(root).parts
        and path.suffix not in {'.pyc', '.pyo'}
    }
    for name in sorted(actual - expected):
        errors.append(f'not in release manifest: {name}')
    summary = manifest['summary']
    if len(expected) != summary['files'] or total_bytes != summary['bytes']:
        errors.append('package totals do not match release manifest')
    print(json.dumps({'ok': not errors, 'files': len(expected), 'bytes': total_bytes, 'errors': errors}, ensure_ascii=False))
    return 1 if errors else 0


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
