"""Раскладка записи автора по сценам (две записи → 11 клипов в audio_user/).

Границы вырезаны по словам из расшифровки faster-whisper: каждая сцена начинается
с первого слова фразы и кончается перед первым словом следующей. Так паузы
автора сохраняются, а лишнее «до» и «после» отрезается.

python3 src/cut_user_voice.py
"""
import os, subprocess, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SR = 48000
A = "/root/.hermes/cache/audio/audio_bbd49854cb2c.ogg"   # сцены 1-7
B = "/root/.hermes/cache/audio/audio_d0dd21460dff.ogg"   # сцены 8-11

# (источник, начало, конец, имя файла сцены)
CUTS = [
    (A, 0.00, 5.20, "01_hook.wav"),
    (A, 5.45, 10.60, "02_ui.wav"),
    (A, 10.95, 17.40, "03_compare.wav"),
    (A, 17.60, 23.10, "04_prompt.wav"),
    (A, 23.10, 28.80, "05_flow.wav"),
    (A, 29.00, 33.55, "06_skills.wav"),
    (A, 33.55, 38.30, "07_steps.wav"),
    (B, 0.85, 5.70, "08_tools.wav"),
    (B, 5.95, 10.45, "09_fix.wav"),
    (B, 10.45, 13.95, "10_file.wav"),
    (B, 14.05, 22.60, "11_outro.wav"),
]


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def trim_gate(x, thresh=0.008, pad_ms=55):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    x = x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]
    # гейт: давим шум в тихих окнах
    win = int(0.018 * SR)
    n = len(x) // win
    if n:
        body = x[:n * win].reshape(n, win)
        rms = np.sqrt((body ** 2).mean(axis=1))
        gain = np.clip((rms - 0.0025) / 0.005, 0, 1).astype(np.float32)
        gain = np.convolve(gain, np.ones(5) / 5, mode="same")
        x = np.concatenate([(body * gain[:, None]).reshape(-1), x[n * win:]])
    # мягкие края, чтобы не было щелчков
    f = int(0.008 * SR)
    if len(x) > 2 * f:
        x[:f] *= np.linspace(0, 1, f)
        x[-f:] *= np.linspace(1, 0, f)
    return x.astype(np.float32)


def save(path, x):
    peak = float(np.max(np.abs(x))) or 1.0
    x = x / peak * 0.9
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    out = os.path.join(ROOT, "audio_user")
    os.makedirs(out, exist_ok=True)
    src_cache = {A: decode(A), B: decode(B)}
    total = 0.0
    for path, a, b, name in CUTS:
        x = src_cache[path][int(a * SR):int(b * SR)]
        x = trim_gate(x)
        save(os.path.join(out, name), x)
        total += len(x) / SR
        print(f"{name:18s} {len(x)/SR:5.2f} с")
    print(f"итого речи {total:.1f} с")


if __name__ == "__main__":
    main()
