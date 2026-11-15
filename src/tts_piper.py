#!/usr/bin/env python3
"""Озвучка эпизода piper-tts (мужские ru-голоса: ruslan / denis / dmitri).

Silero не используется по требованию автора канала.

    EPISODE_DIR=episodes/hermes python3 src/tts_piper.py --voice ruslan

Пишет audio/NN.wav 48 кГц моно в формате, который ждёт timeline.py:
каждая фраза синтезируется отдельно, края обрезаются, тихий шум гаснет.
"""
import argparse, json, os, re, subprocess, tempfile, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
VOICE_DIR = os.path.join(ROOT, "voices", "piper")

LEAD = 0.15
GAP = 0.34
TAIL = 0.28

SENT = re.compile(r"(?<=[.!?…])\s+")

EP = os.environ.get("EPISODE_DIR") or ROOT
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
AUD = os.path.join(EP, "audio")
os.makedirs(AUD, exist_ok=True)
SCRIPT = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))


def synth(text, model, length_scale):
    """Одна фраза -> float32 48 кГц."""
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tf:
        raw = tf.name
    p = subprocess.run(["piper", "-m", model, "-f", raw,
                        "--length-scale", str(length_scale)],
                       input=text.encode(), capture_output=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.decode()[-400:])
    wav48 = raw + ".48.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw,
                    "-ar", str(SR), "-ac", "1", wav48], check=True)
    with wave.open(wav48) as w:
        x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768
    os.unlink(raw); os.unlink(wav48)
    return x


def trim_edges(x, thresh=0.010, pad_ms=70):
    idx = np.where(np.abs(x) > thresh)[0]
    if not len(idx):
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]


def denoise_low(x, thresh=0.0045, win_ms=18):
    win = max(1, int(win_ms / 1000 * SR))
    n = len(x) // win
    if not n:
        return x
    body = x[:n * win].reshape(n, win)
    rms = np.sqrt((body ** 2).mean(axis=1))
    gain = np.clip((rms - thresh) / (thresh * 2), 0, 1).astype(np.float32)
    gain = np.convolve(gain, np.ones(5) / 5, mode="same")
    return np.concatenate([(body * gain[:, None]).reshape(-1), x[n * win:]]).astype(np.float32)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="ruslan", choices=["ruslan", "denis", "dmitri"])
    ap.add_argument("--length-scale", type=float, default=1.05,
                    help="больше = медленнее")
    a = ap.parse_args()
    model = os.path.join(VOICE_DIR, f"ru_RU-{a.voice}-medium.onnx")
    if not os.path.exists(model):
        raise SystemExit(f"нет модели {model}")

    for sc in SCRIPT["scenes"]:
        text = (sc.get("tts") or sc["text"]).replace("+", "")
        parts = [p.strip() for p in SENT.split(text) if p.strip()]
        chunks = [denoise_low(trim_edges(synth(p, model, a.length_scale))) for p in parts]
        out = [np.zeros(int(LEAD * SR), dtype=np.float32)]
        for i, c in enumerate(chunks):
            out.append(c)
            out.append(np.zeros(int((GAP if i < len(chunks) - 1 else TAIL) * SR), dtype=np.float32))
        y = np.concatenate(out)
        peak = float(np.max(np.abs(y))) or 1.0
        y = y / peak * 0.92
        path = os.path.join(AUD, sc["audio"])
        with wave.open(path, "wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
            w.writeframes((np.clip(y, -1, 1) * 32767).astype(np.int16).tobytes())
        print(f"{sc['audio']:10s} {len(y)/SR:6.2f}s  {sc['text'][:44]}…", flush=True)


if __name__ == "__main__":
    main()
