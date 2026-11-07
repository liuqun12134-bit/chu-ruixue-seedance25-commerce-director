# 初瑞雪通用表现：记录与清单

主线是 **表达类别 / 情绪语气 / 关键词与相近说法 / 对应表现**。一种表达和一套相容的表现为一条记录，附一个或多个观察；同类表达可有不同动作变体。只有动作尚无台词关系的素材保留为待补全，不另设通用、语言两库。

## 共享来源

`performance-library/sources.json` 继续使用 schema_version=1、person_id=chu-ruixue、sources 列表。每个来源：

- id、family_id：小写字母数字连字符 ID；同一原片的剪辑、转码和转载共用 family_id。
- kind=real_person、identity_basis、description、source_url（公开稳定网址或 null）。身份依据不能是模型猜测，生成片不能登记为本人证据。
- media_path：`sources/ID/` 下的包内视频路径；sha256 为实际哈希；duration_seconds 为保存文件实测长度。
- source_start_seconds：片段在原片的起点，未知 null；audio_state 为 original 或 absent。
- observation_method、limitations：实际分析方式及限制。

保存连续视频或含动作起落和前后语境的片段，保留原音轨；无声上传副本另存，不覆盖证据。路径用 `/` 分隔的包内相对路径，不含 `..`、盘符、绝对路径或网址。

## 表现记录（schema_version=2）

保存为 `performance-library/entries/ID/record.json`，使用[模板](../templates/performance-record.json)。模板不是证据。

基础字段：record_type=performance、person_id=chu-ruixue，id 等于目录名；title、summary、created_on、updated_on、enabled、modes（talk/use）、tags（动作特征）、preconditions、avoid、evidence_status。不再使用 banks 或 meaning_tags。

`expression` 是检索与清单主体：

| 字段 | 内容 |
| --- | --- |
| status | ready 已核实关联；pending 待补全/待核查 |
| intent | 表达类别，如引导购买；未知 null |
| tone_tags | 实际语气/情绪，不能从手势形状推断 |
| keywords | 已核查原话里出现的关键词/短语，供词面召回 |
| paraphrases | 为匹配推扩的相近说法，与原片实词分列，不算证据 |
| exclusions | 同词不同义、否定等不适用情境/说法，供整句判断 |
| placement | 动作相对该类台词的发起与收势时机；未知 null |
| pending_reason | pending 必填欠缺什么；ready 为 null |

ready 必须有 intent、tone_tags、keywords、placement，全部观察均有核查过的原话、语气及动作对应关系。关键词须能在至少一条已核查原话中找到；扩展近义说法写入 paraphrases。pending 可以保留待审分类线索，但缺依据就留空，不由动作反猜“强调/催单”。

`performance` 保留 start_state、movement、gaze_expression、rhythm、recovery、end_state。按本人素材记录连续表现，不设统一小动作、慢速或固定次数。ready 的 title 建议为“表达类别｜表现变体”；清单先展示 expression，动作过程放详情。

`observations` 非空，每项：

- source_id、start_seconds、end_seconds 指向所存视频内区间；context、observed_sequence 说明语境及该次过程。
- utterance 为真实原话或 null；speech_review 为 heard / reviewed_asr / unreviewed_asr / unavailable；alignment 为 reviewed / approximate / unavailable。reviewed_asr 必须对声音复核，机器转写不能自动升级；无原声时原话和对齐均不可用。
- tone：该次实际语气/情绪；relationship：哪段原话配合哪个动作、怎样发起和收回。ready 两项必填，pending 未核实可为 null。

evidence_status 为 example 或 repeated_observation；后者至少两个独立 family_id，且在 summary 或 relationship 写清重复点、变体与限制。这个最低门槛不证明普遍偏好或统计概率；同一原片的多个剪辑不增加独立证据数。

## 待审与入库清单

主表按表达类别分组：**表达类别｜情绪/语气｜原片关键词与相近说法｜对应动作/表情｜核查与重复情况**。同类可列多个变体。待补全单列，明确欠缺什么；未知类别显示“待确认”，不计为可用关联。

展开详情展示原话、视频定位、动作起点/过程/回收、持物条件与证据。旧记录中“适合强调某点”一类编排建议与观察分开显示，不当作发现了真人习惯。

`python scripts/catalog.py review` 生成 `performance-library/review.html`。默认检索只返回 enabled 且 ready 记录；`performances --include-pending` 用于检查待补全。模板和清单不预置未经核实的“购买引导→向下指”真人结论。

升级先保留历史和来源，再修改字段；写完运行 reindex、validate、review。校验结构与引用，不替代真实听审、语义判断和观看。
