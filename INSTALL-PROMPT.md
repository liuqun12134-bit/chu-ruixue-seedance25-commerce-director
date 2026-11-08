# 给同事的完整安装提示词

将以下内容交给目标电脑的 agent。仓库公开，无需 GitHub 账号或令牌。

```text
请完整安装「初瑞雪 Seedance 2.5 电商口播导演」技能、所有库及素材，并实际验证。

仓库：https://github.com/liuqun12134-bit/chu-ruixue-seedance25-commerce-director
分支：main
包内技能目录：skills/chu-ruixue-seedance25-commerce-director

检查本机 Git、Git LFS 和 Python 3.10+，补齐实际缺少的工具。使用 git clone 获取完整仓库，再执行 git lfs pull；不把 LFS 指针或不含视频的 ZIP 当作安装完成。

在仓库根目录执行：
python tools/verify_package.py
python skills/chu-ruixue-seedance25-commerce-director/scripts/catalog.py validate

验证通过后，复制整个技能文件夹到当前 agent 实际支持的用户级技能目录。保留 SKILL.md、agents、references、scripts、templates、tests、product-library、script-library、action-library、performance-library、历史 demo-library，以及所有媒体、转写、记录、索引与历史。

已有同名技能先完整备份；保留本地新增资料，同路径或同 ID 有不同内容先比较处理，不静默覆盖，不删除用户资料。不修改独立旧版 seedance25-commerce-director。

安装后运行实际安装目录的 scripts/catalog.py validate，再运行 scripts/update.py 建立该安装的升级基线。首次接入报告冲突时列出差异并处理，不强制覆盖。不要在临时克隆副本运行后声称实际安装已接入。

报告安装位置、版本、各库记录数、待核对状态与校验结果。必要时新开对话重新加载技能。以后我说“更新初瑞雪技能和所有库”就运行该技能的更新入口；说“检查更新”就使用 --check。

本次不提交付费生成任务。音频环境需要时再运行初始化，不把安装或更新当作完成听审。
```
