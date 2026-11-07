# 运行与迁移

本包是独立规则、资料及本地辅助脚本，不内置视频生成、第三方凭据或 ASR 模型。目标环境能读文件即可读规则和库；视频/音频分析依赖实际可用能力。不能声称文字/静帧检查等于播放、听审或口型验证。

- Python 3.10+：运行 `scripts/library.py` 和 `scripts/catalog.py`，只用标准库。脚本默认定位自身所在技能，不会读取旧技能目录。
- ffmpeg/ffprobe：`scripts/audio.py` 检查音轨、解码时长、补尾静音和制作无声参考副本。支持 `--ffmpeg`、`--ffprobe` 指定程序；缺依赖时明确报错，不自动安装。
- 可选本地 faster-whisper 与模型：`transcribe` 需要 Python 版本与已有二进制依赖兼容，模型通过 `--model-dir` 指定。使用已有依赖时可加 `--dependency-dir`；不把某台机器的绝对路径写进技能规则。
- 无可靠 ASR/听取能力：使用用户稿与标注清楚的建议时序，说明未核对的部分；不能凭时长编台词。

真实抽帧可用本地工具，保留时间来源及实际观察方法；不重绘证据。不擅自上传原媒体到第三方补齐能力。付费生成、付费口型修复与重试遵循当次授权，技能本身不提供授权。

所有库资产使用包内相对路径。人物来源保留可追溯的实际连续片段及哈希；文件名可匿名化，来源说明不依赖原电脑路径。原音轨和无声上传副本区分，生成成片不入真人证据库。

迁移复制整个 `chu-ruixue-seedance25-commerce-director` 文件夹。它与旧版各自维护，后续入库不自动双写。升级本技能前保留现有库、产品关联及人物证据；同 ID 不同内容先比较，不能覆盖用户新增记录。公开发布或 GitHub 同步是单独动作，不因本地保存而自动进行。

写库后运行：

```text
python scripts/catalog.py reindex
python scripts/catalog.py validate
python scripts/catalog.py review
```

人物记录使用 v2：原通用/语言标签合并为 expression；原话、语气和对应关系未核查的旧记录转为 pending，保留原记录历史及来源。`catalog.py performances` 默认只返回 ready，`--include-pending` 供检查；`review` 生成主表按表达类别组织的 `performance-library/review.html`，可用 `--output` 指定库内其他 HTML 清单路径。

验证只覆盖结构、引用、资产和索引，不验证真实身份、自然程度、产品功效、模型服从性或最终投放表现。
