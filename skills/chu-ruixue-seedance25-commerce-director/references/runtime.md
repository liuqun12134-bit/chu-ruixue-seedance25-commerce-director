# 运行与迁移

从公开 GitHub 获取最新技能与库时使用[更新功能](updating.md)；机器依赖初始化与技能更新各自独立。

本包是四库专用规则、资料及本地辅助脚本，不内置视频生成、第三方凭据或 ASR 模型。目标环境能读文件即可读规则和库；视频/音频分析依赖实际可用能力。不能声称文字/静帧检查等于播放、听审或口型验证。

用户启动初始化时，按[初始化流程](initialization.md)运行 `scripts/initialize.ps1`：自动检测、复用或安装本地 Python、FFmpeg/ffprobe、转写依赖和模型，并保存机器配置。支持 Windows x64；其他系统明确报告当前自动安装不支持。初始化下载免费工具和模型，不调用云端转写、不上传用户媒体、不安装生成服务。

- Python 3.10+：运行 `scripts/library.py` 和 `scripts/catalog.py`，只用标准库。脚本默认定位自身所在技能，不会读取旧技能目录。
- ffmpeg/ffprobe：`scripts/audio.py` 检查音轨、解码时长、补尾静音和制作无声参考副本。默认读取初始化配置，支持 `--ffmpeg`、`--ffprobe` 显式覆盖；音频处理命令本身不联网安装。
- 本地 faster-whisper 与模型：初始化将其作为完整原声分析环境的必需组件。`audio.py transcribe` 默认读取配置并调用匹配的 Python 环境与模型，无须每次寻找路径；仍支持 `--model-dir`、`--dependency-dir` 及 `--runtime-config` 显式指定。库管理脚本仍只依赖 Python 标准库。
- 无可靠 ASR/听取能力：使用用户稿与标注清楚的建议时序，说明未核对的部分；不能凭时长编台词。

真实抽帧可用本地工具，保留时间来源及实际观察方法；不重绘证据。不擅自上传原媒体到第三方补齐能力。付费生成、付费口型修复与重试遵循当次授权，技能本身不提供授权。

所有库资产使用包内相对路径。人物来源保留可追溯的实际连续片段及哈希；文件名可匿名化，来源说明不依赖原电脑路径。原音轨和无声上传副本区分，生成成片不入真人证据库。

迁移复制整个 `chu-ruixue-seedance25-commerce-director` 文件夹。它与旧版各自维护，后续入库不自动双写。升级本技能前保留现有库、产品关联及人物证据；同 ID 不同内容先比较，不能覆盖用户新增记录。公开发布或 GitHub 同步是单独动作，不因本地保存而自动进行。

机器环境和绝对路径配置不随技能迁移；新电脑运行初始化重新检测。脚本使用用户级独立目录，不更改全局 PATH，不修改复用的 Python 环境，不需要用户手工找出转写程序。详见初始化文档中的安装来源、检查模式和失败处理。

写库后运行：

```text
python scripts/catalog.py reindex
python scripts/catalog.py validate
python scripts/catalog.py review
```

人物记录使用 v2：原通用/语言标签合并为 expression；原话、语气和对应关系未核查的旧记录转为 pending，保留原记录历史及来源。`catalog.py performances` 默认只返回 ready，`--include-pending` 供检查；`review` 生成主表按表达类别组织的 `performance-library/review.html`，可用 `--output` 指定库内其他 HTML 清单路径。

验证只覆盖结构、引用、资产和索引，不验证真实身份、自然程度、产品功效、模型服从性或最终投放表现。


## v2四库

catalog.py reindex/validate同时检查四库和旧来源资产，review生成四库总览library-review.html及原人物清单。studio.py提供产品精确识别、绑定、脚本/动作候选和幂等迁移；仅用Python标准库，无新增联网依赖。

旧demo-library保留为证据归档，不再承担同款优先编排。旧对标产品迁移为reference_only，不能当作用户目标产品；需通过采访明确身份后建target档案。迁移动作保留原证据与限制，五标签未核查为draft；新增脚本不得冒称重新观看过原片。整个技能目录一起迁移，不删除原媒体。
