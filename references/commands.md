# 命令序列（可直接复制）

路径以技能目录的 `config.json` 为准（`install.ps1` 生成）。下面这段会**自动读配置**，换机器不用改：

```powershell
$SKILL = 'C:\Users\jack\.dsh\skills\video-understanding'
$cfg   = Get-Content "$SKILL\config.json" -Raw | ConvertFrom-Json
$VW    = $cfg.video_watch_plus_skill
$VENV  = $cfg.venv_python
$ROOT  = $cfg.tool_root
$TOOLS = Join-Path $ROOT 'tools'
$FF    = Split-Path $cfg.ffmpeg -Parent
$WORK  = Join-Path $cfg.work_root '<slug>'
New-Item -ItemType Directory -Force -Path $WORK | Out-Null
$env:PYTHONIOENCODING = 'utf-8'
$env:HF_HOME = $cfg.hf_home
```

**所有 Python 命令都用 `$VENV`**（3.12，含 numpy/Pillow/faster-whisper/python-docx），不要用系统 Python。

> 没有 `config.json` 时先跑一次：`powershell -ExecutionPolicy Bypass -File "$SKILL\install.ps1"`

## 1. 下载（仅当源是链接）

```powershell
foreach ($n in @('HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy')) { Remove-Item "env:$n" -ErrorAction SilentlyContinue }
$env:NO_PROXY = '*'
& $VENV -m yt_dlp --ffmpeg-location $FF -f "bv*[height<=1080]+ba/b" --no-progress -o "$WORK\source.%(ext)s" '<url>'
```

> 坑：本地代理（127.0.0.1:7897）会让下载卡死在 "Established" 状态。先清代理变量再下。

## 2. 量测

```powershell
python "$VW\vendor\vw.py" probe "$WORK\source.mp4" --out "$WORK\probe"
```

产出 `$WORK\probe\timeline.json`。

## 3. 骨架初判（含字幕探测）

```powershell
# N = 骨架帧数，按分档算；--max = N + 2 让事件预算为 0
$N = 50
python "$VW\vendor\vw.py" plan "$WORK\probe\timeline.json" --skeleton $N --max ($N+2) --out "$WORK\triage.json"
python "$VW\vendor\vw.py" sheet "$WORK\triage.json" "$WORK\source.mp4" --out "$WORK\triage"
```

看图版：**有没有字幕条**、**什么类型**。

## 4. 字幕带（有烧录字幕时）

先整宽出一张，确认字幕在哪一带：

```powershell
# x,y,w,h —— 1280x720 的片子，字幕通常在 y≈570 起
python "$VW\vendor\vw.py" sheet "$WORK\triage.json" "$WORK\source.mp4" --out "$WORK\strip" --strip "0,570,1280,150" --strip-zoom 2
```

产出 `$WORK\strip\strip_NN.png`：**每张只装 2 条**（实测 52 帧 → 26 张），所以它适合"先确认字幕位置"，不适合批量读。

**批量读字幕用裁切 + 拼接**（每张 8 条，实测可读）：

```powershell
$img = "$WORK\subs"; New-Item -ItemType Directory -Force $img | Out-Null
$times = @(5,10,15,20,25,30,35,40)      # 要读的时刻，8 个一组
$i = 0; $files = @()
foreach ($t in $times) {
  $p = "$img\t$i.png"; $i++
  & "$FF\ffmpeg.exe" -hide_banner -loglevel error -ss $t -i "$WORK\source.mp4" -frames:v 1 -vf "crop=1280:150:0:570" $p -y
  $files += $p
}
& "$TOOLS\ImageMagick\magick.exe" montage $files -tile 1x -geometry +0+6 -background '#101010' "$img\stack.png"
```

一张 `stack.png` 里 8 条字幕，逐行读。条数太多（>10）字会变小，宁可多出几张。

> 坑一：`--strip` 的 `--out` 是**目录**；`plan` 的 `--out` 是**文件名**。写反了不一定报错。
> 坑二：`sheet` 的 `--media` 是片源本身（`$WORK\source.mp4`），**不是** `$WORK\probe\` 目录里的东西。写错会报 `No such file or directory`。

## 5. ASR（有人声且无字幕时）

```powershell
$env:HF_HOME = 'D:\Desktop\DSH-text\video-watch-plus\models'
$env:HF_ENDPOINT = 'https://hf-mirror.com'
$env:HF_HUB_DISABLE_XET = '1'
& $VENV "$VW\scripts\asr_hallucination_check.py" "$WORK\source.mp4" --model small --lang zh *> "$WORK\asr.txt"
```

> 模型 `small` 中文够用；`tiny` 只适合做闸门测试。
> 跑完先看判定那几行：`判定为幻觉` 或 `VAD 无输出` → 不要用它的文字。
>
> **无字幕时 ASR 必然有同音错字**，实测合成教学片：`趋势线→趋线`、`变陡→变斗`、`尖峰→监锋`、`先看轴→先看周`。没有字幕可校正时，这些位置必须在交付里标成「不确定」。

## 6. 声学闸门（可选但推荐）

```powershell
python "$VW\scripts\audio_probe.py" "$WORK\source.mp4" --json "$WORK\audio.json"
```

判型「未达判据（置信 low）」很常见——这是弃权，不是结论；此时以 ASR 的 VAD 为准。

## 7. 正式采样

```powershell
# 骨架 N + 事件预算 M（总帧数上限），burst 按类型，window 按类型
python "$VW\vendor\vw.py" plan "$WORK\probe\timeline.json" --skeleton $N --max 72 --burst 3 --window 120 --out "$WORK\shotlist.json"
python "$VW\vendor\vw.py" sheet "$WORK\shotlist.json" "$WORK\source.mp4" --out "$WORK\sheets"
```

## 8. 补细节

```powershell
# 某几秒的整帧（看构图/人物）
python "$VW\vendor\vw.py" grid --media "$WORK\source.mp4" --t0 100 --t1 130 --frames 9 --cols 3 --out "$WORK\detail"
# 某几秒的字（唯一可信读字通道）
python "$VW\vendor\vw.py" read --media "$WORK\source.mp4" --times "12,34" --region "0,560,1280,160" --out "$WORK\read"
```

## 参数速查

| 参数 | 属于 | 含义 |
|---|---|---|
| `--skeleton N` | plan | 骨架帧数（间隔 = 时长 ÷ N） |
| `--max M` | plan | 总帧数上限；`--max N+2` = 只出骨架 |
| `--burst B` | plan | 事件处连拍几帧（0 = 按运动量自动） |
| `--burst-dt` | plan | 组内间隔秒，默认 0.12 |
| `--window W` | plan | 事件名额轮转窗口秒数（小 = 分布更散） |
| `--pix-thresh` | plan | 画面内容突变阈值，文档/界面类可调低 |
| `--strip x,y,w,h` | sheet | 定窗条带：同一区域跨帧纵排（读字幕/读表格） |
| `--region x,y,w,h` | grid / read / seq | 先裁区域再拼接 |
| `--zoom N` | read / seq / strip-zoom | 放大倍数 |

## 输出文件约定

```text
$WORK\
├─ source.mp4
├─ probe\timeline.json
├─ triage.json + triage\         骨架初判
├─ strip\                        字幕带（有字幕时）
├─ asr.txt                       转写（有人声无字幕时）
├─ shotlist.json + sheets\       正式采样
├─ detail\  read\                补细节
└─ transcript.md                 对齐后的文字（字幕为准）
```
