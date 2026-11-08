# 历史演示记录格式（兼容与溯源）

本文仅用于读取旧demo-library证据，不是新版入库入口。新动作、脚本和目标产品使用[四库格式](libraries.md)；不要继续新增两套产品专属/品类动作副本。下面的scope与products.json仅描述旧格式，不限制新版跨商品借鉴。

记录是 UTF-8 JSON 文字文件，可由不同 agent 直接读写；复杂观察可附 Markdown 和图片。使用 [demo-record.json](../templates/demo-record.json) 模板；模板是结构样例，不是已入库证据，复制后必须填入本次事实。

## 共用字段

`schema_version=1`；id 为不重复的小写字母/数字/连字符，必须等于目录名；title；record_type 为 demo；modes 为 talk/use 的非空列表（两者通用就都填）；category 非空；product_name 可 null；product_form/container/body_part 可 null；tags 列表；created_on/updated_on 为 YYYY-MM-DD；summary 非空。品类可以逐步扩展，不维护固定面膜分支。

结构：`demo-library/entries/ID/record.json`。所有资产引用相对于这份 record.json 所在目录；路径不得绝对、不得含 .. 越界、不得是网址；路径对应的文件必须真实存在并位于该条目内部。附件可存图片、提示词、来源观察；整段视频是否随包携带如实登记。

## 演示字段

provenance：kind 是 video_analysis（本次实际分析视频）、legacy_text（迁移历史文字）或 authored_method（设计方法，未经视频验证）；description、observation_method、limitations；source_url 可 null 或公开 http(s)网址；source_asset 为包内视频相对路径或 null；notes_path 为来源观察文件相对路径或 null；analyzed_on 为实际分析日（未知可 null）；duration_seconds 为实测值或 null；time_reliability 为 measured/approximate/unknown/not_applicable。

preconditions 列表描述适用的起始条件。units 非空，每个单元含 id、name、source_time（区间说明或 null）、start_conditions、action、transition、end_state、expected_effect、avoid、prompt_fragment。单元 id 在条目内唯一。动作和效果以此关联；不只存“自然涂抹、效果好”。图像 keyframes 为列表，每项 path、timestamp_seconds（未知 null）、role 和 observation。没有帧就空列表并在来源限制说明。

## 适用范围与产品关联

演示记录增加 scope（category 或 product）、product_id（专属产品 ID，品类记录为 null）、enabled（布尔，默认 true）。旧记录未声明 scope 时，product_name 为空的按品类兼容；有产品名的视为 unassigned，保留展示但不参与自动编排，整理后再使用。

product_name 仅描述来源视频中的产品，不作为精确匹配键。品类通用记录允许保留来源产品名。产品专属记录必须指向 demo-library/products.json 中的一个产品。

products.json 格式为 schema_version=1、products 列表。每项含 id、name、category、description（包装/规格说明，可空）、reference_hashes（参考图 SHA256 列表，可空）、enabled。ID 稳定且唯一；同一参考图命中多个启用产品时不能自动选择。只保存哈希关联，原产品图由素材库或用户提供。

使用 `python scripts/library.py bind-product PRODUCT_ID IMAGE_PATH` 给本技能已登记产品关联一张参考图。`--root` 仅在用户明确要求维护另一个目标库时指定，不默认指向旧技能或素材万象的共享库。文件复制到别的电脑后，只要图像内容不变，关联继续有效。重新导出的图片需重新关联或由用户明确选择产品。

## 索引与更新

demo-library/index.json 从记录与产品关联派生，包含 ID、标题、模式、品类、形态、包装、部位、产品名、标签、摘要、来源类型、适用范围、启用状态和产品 ID与相对路径。先读索引再读取匹配记录；索引不是另一套事实来源。

维护后用 `python scripts/catalog.py reindex` 和 `python scripts/catalog.py validate` 同时检查四库与历史来源。`library.py` 保留旧资产兼容检查；新增产品与图片绑定使用studio.py，不写回旧产品表。校验不判断视频质量、反馈真假或模型能力。

维护同一份可写目录；并发修改同一条目前先读最新文件，合并本轮变更，不回写过期副本。同步或升级保留用户记录；同 ID 不同内容需要合并，不静默选远程版本。用户授权保存本地不自动等于授权公开传播原素材。
