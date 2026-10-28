# -*- coding: utf-8 -*-
"""语音闸门 + 转写 + 可疑片段检测（批量档核心）。

用法：
    python asr_probe.py <media> --out out.json
    python asr_probe.py <media> --gate-only            # 只判有无语音，不加载模型（秒级）
    python asr_probe.py <media> --fast                 # beam_size=1，更快
    python asr_probe.py <media> --model small --lang zh

退出码：0 正常；2 无音轨/解码失败；3 模型加载失败。
"""
import argparse
import json
import os
import sys
import time

SR = 16000


def decode(media):
    from faster_whisper.audio import decode_audio
    return decode_audio(media, sampling_rate=SR)


def vad_of(audio):
    """返回 (语音时长秒, 语音段列表, 总时长秒)。纯 CPU 计算，不加载 ASR 模型。"""
    from faster_whisper.vad import get_speech_timestamps, VadOptions
    ts = get_speech_timestamps(audio, VadOptions(), sampling_rate=SR)
    total = len(audio) / SR
    speech = sum((t["end"] - t["start"]) / SR for t in ts)
    return speech, ts, total


def energy_ratio(audio):
    """有声帧占比：用来兜住 VAD 的盲区（唱歌/音乐它常常听不出来）。"""
    import numpy as np
    frame = int(SR * 0.02)          # 20ms
    n = len(audio) // frame
    if n == 0:
        return 0.0
    rms = np.sqrt(np.mean(audio[:n * frame].reshape(n, frame) ** 2, axis=1))
    floor = float(np.percentile(rms, 10))
    thresh = max(floor * 3.0, 0.005)   # 比静音底噪高三倍，或绝对门限
    return float(np.mean(rms > thresh))


def gate_of(speech, total, energy=0.0):
    """三态闸门：VAD 说没有，不代表真的没有人（唱歌它不认）。"""
    ratio = speech / total if total > 0 else 0.0
    if ratio >= 0.05:
        return "speech", ratio
    if ratio >= 0.01:
        return "weak_speech", ratio
    # VAD 没听到 → 看能量：真静音才算无声，有能量就是「不确定」
    if energy < 0.02:
        return "silent", ratio
    return "uncertain", ratio


def transcribe(audio, model_name, lang, fast, download_root, vad_filter=True):
    from faster_whisper import WhisperModel

    def build(local_only):
        return WhisperModel(model_name, device="cpu", compute_type="int8",
                            download_root=download_root,
                            local_files_only=local_only)

    # 优先离线加载：批量档下每条都去问一次 Hub 会把 8 秒拖成 8 分钟
    try:
        model = build(True)
    except Exception:
        model = build(False)
    segs, info = model.transcribe(
        audio, language=lang, vad_filter=vad_filter,
        beam_size=1 if fast else 5,
        condition_on_previous_text=False,
    )
    out = []
    for s in segs:
        out.append({
            "start": round(s.start, 2),
            "end": round(s.end, 2),
            "text": s.text.strip(),
            "avg_logprob": round(s.avg_logprob, 3),
            "no_speech_prob": round(s.no_speech_prob, 3),
            "compression_ratio": round(s.compression_ratio, 2),
        })
    return out, getattr(info, "language", lang)


def looks_like_real_voice(segs):
    """关掉 VAD 强制出字之后，判断这批文本是真有人声还是幻觉。

    实测数据（small 模型、beam=1、vad_filter=False）：
      - 唱歌（4 分钟）：46 段、唯一 46/46、覆盖 78%、no_speech 0.66、logprob -0.69
      - 纯音（440Hz）：8 段、唯一 1/8、覆盖 99%、no_speech 0.58、logprob -1.11

    结论：no_speech 分不开这两者（唱歌本来就不像说话），**文本多样性**才是分水岭。
    """
    if len(segs) < 5:
        return False, f"段数太少（{len(segs)}）"
    texts = [s["text"] for s in segs if s["text"]]
    if not texts:
        return False, "没有文本"
    uniq = len(set(texts)) / len(texts)
    lp = sum(s["avg_logprob"] for s in segs) / len(segs)
    if uniq < 0.6:
        return False, f"文本重复率过高（unique {uniq:.2f}）"
    if lp < -0.9:
        return False, f"置信度过低（logprob {lp:.2f}）"
    return True, f"段数 {len(segs)}、unique {uniq:.2f}、logprob {lp:.2f}"


