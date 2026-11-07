# 完整安装提示词

将下面内容交给目标电脑的 agent。此私有仓库包含 Git LFS 视频，目标电脑需要已有 GitHub 访问权限，不要把令牌发到聊天里。

```text
请帮我完整安装「初瑞雪 Seedance 2.5 电商口播导演」专用 Skill，并实际执行检查。

仓库：https://github.com/liuqun12134-bit/chu-ruixue-seedance25-commerce-director
分支：main
技能目录：skills/chu-ruixue-seedance25-commerce-director
技能名称：chu-ruixue-seedance25-commerce-director

技能与对应库是一个整体。完整保留 SKILL.md、agents、references、scripts、templates、demo-library、performance-library，以及其中的来源视频、关键帧、转写、记录、索引、清单和历史，不能只安装规则或空库。

先确认本机 Git、Git LFS 和 GitHub 登录。用 git clone 获取该私有仓库，并在仓库内执行 git lfs pull。不要把只下载到 LFS 指针的仓库或 ZIP 当成完整素材。使用本机已有登录；缺登录时提示正规登录步骤，不索取或展示访问令牌。

在仓库根目录执行：
python tools/verify_package.py
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate

所有文件大小和 SHA-256 与清单一致、库检查通过后，把整个技能目录复制到当前 agent 实际支持的用户级技能位置。已有同名技能时先完整备份，保留本地新增内容；同 ID 内容不同先比较合并，不静默覆盖。不要修改独立的旧版 seedance25-commerce-director。

安装后再次运行已安装目录中的 scripts/catalog.py validate。若发生合并，先重建索引，再验证；说明安装内容与仓库快照的差异。保持 ready/pending 等证据状态，不把这次安装当成已完成音频听审或已确认人物习惯。

告诉我安装位置、版本、三类库的记录数量、待核对状态和校验结果。若 agent 不支持自动发现本地 Skill，说明如何显式加载 SKILL.md，不宣称已自动启用。本次仅下载、安装和校验，不提交任何付费生成任务。
```
