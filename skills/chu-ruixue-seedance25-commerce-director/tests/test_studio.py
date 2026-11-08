"""Behavioral invariants for identity, matching, causality and failure attribution."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
import studio
import library


class StudioTests(unittest.TestCase):
    def setUp(self):
        self.test_base = (Path.cwd() / '.studio-test-work').resolve()
        self.test_base.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=self.test_base)
        self.root = Path(self.tmp.name)
        self.product = studio.base('product', 'product-toneup', '素颜霜', '2026-11-08', studio.provenance('user_interview', '测试中用户已回答'))
        self.product.update(status='ready', role='target', aliases=[], reference_hashes=[],
                            category={'value': '素颜霜', 'basis': 'user_confirmed'},
                            facts={k: {'value': None, 'status': 'unknown', 'basis': '未询问非核心字段'} for k in studio.FACTS},
                            match_fields={'texture': ['膏霜'], 'packaging': ['旋盖罐'], 'body_part': ['面颊', '手背']},
                            rules=[], interview={'asked': [], 'missing_core': [], 'supplement_answer': '没有补充', 'complete': True})
        self.product['facts']['usage'] = {'value': '少量涂于面颊或手背', 'status': 'confirmed', 'basis': '用户回答'}
        self.put('product', self.product)

    def tearDown(self):
        self.assertTrue(self.root.resolve().is_relative_to(self.test_base))
        self.tmp.cleanup()

    def put(self, kind, data):
        path = self.root / f'{kind}-library/entries/{data["id"]}/record.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
        return path

    def action(self, key='action-cream', **constraints):
        record = studio.base('action', key, '手背展示', '2026-11-08', studio.provenance('user_authored', '用户设计'))
        record.update(status='ready', modes=['use'], source_category={'value': '素颜霜', 'basis': 'user_confirmed'},
                      approved_product_ids=[], migration_needs_review=False, legacy_ref=None,
                      applicability={k: {'mode': 'unrestricted', 'values': [], 'basis': '该动作不依赖此维度'} for k in studio.DIMENSIONS},
                      sequence={'start_conditions': ['手背已涂好'], 'action': '举近手背', 'transition': '离手后举近',
                                'end_state': '看清涂后状态', 'expected_effect': '以当前产品为准', 'avoid': ['曝光变白']})
        for key, value in constraints.items():
            record['applicability'][key] = {'mode': 'constrained', 'values': value, 'basis': '实际操作条件'}
        self.put('action', record)
        return record

    def script(self):
        record = studio.base('script', 'script-face', '面部使用', '2026-11-08', studio.provenance('user_authored', '用户口述'))
        def stage(key, deps):
            return {'id': key, 'goal': key, 'required': True, 'depends_on': deps, 'audio_intents': [],
                    'entry_state': '真实进入状态', 'action_options': [], 'exit_state': '阶段完成',
                    'carry_forward': ['妆效保持'], 'acceptance': ['效果仍在']}
        record.update(status='ready', modes=['use'], categories=['素颜霜'], product_ids=[],
                      source_category={'value': '素颜霜', 'basis': 'user_confirmed'}, goal='看清妆效',
                      adaptation_notes='按音频重排，保留因果', source_sequence=['apply', 'show'], initial_state_satisfies=[],
                      maintained_states=['转头保持妆效'], effect_required=True, effect_stage_ids=['show'],
                      stages=[stage('apply', []), stage('show', ['apply'])])
        self.put('script', record)
        return record

    def failure(self):
        record = {'schema_version': 1, 'record_type': 'failure', 'id': 'failure-turn', 'product_id': self.product['id'],
                  'created_on': '2026-11-08', 'user_problem': '转头后妆效消失', 'input_files': [], 'observations': [],
                  'hypotheses': ['可能与转头有关'], 'proposed_changes': ['待测试修法'], 'unknowns': ['缺输入原图'],
                  'related_script_ids': [], 'related_action_ids': [], 'findings': [], 'rule_updates': [], 'attempts': []}
        path = self.root / f'product-library/entries/{self.product["id"]}/failures/failure-turn.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        return record, path

    def test_same_body_part_does_not_mix_oil_and_cream(self):
        self.action('action-oil', texture=['油状'], packaging=['滴管瓶'], body_part=['手背'])
        self.action('action-cream', texture=['膏霜'], packaging=['旋盖罐'], body_part=['手背'])
        result = studio.actions(self.root, self.product['id'], 'use', body_part='手背')
        self.assertEqual([r['id'] for r in result['candidates']], ['action-cream'])
        self.assertEqual([r['id'] for r in result['excluded']], ['action-oil'])

    def test_shared_display_does_not_require_packaging_match(self):
        self.action('action-show', body_part=['手背'])
        result = studio.actions(self.root, self.product['id'], 'use', body_part='手背')
        self.assertTrue(result['candidates'][0]['eligible_for_arrangement'])

    def test_unknown_is_not_unrestricted(self):
        action = self.action()
        action['applicability']['texture'] = {'mode': 'unknown', 'values': [], 'basis': '未核查'}
        self.put('action', action)
        row = studio.actions(self.root, self.product['id'], 'use')['candidates'][0]
        self.assertFalse(row['eligible_for_arrangement'])
        self.assertTrue(any('texture' in value for value in row['needs_review']))

    def test_product_association_cannot_override_wrong_package(self):
        action = self.action(category=['面部护理油'], packaging=['滴管瓶'])
        action['approved_product_ids'] = [self.product['id']]
        self.put('action', action)
        result = studio.actions(self.root, self.product['id'], 'use')
        self.assertFalse(result['candidates'])
        self.assertTrue(any('packaging' in reason for reason in result['excluded'][0]['reasons']))

    def test_requested_part_cannot_override_product_usage(self):
        with self.assertRaises(library.Invalid):
            studio.actions(self.root, self.product['id'], 'use', body_part='眼睑')

    def test_ready_product_requires_final_interview_answer(self):
        self.product['interview']['supplement_answer'] = None
        self.put('product', self.product)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_reference_product_never_autoresolves_as_target(self):
        image = self.root / 'image.bin'
        image.write_bytes(b'reference')
        self.product['role'] = 'reference_only'
        self.product['reference_hashes'] = [studio.sha(image)]
        self.put('product', self.product)
        with self.assertRaises(library.Invalid):
            studio.resolve_product(self.root, image=image)

    def test_conflicting_product_image_is_rejected(self):
        image = self.root / 'image.bin'
        image.write_bytes(b'product-one')
        other = copy.deepcopy(self.product)
        other['id'] = 'product-other'
        other['reference_hashes'] = [studio.sha(image)]
        self.put('product', other)
        with self.assertRaises(library.Invalid):
            studio.resolve_product(self.root, self.product['id'], image)

    def test_duplicate_target_hash_is_rejected(self):
        self.product['reference_hashes'] = ['a' * 64]
        self.put('product', self.product)
        other = copy.deepcopy(self.product)
        other['id'] = 'product-other'
        self.put('product', other)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_script_preserves_effect_stage(self):
        script = self.script()
        self.assertEqual(len(studio.scripts(self.root, self.product['id'], 'use')['candidates']), 1)
        script['stages'][1]['required'] = False
        self.put('script', script)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_script_cycle_is_rejected(self):
        script = self.script()
        script['stages'][0]['depends_on'] = ['show']
        self.put('script', script)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_script_unknown_action_is_rejected(self):
        script = self.script()
        script['stages'][0]['action_options'] = ['action-missing']
        self.put('script', script)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_failure_hypothesis_cannot_become_rule(self):
        self.product['rules'] = [{'id': 'no-turn', 'text': '禁止转头', 'status': 'confirmed', 'modes': ['use'], 'trigger': '所有视频', 'basis': '错误推测'}]
        self.put('product', self.product)
        record, path = self.failure()
        record['rule_updates'] = [{'rule_id': 'no-turn', 'reason_kind': 'hypothesis', 'basis': '单次失败'}]
        path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_failure_untested_fix_is_saved_without_rule_promotion(self):
        self.failure()
        result = studio.collect(self.root)
        self.assertEqual(len(result['failure']), 1)
        self.assertEqual(result['product'][self.product['id']]['rules'], [])

    def test_tested_claim_requires_evidence(self):
        action = self.action()
        action['generation_status'] = 'tested'
        self.put('action', action)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_source_path_cannot_escape_library(self):
        action = self.action()
        action['provenance']['source_refs'] = ['../outside.mp4']
        self.put('action', action)
        with self.assertRaises(library.Invalid):
            studio.collect(self.root)

    def test_stale_index_detected_after_update(self):
        studio.run(self.root, 'reindex')
        self.product['title'] = '改名后的素颜霜'
        self.put('product', self.product)
        with self.assertRaises(library.Invalid):
            studio.run(self.root, 'validate')

    def test_migration_is_idempotent_and_preserves_user_edits(self):
        registry = self.root / 'demo-library/products.json'
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({'schema_version': 1, 'products': []}), encoding='utf-8')
        old = {'schema_version': 1, 'record_type': 'demo', 'id': 'demo-fixture', 'title': '旧演示',
               'category': '素颜霜', 'summary': '已有参考', 'modes': ['use'], 'product_name': None,
               'product_form': None, 'container': None, 'body_part': None, 'tags': [], 'enabled': True,
               'created_on': '2026-11-08', 'updated_on': '2026-11-08', 'scope': 'category', 'product_id': None,
               'provenance': {'kind': 'authored_method', 'description': '旧方法', 'observation_method': '文字设计',
                              'limitations': [], 'time_reliability': 'not_applicable', 'duration_seconds': None,
                              'analyzed_on': None, 'source_url': None, 'source_asset': None, 'notes_path': None},
               'preconditions': ['已有涂后状态'], 'keyframes': [], 'units': [
                   {'id': 'show', 'name': '举近', 'source_time': None, 'start_conditions': ['已涂'],
                    'action': '举近', 'transition': '离手', 'end_state': '看清', 'expected_effect': '本品效果',
                    'avoid': [], 'prompt_fragment': '举近展示'}]}
        self.put('demo', old)
        self.assertEqual(len(studio.migrate(self.root)['created']), 1)
        path = self.root / 'action-library/entries/action-fixture-show/record.json'
        record = library.load(path)
        record['title'] = '用户修改后的动作'
        path.write_text(json.dumps(record, ensure_ascii=False), encoding='utf-8')
        result = studio.migrate(self.root)
        self.assertFalse(result['created'])
        self.assertEqual(library.load(path)['title'], '用户修改后的动作')
        old['summary'] = '原来源有更新'
        self.put('demo', old)
        self.assertTrue(studio.migrate(self.root)['conflicts'])
        self.assertEqual(library.load(path)['title'], '用户修改后的动作')


if __name__ == '__main__':
    unittest.main()
