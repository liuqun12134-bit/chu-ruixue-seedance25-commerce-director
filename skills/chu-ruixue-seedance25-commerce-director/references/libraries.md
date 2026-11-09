# 四库与数据格式

## 存放

- product-library/entries/PRODUCT/record.json：产品；该目录failures/CASE.json为失败记录。
- script-library/entries/SCRIPT/record.json：完整脚本。
- action-library/entries/ACTION/record.json：一个共用动作。
- performance-library：原v2真人库，见[人物格式](performance-format.md)。
- demo-library只保留旧来源资产和兼容索引，不是第五个编排库。

index.json由记录派生，不是另一套事实。source_refs、媒体引用使用技能根相对路径，不含盘符、URL、..。新媒体存所属库sources或记录assets；引用同源，不复制成独立证据。

## 新记录格式

三个新库schema_version=1，稳定ASCII id，record_type，title，enabled，status(draft/ready)，created_on/updated_on，provenance。模板见[产品](../templates/product-record.json)、[脚本](../templates/script-record.json)、[动作](../templates/action-record.json)、[失败](../templates/failure-record.json)。模板不进索引，空项需补齐。

provenance含kind(user_interview/user_authored/video_analysis/authored_method/legacy_migration)、basis、source_refs、limitations。generation_status=untested/tested；tested需generation_evidence文件依据，不能由结构验证升级。

### 产品

role=target/reference_only；旧对标迁移为reference_only，不可自动识别为用户新品。aliases、reference_hashes用于精确识别，重复绑定阻止；重新导出图片不能靠旧hash认同款。

category={value,basis}，basis为user_confirmed/document_confirmed/legacy/unknown。facts包含packaging、net_content、dimensions、contents、texture、usage、body_parts、finish、selling_points，各项{value,basis,status}，未知null。match_fields为texture/packaging/body_part检索标签列表，未知null；不把空列表当不限。

rules各项id/text/status(confirmed/pending)/modes/trigger/basis。规则写条件和目标，不把每个卖点都变成每条必演。interview有asked、missing_core、supplement_answer、complete；ready目标需要已确认分类、关键用法、用户对最后补充问题已有回答。history保存更新依据与旧值。

### 动作

applicability固定五项category/texture/packaging/body_part/purpose，每项{mode,values,basis}：constrained有非空values；unrestricted空values且解释为什么与动作无关；unknown空values，未知不能当不限。

用途标签可跨来源品类检索：购买引导、产品暂放、产品取回。标签写入applicability.purpose.values，保留已有用途；具体条件见[通用编排规则](directing.md#通用编排规则)。只补当前动作实际包含的用途，不以补标签解除其他维度限制或升级证据状态。

source_category记录来源分类，不等于所有适用品类。approved_product_ids为有依据的适用关联，不能覆盖包装等硬条件。sequence保存start_conditions/action/transition/end_state/expected_effect/avoid。legacy_ref={record_path,unit_id}追溯旧单元；迁移标签未核实保持draft和migration_needs_review。

### 脚本

categories为分类，product_ids为空可共享。source_category保存来源分类依据，source_sequence保存原顺序。stages各项id/goal/required/depends_on/audio_intents/entry_state/action_options/exit_state/carry_forward/acceptance。depends_on仅写因果，不能锁死原片所有顺序；initial_state_satisfies说明已完成前置条件的首帧。

effect_required=true时effect_stage_ids必须指向必需展示环节；maintained_states写转头/遮挡/收尾仍需保持的状态。完整脚本可user_authored且untested；来源片段不足则draft。

### 失败

record_type=failure、product_id和目录一致。input_files项为role/path/sha256，缺资料列unknowns。user_problem、observations、hypotheses、proposed_changes分开。findings项为classification/evidence/confidence。rule_updates只能以user_requirement/verified_product_fact为reason_kind，引用已存在的正式rule_id；原因假设不得晋升规则。attempts保存测试变化、结果、证据、适用范围。

## 工具

```text
python scripts/studio.py products
python scripts/studio.py resolve-product --product-id PRODUCT
python scripts/studio.py resolve-product --image IMAGE
python scripts/studio.py bind-product --product-id PRODUCT --image IMAGE
python scripts/studio.py actions --product-id PRODUCT --mode use --body-part 手背 --purpose 涂后展示
python scripts/studio.py scripts --product-id PRODUCT --mode use
python scripts/catalog.py performances --mode talk --intent 引导购买 --text "喜欢的可以拍了"
```

动作返回candidates/excluded及reasons/needs_review。产品标签与明确限制冲突排除；未知只作为待核查候选，不能当通过。跨品类可经已记录产品适用关联召回，但其他维度仍检查。标签采用如油状/膏霜、滴管瓶/旋盖罐、手背/面颊、涂后展示的短词；近义标签由导演阅读原记录判断，不把词不相等直接等同物理冲突。

脚本召回后仍由导演按音频、时长、首帧重排。只用ready人物关联，pending不是可用习惯。

## 迁移与维护

studio.py migrate仅新增缺失迁移记录，重跑不覆盖修改；来源变更报告冲突。旧产品→reference_only，旧单元→有legacy_ref的共用动作，旧标签未核实不伪装ready。不会自动把单元串成已观察完整脚本。

维护后catalog.py reindex、validate、review；所有记录通过才生成索引。legacy library.py用于旧资产检查；新增目标产品和图片绑定用studio.py，避免写回旧产品表。
