#!/usr/bin/env python3
"""Detect/reuse local tools, repair only in a managed runtime, verify before saving."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import wave
import zipfile

from runtime_config import read_config, runtime_root, write_json

sys.dont_write_bytecode = True
MODEL_REPO = 'Systran/faster-whisper-small'
MODEL_REVISION = '536b0662742c02347bc0e980a01041f333bce120'
MODEL_FILES = ('config.json', 'model.bin', 'tokenizer.json', 'vocabulary.txt')
FFMPEG_URL = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
IMPORT_PROBE = '''import json,struct,sys
import numpy,ctranslate2,av,onnxruntime,tokenizers,huggingface_hub
from faster_whisper import WhisperModel
assert sys.version_info[:2]==(3,12) and struct.calcsize('P')==8
import importlib.metadata as m
print(json.dumps({'python':sys.executable,'versions':{n:m.version(n) for n in ['faster-whisper','ctranslate2','numpy','huggingface-hub','av','onnxruntime','tokenizers']}}))
'''
MODEL_PROBE = '''import sys,json,numpy as np
from faster_whisper import WhisperModel
model=WhisperModel(sys.argv[1],device='cpu',compute_type='int8',cpu_threads=2,local_files_only=True)
segments,info=model.transcribe(np.zeros(16000,dtype=np.float32),language='zh',beam_size=1,condition_on_previous_text=False)
list(segments)
print(json.dumps({'ok':True,'device':'cpu','compute_type':'int8'}))
'''


def run(command, timeout=90):
    options = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    result = subprocess.run([str(x) for x in command], stdin=subprocess.DEVNULL,
                            capture_output=True, timeout=timeout, **options)
    if result.returncode:
        raise RuntimeError((result.stderr or result.stdout).decode('utf-8', errors='replace')[-2500:])
    return result.stdout.decode('utf-8', errors='replace')


def progress(message):
    print(message, file=sys.stderr, flush=True)


def unique_paths(values):
    seen = set()
    for value in values:
        if not value:
            continue
        path = Path(value).expanduser().resolve()
        key = os.path.normcase(str(path))
        if key not in seen:
            seen.add(key)
            yield path


def probe_python(executable):
    try:
        return json.loads(run([executable, '-c', IMPORT_PROBE]).strip())
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired):
        return None


def python_candidates(root, search_root, cached):
    return unique_paths([cached.get('python'), root / 'venv/Scripts/python.exe',
                         search_root / '.tools/local-asr/Scripts/python.exe', sys.executable])


def find_python(root, search_root, cached):
    for candidate in python_candidates(root, search_root, cached):
        if candidate.is_file():
            probe = probe_python(candidate)
            if probe:
                return candidate, probe
    return None, None


def install_python_packages(root):
    # Never pip-install into a reused environment or change the user's global Python.
    target = root / 'venv'
    executable = target / 'Scripts/python.exe'
    if target.exists():
        target = root / ('venv-repair-' + str(time.time_ns()))
        executable = target / 'Scripts/python.exe'
    progress('安装转写依赖到独立环境…')
    run([sys.executable, '-m', 'venv', target], timeout=120)
    run([executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--no-input',
         '--index-url', 'https://pypi.org/simple', '--only-binary=:all:',
         '-r', Path(__file__).with_name('runtime-requirements.txt')], timeout=900)
    probe = probe_python(executable)
    if not probe:
        raise RuntimeError('Installed ASR packages failed import verification; runtime was not marked ready.')
    return executable, probe


def find_tool(name, root, cached):
    values = [cached.get(name), shutil.which(name)]
    folder = root / 'ffmpeg'
    if folder.is_dir():
        values.extend(folder.glob('**/bin/' + name + '.exe'))
        values.append(folder / 'bin' / (name + '.exe'))
    for path in unique_paths(values):
        if path.is_file():
            try:
                version = run([path, '-version'], timeout=20)
                if version.startswith(name + ' version'):
                    return path
            except (OSError, RuntimeError, subprocess.TimeoutExpired):
                pass
    return None


def download(url, destination):
    temporary = destination.with_name(destination.name + '.part')
    request = urllib.request.Request(url, headers={'User-Agent': 'CRX-Skill-Initializer/1.0'})
    started = time.monotonic()
    with urllib.request.urlopen(request, timeout=45) as response, temporary.open('wb') as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
            if time.monotonic() - started > 900:
                raise RuntimeError('Download exceeded fifteen minutes; initialization remains incomplete.')
    temporary.replace(destination)


def extract_verified_zip(archive, destination, expected):
    digest = hashlib.sha256()
    with archive.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    if digest.hexdigest().lower() != expected.lower():
        raise RuntimeError('FFmpeg archive checksum mismatch; archive was not extracted.')
    base = destination.resolve()
    with zipfile.ZipFile(archive) as source:
        for entry in source.infolist():
            normalized = entry.filename.replace('\\', '/')
            target = (base / normalized).resolve()
            if ':' in normalized or not target.is_relative_to(base) or (entry.external_attr >> 16) & 0o170000 == 0o120000:
                raise RuntimeError('Unsafe archive member; archive was not extracted.')
        source.extractall(base)


def install_ffmpeg(root):
    progress('下载并校验 FFmpeg / ffprobe…')
    cache = root / 'downloads'
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / 'ffmpeg-release-essentials.zip'
    checksum = cache / 'ffmpeg-release-essentials.zip.sha256'
    download(FFMPEG_URL + '.sha256', checksum)
    match = re.search(r'\b[0-9a-fA-F]{64}\b', checksum.read_text(encoding='utf-8-sig'))
    if not match:
        raise RuntimeError('FFmpeg publisher did not provide a valid SHA256.')
    download(FFMPEG_URL, archive)
    target = root / 'ffmpeg' / ('install-' + str(time.time_ns()))
    extract_verified_zip(archive, target, match.group(0))
    ffmpeg = next(target.glob('*/bin/ffmpeg.exe'), None)
    ffprobe = next(target.glob('*/bin/ffprobe.exe'), None)
    if not ffmpeg or not ffprobe:
        raise RuntimeError('Downloaded FFmpeg archive did not contain both tools.')
    return {'url': FFMPEG_URL, 'sha256': match.group(0).lower(),
            'ffmpeg': str(ffmpeg), 'ffprobe': str(ffprobe)}


def media_smoke(ffmpeg, ffprobe, root):
    with tempfile.TemporaryDirectory(prefix='media-check-', dir=root) as directory:
        source = Path(directory) / 'input.wav'
        with wave.open(str(source), 'wb') as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(16000)
            output.writeframes(b'\x00\x00' * 1600)
        decoded = Path(directory) / 'decoded.wav'
        run([ffmpeg, '-v', 'error', '-nostdin', '-i', source, '-ar', '16000', '-ac', '1', decoded])
        meta = json.loads(run([ffprobe, '-v', 'error', '-show_streams', '-of', 'json', decoded]))
        if not any(s.get('codec_type') == 'audio' for s in meta.get('streams', [])):
            raise RuntimeError('FFmpeg round-trip produced no readable audio stream.')


def model_candidates(root, search_root, cached, explicit):
    values = [explicit, cached.get('model_dir'), root / 'models' / MODEL_REVISION]
    for base in [search_root / '.tools/asr-models', Path.home() / '.cache/huggingface/hub']:
        folder = base / ('models--' + MODEL_REPO.replace('/', '--')) / 'snapshots'
        if folder.is_dir():
            values.extend(sorted(folder.iterdir()))
    return unique_paths(values)


def find_model(executable, candidates):
    for path in candidates:
        if all((path / name).is_file() for name in MODEL_FILES):
            try:
                progress('验证本地转写模型加载及 CPU 推理…')
                run([executable, '-c', MODEL_PROBE, path], timeout=180)
                return path
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                progress('已有模型未通过验证，将继续查找或修复：' + str(exc)[-300:])
    return None


def install_model(root, executable):
    target = root / 'models' / MODEL_REVISION
    if target.exists():
        target = root / 'models' / (MODEL_REVISION + '-repair-' + str(time.time_ns()))
    progress('下载固定版本 Whisper small 模型；只下载模型，不上传音频…')
    code = ('from huggingface_hub import snapshot_download; import sys; '
            'snapshot_download(repo_id=sys.argv[1],revision=sys.argv[2],local_dir=sys.argv[3],'
            'allow_patterns=["config.json","model.bin","tokenizer.json","vocabulary.txt"],max_workers=2)')
    run([executable, '-c', code, MODEL_REPO, MODEL_REVISION, target], timeout=1800)
    model = find_model(executable, [target])
    if model is None:
        raise RuntimeError('Downloaded model failed inference verification; initialization remains incomplete.')
    return model


def initialize(args):
    if os.name != 'nt' or platform.machine().lower() not in ('amd64', 'x86_64'):
        raise RuntimeError('Automatic installation currently supports Windows x64 only.')
    root = args.runtime_dir.expanduser().resolve()
    search_root = args.search_root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    cached = read_config(root / 'runtime.json')
    missing, installed = [], []
    if args.python_installed:
        missing.append('Python')
        installed.append('Python 3.12.10')
    executable, py_info = find_python(root, search_root, cached)
    if executable is None:
        missing.append('本地转写依赖')
        if not args.check_only:
            executable, py_info = install_python_packages(root)
            installed.append('本地转写依赖')
    ffmpeg, ffprobe = find_tool('ffmpeg', root, cached), find_tool('ffprobe', root, cached)
    media_error = None
    if ffmpeg and ffprobe:
        try:
            media_smoke(ffmpeg, ffprobe, root)
        except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
            media_error = str(exc)
            ffmpeg = ffprobe = None
    for name, value in [('ffmpeg', ffmpeg), ('ffprobe', ffprobe)]:
        if value is None:
            missing.append(name)
    ffmpeg_source = cached.get('ffmpeg_source')
    if (not ffmpeg or not ffprobe) and not args.check_only:
        ffmpeg_source = install_ffmpeg(root)
        # Use the newly verified archive, not an older broken managed/global pair.
        ffmpeg = ffmpeg or Path(ffmpeg_source['ffmpeg'])
        ffprobe = ffprobe or Path(ffmpeg_source['ffprobe'])
        if not ffmpeg or not ffprobe:
            raise RuntimeError('FFmpeg installation did not produce both executables.')
        media_smoke(ffmpeg, ffprobe, root)
        installed.append('FFmpeg / ffprobe')
    model = None
    if executable:
        model = find_model(executable, model_candidates(root, search_root, cached, args.model_dir))
    if model is None:
        missing.append('转写模型（缺失或尚不能验证）')
        if not args.check_only:
            model = install_model(root, executable)
            installed.append('Whisper small 模型')
    ready = bool(executable and ffmpeg and ffprobe and model)
    config = {'schema_version': 1, 'python': str(executable) if executable else None,
              'ffmpeg': str(ffmpeg) if ffmpeg else None, 'ffprobe': str(ffprobe) if ffprobe else None,
              'model_dir': str(model) if model else None, 'python_info': py_info,
              'ffmpeg_source': ffmpeg_source, 'verified_at': time.strftime('%Y-%m-%dT%H:%M:%S%z')}
    if ready and not args.check_only:
        write_json(root / 'runtime.json', config)
    status = ('installed' if installed else 'ready') if ready else 'missing'
    report = {'ok': ready, 'status': status, 'missing_before': missing, 'installed': installed,
              'check_only': args.check_only, 'runtime_dir': str(root), 'components': config,
              'message': ('缺少的组件已安装配置并通过可用性检查。' if installed else '本地必需依赖齐全，没有缺少，无需安装。')
              if ready else '发现缺项，检查模式未安装；运行正式初始化可自动补齐。',
              'verification_scope': '程序调用、音频解码、模型加载及静音推理；不认证识别准确率或人工听审。'}
    write_json(root / 'initialization-report.json', report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runtime-dir', type=Path, default=runtime_root())
    parser.add_argument('--search-root', type=Path, default=Path.cwd())
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--python-installed', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    # Exclusive lock prevents concurrent pip/download/config writes. No stale lock is auto-deleted.
    lock = None
    try:
        args.runtime_dir.mkdir(parents=True, exist_ok=True)
        lock_path = args.runtime_dir / 'initialize.lock'
        lock = lock_path.open('x', encoding='utf-8')
        lock.write(str(os.getpid()))
        lock.flush()
        report = initialize(args)
        print(json.dumps(report, ensure_ascii=False))
        return 0 if report['ok'] else 2
    except Exception as exc:
        report = {'ok': False, 'status': 'failed', 'error': str(exc),
                  'message': '初始化未完成，未将环境标为齐全；已有环境保留。'}
        if lock:
            write_json(args.runtime_dir / 'initialization-report.json', report)
        print(json.dumps(report, ensure_ascii=False), file=sys.stderr)
        return 1
    finally:
        if lock:
            lock.close()
            lock_path.unlink()


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())

