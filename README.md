# 初瑞雪 Seedance 2.5 电商口播导演

专用 Skill，版本 **1.1.0**。**技能规则与三个逻辑库是一体的，同仓库保存、一起安装和迁移。** 此仓库为私有仓库。

完整安装目录：[skills/chu-ruixue-seedance25-commerce-director](skills/chu-ruixue-seedance25-commerce-director/SKILL.md)。它独立维护，不依赖旧版 `seedance25-commerce-director` 的安装或资料。

## 功能

- 根据首帧、人物/产品参考及原声，设计纯口播或边讲边用方案；默认先给三个简短方案，选择后出完整提示词。
- 结合真实产品操作与初瑞雪本人素材，按台词类别、关键词、意思、语气和持物条件匹配动作。
- 经授权从对标视频补充库，保留来源、关键帧、相对路径、证据状态和历史。
- 检查原音频，诊断当次成片并修订导演稿。技能本身不自动生成图片或提交付费视频任务。

## 一体保存的三个逻辑库

| 逻辑库 | 用途 | 本次快照 |
| --- | --- | --- |
| 产品专属演示库 | 同款产品的操作、结构和适用条件 | 11 条记录 |
| 品类演示库 | 同类产品可参考的使用方法 | 7 条记录 |
| 初瑞雪通用表现库 | 表达类别 → 情绪/语气 → 关键词/相近说法 → 对应动作与表情 | 33 条记录，29 个来源视频 |

产品与品类记录都保存在 `demo-library`，按 `scope` 区分，共 **58 个动作单元**；人物表现保存在 `performance-library`。

当前人物表现记录均为 **pending（待核对）**，已核实的台词与动作关联为 **0 条**。素材和候选动作已保留，但不能把未听审的 ASR 或静帧观察当成已核实的表达习惯。默认检索只使用 ready 关联；本次同步不改变证据状态。

2026-11-07 快照完整包含 **425 个技能文件、811,137,691 字节**，其中有 **34 个 MP4 文件、196 张图片**。这些是包内实际资产数量，不代表独立拍摄次数；同一来源可能服务多个库。逐文件大小与 SHA-256 见 [package-manifest.json](package-manifest.json)。

```text
skills/chu-ruixue-seedance25-commerce-director/
  SKILL.md
  agents/
  references/
  scripts/
  templates/
  demo-library/          产品、品类、动作单元、关键帧、包内原视频、检查记录
  performance-library/   本人来源视频、表现记录、转写、清单、历史
```

## 完整下载与安装

本仓库的 MP4 通过 **Git LFS** 随同一个仓库版本管理。需要 Git、Git LFS、能访问此私有仓库的 GitHub 登录，以及 Python 3.10+（用于检查）。只下载 `SKILL.md` 或只拿到 LFS 指针不能构成完整安装。

```sh
git lfs install
git clone https://github.com/liuqun12134-bit/chu-ruixue-seedance25-commerce-director.git
cd chu-ruixue-seedance25-commerce-director
git lfs pull
python tools/verify_package.py
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate
```

检查通过后，将整个 `skills/chu-ruixue-seedance25-commerce-director` 目录复制到目标 agent 的用户级技能目录。Codex 通常使用 `~/.codex/skills/`，以目标环境实际设置为准。已有同名技能时先备份并比较，保留本地新增资料，同 ID 有差异先合并。

也可把 [安装提示词](INSTALL-PROMPT.md) 交给目标 agent 执行。下载 ZIP 时必须确认已包含真实视频；`verify_package.py` 会检查文件大小与哈希，拒绝把 LFS 指针文件当成视频。

库内引用使用相对路径；历史来源记录中的原电脑路径只用于追溯，不作为安装依赖。查看图像、听音频、转写与生成依赖目标环境实际支持，不会随技能附带模型或凭据。

## 使用示例

- “使用初瑞雪导演 Skill，根据这些首帧和原声，先给三个边讲边用方案。”
- “用方案二，保留原声，直接给完整提示词。”
- “把这些初瑞雪本人视频加入霜类演示库，并检查是否有可核对的台词与动作关联。”
- “检查这段成片的手部连续性和原声，给出完整修订稿。”

## 后续维护与同步

新增条目时一并维护相应记录、索引、视频、关键帧和历史，不排除整个库或媒体文件。每次发布前运行技能检查并更新包清单：

```sh
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py reindex
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py review
```

`package-manifest.json` 是本次发布快照；后续变更必须重新生成对应的大小与 SHA-256 清单，再运行 `python tools/verify_package.py`。确认 Git LFS 上传成功后再把同步报告为完成。每次换电脑仍须执行 `git lfs pull` 和检查。

本地入库与 GitHub 同步是不同动作；这次上传已获明确授权，不创建自动同步任务，也不自动改写旧版技能。校验覆盖文件、哈希、结构、索引和相对引用，不证明真人身份、听审结果或最终生成质量。
