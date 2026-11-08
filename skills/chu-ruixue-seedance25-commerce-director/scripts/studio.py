#!/usr/bin/env python3
"""Four-library records, conservative retrieval and non-destructive legacy migration."""
from __future__ import annotations

import argparse
import hashlib
import html
import json
from pathlib import Path
import re
import sys

sys.dont_write_bytecode = True
import library as legacy

KINDS = ('product', 'script', 'action')
DIMENSIONS = ('category', 'texture', 'packaging', 'body_part', 'purpose')
FACTS = ('packaging', 'net_content', 'dimensions', 'contents', 'texture', 'usage',
         'body_parts', 'finish', 'selling_points')
PROVENANCE = {'user_interview', 'user_authored', 'video_analysis', 'authored_method', 'legacy_migration'}
require, strings, text = legacy.require, legacy.strings, legacy.text


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def ident(value, field='id'):
    require(isinstance(value, str) and re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', value), f'{field}: invalid ID')


def options(value, allowed, field, nonempty=False):
    strings(value, field, nonempty)
    require(len(value) == len(set(value)) and set(value) <= set(allowed), f'{field}: invalid options')


def category(value):
    require(isinstance(value, dict), 'category: expected object')
    require(value.get('basis') in {'user_confirmed', 'document_confirmed', 'legacy', 'unknown'}, 'category: invalid basis')
    require(value.get('value') is None or isinstance(value['value'], str) and value['value'].strip(), 'category: invalid value')
    if value['basis'] != 'unknown':
        text(value['value'], 'category.value')


def source(root, value):
    legacy.asset(root, value, 'source path')


def common(root, path, record, kind):
    require(isinstance(record, dict), 'record must be an object')
    require(record.get('schema_version') == 1 and record.get('record_type') == kind, f'{path}: invalid schema/type')
    ident(record.get('id'))
    require(path.parent.name == record['id'], f'{path}: directory/ID mismatch')
    text(record.get('title'), 'title')
    require(type(record.get('enabled')) is bool, 'enabled must be boolean')
    require(record.get('status') in {'draft', 'ready'}, 'invalid status')
    for key in ('created_on', 'updated_on'):
        legacy.date(record.get(key), key)
    require(record['created_on'] <= record['updated_on'], 'dates out of order')
    p = record.get('provenance')
    require(isinstance(p, dict) and p.get('kind') in PROVENANCE, 'invalid provenance')
    text(p.get('basis'), 'provenance.basis')
    strings(p.get('source_refs'), 'source_refs')
    strings(p.get('limitations'), 'limitations')
    for ref in p['source_refs']:
        source(root, ref)
    if p['kind'] == 'video_analysis':
        require(bool(p['source_refs']), 'video analysis needs source evidence')
    require(record.get('generation_status') in {'untested', 'tested'}, 'invalid generation status')
    strings(record.get('generation_evidence'), 'generation_evidence')
    for ref in record['generation_evidence']:
        source(root, ref)
    if record['generation_status'] == 'tested':
        require(bool(record['generation_evidence']), 'tested needs actual evidence')
    require(isinstance(record.get('history'), list), 'history must be a list')


def validate_product(record):
    require(record.get('role') in {'target', 'reference_only'}, 'invalid product role')
    strings(record.get('aliases'), 'aliases')
    hashes = record.get('reference_hashes')
    require(isinstance(hashes, list) and len(hashes) == len(set(hashes)) and
            all(isinstance(v, str) and re.fullmatch('[a-f0-9]{64}', v) for v in hashes), 'invalid image hashes')
    category(record.get('category'))
    facts = record.get('facts')
    require(isinstance(facts, dict) and set(FACTS) <= facts.keys(), 'missing product facts')
    for key in FACTS:
        fact = facts[key]
        require(isinstance(fact, dict) and fact.get('status') in {'confirmed', 'observed', 'unknown'}, f'fact {key}: invalid')
        require('value' in fact, f'fact {key}: missing value')
        text(fact.get('basis'), f'fact {key}.basis')
        if fact['status'] != 'unknown':
            require(fact['value'] not in (None, '', []), f'fact {key}: known value missing')
    fields = record.get('match_fields')
    require(isinstance(fields, dict), 'match_fields missing')
    for key in ('texture', 'packaging', 'body_part'):
        require(key in fields, f'match_fields missing {key}')
        if fields[key] is not None:
            strings(fields[key], f'match_fields.{key}', True)
    rules = record.get('rules')
    require(isinstance(rules, list), 'rules must be list')
    seen = set()
    for rule in rules:
        ident(rule.get('id'), 'rule.id')
        require(rule['id'] not in seen, 'duplicate rule')
        seen.add(rule['id'])
        for key in ('text', 'trigger', 'basis'):
            text(rule.get(key), f'rule.{key}')
        require(rule.get('status') in {'confirmed', 'pending'}, 'invalid rule status')
        options(rule.get('modes'), {'talk', 'use'}, 'rule.modes', True)
    interview = record.get('interview')
    require(isinstance(interview, dict) and type(interview.get('complete')) is bool, 'invalid interview')
    strings(interview.get('asked'), 'interview.asked')
    strings(interview.get('missing_core'), 'interview.missing_core')
    require(interview.get('supplement_answer') is None or isinstance(interview['supplement_answer'], str), 'invalid supplement answer')
    if interview['complete']:
        text(interview['supplement_answer'], 'interview final answer')
    if record['status'] == 'ready' and record['role'] == 'target':
        require(record['category']['basis'] in {'user_confirmed', 'document_confirmed'}, 'ready product needs confirmed category')
        require(interview['complete'] and not interview['missing_core'], 'ready product has unfinished core interview')
        require(facts['usage']['status'] != 'unknown', 'ready product needs usage')


def validate_action(root, record, products):
    options(record.get('modes'), {'talk', 'use'}, 'action.modes', True)
    category(record.get('source_category'))
    fields = record.get('applicability')
    require(isinstance(fields, dict) and set(fields) == set(DIMENSIONS), 'action needs all five applicability fields')
    for key, field in fields.items():
        require(isinstance(field, dict) and field.get('mode') in {'constrained', 'unrestricted', 'unknown'}, f'{key}: invalid match mode')
        strings(field.get('values'), key, field['mode'] == 'constrained')
        text(field.get('basis'), f'{key}.basis')
        if field['mode'] != 'constrained':
            require(not field['values'], f'{key}: values only allowed for constrained fields')
    strings(record.get('approved_product_ids'), 'approved_product_ids')
    require(set(record['approved_product_ids']) <= products.keys(), 'action has unknown product association')
    sequence = record.get('sequence')
    require(isinstance(sequence, dict), 'action sequence missing')
    strings(sequence.get('start_conditions'), 'start_conditions', True)
    strings(sequence.get('avoid'), 'avoid')
    for key in ('action', 'transition', 'end_state', 'expected_effect'):
        text(sequence.get(key), f'sequence.{key}')
    ref = record.get('legacy_ref')
    if ref is not None:
        source(root, ref.get('record_path'))
        old = legacy.load(root / ref['record_path'])
        require(any(u['id'] == ref.get('unit_id') for u in old['units']), 'legacy unit not found')
    if record.get('migration_needs_review'):
        require(record['status'] == 'draft', 'unreviewed migration cannot be ready')


def validate_script(record, products, actions):
    options(record.get('modes'), {'talk', 'use'}, 'script.modes', True)
    strings(record.get('categories'), 'categories')
    strings(record.get('product_ids'), 'product_ids')
    require(set(record['product_ids']) <= products.keys(), 'script references unknown product')
    category(record.get('source_category'))
    for key in ('goal', 'adaptation_notes'):
        text(record.get(key), key)
    for key in ('source_sequence', 'initial_state_satisfies', 'maintained_states'):
        strings(record.get(key), key)
    stages = record.get('stages')
    require(isinstance(stages, list) and stages, 'script needs stages')
    by_id = {}
    for stage in stages:
        ident(stage.get('id'), 'stage.id')
        require(stage['id'] not in by_id, 'duplicate stage')
        by_id[stage['id']] = stage
        require(type(stage.get('required')) is bool, 'stage.required must be boolean')
        for key in ('goal', 'entry_state', 'exit_state'):
            text(stage.get(key), f'stage.{key}')
        for key in ('depends_on', 'audio_intents', 'action_options', 'carry_forward', 'acceptance'):
            strings(stage.get(key), f'stage.{key}', key == 'acceptance')
        require(set(stage['action_options']) <= actions.keys(), 'script has unknown action reference')
    visiting, done = set(), set()
    def visit(key):
        require(key in by_id, f'unknown dependency: {key}')
        require(key not in visiting, 'script dependency cycle')
        if key in done:
            return
        visiting.add(key)
        for dep in by_id[key]['depends_on']:
            visit(dep)
        visiting.remove(key)
        done.add(key)
    for key in by_id:
        visit(key)
    require(type(record.get('effect_required')) is bool, 'effect_required must be boolean')
    strings(record.get('effect_stage_ids'), 'effect_stage_ids', record['effect_required'])
    for key in record['effect_stage_ids']:
        require(key in by_id and by_id[key]['required'], 'effect stage must exist and be required')
    if record['effect_required']:
        strings(record['maintained_states'], 'effect maintained_states', True)


def validate_failure(root, path, record, products, scripts, actions):
    require(record.get('schema_version') == 1 and record.get('record_type') == 'failure', 'invalid failure schema')
    ident(record.get('id'))
    require(path.stem == record['id'], 'failure filename mismatch')
    pid = record.get('product_id')
    require(pid in products and path.parent.parent.name == pid, 'failure product mismatch')
    text(record.get('user_problem'), 'user_problem')
    legacy.date(record.get('created_on'), 'failure.created_on')
    for key in ('observations', 'hypotheses', 'proposed_changes', 'unknowns', 'related_script_ids', 'related_action_ids'):
        strings(record.get(key), key)
    require(set(record['related_script_ids']) <= scripts.keys(), 'failure unknown script')
    require(set(record['related_action_ids']) <= actions.keys(), 'failure unknown action')
    require(isinstance(record.get('input_files'), list), 'input_files missing')
    for f in record['input_files']:
        text(f.get('role'), 'input role')
        source(root, f.get('path'))
        require(f.get('sha256') == sha(root / f['path']), 'failure input hash mismatch')
    require(isinstance(record.get('findings'), list), 'findings missing')
    for f in record['findings']:
        require(f.get('classification') in {'rule_gap', 'script_problem', 'action_mismatch', 'execution_deviation', 'unknown'}, 'invalid finding')
        text(f.get('evidence'), 'finding evidence')
        require(f.get('confidence') in {'confirmed', 'likely', 'uncertain'}, 'invalid confidence')
    require(isinstance(record.get('rule_updates'), list), 'rule_updates missing')
    rules = {r['id']: r for r in products[pid]['rules']}
    for update in record['rule_updates']:
        require(update.get('reason_kind') in {'user_requirement', 'verified_product_fact'}, 'hypotheses cannot become formal rules')
        text(update.get('basis'), 'rule update basis')
        require(update.get('rule_id') in rules and rules[update['rule_id']]['status'] == 'confirmed', 'rule update must reference a confirmed rule')
    require(isinstance(record.get('attempts'), list), 'attempts missing')
    for attempt in record['attempts']:
        require(attempt.get('outcome') in {'untested', 'failed', 'improved', 'succeeded'}, 'invalid attempt outcome')
        strings(attempt.get('changes'), 'attempt.changes')
        strings(attempt.get('evidence_refs'), 'attempt.evidence_refs')
        strings(attempt.get('scope'), 'attempt.scope')
        if attempt['outcome'] != 'untested':
            require(bool(attempt['evidence_refs']), 'tested attempt needs evidence')
        for ref in attempt['evidence_refs']:
            source(root, ref)


def collect(root):
    root = Path(root).resolve()
    result = {kind: {} for kind in KINDS}
    for kind in KINDS:
        base = root / f'{kind}-library/entries'
        for path in sorted(base.rglob('record.json')):
            require(path.parent.parent == base and path.resolve().is_relative_to(base.resolve()), 'invalid record location')
            record = legacy.load(path)
            common(root, path, record, kind)
            require(record['id'] not in result[kind], 'duplicate record id')
            result[kind][record['id']] = record
    for record in result['product'].values():
        validate_product(record)
    bound = {}
    for record in result['product'].values():
        if record['role'] == 'target' and record['enabled']:
            for checksum in record['reference_hashes']:
                require(checksum not in bound, f'product image bound twice: {record["id"]}')
                bound[checksum] = record['id']
    for record in result['action'].values():
        validate_action(root, record, result['product'])
    for record in result['script'].values():
        validate_script(record, result['product'], result['action'])
    failures = []
    for path in sorted((root / 'product-library/entries').glob('*/failures/*.json')):
        require(path.resolve().is_relative_to((root / 'product-library').resolve()), 'failure escapes library')
        record = legacy.load(path)
        validate_failure(root, path, record, result['product'], result['script'], result['action'])
        failures.append({**record, 'path': path.relative_to(root).as_posix()})
    result['failure'] = failures
    return result


def indexes(root):
    data = collect(root)
    pairs = []
    for kind in KINDS:
        entries = []
        for record in data[kind].values():
            row = dict(record)
            row['path'] = f'{kind}-library/entries/{record["id"]}/record.json'
            if kind == 'product':
                row['failure_cases'] = [{'id': f['id'], 'path': f['path']} for f in data['failure'] if f['product_id'] == record['id']]
            entries.append(row)
        pairs.append((Path(root) / f'{kind}-library/index.json', {'schema_version': 1, 'library': kind, 'entries': entries}))
    return pairs, {f'{k}_records': len(v) for k, v in data.items()}


def run(root, command):
    pairs, stats = indexes(root)
    for path, expected in pairs:
        if command == 'reindex':
            legacy.atomic_json(path, expected)
        else:
            require(path.is_file() and legacy.load(path) == expected, f'{path}: index stale')
    return stats


def resolve_product(root, product_id=None, image=None):
    products = collect(root)['product']
    if product_id:
        require(product_id in products, 'Product not registered; ask user or start interview.')
        record = products[product_id]
        require(record['enabled'] and record['role'] == 'target', 'Reference-only or disabled product is not a target; ask user.')
        if image:
            checksum = sha(image)
            others = [p['id'] for p in products.values() if p['enabled'] and p['role'] == 'target'
                      and checksum in p['reference_hashes'] and p['id'] != product_id]
            require(not others, 'Named product conflicts with image binding; ask user.')
        return record
    require(image is not None, 'Specify target product or image; do not guess category.')
    checksum = sha(image)
    matches = [p for p in products.values() if p['enabled'] and p['role'] == 'target' and checksum in p['reference_hashes']]
    require(len(matches) == 1, 'Image does not identify exactly one target product; ask user.')
    return matches[0]


def bind(root, product_id, image):
    product = resolve_product(root, product_id, image)
    checksum = sha(image)
    if checksum not in product['reference_hashes']:
        product['reference_hashes'].append(checksum)
        legacy.atomic_json(Path(root) / f'product-library/entries/{product_id}/record.json', product)
    run(root, 'reindex')
    return {'product_id': product_id, 'sha256': checksum}


def actions(root, product_id=None, mode=None, category_filter=None, body_part=None, purpose=None, include_drafts=True):
    data = collect(root)
    product = resolve_product(root, product_id) if product_id else None
    values = {key: None for key in DIMENSIONS}
    if product:
        values['category'] = [product['category']['value']] if product['category']['value'] else None
        values.update(product['match_fields'])
    if category_filter:
        if product and values['category']:
            require(category_filter in values['category'], 'Category conflicts with target product profile.')
        values['category'] = [category_filter]
    if body_part:
        if product and values['body_part']:
            require(body_part in values['body_part'], 'Requested body part conflicts with product profile.')
        values['body_part'] = [body_part]
    if purpose:
        values['purpose'] = [purpose]
    candidates, excluded = [], []
    for record in data['action'].values():
        if not record['enabled'] or (not include_drafts and record['status'] != 'ready'):
            continue
        reasons, needs = [], []
        if mode and mode not in record['modes']:
            reasons.append('mode mismatch')
        for key in DIMENSIONS:
            condition, current = record['applicability'][key], values[key]
            if condition['mode'] == 'unrestricted':
                continue
            if key == 'category' and product_id in record['approved_product_ids']:
                continue
            if condition['mode'] == 'unknown' or not current:
                needs.append(key + ': unknown applicability or target condition')
            elif not set(condition['values']).intersection(current):
                reasons.append(key + ': tag mismatch; inspect source before any override')
        if record['status'] != 'ready':
            needs.append('draft: review source and applicability before use')
        if product and product['status'] != 'ready':
            needs.append('product interview incomplete')
        row = {**record, 'reasons': reasons, 'needs_review': needs, 'eligible_for_arrangement': not reasons and not needs}
        (excluded if reasons else candidates).append(row)
    return {'candidates': candidates, 'excluded': excluded, 'candidates_only': True,
            'note': 'Tags shortlist candidates; inspect physical conditions, source and audio. Unknown is not unrestricted.'}


def scripts(root, product_id, mode=None, include_drafts=True):
    data = collect(root)
    product = resolve_product(root, product_id)
    rows = []
    for record in data['script'].values():
        if not record['enabled'] or mode and mode not in record['modes']:
            continue
        if not include_drafts and record['status'] != 'ready':
            continue
        if record['product_ids'] and product_id not in record['product_ids']:
            continue
        if record['categories'] and product['category']['value'] not in record['categories'] and product_id not in record['product_ids']:
            continue
        needs = []
        if record['status'] == 'draft':
            needs.append('script draft')
        if product['status'] == 'draft':
            needs.append('product interview incomplete')
        rows.append({**record, 'needs_review': needs})
    return {'candidates': rows, 'candidates_only': True, 'note': 'Reorder flexible stages using actual audio; preserve dependencies and final states.'}


def provenance(kind, basis, refs=None, limitations=None):
    return {'kind': kind, 'basis': basis, 'source_refs': refs or [], 'limitations': limitations or []}


def base(kind, key, title, date, p):
    return {'schema_version': 1, 'record_type': kind, 'id': key, 'title': title, 'enabled': True,
            'status': 'draft', 'created_on': date, 'updated_on': date, 'provenance': p,
            'generation_status': 'untested', 'generation_evidence': [], 'history': []}


def migrate(root):
    root = Path(root)
    created, preserved, conflicts = [], [], []
    def save(kind, record, source_path):
        target = root / f'{kind}-library/entries/{record["id"]}/record.json'
        record['migration_source_sha256'] = sha(source_path)
        if target.exists():
            existing = legacy.load(target)
            if existing.get('migration_source_sha256') != record['migration_source_sha256']:
                conflicts.append(target.relative_to(root).as_posix())
            else:
                preserved.append(record['id'])
            return
        legacy.atomic_json(target, record)
        created.append(record['id'])
    registry = root / 'demo-library/products.json'
    for old in legacy.products(root):
        record = base('product', old['id'], old['name'], '2026-11-08',
                      provenance('legacy_migration', '旧对标产品登记，不自动视为用户新品。', ['demo-library/products.json'], ['需主动采访确认目标产品身份与规则。']))
        record.update(role='reference_only', aliases=[], reference_hashes=old.get('reference_hashes', []),
                      category={'value': old['category'], 'basis': 'legacy'},
                      facts={key: {'value': None, 'status': 'unknown', 'basis': '尚未采访'} for key in FACTS},
                      match_fields={key: None for key in ('texture', 'packaging', 'body_part')}, rules=[],
                      interview={'asked': [], 'missing_core': ['目标产品身份', '品类确认', '用法与效果', '包装规格'], 'supplement_answer': None, 'complete': False})
        record['facts']['packaging'] = {'value': old.get('description') or None, 'status': 'observed' if old.get('description') else 'unknown', 'basis': '旧来源登记，非本次重新观察'}
        save('product', record, registry)
    for path, old in legacy.collect(root)['demo']:
        ref = path.relative_to(root).as_posix()
        for unit in old['units']:
            key = 'action-' + old['id'].removeprefix('demo-') + '-' + unit['id']
            record = base('action', key, unit['name'], old['updated_on'], provenance('legacy_migration',
                          '迁移旧动作事实与来源；未重新观看或验证五类适用标签。', [ref], old['provenance']['limitations']))
            record.update(modes=old['modes'], source_category={'value': old['category'], 'basis': 'legacy'},
                          approved_product_ids=[], migration_needs_review=True,
                          applicability={key: {'mode': 'unknown', 'values': [], 'basis': '迁移后需根据动作核查；不把未知当不限。'} for key in DIMENSIONS},
                          sequence={key: unit[key] for key in ('start_conditions', 'action', 'transition', 'end_state', 'expected_effect', 'avoid')},
                          legacy_ref={'record_path': ref, 'unit_id': unit['id']},
                          legacy_context={key: old.get(key) for key in ('category', 'product_form', 'container', 'body_part', 'product_id', 'scope')},
                          source_time=unit.get('source_time'))
            record['applicability']['category'] = {'mode': 'constrained', 'values': [old['category']], 'basis': '沿用旧分类，仅召回候选；新增入库按用户确认分类。'}
            save('action', record, path)
    stats = run(root, 'reindex')
    return {**stats, 'created': created, 'preserved': preserved, 'conflicts': conflicts}


def review(root):
    root = Path(root)
    data = collect(root)
    parts = ['<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>四库清单</title>',
             '<style>body{font:16px system-ui;max-width:1100px;margin:32px auto;padding:0 16px;line-height:1.6}table{border-collapse:collapse;width:100%}td,th{text-align:left;border-bottom:1px solid #aaa;padding:8px;overflow-wrap:anywhere}a{color:#1763a0}</style>',
             '<h1>初瑞雪专用导演 · 四库清单</h1><p>draft/待核查不等于可自动编排；结构校验不等于生成验证。</p>']
    for kind, label in [('product', '产品规则'), ('script', '完整脚本'), ('action', '动作参考')]:
        parts.append(f'<h2>{label} · {len(data[kind])}</h2><table><tr><th>记录</th><th>状态</th><th>来源/身份</th></tr>')
        for r in data[kind].values():
            path = f'{kind}-library/entries/{r["id"]}/record.json'
            parts.append('<tr><td><a href="' + html.escape(path, quote=True) + '">' + html.escape(r['title']) + '</a></td><td>' + html.escape(r['status']) + '</td><td>' + html.escape(r.get('role', r['provenance']['kind'])) + '</td></tr>')
        parts.append('</table>')
    parts.append(f'<h2>失败记录 · {len(data["failure"])}</h2><ul>')
    for f in data['failure']:
        parts.append('<li><a href="' + html.escape(f['path'], quote=True) + '">' + html.escape(f['user_problem']) + '</a></li>')
    parts.append('</ul><h2>初瑞雪人物表现</h2><a href="performance-library/review.html">查看原话、动作与证据状态</a></html>')
    path = root / 'library-review.html'
    path.write_text('\n'.join(parts), encoding='utf-8')
    return {'overview': str(path), **{f'{k}_records': len(v) for k, v in data.items()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['migrate', 'validate', 'reindex', 'review', 'products', 'resolve-product', 'bind-product', 'actions', 'scripts'])
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--product-id')
    parser.add_argument('--image', type=Path)
    parser.add_argument('--mode', choices=['talk', 'use'])
    parser.add_argument('--category')
    parser.add_argument('--body-part')
    parser.add_argument('--purpose')
    parser.add_argument('--ready-only', action='store_true')
    args = parser.parse_args()
    try:
        if args.command in {'validate', 'reindex'}:
            result = run(args.root, args.command)
        elif args.command == 'migrate':
            result = migrate(args.root)
        elif args.command == 'review':
            result = review(args.root)
        elif args.command == 'products':
            result = {'products': list(collect(args.root)['product'].values())}
        elif args.command == 'resolve-product':
            result = {'product': resolve_product(args.root, args.product_id, args.image)}
        elif args.command == 'bind-product':
            require(args.product_id and args.image, 'bind requires product-id and image')
            result = bind(args.root, args.product_id, args.image)
        elif args.command == 'actions':
            result = actions(args.root, args.product_id, args.mode, args.category, args.body_part, args.purpose, not args.ready_only)
        else:
            require(args.product_id, 'scripts requires target product-id')
            result = scripts(args.root, args.product_id, args.mode, not args.ready_only)
        print(json.dumps({'ok': True, **result}, ensure_ascii=False))
        return 0
    except (legacy.Invalid, OSError, KeyError, TypeError, ValueError) as exc:
        print(json.dumps({'ok': False, 'error': str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    raise SystemExit(main())
