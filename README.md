# dsh-video-understanding

给 DeepSeek Harness用的视频理解技能包：

让DSH理解视频，生成一份结构化的视频总结（.docx格式）。

使用方法：输入B 站视频链接或本地视频地址，DSH会按工作流，抓帧（截图），音频转文字字幕，读画面字幕校准，判断视频类型，输出带编号表图的视频总结报告。

> 底层依赖 video-watch-plus（https://github.com/xinhailaopo/video-watch-plus    ）  （MIT，ffmpeg 量测与图版工具）——本仓库增加了我设计的工作流，规范DSH「什么时候抓帧、字幕校准方法、分档生成总结规范」。

## 它能做什么

三个档位，按需求和预算选：

| 档位 | 触发语 | 机制 | 产出 |
|---|---|---|---|
| 批量档 | 「批量过一遍」 | 直接语音转字幕，再校准字幕。分析校准后的字幕，生成总结。适用于那些吃灰的文件夹，批量生成文表总结，再决定要不要看，token 成本较低，适合批量使用。 | 总览表 + 每条 3–5 条要点，不含图片 |
| 标准档（默认） | 「看这条视频」 | 如果你没有说明使用“批量档”或“细致档”，默认使用此档位。抓帧依据骨架和字幕，以及硬切判断，智能抓帧，生成图文表总结。成本及时间较为均衡。 | 结构时间轴 + 逐段拆解 + 重点对比 + 可靠性声明 |
| 细致档 | 「仔细看」 | 由于标准档是根据模型运算结果智能抓帧，难免会有一些画面疏漏。那细致档就更简单粗暴，每秒截一帧分析（我想就算我想要看清楚画面也要起码1秒吧），生成图文表总结。成本和时间较高。 | 逐页表（每秒一帧）+ 完整视频图文总结 + 重点细讲 + 字幕全文 |

两种视频性质，决定文档结构：

| 类别 | 包含 | 差异 |
|---|---|---|
| 观点类 | 教学、科普、经验分享、新闻、评论、访谈 | 标准档有「重点突出」、细致档有「重点细讲」 |
| 赏析类 | 音乐 PV、娱乐搞笑、生活/vlog、纯记录 | 上述两节去掉，靠逐段拆解承载判断 |

## 输出长什么样

生成的 Word，不同档位有不同规范，默认是我的规范，你想改让DSH改就好。

参考视频：经验分享类，音乐PV（没错，她竟然可以解析音乐PV！）

## 安装

建议直接把本仓库地址发给DSH，让它检查一下是否可以安装，可以避免很多不必要的麻烦。

前置：Windows 10/11 x64、DSH 桌面版、Git、Python 3.12（DSH 通常自带）。

```powershell
# 1. 克隆到 DSH 的技能目录（仓库根目录就是技能根目录）
git clone https://github.com/wonder-39/dsh-video-understanding "$env:USERPROFILE\.dsh\skills\video-understanding"

# 2. 一键安装（下载 ffmpeg + ImageMagick、建 venv 装依赖、写配置、自检）
powershell -ExecutionPolicy Bypass -File "$env:USERPROFILE\.dsh\skills\video-understanding\install.ps1"

# 3. 新开一个 DSH 对话，直接说「看看这条视频 <链接>」
```

安装脚本还会跑一次 11 项自检；看到「全部通过，可以开工」即可。工具默认装在 D:\video-understanding（无 D 盘则落用户目录），可用 -ToolRoot 指定。

## 用法

```text
看看这条视频 https://www.bilibili.com/video/BV...
批量过一遍这个收藏夹（3 条以上自动走批量档）
仔细看，每秒都截一帧
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

- 文字优先于画面。 画面烧录字幕 > 语音识别 > 纯视觉。有字幕时逐句裁切校读，ASR 只用来补时间轴。相当于字幕识别互校正。
- 先闸门后转写。 没有人声就不跑 ASR——否则会拿到编出来的台词。Silero VAD 检查不到唱歌，所以额外用「音频能量 + 强制转写后的文本多样性」兜底。就是先判断有没有人声，避免在纯音乐或 BGM 上乱编字幕。
- 诚实标注边界。 每份文档都有可靠性声明：采样间隔、最大盲区、哪些是推测、哪些没核实。

## 依赖与成本

| 组件 | 体积 | 说明 |
|---|---|---|
| ffmpeg + ImageMagick | 约 870 MB | 安装脚本自动下载 |
| Python venv | 约 350 MB | faster-whisper / av / numpy / Pillow / python-docx |
| whisper 模型 | 按需（small 约 480 MB） | 首次转写时下载，走 hf-mirror |

## 许可&声明

MIT。参考并依赖 video-watch-plus（https://github.com/xinhailaopo/video-watch-plus）（MIT，© CFITSec 上游），该包不在本仓库内分发，由安装脚本从上游获取。

声明：由于是我第一次在github发项目，如有不规范请指正并见谅。
