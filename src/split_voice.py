"""Режет запись пользователя на сцены по паузам и укладывает в audio_user/.

python3 src/split_voice.py запись.ogg --expect 11

Требования к записи: 11 фраз подряд, пауза ~1 секунда между фразами.
Скрипт находит речевые сегменты через silencedetect, проверяет количество,
обрезает края и гасит тихий шум. Если сегментов больше/меньше — падает
с понятным сообщением, чтобы не собирать ролик на кривых таймингах.
"""
import argparse, os, re, subprocess, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
SCENE_FILES = [f"{i:02d}_{name}.wav" for i, name in enumerate(
    ["hook", "ui", "compare", "prompt", "flow", "skills", "steps", "tools", "fix", "file", "outro"], 1)]


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def speech_segments(path, min_pause=0.45, thresh_db=-38):
    dur = len(decode(path)) / SR
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                        "-af", f"silencedetect=n={thresh_db}dB:d={min_pause}", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start: (-?[\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    segs, cur = [], 0.0
    for i, s in enumerate(starts):
        e = ends[i] if i < len(ends) else dur
        if s - cur > 0.30:
            segs.append((max(0.0, cur), s))
        cur = e
    if dur - cur > 0.30:
        segs.append((cur, dur))
    return segs


def trim_gate(x, thresh=0.006, pad_ms=60):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)].astype(np.float32)


def save_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("source")
    ap.add_argument("--expect", type=int, default=11)
    ap.add_argument("--out", default="audio_user")
    a = ap.parse_args()

    segs = speech_segments(a.source)
    print(f"найдено фраз: {len(segs)} (ожидалось {a.expect})")
    for i, (s, e) in enumerate(segs, 1):
        print(f"  {i:2d}. {s:6.2f} → {e:6.2f}  ({e - s:.2f} с)")
    if len(segs) != a.expect:
        sys.exit("количество фраз не совпало — перепиши с более ровными паузами "
                 "(~1 секунда между фразами) или поправь --expect")

    x = decode(a.source)
    out_dir = a.out if os.path.isabs(a.out) else os.path.join(ROOT, a.out)
    os.makedirs(out_dir, exist_ok=True)
    total = 0.0
    for (s, e), fn in zip(segs, SCENE_FILES):
        clip = trim_gate(x[int(s * SR):int(e * SR)])
        peak = float(np.max(np.abs(clip))) or 1.0
        clip = clip / peak * 0.9
        save_wav(os.path.join(out_dir, fn), clip)
        total += len(clip) / SR
        print(f"  → {fn:18s} {len(clip)/SR:5.2f} с")
    print(f"итого речи: {total:.1f} с (+ паузы между сценами)")


if __name__ == "__main__":
    main()
