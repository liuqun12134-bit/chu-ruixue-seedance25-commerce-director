"""Render the unified performance library as an expression-first review table."""
from collections import defaultdict
from html import escape
import os
from pathlib import Path
from urllib.parse import quote


def e(value):
    return escape(str(value), quote=True)


def words(values, empty='待核查'):
    return '、'.join(e(value) for value in values) if values else empty


def relative_url(path, output):
    return quote(Path(os.path.relpath(path, output.parent)).as_posix(), safe='/')


def detail(base, output, record, sources):
    parts = [f'<p class="muted">{e(record["summary"])}</p>']
    expression = record['expression']
    if expression['status'] == 'pending':
        parts.append(f'<p class="notice"><b>待补全原因：</b>{e(expression["pending_reason"])}</p>')
    parts.append('<dl>')
    for key, label in [('start_state', '动作起点'), ('movement', '动作过程'),
                       ('gaze_expression', '目光与表情'), ('rhythm', '节奏依据'),
                       ('recovery', '收回'), ('end_state', '结束状态')]:
        parts.append(f'<dt>{label}</dt><dd>{e(record["performance"][key])}</dd>')
    condition_label = '原记录条件／建议，需结合原声复核' if expression['status'] == 'pending' else '适用条件'
    parts.extend([f'<dt>{condition_label}</dt><dd>{words(record["preconditions"], "—")}</dd>',
                  f'<dt>不适用</dt><dd>{words(record["avoid"], "—")}</dd>',
                  f'<dt>语义排除条件</dt><dd>{words(expression["exclusions"], "—")}</dd></dl>'])
    for observation in record['observations']:
        source = sources[observation['source_id']]
        start, end = observation['start_seconds'], observation['end_seconds']
        media = relative_url(base / source['media_path'], output)
        clip = f'{media}#t={start},{end}'
        verified = observation['speech_review'] in {'heard', 'reviewed_asr'}
        speech_label = '已核查原话' if verified else '待核查文字'
        speech = e(observation['utterance']) if observation['utterance'] else '尚未核查'
        parts.append(f'<div class="observation"><h4>原片证据 · {start:g}–{end:g} 秒</h4>'
                     f'<p>{e(observation["context"])}</p>'
                     f'<p><b>{speech_label}：</b>{speech}</p>'
                     f'<p><b>当时语气：</b>{e(observation.get("tone") or "待核查")}</p>'
                     f'<p><b>台词与动作的关系：</b>{e(observation.get("relationship") or "待核查")}</p>'
                     f'<a href="{clip}">打开原片并定位</a>'
                     f'<video controls preload="none" src="{clip}"></video>'
                     f'<p class="muted">来源：{e(source["id"])} · 独立来源组：{e(source["family_id"])}</p></div>')
    notes = record.get('review_notes', {})
    if notes.get('limitations'):
        parts.append(f'<p class="notice">核查限制：{words(notes["limitations"])}</p>')
    sheets = notes.get('evidence_sheets', [])
    if sheets:
        parts.append('<details class="frames"><summary>抽帧证据（不代替连续播放和原声核查）</summary>')
        for sheet in sheets:
            url = relative_url(base / sheet, output)
            parts.append(f'<a href="{url}"><img loading="lazy" src="{url}" alt="原片抽帧证据"></a>')
        parts.append('</details>')
    parts.append(f'<p><a href="{relative_url(base / "entries" / record["id"] / "record.json", output)}">查看完整记录</a></p>')
    return ''.join(parts)


