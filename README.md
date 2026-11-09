# 初瑞雪 Seedance 2.5 电商口播导演

版本 **2.1.3**，公开仓库。技能、四库和素材作为整体安装与更新，无需 GitHub 账号即可下载。

技能入口：[SKILL.md](skills/chu-ruixue-seedance25-commerce-director/SKILL.md)。独立于旧版 seedance25-commerce-director。

## 能力与库

支持产品采访、参考视频提炼完整脚本与动作、口述维护、失败归档、本地音频环境初始化、原声导演编排和 GitHub 更新。默认先给三个简短方案，选定后出完整稿；不自动生图或提交付费视频。

| 库 | 内容 | 当前数量 |
| --- | --- | --- |
| product-library | 产品身份、包装、用法、卖点与失败记录 | 6 条 |
| script-library | 完整脚本、顺序依赖、必需/可选环节 | 49 条 |
| action-library | 动作适用信息、起点、操作、结束与证据 | 122 条 |
| performance-library | 台词、语气和本人表情/动作关联 | 76 条，81 个来源 |

历史 demo-library 保留 26 条来源记录、81 个动作单元。人物表现目前全部 pending，ready 关联为 0；安装、更新和结构校验不会把候选资料变成已听审证据。

2026-11-09 产品规则更新（2.1.3）：新增 ZUZU 人参油 30 mL 目标产品档案、四视参考图和用户采访原文。记录旋开滴管后按压吸油、单次约 1/3–1/2 滴管、面部使用及面霜/面膜搭配、水润光泽保持，以及可选的晃瓶展示人参与少量气泡。档案 ready，生成未测试；功效卖点与实际可视效果分别记录。

2026-11-09 人参油整批同步（2.1.1）：包含此前小爱 AI 参考的 2 条路线、11 条动作，以及本批 52 份真人来源、43 条路线草稿、23 条新动作、6 条已有动作证据补充和 43 条待听审人物记录。55 个文件含小爱1/3完全重复；真人近重复及截损版本归组保存。人参油 (5) 仅前约14秒可解码，记录已关联完整版本。全部保留证据状态，未新增产品用法或功效规则。此前素颜霜更新继续保留。

本批清单：[逐视频脚本、动作、原片与待核项](skills/chu-ruixue-seedance25-commerce-director/script-library/batches/20261109-ginseng-daily/review.html)。

逐文件大小及 SHA-256 见 [package-manifest.json](package-manifest.json)。机器环境、ASR 模型和凭据不在包内。

## 安装

需要 Git、Git LFS、Python 3.10+。视频使用 Git LFS，网页 ZIP 或单个 SKILL.md 不能代替完整安装。

```text
git lfs install
git clone https://github.com/liuqun12134-bit/chu-ruixue-seedance25-commerce-director.git
cd chu-ruixue-seedance25-commerce-director
git lfs pull
python tools/verify_package.py
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate
```

验证通过后，把完整 skills/chu-ruixue-seedance25-commerce-director 复制到 agent 实际支持的技能目录。已有版本先备份，比较同路径差异并保留本地资料。然后在**安装后的目录**运行 `python scripts/update.py` 建立升级基线。可直接把[安装提示词](INSTALL-PROMPT.md)交给同事。

## 同事更新

安装本版后，对 agent 说：**“更新初瑞雪技能和所有库。”** 或在实际安装目录运行：

```text
python scripts/update.py --check
python scripts/update.py
```

检查只获取提交与发布清单，不下载视频。更新下载完整新版、校验媒体哈希、保留本地独有文件，临时合并并验证后替换，完整旧版留作备份。双方同时修改同一文件会停止并列出冲突。同事的资料不会上传。

旧版没有更新脚本，先完整安装一次 2.1.0，之后无需重复手工下载安装。不会后台定时更新，只有主动请求时执行。详见[更新与恢复说明](skills/chu-ruixue-seedance25-commerce-director/references/updating.md)。

## 维护者发布

本地入库不自动推送。明确同步时，把整个技能与库同步到本仓库对应目录，运行 catalog.py 的 reindex、validate、review，重新生成 package-manifest.json（逐文件大小、SHA-256 和总数），运行 `python tools/verify_package.py` 与 `git lfs fsck`，推送提交和 LFS 对象到 main。更新器按提交及文件哈希识别变化，新增库也能更新。

公开仓库内容任何人都能下载。发布范围以维护者授权为准；本地检查不能证明真人身份、听审结果、生成服从性或成片效果。
