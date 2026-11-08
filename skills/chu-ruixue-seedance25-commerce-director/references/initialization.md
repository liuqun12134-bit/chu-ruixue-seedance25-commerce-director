# 初始化本地分析环境

## 入口与执行

用户说“初始化初瑞雪导演技能”“启动初始化”“换电脑配置一下”或明确要求检测并安装依赖时，直接执行完整初始化。此请求已包含缺项安装配置，无须再次询问是否安装免费依赖；仍遵守实际执行环境的权限、网络限制。若系统要求授权，针对具体被阻止的动作说明，不宣称已成功。

初始化任务不需要用户提供业务素材，不进入三方案选择流程。只要求检查且不安装时使用 `-CheckOnly`。

在当前工作目录运行下面的命令；`SKILL_DIR` 用本次实际技能目录替换，不把旧电脑的路径写死：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "SKILL_DIR/scripts/initialize.ps1"
```

检查模式：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "SKILL_DIR/scripts/initialize.ps1" -CheckOnly
```

`-ExecutionPolicy Bypass` 只作用于这个 PowerShell 进程，不修改持久执行策略。启动进程后持续查询至完成，不将后台安装仍在运行说成已完成。

## 检测与安装范围

当前自动安装支持 **Windows x64**。不支持的平台明确报告，不安装 Windows 程序。

| 组件 | 检测方式 | 缺失或损坏时 |
| --- | --- | --- |
| Python 3.12 x64（初始化基线） | 执行解释器，检查版本/64位/标准库 | 从 python.org 下载 Python 3.12.10，验证发布者数字签名，安装到独立目录，不修改 PATH |
| FFmpeg 与 ffprobe | 执行版本命令并实际解码/探测短 WAV | 从 Gyan 的 FFmpeg Windows 构建源下载 essentials ZIP，核对该源的 SHA256，检查压缩包路径后解压 |
| 本地转写依赖 | 实际导入 faster-whisper、CTranslate2、NumPy、PyAV、ONNX Runtime、tokenizers 等 | 建立专用虚拟环境，从 PyPI 安装 `scripts/runtime-requirements.txt` 的固定主要版本；不改原有环境 |
| Whisper small 模型 | 检查必需文件、实际加载、用一秒合成静音完成 CPU int8 推理 | 从 Hugging Face 的 `Systran/faster-whisper-small` 下载固定修订 `536b0662742c02347bc0e980a01041f333bce120`，再验证 |

这些是本技能音视频分析和库管理实际依赖。不是 Windows 后台服务，不需要长期运行。初始化不安装 Fish、付费生图/视频工具、云转写服务或第三方密钥，也不上传用户媒体。模型文件来自远程下载，音频识别在本地进行。CPU 路线不以独立显卡/CUDA 为前提。

安装检查证明“能调用”，不能证明识别准确、台词已经听审或口型正确。合成静音只用于运行检查，不作为中文识别质量测试。首次安装耗时取决于网络和电脑性能；无网络时可复用已有资源，缺项下载失败则如实报告。

## 路径、复用与迁移

默认运行目录：`%USERPROFILE%/.codex/runtimes/chu-ruixue-seedance25-commerce-director/`。保留 `runtime.json` 和 `initialization-report.json`，模型与新环境也放在该目录；这些机器文件不放入演示库或 Git 仓库。使用稳定用户目录，避免 Codex 沙箱将 LOCALAPPDATA 重定向后找不到配置。

检测上次配置、初始化自建环境、当前项目 `.tools/local-asr`、PATH/Python launcher 和 Codex Python；模型检查当前项目 `.tools/asr-models`、常见 Hugging Face 缓存及上次配置。不会遍历全盘。可用 `-SearchRoot` 指定旧项目根目录，`-PythonPath` 指定解释器，`-ModelDir` 指定已有模型。迁移后旧路径失效时重新检测，不直接信任旧配置。

可用 `-RuntimeDir` 或环境变量 `CRX_RUNTIME_DIR` 指定可写的独立运行目录。通过 `-RuntimeDir` 使用非默认目录后，后续也设置 `CRX_RUNTIME_DIR`，或给 `audio.py` 传 `--runtime-config "目录/runtime.json"`。

完整初始化只在所有组件验证通过后保存配置。后续 `audio.py transcribe INPUT --output OUTPUT.json` 自动使用保存的解释器、工具和模型路径；不会每次重装。显式传入的模型和 FFmpeg 路径优先于配置。

## 结果和故障

- `status=ready`：对用户明确说 **“本地必需依赖齐全，没有缺少，无需安装。”**列出已验证的组件即可。
- `status=installed`：列出本次安装/修复项，说明通过可用性检查，并给出配置位置。
- `status=missing`：仅检查模式发现缺项，列出缺项；模型因解释器缺失无法验证时说“尚不能验证”，不直接称模型文件不存在。
- `status=failed`：报告具体失败项，不能报告初始化完成。现有资源不删除，缓存保留；修复网络/权限等实际问题后再运行。安装或模型加载失败不会无限重试，也不自动切到云端上传。

退出码：0=齐全或补齐成功，2=检查发现缺项，1=初始化失败。检查模式仍会写本机检查报告和临时测试文件，但不安装、不下载、不覆盖运行配置。

初始化使用排他锁防止同时安装。若异常退出遗留 `initialize.lock`，先核对记录的进程确实已经结束，再仅清理该锁文件；不要删除整个运行目录或用户原有环境。

