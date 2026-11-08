#!/usr/bin/env python3
"""Validate four active libraries, legacy evidence and verified performance mappings."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import library as demo
import studio

PERSON = 'chu-ruixue'


def identity(value, field):
    demo.require(isinstance(value, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value),
                 f'{field}: invalid ID')


def number(value, field):
    demo.require(type(value) in (int, float) and math.isfinite(value) and value >= 0,
                 f'{field}: expected nonnegative finite seconds')


def choice_list(value, allowed, field):
    demo.strings(value, field, True)
    demo.require(len(value) == len(set(value)) and set(value) <= allowed, f'{field}: invalid values')


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def normalized(value):
    return re.sub(r'\W+', '', value, flags=re.UNICODE).casefold()


def nullable_text(value, field):
    if value is not None:
        demo.text(value, field)


def validate_expression(record):
    key = record['id']
    demo.require('banks' not in record and 'meaning_tags' not in record,
                 f'{key}: v2 uses expression instead of separate general/language banks')
    expression = record.get('expression')
    demo.require(isinstance(expression, dict), f'{key}: missing expression')
    demo.require(expression.get('status') in {'ready', 'pending'}, f'{key}: invalid expression status')
    for field in ('intent', 'placement', 'pending_reason'):
        demo.require(field in expression, f'{key}.expression: missing {field}')
        nullable_text(expression[field], f'{key}.expression.{field}')
    for field in ('tone_tags', 'keywords', 'paraphrases', 'exclusions'):
        demo.strings(expression.get(field), f'{key}.expression.{field}')
        demo.require(len(expression[field]) == len(set(expression[field])),
                     f'{key}.expression.{field}: duplicate values')
    if expression['status'] == 'ready':
        for field in ('intent', 'placement'):
            demo.text(expression[field], f'{key}.expression.{field}')
        for field in ('tone_tags', 'keywords'):
            demo.require(bool(expression[field]), f'{key}.expression.{field}: ready mapping needs values')
        demo.require(expression['pending_reason'] is None, f'{key}: ready mapping cannot have a pending reason')
    else:
        demo.text(expression['pending_reason'], f'{key}.expression.pending_reason')
    return expression


def collect_performance(root):
    base = root / 'performance-library'
    data = demo.load(base / 'sources.json')
    demo.require(isinstance(data, dict) and data.get('schema_version') == 1 and
                 data.get('person_id') == PERSON and isinstance(data.get('sources'), list),
                 'invalid performance source registry')
    sources = {}
    hashes = {}
    for source in data['sources']:
        demo.require(isinstance(source, dict), 'source must be an object')
        key = source.get('id')
        identity(key, 'source.id')
        identity(source.get('family_id'), 'source.family_id')
        demo.require(key not in sources, f'duplicate source: {key}')
        demo.require(source.get('kind') == 'real_person', f'{key}: only real-person evidence is allowed')
        for field in ('identity_basis', 'description', 'observation_method'):
            demo.text(source.get(field), f'{key}.{field}')
        demo.strings(source.get('limitations'), f'{key}.limitations')
        link = source.get('source_url')
        demo.require(link is None or isinstance(link, str) and re.fullmatch(r'https?://[^\s]+', link),
                     f'{key}: invalid source URL')
        media = source.get('media_path')
        demo.text(media, f'{key}.media_path')
        demo.asset(base, media, f'{key}.media_path')
        demo.require(Path(media).parts[:2] == ('sources', key) and
                     Path(media).suffix.lower() in {'.mp4', '.mov', '.mkv', '.webm', '.avi', '.m4v'},
                     f'{key}: save actual video under sources/ID/')
        checksum = source.get('sha256')
        demo.require(isinstance(checksum, str) and re.fullmatch(r'[a-f0-9]{64}', checksum),
                     f'{key}: invalid SHA256')
        demo.require(digest(base / media) == checksum, f'{key}: source hash mismatch')
        if checksum in hashes:
            demo.require(hashes[checksum] == source['family_id'], f'{key}: identical source cannot be independent')
        hashes[checksum] = source['family_id']
        number(source.get('duration_seconds'), f'{key}.duration_seconds')
        demo.require(source['duration_seconds'] > 0, f'{key}: source duration must be positive')
        demo.require('source_start_seconds' in source, f'{key}: declare source start or null')
        if source['source_start_seconds'] is not None:
            number(source['source_start_seconds'], f'{key}.source_start_seconds')
        demo.require(source.get('audio_state') in {'original', 'absent'}, f'{key}: invalid audio state')
        sources[key] = source

    rows = []
    entries = base / 'entries'
    for path in sorted(entries.rglob('record.json')):
        demo.require(path.parent.parent == entries and path.resolve().is_relative_to(base.resolve()),
                     f'invalid record location: {path}')
        record = demo.load(path)
        demo.require(isinstance(record, dict), 'performance record must be an object')
        key = record.get('id')
        identity(key, 'record.id')
        demo.require(path.parent.name == key, 'record ID must match its directory')
        demo.require(record.get('schema_version') == 2 and record.get('record_type') == 'performance'
                     and record.get('person_id') == PERSON, f'{key}: invalid record type/person/version')
        demo.require(type(record.get('enabled')) is bool, f'{key}: enabled must be boolean')
        for field in ('title', 'summary'):
            demo.text(record.get(field), f'{key}.{field}')
        for field in ('created_on', 'updated_on'):
            demo.date(record.get(field), f'{key}.{field}')
        demo.require(record['updated_on'] >= record['created_on'], f'{key}: dates out of order')
        expression = validate_expression(record)
        choice_list(record.get('modes'), {'talk', 'use'}, f'{key}.modes')
        for field in ('tags', 'avoid'):
            demo.strings(record.get(field), f'{key}.{field}')
        demo.strings(record.get('preconditions'), f'{key}.preconditions', True)
        demo.require(record.get('evidence_status') in {'example', 'repeated_observation'}, f'{key}: invalid evidence status')
        performance = record.get('performance')
        demo.require(isinstance(performance, dict), f'{key}: missing performance')
        for field in ('start_state', 'movement', 'gaze_expression', 'rhythm', 'recovery', 'end_state'):
            demo.text(performance.get(field), f'{key}.performance.{field}')
        observations = record.get('observations')
        demo.require(isinstance(observations, list) and observations, f'{key}: missing observations')
        families = set()
        seen = set()
        reviewed_utterances = []
        for observation in observations:
            demo.require(isinstance(observation, dict), f'{key}: invalid observation')
            source_id = observation.get('source_id')
            demo.require(isinstance(source_id, str) and source_id in sources, f'{key}: unknown source')
            source = sources[source_id]
            start, end = observation.get('start_seconds'), observation.get('end_seconds')
            number(start, f'{key}.start_seconds')
            number(end, f'{key}.end_seconds')
            demo.require(start < end <= source['duration_seconds'], f'{key}: observation outside source interval')
            interval = (source_id, start, end)
            demo.require(interval not in seen, f'{key}: duplicate observation')
            seen.add(interval)
            families.add(source['family_id'])
            for field in ('context', 'observed_sequence'):
                demo.text(observation.get(field), f'{key}.{field}')
            utterance, review, alignment = (observation.get(f) for f in ('utterance', 'speech_review', 'alignment'))
            demo.require(utterance is None or isinstance(utterance, str) and utterance.strip(), f'{key}: invalid utterance')
            demo.require(review in {'heard', 'reviewed_asr', 'unreviewed_asr', 'unavailable'}, f'{key}: invalid speech review')
            demo.require(alignment in {'reviewed', 'approximate', 'unavailable'}, f'{key}: invalid alignment')
            if source['audio_state'] == 'absent' or review == 'unavailable':
                demo.require(review == 'unavailable' and utterance is None and alignment == 'unavailable',
                             f'{key}: unavailable speech cannot carry a transcript or alignment')
            else:
                demo.text(utterance, f'{key}.utterance')
            for field in ('tone', 'relationship'):
                demo.require(field in observation, f'{key}: observation missing {field}')
                nullable_text(observation[field], f'{key}.observation.{field}')
            if expression['status'] == 'ready':
                demo.require(review in {'heard', 'reviewed_asr'} and alignment in {'reviewed', 'approximate'},
                             f'{key}: ready mapping needs reviewed speech/alignment')
                demo.text(observation['tone'], f'{key}.observation.tone')
                demo.text(observation['relationship'], f'{key}.observation.relationship')
                reviewed_utterances.append(normalized(utterance))
        if expression['status'] == 'ready':
            for keyword in expression['keywords']:
                term = normalized(keyword)
                demo.require(term and any(term in utterance for utterance in reviewed_utterances),
                             f'{key}: keyword {keyword!r} absent from reviewed speech; put expansions in paraphrases')
        if record['evidence_status'] == 'repeated_observation':
            demo.require(len(families) >= 2, f'{key}: repeated behavior needs independent source families')
        for sheet in record.get('review_notes', {}).get('evidence_sheets', []):
            demo.asset(base, sheet, f'{key}.evidence_sheet')
        row = {field: record[field] for field in ('id', 'title', 'summary', 'enabled', 'modes', 'tags',
                                                  'expression', 'evidence_status', 'preconditions', 'avoid')}
        row.update(path=path.relative_to(base).as_posix(), source_ids=sorted({o['source_id'] for o in observations}),
                   independent_families=len(families), observation_count=len(observations),
                   eligible_for_arrangement=record['enabled'] and expression['status'] == 'ready',
                   movement=performance['movement'], gaze_expression=performance['gaze_expression'],
                   recovery=performance['recovery'])
        rows.append(row)
    return {'schema_version': 2, 'library': 'performance', 'person_id': PERSON, 'entries': rows}, len(sources)


def run(root, command):
    root = root.resolve()
    demo.require(root.is_dir(), 'skill root does not exist')
    # Validate all content before rebuilding either index.
    records = demo.collect(root)
    performance, sources = collect_performance(root)
    new_pairs, new_stats = studio.indexes(root)
    demo.check_links(root, rebuilding=command == 'reindex')
    pairs = [(root / 'demo-library/index.json', demo.index_data(root, 'demo', records['demo'])),
             (root / 'performance-library/index.json', performance), *new_pairs]
    for path, expected in pairs:
        if command == 'reindex':
            demo.atomic_json(path, expected)
        else:
            demo.require(path.is_file() and demo.load(path) == expected, f'{path.name}: index stale; run reindex')
    return {'demo_records': len(records['demo']), 'demo_units': sum(len(r['units']) for _, r in records['demo']),
            'performance_records': len(performance['entries']), 'performance_sources': sources,
            'ready_mappings': sum(r['eligible_for_arrangement'] for r in performance['entries']),
            'pending_mappings': sum(r['expression']['status'] == 'pending' for r in performance['entries']), **new_stats}


def performances(root, mode=None, intent=None, query=None, include_pending=False):
    index, _ = collect_performance(root)
    query_normalized = normalized(query or '')
    rows = []
    for row in index['entries']:
        expression = row['expression']
        if not row['enabled'] or not (row['eligible_for_arrangement'] or include_pending):
            continue
        if mode and mode not in row['modes']:
            continue
        if intent and normalized(expression['intent'] or '') != normalized(intent):
            continue
        row['matched_keywords'] = [word for word in expression['keywords']
                                   if normalized(word) and normalized(word) in query_normalized]
        row['matched_paraphrases'] = [word for word in expression['paraphrases']
                                     if normalized(word) and normalized(word) in query_normalized]
        rows.append(row)
    rows.sort(key=lambda r: (not r['eligible_for_arrangement'],
                            -len(r['matched_keywords']) - len(r['matched_paraphrases']), r['id']))
    return {'candidates': rows, 'count': len(rows), 'candidates_only': True,
            'note': '词面匹配仅帮助召回；完整语义、否定/引用、语气、持物和前后状态由导演判断。保留同类全部候选供近义判断，待补全不可作为已核实关联编排。'}


def review(root, output):
    import performance_review
    index, source_count = collect_performance(root)
    base = root / 'performance-library'
    output = (output or base / 'review.html').resolve()
    demo.require(output.is_relative_to(base.resolve()) and output.suffix.lower() == '.html',
                 'review output must be an HTML file inside performance-library')
    sources = {s['id']: s for s in demo.load(base / 'sources.json')['sources']}
    records = [(row, demo.load(base / row['path'])) for row in index['entries']]
    performance_review.render(base, output, records, sources)
    return {'output': str(output), **studio.review(root), 'records': len(records), 'sources': source_count,
            'ready_mappings': sum(row['eligible_for_arrangement'] for row in index['entries'])}


def units(root, mode, category, product_id):
    result = studio.actions(root, product_id=product_id, mode=mode, category_filter=category)
    return {**result, 'units': result['candidates'], 'count': len(result['candidates']),
            'note': 'Compatibility entrypoint now uses the shared action library. Drafts and unknown fields require review.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['validate', 'reindex', 'units', 'performances', 'review'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--mode', choices=['talk', 'use'])
    parser.add_argument('--category')
    parser.add_argument('--product-id')
    parser.add_argument('--intent', help='Expression category to inspect; semantics are judged by the director')
    parser.add_argument('--text', help='Current utterance; lexical hits do not automatically select actions')
    parser.add_argument('--include-pending', action='store_true', help='Inspect unfinished mappings as well')
    parser.add_argument('--output', type=Path, help='Review HTML path inside performance-library')
    args = parser.parse_args()
    try:
        if args.command == 'units':
            demo.require(args.mode is not None, 'units requires --mode')
            result = units(args.root.resolve(), args.mode, args.category, args.product_id)
        elif args.command == 'performances':
            result = performances(args.root.resolve(), args.mode, args.intent, args.text, args.include_pending)
        elif args.command == 'review':
            result = review(args.root.resolve(), args.output)
        else:
            result = run(args.root, args.command)
        print(json.dumps({'ok': True, 'command': args.command, **result}, ensure_ascii=False, allow_nan=False))
        return 0
    except (demo.Invalid, OSError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
