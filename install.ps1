<#
.SYNOPSIS
    一键安装 video-understanding 视频理解工作流（Windows）。

.DESCRIPTION
    做四件事：
      1. 克隆底层技能 video-watch-plus（GitHub）
      2. 下载 ffmpeg 完整构建 + ImageMagick 便携版（约 280MB）
      3. 建 Python 3.12 虚拟环境并装 faster-whisper / av / numpy / yt-dlp
      4. 写 config.json + 环境变量，跑 doctor 自检

.USAGE
    powershell -ExecutionPolicy Bypass -File install.ps1
    powershell -ExecutionPolicy Bypass -File install.ps1 -ToolRoot D:\video-understanding
    powershell -ExecutionPolicy Bypass -File install.ps1 -SkipTools -SkipVenv    # 只写配置
#>
[CmdletBinding()]
param(
    [string]$ToolRoot = "",
    [string]$SkillRoot = "",
    [switch]$SkipTools,
    [switch]$SkipVenv,
    [switch]$SkipEnv
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Info($m) { Write-Host "[*] $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "[ok] $m" -ForegroundColor Green }
function Warn($m) { Write-Host "[!] $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "[x] $m" -ForegroundColor Red; exit 1 }

# ---------- 0. 定位 ----------
if (-not $SkillRoot) {
    $SkillRoot = Split-Path -Parent $PSCommandPath
}
if (-not (Test-Path (Join-Path $SkillRoot "SKILL.md"))) {
    Die "SkillRoot 里没有 SKILL.md：$SkillRoot"
}
if (-not $ToolRoot) {
    if (Test-Path "D:\") { $ToolRoot = "D:\video-understanding" }
    else { $ToolRoot = Join-Path $env:USERPROFILE "video-understanding" }
}
$DshSkills = Join-Path $env:USERPROFILE ".dsh\skills"
$VwSkill = Join-Path $DshSkills "video-watch-plus"

Info "技能目录：$SkillRoot"
Info "工具目录：$ToolRoot"
New-Item -ItemType Directory -Force -Path $ToolRoot | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ToolRoot "models") | Out-Null
New-Item -ItemType Directory -Force -Path (Join-Path $ToolRoot "work") | Out-Null

# ---------- 1. 底层技能 ----------
if (-not (Test-Path (Join-Path $VwSkill "vendor\vw.py"))) {
    if (-not (Get-Command git -ErrorAction SilentlyContinue)) { Die "需要 git，请先安装 Git for Windows" }
    New-Item -ItemType Directory -Force -Path $DshSkills | Out-Null
    Info "克隆 video-watch-plus …"
    & git clone --depth 1 https://github.com/xinhailaopo/video-watch-plus $VwSkill
    if ($LASTEXITCODE -ne 0) { Die "克隆失败，请检查网络或手动 clone 到 $VwSkill" }
}
Ok "底层技能就位：$VwSkill"

# ---------- 2. 工具链 ----------
$ffmpeg = ""; $ffprobe = ""; $magick = ""
if (-not $SkipTools) {
    $setup = Join-Path $VwSkill "scripts\setup-windows.ps1"
    if (-not (Test-Path $setup)) { Die "找不到 $setup" }
    Info "下载 ffmpeg + ImageMagick（约 280MB），可能需要几分钟 …"
    & powershell -ExecutionPolicy Bypass -File $setup `
        -ToolsDir (Join-Path $ToolRoot "tools") `
        -VwPy (Join-Path $VwSkill "vendor\vw.py")
    if ($LASTEXITCODE -ne 0) { Warn "setup-windows.ps1 返回 $LASTEXITCODE，继续尝试读配置" }
}
$vwCfg = Join-Path $env:USERPROFILE ".config\video-watch\vw.config.json"
if (Test-Path $vwCfg) {
    $j = Get-Content $vwCfg -Raw | ConvertFrom-Json
    $ffmpeg = $j.ffmpeg; $ffprobe = $j.ffprobe; $magick = $j.magick
    Ok "从 vw.config.json 读到工具路径"
} else {
    Warn "没找到 vw.config.json（工具可能没装），doctor 会报告缺失"
}

# ---------- 3. Python 3.12 环境 ----------
$venv = Join-Path $ToolRoot "venv"
$vpy = Join-Path $venv "Scripts\python.exe"

function Find-Py312 {
    $cands = @()
    # DSH 自带的 3.12
    $cands += (Join-Path $env:USERPROFILE ".dsh\dsh-runtimes\dsh-primary-runtime\dependencies\python\python.exe")
    $cands += "D:\sorftware\DSH\DSH\resources\runtime\primary-runtime\dependencies\python\python.exe"
    foreach ($c in $cands) {
        if (Test-Path $c) { return $c }
    }
    if (Get-Command py -ErrorAction SilentlyContinue) {
        try { $p = & py -3.12 -c "import sys;print(sys.executable)" 2>$null; if ($p) { return $p.Trim() } } catch {}
    }
    return $null
}

if (-not $SkipVenv) {
    if (-not (Test-Path $vpy)) {
        $base = Find-Py312
        if (-not $base) { Die "找不到 Python 3.12。请先装 Python 3.12（3.13/3.14 缺 ctranslate2 wheel）" }
        Info "用 $base 建虚拟环境 …"
        & $base -m venv $venv
        if ($LASTEXITCODE -ne 0) { Die "创建 venv 失败" }
    }
    Ok "venv 就位：$vpy"

    Info "安装 faster-whisper / av<19 / numpy / yt-dlp …"
    $env:HF_ENDPOINT = "https://hf-mirror.com"
    $env:HF_HUB_DISABLE_XET = "1"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if ($uv) {
        & uv pip install --python $vpy faster-whisper "av<19" numpy yt-dlp pillow python-docx
    } else {
        # 没有 uv 时先尝试装 uv（解析快得多），失败再退回 pip
        & $vpy -m pip install --quiet uv 2>$null
        if ($LASTEXITCODE -eq 0 -and (Test-Path (Join-Path $venv "Scripts\uv.exe"))) {
            & (Join-Path $venv "Scripts\uv.exe") pip install --python $vpy faster-whisper "av<19" numpy yt-dlp pillow python-docx
        } else {
            Warn "没有 uv，改用 pip（依赖解析可能较慢）"
            & $vpy -m pip install --only-binary=:all: faster-whisper "av<19" numpy yt-dlp pillow python-docx
        }
    }
    if ($LASTEXITCODE -ne 0) { Warn "依赖安装返回 $LASTEXITCODE，请运行 doctor 确认" }
}

# ---------- 4. 环境变量 ----------
if (-not $SkipEnv) {
    $hfHome = Join-Path $ToolRoot "models"
    [Environment]::SetEnvironmentVariable("HF_HOME", $hfHome, "User")
    [Environment]::SetEnvironmentVariable("HF_ENDPOINT", "https://hf-mirror.com", "User")
    [Environment]::SetEnvironmentVariable("HF_HUB_DISABLE_XET", "1", "User")
    Ok "已写用户级环境变量 HF_HOME / HF_ENDPOINT / HF_HUB_DISABLE_XET"
}

# ---------- 5. 写 config.json（无 BOM） ----------
$cfg = [ordered]@{
    video_watch_plus_skill = $VwSkill
    tool_root              = $ToolRoot
    venv_python            = $vpy
    ffmpeg                 = $ffmpeg
    ffprobe                = $ffprobe
    magick                 = $magick
    hf_home                = (Join-Path $ToolRoot "models")
    work_root              = (Join-Path $ToolRoot "work")
}
$cfgPath = Join-Path $SkillRoot "config.json"
$json = $cfg | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText($cfgPath, $json, [Text.UTF8Encoding]::new($false))
Ok "已写配置：$cfgPath"

# ---------- 6. 自检 ----------
$doctor = Join-Path $SkillRoot "scripts\doctor.py"
$pyForDoctor = $vpy
if (-not (Test-Path $pyForDoctor)) {
    $pyForDoctor = (Find-Py312)
}
if ((Test-Path $doctor) -and $pyForDoctor) {
    Info "运行自检 …"
    & $pyForDoctor $doctor
} else {
    Warn "跳过自检（缺 doctor.py 或 Python）"
}