def record_rows(base, output, row, record, sources):
    expression = record['expression']
    ready = expression['status'] == 'ready'
    label = '已核实关联' if ready else '待补全'
    if not record['enabled']:
        label += ' · 已停用'
    evidence = '跨独立来源反复观察' if record['evidence_status'] == 'repeated_observation' else '单次情境样例'
    intent = e(expression['intent'] or '待确认')
    if not ready and expression['intent']:
        intent = '待审：' + intent
    tone = words(expression['tone_tags'])
    if not ready and expression['tone_tags']:
        tone = '待审：' + tone
    lexical_label = '原片实词' if ready else '待核查实词'
    lexical = f'<b>{lexical_label}</b><p>{words(expression["keywords"])}</p>'
    lexical += f'<b>近义扩展</b><p>{words(expression["paraphrases"], "尚未扩展")}</p>'
    search = ' '.join([record['title'], record['summary'], expression['intent'] or '',
                       *expression['keywords'], *expression['paraphrases'], *expression['tone_tags']])
    placement = expression['placement'] or '需核对台词后确定'
    return (f'<tbody data-search="{e(search)}" id="{e(record["id"])}">'
            f'<tr class="mapping"><td data-label="表达类别"><strong>{intent}</strong></td>'
            f'<td data-label="情绪／语气">{tone}</td>'
            f'<td data-label="关键词／相近说法">{lexical}</td>'
            f'<td data-label="对应表现"><p>{e(record["performance"]["movement"])}</p>'
            f'<p class="muted">表情目光：{e(record["performance"]["gaze_expression"])}</p>'
            f'<p class="muted">安排时机：{e(placement)}</p></td>'
            f'<td data-label="核查情况"><span class="badge {"ready" if ready else "pending"}">{label}</span>'
            f'<p>{e(evidence)}</p><p class="muted">{row["observation_count"]} 次观察 · '
            f'{row["independent_families"]} 个来源组</p></td></tr>'
            f'<tr><td colspan="5" class="detail-cell"><details><summary>查看原话、视频和动作过程</summary>'
            f'{detail(base, output, record, sources)}</details></td></tr></tbody>')


def render(base, output, records, sources):
    ready_count = sum(row['eligible_for_arrangement'] for row, _ in records)
    pending_count = sum(record['expression']['status'] == 'pending' for _, record in records)
    groups = defaultdict(list)
    for row, record in records:
        expression = record['expression']
        group = expression['intent'] if row['eligible_for_arrangement'] else (
            '待补全 · 话术与动作关系尚未核实' if expression['status'] == 'pending' else '已停用关联')
        groups[group].append((row, record))
    sections = []
    for name, pairs in sorted(groups.items(), key=lambda item: (item[0].startswith(('待补全', '已停用')), item[0])):
        body = ''.join(record_rows(base, output, row, record, sources) for row, record in pairs)
        sections.append(f'<section class="group"><h2>{e(name)} <span>{len(pairs)} 条</span></h2>'
                        '<div class="table-wrap"><table><colgroup><col class="intent"><col class="tone">'
                        '<col class="phrases"><col class="action"><col class="status"></colgroup>'
                        '<thead><tr><th>表达类别</th><th>情绪／语气</th><th>关键词／相近说法</th>'
                        '<th>对应表现</th><th>核查情况</th></tr></thead>' + body + '</table></div></section>')
    empty = ('<p class="notice">当前没有已核实的话术—动作关联。已有动作素材保留在下方待补全区；'
             '核对原声、语气及动作对应关系后，再参与新台词的动作编排。</p>' if ready_count == 0 else '')
    content = f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>初瑞雪通用表现库 · 表达与动作</title><style>
