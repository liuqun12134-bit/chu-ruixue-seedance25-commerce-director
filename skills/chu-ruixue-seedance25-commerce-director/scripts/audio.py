#!/usr/bin/env python3
"""Local audio inspection, tail silence, silent motion references and optional local ASR."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True


class AudioError(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise AudioError(message)


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def execute(command, stdout=subprocess.PIPE):
    try:
        result = subprocess.run(command, stdin=subprocess.DEVNULL, stdout=stdout, stderr=subprocess.PIPE, check=False)
    except FileNotFoundError as exc:
        raise AudioError(f'Missing executable: {command[0]}') from exc
    if result.returncode:
        raise AudioError(result.stderr.decode('utf-8', errors='replace')[-2000:])
    return result.stdout


def probe(path, args):
    raw = execute([args.ffprobe, '-v', 'error', '-show_format', '-show_streams', '-of', 'json', str(path)])
    return json.loads(raw)


def finite_float(value):
    try:
        parsed = float(value)
        return parsed if math.isfinite(parsed) else None
    except (TypeError, ValueError):
        return None


def audio_streams(meta):
    return [s for s in meta.get('streams', []) if s.get('codec_type') == 'audio']


def choose_audio(meta, requested):
    streams = audio_streams(meta)
    require(bool(streams), 'Input has no audio track.')
    require(requested is not None or len(streams) == 1,
            'Multiple audio tracks: inspect first and choose --audio-index explicitly (zero based).')
    index = 0 if requested is None else requested
    require(0 <= index < len(streams), 'Audio index is outside available tracks.')
    return index, streams[index]


def decode_pcm(path, index, rate, channels, args, stream):
    execute([args.ffmpeg, '-v', 'error', '-nostdin', '-i', str(path), '-map', f'0:a:{index}',
             '-vn', '-ar', str(rate), '-ac', str(channels), '-c:a', 'pcm_s16le', '-f', 's16le', 'pipe:1'], stdout=stream)


def decoded_frames(path, index, stream_info, args):
    rate, channels = int(stream_info['sample_rate']), int(stream_info['channels'])
    require(rate > 0 and channels > 0, 'Invalid audio rate/channels.')
    with tempfile.TemporaryFile() as pcm:
        decode_pcm(path, index, rate, channels, args, pcm)
        size = pcm.tell()
    require(size % (2 * channels) == 0, 'Decoded PCM ends in a partial sample.')
    return size // (2 * channels), rate, channels


def inspect(path, args):
    meta = probe(path, args)
    tracks = []
    for index, stream in enumerate(audio_streams(meta)):
        frames, rate, channels = decoded_frames(path, index, stream, args)
        tracks.append({'audio_index': index, 'codec': stream.get('codec_name'), 'sample_rate': rate,
                       'channels': channels, 'stream_duration_seconds': finite_float(stream.get('duration')),
                       'stream_start_seconds': finite_float(stream.get('start_time')),
                       'decoded_frames': frames, 'decoded_duration_seconds': frames / rate})
    return {'input': str(path), 'sha256': digest(path),
            'container_duration_seconds': finite_float(meta.get('format', {}).get('duration')),
            'audio_tracks': tracks, 'video_track_count': sum(s.get('codec_type') == 'video' for s in meta.get('streams', [])),
            'content_review': 'not_performed', 'note': 'Durations do not establish words, repetition, speech boundaries or lip sync.'}


def destination(path, source):
    result = path.resolve()
    require(result != source, 'Output must differ from input.')
    require(not result.exists(), 'Output already exists; choose a new path.')
    result.parent.mkdir(parents=True, exist_ok=True)
    return result


def commit(temp, output):
    # Exclusive creation also protects against a destination created after the initial check.
    with output.open('xb') as target, temp.open('rb') as source:
        shutil.copyfileobj(source, target)


def pad_tail(path, args):
    require(args.duration is not None and math.isfinite(args.duration) and args.duration > 0,
            'pad-tail needs a positive finite --duration in seconds.')
    require(args.output is not None and args.output.suffix.lower() == '.wav', 'pad-tail needs a new .wav --output.')
    output = destination(args.output, path)
    index, stream = choose_audio(probe(path, args), args.audio_index)
    frames, rate, channels = decoded_frames(path, index, stream, args)
    target_frames = round(args.duration * rate)
    require(target_frames >= frames, 'Target would cut audio; tail padding never shortens or changes speed.')
    with tempfile.TemporaryDirectory(prefix='.audio-', dir=output.parent) as work:
        temp = Path(work) / 'padded.wav'
        execute([args.ffmpeg, '-v', 'error', '-nostdin', '-n', '-i', str(path), '-map', f'0:a:{index}',
                 '-vn', '-af', f'apad=whole_len={target_frames}', '-ar', str(rate), '-ac', str(channels),
                 '-c:a', 'pcm_s16le', str(temp)])
        out_stream = audio_streams(probe(temp, args))[0]
        actual, _, _ = decoded_frames(temp, 0, out_stream, args)
        require(actual == target_frames, 'Padded file did not reach the requested sample length.')
        commit(temp, output)
    return {'input': str(path), 'source_sha256': digest(path), 'audio_index': index,
            'output': str(output), 'output_sha256': digest(output), 'original_decoded_seconds': frames / rate,
            'output_decoded_seconds': target_frames / rate, 'added_silence_seconds': (target_frames - frames) / rate,
            'note': 'Tail silence only; not a proven repetition fix. Source kept intact.'}


def mute_reference(path, args):
    require(args.output is not None and args.output.suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm'},
            'mute-reference needs a new video --output (.mp4/.mov/.mkv/.webm).')
    output = destination(args.output, path)
    require(any(s.get('codec_type') == 'video' for s in probe(path, args).get('streams', [])), 'Input has no video.')
    with tempfile.TemporaryDirectory(prefix='.audio-', dir=output.parent) as work:
        temp = Path(work) / ('muted' + output.suffix.lower())
        execute([args.ffmpeg, '-v', 'error', '-nostdin', '-n', '-i', str(path), '-map', '0:v:0',
                 '-c:v', 'copy', '-an', str(temp)])
        meta = probe(temp, args)
        require(not audio_streams(meta) and any(s.get('codec_type') == 'video' for s in meta.get('streams', [])),
                'Silent reference verification failed.')
        commit(temp, output)
    return {'input': str(path), 'source_sha256': digest(path), 'output': str(output), 'output_sha256': digest(output),
            'audio_track_count': 0, 'note': 'First video track copied without re-encoding; original retained for evidence.'}


def transcribe(path, args):
    require(args.output is not None and args.output.suffix.lower() == '.json', 'transcribe needs a new .json --output.')
    output = destination(args.output, path)
    require(args.model_dir is not None and args.model_dir.is_dir(), 'Use --model-dir with an existing local faster-whisper model.')
    index, _ = choose_audio(probe(path, args), args.audio_index)
    if args.dependency_dir:
        require(args.dependency_dir.is_dir(), '--dependency-dir does not exist.')
        sys.path.insert(0, str(args.dependency_dir.resolve()))
    try:
        import numpy as np
        from faster_whisper import WhisperModel
    except (ImportError, OSError) as exc:
        raise AudioError(f'Local ASR dependency unavailable/incompatible: {exc}. No installation or download attempted.') from exc
    with tempfile.TemporaryFile() as pcm:
        decode_pcm(path, index, 16000, 1, args, pcm)
        pcm.seek(0)
        waveform = np.frombuffer(pcm.read(), dtype='<i2').astype(np.float32) / 32768.0
    require(waveform.size > 0, 'No audio samples decoded.')
    model = WhisperModel(str(args.model_dir.resolve()), device='cpu', compute_type='int8', cpu_threads=6, local_files_only=True)
    segments, info = model.transcribe(waveform, language=args.language, beam_size=5,
                                      word_timestamps=True, condition_on_previous_text=False)
    rows = []
    for segment in segments:
        rows.append({'start': segment.start, 'end': segment.end, 'text': segment.text,
                     'avg_logprob': segment.avg_logprob, 'no_speech_prob': segment.no_speech_prob,
                     'words': [{'start': w.start, 'end': w.end, 'text': w.word, 'probability': w.probability}
                               for w in segment.words or []]})
    result = {'schema_version': 1, 'input': str(path), 'source_sha256': digest(path), 'audio_index': index,
              'model_path': str(args.model_dir.resolve()), 'decoded_seconds_16khz': waveform.size / 16000,
              'language': info.language, 'review_status': 'unreviewed_asr', 'timing_status': 'estimated',
              'note': 'Machine hypothesis only; check uncertain words and repetition against actual sound and lips.', 'segments': rows}
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write('\n')
    return {'output': str(output), 'source_sha256': result['source_sha256'], 'segments': len(rows),
            'review_status': result['review_status'], 'timing_status': result['timing_status']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['inspect', 'pad-tail', 'mute-reference', 'transcribe'])
    parser.add_argument('input', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--duration', type=float)
    parser.add_argument('--audio-index', type=int)
    parser.add_argument('--ffmpeg', default='ffmpeg')
    parser.add_argument('--ffprobe', default='ffprobe')
    parser.add_argument('--model-dir', type=Path)
    parser.add_argument('--dependency-dir', type=Path)
    parser.add_argument('--language', default='zh')
    args = parser.parse_args()
    try:
        path = args.input.resolve()
        require(path.is_file(), 'Input must be an existing local media file.')
        command = {'inspect': inspect, 'pad-tail': pad_tail, 'mute-reference': mute_reference, 'transcribe': transcribe}[args.command]
        result = command(path, args)
        print(json.dumps({'ok': True, 'command': args.command, **result}, ensure_ascii=False, allow_nan=False))
        return 0
    except (AudioError, OSError, ValueError, RuntimeError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
