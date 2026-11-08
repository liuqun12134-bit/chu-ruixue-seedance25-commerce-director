"""Machine-local runtime paths; no installation or network access on import."""
import json
import os
from pathlib import Path

RUNTIME_NAME = 'chu-ruixue-seedance25-commerce-director'


def runtime_root():
    override = os.environ.get('CRX_RUNTIME_DIR')
    if override:
        return Path(override).expanduser().resolve()
    # LOCALAPPDATA is redirected to an ephemeral sandbox directory in Codex Windows.
    # USERPROFILE / Path.home remains stable across sandboxed and elevated calls.
    return Path.home() / '.codex' / 'runtimes' / RUNTIME_NAME


def read_config(path=None):
    path = Path(path) if path else runtime_root() / 'runtime.json'
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        if not isinstance(data, dict) or data.get('schema_version') != 1:
            return {}
        return data
    except (OSError, ValueError):
        return {}


def write_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)