def find_suspicious(segs):
    """可疑段：低置信 / 高压缩比（复读）/ 自我判定无人声 / 过短 / 与相邻段重复。"""
    bad = []
    for i, s in enumerate(segs):
        why = []
        if s["avg_logprob"] < -0.6:
            why.append("low_logprob")
        if s["compression_ratio"] > 2.4:
            why.append("repetition")
        if s["no_speech_prob"] > 0.5:
            why.append("no_speech")
        if len(s["text"]) < 2:
            why.append("too_short")
        if i > 0 and s["text"] and s["text"] == segs[i - 1]["text"]:
            why.append("duplicate")
        if why:
            bad.append({**s, "why": why})
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("media")
    ap.add_argument("--out", default=None)
    ap.add_argument("--gate-only", action="store_true")
    ap.add_argument("--fast", action="store_true")
    ap.add_argument("--model", default="small")
    ap.add_argument("--lang", default="zh")
    args = ap.parse_args()

    if not os.path.exists(args.media):
        print(f"找不到文件：{args.media}", file=sys.stderr)
        return 2

    t0 = time.time()
    try:
        audio = decode(args.media)
    except Exception as e:
        print(f"解码失败（可能没有音轨）：{e}", file=sys.stderr)
        return 2

    speech, ts, total = vad_of(audio)
    energy = energy_ratio(audio)
    gate, ratio = gate_of(speech, total, energy)
    print(f"素材 {os.path.basename(args.media)}  时长 {total:.1f}s")
    print(f"语音 {speech:.1f}s / {total:.1f}s = {ratio:.1%}  语音段 {len(ts)} 个"
          f"  有声帧 {energy:.1%}")
    print(f"闸门初判：{gate}   耗时 {time.time()-t0:.1f}s（VAD 阶段）")

    result = {
        "media": os.path.basename(args.media),
        "duration": round(total, 2),
        "vad_gate": gate,
        "gate": gate,
        "verified_by": "vad",
        "speech_ratio": round(ratio, 4),
        "energy_ratio": round(energy, 4),
        "speech_segments": len(ts),
        "model": None,
        "language": None,
        "segments": [],
        "suspicious": [],
    }

    need_asr = gate in ("speech", "weak_speech", "uncertain") and not args.gate_only
    if gate == "uncertain":
        print("VAD 没听到人声但音频有能量（可能是唱歌/音乐）→ 交给 ASR 确认。")
    if gate in ("silent", "uncertain") and args.gate_only:
        print("（--gate-only：不转写）")
    if gate == "silent" and not args.gate_only:
        print("→ 近乎静音，按批量档规则不再转写。")

    if need_asr:
        download_root = os.environ.get("HF_HOME") or None
        try:
            segs, lang = transcribe(audio, args.model, args.lang, args.fast,
                                    download_root, vad_filter=True)
        except Exception as e:
            print(f"模型加载/转写失败：{e}", file=sys.stderr)
            return 3

        used_vad = True
        # 唱歌会被 VAD 整段滤掉（实测一首 4 分钟的歌 → 0 段）。
        # 闸门本来就是「不确定」时，关掉 VAD 再试一次，再用三条判据防幻觉。
        if not segs and gate == "uncertain":
            print("VAD 首轮 0 段（唱歌常这样）→ 关掉 VAD 重跑一次。")
            try:
                segs2, lang2 = transcribe(audio, args.model, args.lang,
                                          args.fast, download_root,
                                          vad_filter=False)
            except Exception as e:
                print(f"重跑失败：{e}", file=sys.stderr)
                segs2 = []
            if segs2:
                ok, why = looks_like_real_voice(segs2)
                print(f"强制出字判定：{'采信' if ok else '当幻觉丢弃'} —— {why}")
                if ok:
                    segs, lang, used_vad = segs2, lang2, False

        bad = find_suspicious(segs)
        result.update({"model": args.model, "language": lang,
                       "used_vad_filter": used_vad,
                       "segments": segs, "suspicious": bad})
        if gate == "uncertain":
            result["gate"] = "speech" if segs else "no_speech"
            result["verified_by"] = "asr"
        print(f"转写 {len(segs)} 段，可疑 {len(bad)} 段   总耗时 {time.time()-t0:.1f}s")
        print(f"闸门终判：{result['gate']}（依据 {result['verified_by']}"
              f"{'' if used_vad else '，未用 VAD'}）")
        for b in bad[:8]:
            print(f"  [{b['start']:7.1f}-{b['end']:7.1f}] {','.join(b['why'])} | {b['text'][:40]}")
        if len(bad) > 8:
            print(f"  …另有 {len(bad)-8} 段")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f"→ {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
