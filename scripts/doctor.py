# -*- coding: utf-8 -*-
"""video-understanding 工作流自检：在任何对话、任何工作目录下都能跑。

    python "C:\\Users\\jack\\.dsh\\skills\\video-understanding\\scripts\\doctor.py"

路径优先读技能目录下的 config.json（由 install.ps1 生成），没有再退回本机默认值。
全绿（exit 0）说明这套工作流可用；有 FAIL 会打印修复命令。
"""
import json
import os
import shutil
import subprocess
import sys

SKILL = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INSTALL_CFG = os.path.join(SKILL, "config.json")


def _install_cfg():
    try:
        with open(INSTALL_CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


_IC = _install_cfg()

VW = _IC.get("video_watch_plus_skill") or r"C:\Users\jack\.dsh\skills\video-watch-plus"
ROOT = _IC.get("tool_root") or r"D:\Desktop\DSH-text\video-watch-plus"
VENV = _IC.get("venv_python") or os.path.join(ROOT, "venv", "Scripts", "python.exe")
CFG = os.path.join(os.path.expanduser("~"), ".config", "video-watch", "vw.config.json")

FILTERS = ["scdet", "freezedetect", "silencedetect", "tblend",
           "signalstats", "tile", "drawtext"]

results = []


def check(name, ok, detail="", fix=""):
    results.append((name, ok, detail, fix))
    return ok


def read_cfg():
    try:
        with open(CFG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def main():
    cfg = read_cfg()
    ffmpeg = cfg.get("ffmpeg") or shutil.which("ffmpeg") or ""
    ffprobe = cfg.get("ffprobe") or shutil.which("ffprobe") or ""
    magick = cfg.get("magick") or shutil.which("magick") or ""

    # 1. 技能文件
    missing = [f for f in ("SKILL.md", "references/types.md",
                           "references/commands.md",
                           "references/deliverable.md",
                           "references/tiers.md",
                           "references/batch.md",
                           "references/detailed.md",
                           "scripts/docx_helpers.py",
                           "scripts/asr_probe.py")
               if not os.path.exists(os.path.join(SKILL, f))]
    check("技能文件完整", not missing, ", ".join(missing) if missing else "9 个文件齐全",
          "重新解压技能包到 " + SKILL)

    # 2. 底层工具（video-watch-plus）
    vw_py = os.path.join(VW, "vendor", "vw.py")
    check("video-watch-plus 在位", os.path.exists(vw_py), vw_py,
          "重新 clone video-watch-plus 到 " + VW)

    # 3. 媒体工具
    check("ffmpeg", bool(ffmpeg) and os.path.exists(ffmpeg), ffmpeg or "未找到",
          "跑 video-watch-plus/scripts/setup-windows.ps1")
    check("ffprobe", bool(ffprobe) and os.path.exists(ffprobe), ffprobe or "未找到",
          "同上")
    check("ImageMagick", bool(magick) and os.path.exists(magick), magick or "未找到",
          "同上（图版拼接必需）")

    # 4. ffmpeg 滤镜
    if ffmpeg and os.path.exists(ffmpeg):
        try:
            out = subprocess.run([ffmpeg, "-hide_banner", "-filters"],
                                 capture_output=True, text=True, timeout=60).stdout
            lack = [f for f in FILTERS if f" {f} " not in out]
        except Exception as e:
            lack = [f"读取失败: {e}"]
        check("ffmpeg 7 个必需滤镜", not lack,
              "缺少 " + ", ".join(lack) if lack else "scdet/freezedetect/…/drawtext 齐备",
              "换 ffmpeg 完整构建（需 libfreetype）")

    # 5. ASR 环境
    check("ASR venv（Python 3.12）", os.path.exists(VENV), VENV or "未找到",
          "用 3.12 建 venv 并装 faster-whisper、av<19、numpy")
    if os.path.exists(VENV):
        code = ("import faster_whisper, av, numpy, yt_dlp; "
                "print(faster_whisper.__version__, av.__version__, numpy.__version__)")
        try:
            r = subprocess.run([VENV, "-c", code], capture_output=True,
                               text=True, timeout=120)
            ok = r.returncode == 0
            detail = r.stdout.strip() if ok else (r.stderr.strip().splitlines() or [""])[-1]
        except Exception as e:
            ok, detail = False, str(e)
        check("ASR 依赖可导入", ok, detail,
              "venv\\Scripts\\python -m pip install faster-whisper \"av<19\" numpy yt-dlp")
        # 批量档的语音闸门依赖这条
        vcode = ("from faster_whisper.vad import get_speech_timestamps; "
                 "print('vad ok')")
        try:
            r = subprocess.run([VENV, "-c", vcode], capture_output=True,
                               text=True, timeout=120)
            vok = r.returncode == 0
            vdetail = r.stdout.strip() if vok else (r.stderr.strip().splitlines() or [""])[-1]
        except Exception as e:
            vok, vdetail = False, str(e)
        check("VAD 闸门可用（批量档）", vok, vdetail,
              "升级 faster-whisper；或批量档退回用 asr_hallucination_check.py")

    # 6. 模型缓存
    hf = _IC.get("hf_home") or os.environ.get("HF_HOME") or os.path.join(ROOT, "models")
    check("模型缓存目录", os.path.isdir(hf), hf,
          "设 HF_HOME 到该目录，或首次转写时自动创建")

    # 7. Word 交付（优先查 venv，其次查当前解释器）
    ok, detail = False, "缺 python-docx"
    try:
        import docx  # noqa: F401
        ok, detail = True, "python-docx 可用（当前解释器）"
    except Exception:
        if os.path.exists(VENV):
            try:
                r = subprocess.run([VENV, "-c", "import docx; print('ok')"],
                                   capture_output=True, text=True, timeout=120)
                if r.returncode == 0:
                    ok, detail = True, "python-docx 可用（venv）"
            except Exception:
                pass
    check("Word 依赖（python-docx）", ok, detail,
          "venv\\Scripts\\python -m pip install python-docx pillow")

    # 输出
    width = max(len(r[0]) for r in results)
    fails = 0
    print()
    print("  video-understanding 工作流自检")
    print("  " + "-" * 62)
    for name, ok, detail, fix in results:
        flag = "OK  " if ok else "FAIL"
        if not ok:
            fails += 1
        print(f"  [{flag}] {name.ljust(width)}  {detail}")
        if not ok and fix:
            print(f"         修复：{fix}")
    print("  " + "-" * 62)
    if fails == 0:
        print("  全部通过，可以开工。")
        print("  用法：把视频链接或本地路径交给我，会自动出 Word 报告。")
    else:
        print(f"  {fails} 项未通过，按上面的修复提示处理。")
    print()
    return 0 if fails == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