*{{box-sizing:border-box}}body{{margin:0;background:#f3f6fa;color:#1c2f48;font:15px/1.65 "Microsoft YaHei",system-ui,sans-serif}}
main{{max-width:1480px;margin:0 auto;padding:34px 28px 60px}}header{{background:#fff;border:1px solid #dce4ee;border-radius:16px;padding:26px 30px}}
.eyebrow{{font-size:13px;color:#55739b;margin:0}}h1{{font-size:30px;line-height:1.3;margin:10px 0}}header p{{margin:10px 0}}h2{{font-size:21px;margin:30px 0 12px}}h2 span{{font-size:13px;color:#68809c;margin-left:12px;font-weight:400}}
.stats{{display:flex;flex-wrap:wrap;gap:10px;margin:20px 0 8px}}.stats span{{background:#edf3fb;color:#254e85;padding:8px 14px;border-radius:8px}}
.notice{{background:#fff8e8;border-left:3px solid #d9aa4e;padding:12px 16px;border-radius:4px}}.muted{{color:#687b91;font-size:13px}}
input{{width:100%;border:1px solid #c8d4e5;background:#fff;border-radius:9px;padding:12px 14px;font:inherit;margin-top:10px}}input:focus{{outline:2px solid #4c78bb;outline-offset:2px}}
.table-wrap{{background:#fff;border:1px solid #dce4ee;border-radius:12px;overflow:hidden}}table{{border-collapse:collapse;width:100%;table-layout:fixed}}col.intent{{width:12%}}col.tone{{width:11%}}col.phrases{{width:21%}}col.action{{width:38%}}col.status{{width:18%}}
th{{background:#eaf0f8;text-align:left;font-size:14px;padding:14px 16px}}td{{padding:18px 16px;vertical-align:top;overflow-wrap:anywhere}}td p{{margin:0 0 10px}}td p:last-child{{margin-bottom:0}}tbody+tbody .mapping td{{border-top:1px solid #dce4ee}}
.badge{{display:inline-block;padding:3px 9px;border-radius:6px;font-size:12px;margin-bottom:9px}}.ready{{background:#e0f3e9;color:#226746}}.pending{{background:#fff1d6;color:#8a6417}}
.detail-cell{{padding-top:0;padding-bottom:16px}}summary{{cursor:pointer;color:#2a5da0;font-weight:600;padding:5px 0}}details[open]>summary{{margin-bottom:14px}}dl{{display:grid;grid-template-columns:160px 1fr;gap:10px 18px}}dt{{font-weight:600}}dd{{margin:0}}.observation{{background:#f5f8fc;border-radius:10px;padding:16px;margin:16px 0}}h4{{margin:0 0 10px}}
video{{display:block;width:min(100%,520px);max-height:540px;margin-top:14px;background:#102039;border-radius:8px}}a{{color:#285fac}}img{{max-width:100%;height:auto;margin:12px 0}}footer{{margin-top:32px;color:#687b91;font-size:13px}}[hidden]{{display:none!important}}
@media(max-width:760px){{main{{padding:16px 12px 32px}}header{{padding:20px}}h1{{font-size:24px}}thead,colgroup{{display:none}}table,tbody,tr,td{{display:block;width:100%}}.mapping{{padding:12px 16px}}.mapping td{{padding:8px 0;border:0!important}}.mapping td::before{{content:attr(data-label);display:block;font-size:12px;color:#74859b;margin-bottom:4px}}tbody+tbody{{border-top:1px solid #dce4ee}}.detail-cell{{padding:0 16px 16px}}dl{{grid-template-columns:1fr;gap:3px}}dd{{margin-bottom:10px}}}}
</style></head><body><main><header><p class="eyebrow">产品规则 · 完整脚本 · 共用动作 · 初瑞雪表现</p>
<h1>初瑞雪通用表现库</h1><p>表达类别 → 情绪与语气 → 关键词／相近说法 → 对应动作与表情</p>
<p class="muted">按整句意思查找表现，再结合当前持物和节奏安排动作。原话与视频证据保留在每条详情里。</p>
<div class="stats"><span>已核实可用关联 {ready_count}</span><span>待补全 {pending_count}</span><span>来源视频 {len(sources)}</span></div>
</header>{empty}<label for="search" class="muted">搜索表达类别、说法或动作</label>
<input id="search" type="search" placeholder="例如：引导购买、认真、下单、向下指" autocomplete="off">
<p id="search-empty" class="notice" hidden>没有匹配的记录。</p>{''.join(sections)}
<footer>“近义扩展”用于检索，不代表原片逐字说过。待补全素材不参与已核实关联的默认编排；重复观察也不等于每次必须做同一动作。</footer>
</main><script>
document.getElementById('search').addEventListener('input',function(){{
 const q=this.value.trim().toLocaleLowerCase();let shown=0;
 document.querySelectorAll('tbody[data-search]').forEach(row=>{{row.hidden=!row.dataset.search.toLocaleLowerCase().includes(q);if(!row.hidden)shown++;}});
 document.querySelectorAll('.group').forEach(group=>{{group.hidden=!Array.from(group.querySelectorAll('tbody')).some(row=>!row.hidden);}});
 document.getElementById('search-empty').hidden=shown>0;
}});
</script></body></html>'''
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding='utf-8')
