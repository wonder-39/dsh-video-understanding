# dsh-video-understanding

给 [DeepSeek Harness](https://github.com/deepseek-ai/deepseek-harness)（DSH）用的**视频理解技能**：把一条视频变成一份结构化的 Word 文档。

输入一条 B 站链接或本地视频，它会按档位抓帧、读画面字幕与语音、判断视频类型，输出带编号表图的 `.docx`。

> 底层依赖 [video-watch-plus](https://github.com/xinhailaopo/video-watch-plus)（MIT，ffmpeg 量测与图版工具）——本仓库只负责「看什么、什么时候看、以什么为准」，不重复实现量测。

---

## 它能做什么

三个**档位**，按时间预算选：

| 档位 | 触发语 | 一条 3 分钟视频的耗时 | 产出 |
|---|---|---|---|
| 批量档 | 「批量过一遍」「吃灰收藏夹」 | 1–3 分钟 | 总览表 + 每条 3–5 条要点，**不含图片** |
| 标准档（默认） | 「看看这条视频」 | 8–15 分钟 | 结构时间轴 + 逐段拆解 + 重点对比 + 可靠性声明 |
| 细致档 | 「细致看」「每秒都看」 | 按帧数线性增长 | 逐页表（秒级）+ 完整图文 + 重点细讲 + 字幕全文 |

两类**视频性质**，决定文档结构：

| 类别 | 包含 | 差异 |
|---|---|---|
| 观点类 | 教学、科普、经验分享、新闻、评论、访谈 | 标准档有「重点突出」、细致档有「重点细讲」 |
| 赏析类 | 音乐 PV、娱乐搞笑、生活/vlog、纯记录 | 上述两节去掉，靠逐段拆解承载判断 |

## 输出长什么样

生成的 Word 有三条固定规矩：

- 页脚 `第 X 页 共 Y 页`（真实页码域，不是预填数字）
- 表格与图片整份文档连续编号：`表-1`、`图-1`，表题在上、图题在下
- 不写「文字对账」板块；ASR 纠错存旁挂文件，正文只留「校正 N 处」

<div align="center">
  <sub>（示例文档结构与截图请见仓库 Releases 或自行生成；仓库不包含任何第三方视频画面）</sub>
</div>

## 安装

前置：Windows 10/11 x64、DSH 桌面版、Git、Python 3.12（DSH 通常自带）。

```powershell
# 1. 克隆到 DSH 的技能目录（仓库根目录就是技能根目录）
git clone https://github.com/wonder-39/dsh-video-understanding "$env:USERPROFILE\.dsh\skills\video-understanding"

# 2. 一键安装（下载 ffmpeg + ImageMagick、建 venv 装依赖、写配置、自检）
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.dsh\skills\video-understanding\install.ps1"

# 3. 新开一个 DSH 对话，直接说「看看这条视频 <链接>」
```

安装脚本还会跑一次 11 项自检；看到「全部通过，可以开工」即可。工具默认装在 `D:\video-understanding`（无 D 盘则落用户目录），可用 `-ToolRoot` 指定。

## 用法

```text
看看这条视频 https://www.bilibili.com/video/BV...
批量过一遍这个收藏夹（3 条以上自动走批量档）
细致看，每秒都截一帧
```

## 目录结构

```text
dsh-video-understanding/
├─ SKILL.md                  技能主文件（DSH 读它）
├─ install.ps1               一键安装
├─ SETUP.md                  装机、迁移、踩坑清单
├─ references/
│   ├─ tiers.md              三档定义、成本、图片规则
│   ├─ batch.md              批量档流程
│   ├─ detailed.md           细致档流程
│   ├─ deliverable.md        文档结构与编号规范
│   ├─ types.md              类型判定与采样参数
│   └─ commands.md           可直接复制的命令序列
└─ scripts/
    ├─ asr_probe.py          语音闸门（Silero VAD）+ 转写 + 可疑段
    ├─ doctor.py             环境自检（11 项）
    └─ docx_helpers.py       Word 复用库（编号表图、页码域、固定列宽）
```

## 设计上的几个取舍

- **文字优先于画面。** 画面烧录字幕 > 语音识别 > 纯视觉。有字幕时逐句裁切校读，ASR 只用来补时间轴。
- **先闸门后转写。** 没有人声就不跑 ASR——否则会拿到编出来的台词。Silero VAD 检查不到唱歌，所以额外用「音频能量 + 强制转写后的文本多样性」兜底。
- **图版里的字不采信。** 分辨率不足时视觉会「编」出看起来合理的字，读字一律走原分辨率裁切放大。
- **诚实标注边界。** 每份文档都有可靠性声明：采样间隔、最大盲区、哪些是推测、哪些没核实。

## 依赖与成本

| 组件 | 体积 | 说明 |
|---|---|---|
| ffmpeg + ImageMagick | 约 870 MB | 安装脚本自动下载 |
| Python venv | 约 350 MB | faster-whisper / av / numpy / Pillow / python-docx |
| whisper 模型 | 按需（small 约 480 MB） | 首次转写时下载，走 hf-mirror |

## 许可

MIT。参考并依赖 [video-watch-plus](https://github.com/xinhailaopo/video-watch-plus)（MIT，© CFITSec 上游），该包不在本仓库内分发，由安装脚本从上游获取。
