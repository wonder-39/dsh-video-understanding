# 安装、复用与迁移

## 这套工作流由三块组成

| 块 | 位置 | 作用 | 体积 |
|---|---|---|---|
| 技能本体 | `C:\Users\jack\.dsh\skills\video-understanding\` | 三档流程、类型参数、交付规范、自检、Word 库 | ~40 KB |
| 底层工具 | `C:\Users\jack\.dsh\skills\video-watch-plus\` + `D:\Desktop\DSH-text\video-watch-plus\` | ffmpeg 量测、图版、裁切；venv 跑 ASR | ~1.5 GB |
| 模型缓存 | `D:\Desktop\DSH-text\video-watch-plus\models\` | faster-whisper 权重 | 按需增长 |

## 五个脚本 / 文档在干什么

| 文件 | 作用 |
|---|---|
| `references/tiers.md` | 三档定义、触发词、成本、图片规则 |
| `references/batch.md` | 批量档：闸门 → 转写 → 纠错 → 放弃 |
| `references/detailed.md` | 细致档：每秒一帧、分批读、文档结构 |
| `scripts/asr_probe.py` | 语音闸门 + 转写 + 可疑段（批量档核心） |
| `scripts/docx_helpers.py` | Word 复用库（`Doc` 类） |

## 为什么其他对话也能用

DSH 的技能来自 `~/.dsh/skills` 的文件系统 provider，**与工作目录无关**：任何对话（任何 cwd）启动时都会扫描到 `video-understanding`，并且新增/修改会热加载。

工作目录只影响两件事，都不影响可用性：

- 产物默认写到 `D:\Desktop\DSH-text\video-watch-plus\work\<slug>\`（绝对路径）；
- 最终 .docx 建议放当前工作区根目录（相对当前位置）。

## 一条命令自检

```powershell
python "C:\Users\jack\.dsh\skills\video-understanding\scripts\doctor.py"
```

检查 10 项：技能文件、vw.py、ffmpeg/ffprobe/magick、7 个滤镜、ASR venv、依赖可导入、模型缓存、python-docx。任意目录下运行结果一致；全绿即可开工。

## 迁移到新路径或新机器

只有两处写死了路径，改完再跑 doctor：

1. `scripts\doctor.py` 顶部：`SKILL` / `VW` / `ROOT` / `VENV` 四个常量
2. `SKILL.md` 的「固定路径（本机）」表

`scripts\docx_helpers.py` 不含任何绝对路径，不用改。

### 从零重装

```powershell
# 1) 底层技能
git clone https://github.com/xinhailaopo/video-watch-plus C:\Users\jack\.dsh\skills\video-watch-plus

# 2) 工具链（ffmpeg 完整构建 + ImageMagick 便携版，约 870MB）
powershell -ExecutionPolicy Bypass -File <步骤1路径>\scripts\setup-windows.ps1 `
  -ToolsDir D:\Desktop\DSH-text\video-watch-plus\tools `
  -VwPy <步骤1路径>\vendor\vw.py

# 3) ASR 环境（必须 Python 3.12；3.14 没有 ctranslate2 wheel）
<python3.12> -m venv D:\Desktop\DSH-text\video-watch-plus\venv
D:\Desktop\DSH-text\video-watch-plus\venv\Scripts\python.exe -m pip install `
  faster-whisper "av<19" numpy yt-dlp

# 4) 环境变量（User 级，已设过可跳过）
HF_HOME=D:\Desktop\DSH-text\video-watch-plus\models
HF_ENDPOINT=https://hf-mirror.com
HF_HUB_DISABLE_XET=1
```

装完跑 doctor 复核。

## 踩过的坑（不要重复踩）

| 坑 | 现象 | 解法 |
|---|---|---|
| pip 解析死循环 | CPU 跑满 20 分钟、不写盘、无子进程 | 改用 `uv` |
| 本地代理卡下载 | uv 连上 127.0.0.1:7897 后一动不动 | 清 `HTTP(S)_PROXY`，`NO_PROXY=*` |
| Python 3.14 装 faster-whisper | ctranslate2 无 cp314 wheel | 用 3.12 建 venv |
| `sheet --strip` 当批量读字用 | 每张只装 2 条，52 帧出 26 张 | 裁切 + `magick montage`，每张 8 条 |
| 表头跨页丢、行被切断 | 表格跨页难看 | `w:tblHeader` + `w:cantSplit` |
| 中文标题变孤行 | 标题在页底、正文翻页 | `keep_with_next = True` |
| LOBA 那类海报裁图带字幕 | 图片底部有半行字 | 裁切高度预留字幕带，渲染后再确认 |
