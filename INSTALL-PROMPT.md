# 给同事的完整安装提示词

公开仓库，无需 GitHub 账号或令牌。将下面整段交给目标电脑的 agent。

```text
请直接完整安装并初始化「初瑞雪 Seedance 2.5 电商口播导演」技能，不要只提供教程。

公开仓库：https://github.com/liuqun12134-bit/chu-ruixue-seedance25-commerce-director
分支：main
技能目录：skills/chu-ruixue-seedance25-commerce-director

检查并补齐 Git、Git LFS 和可用的 Python。克隆仓库并执行 git lfs pull，完整安装技能、产品库、脚本库、动作库、人物表现库、历史 demo-library 及所有引用的视频、图片、转写、索引和历史；不能只复制 SKILL.md 或保留 LFS 指针。

在仓库根目录执行 python tools/verify_package.py 和 python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate，确认文件大小、SHA-256 和库结构正确，再安装到本机实际用户级技能目录。Codex 优先使用 CODEX_HOME/skills；未设置时使用用户目录下的 .codex/skills。

已有同名技能先完整备份，保留本地新增资料，同路径内容不同先比较处理，不静默覆盖，不改旧版 seedance25-commerce-director。

在实际安装目录运行 scripts/catalog.py validate、scripts/update.py，建立该安装的更新基线。Windows x64 再按 references/initialization.md 执行 scripts/initialize.ps1，复用已有依赖并补齐缺项，等待完成后报告真实状态；其他系统按技能支持范围说明。

报告实际安装路径、版本、提交、各库数量和验证结果。当前发布为2.1.1，含5条产品、49条脚本、121条动作、76条人物记录及81个人物来源；人物记录全部待听审，以实际最新发布清单为准。保留draft/pending状态，不把安装当作完成听审。本次不生成图片或提交付费视频。以后我说“更新初瑞雪技能和所有库”时，使用已安装技能的更新入口。
```
