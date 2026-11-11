"""Сводит озвучку по таймлайну + тихий синтезированный эмбиент и вуши на стыках."""
import json, os, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень проекта (файлы лежат в src/)
OUT = os.path.join(ROOT, "out")
TL = json.load(open(os.path.join(ROOT, "timeline.json"), encoding="utf-8"))
AUDIO_DIR = os.environ.get("AUDIO_DIR") or os.path.join(ROOT, "audio")
if not os.path.isabs(AUDIO_DIR):
    AUDIO_DIR = os.path.join(ROOT, AUDIO_DIR)
SR = 48000
N = int(TL["total"] * SR) + SR


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def lowpass(x, cutoff):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X *= 1 / (1 + (f / cutoff) ** 4)
    return np.fft.irfft(X, len(x)).astype(np.float32)


def highpass(x, cutoff):
    return x - lowpass(x, cutoff)


def main():
    voice = np.zeros(N, dtype=np.float32)
    for sc in TL["scenes"]:
        a = decode(os.path.join(AUDIO_DIR, sc["audio"]))
        s = int(sc["voice_start"] * SR)
        voice[s:s + len(a)] += a
    voice /= max(1e-6, np.max(np.abs(voice))) / 0.92

    t = np.arange(N) / SR
    rng = np.random.default_rng(11)

    # --- пэд: Am - F - C - G, очень тихо ---
    chords = [[220.0, 261.63, 329.63], [174.61, 220.0, 261.63],
              [130.81, 196.0, 261.63], [196.0, 246.94, 293.66]]
    pad = np.zeros(N, dtype=np.float32)
    bar = 6.4
    for k in range(int(TL["total"] / bar) + 2):
        ch = chords[k % 4]
        s, e = int(k * bar * SR), min(N, int((k + 1) * bar * SR + SR * 0.8))
        if s >= N:
            break
        seg = np.arange(e - s) / SR
        env = np.minimum(1, seg / 1.2) * np.minimum(1, (len(seg) / SR - seg) / 1.2).clip(0, 1)
        blk = np.zeros(e - s, dtype=np.float32)
        for f in ch:
            for det in (0.997, 1.003):
                blk += np.sin(2 * np.pi * f * det * seg + rng.uniform(0, 6)).astype(np.float32)
            blk += 0.25 * np.sin(2 * np.pi * f * 2 * seg).astype(np.float32)
        pad[s:e] += (blk / (len(ch) * 2.6)) * env
    pad = lowpass(pad, 900) * 0.07

    # --- воздух ---
    air = lowpass(rng.normal(0, 1, N).astype(np.float32), 2400)
    air = highpass(air, 500) * 0.0  # шум убран: между фразами должна быть тишина

    # --- пульс: мягкий кик 90 BPM + шляпка ---
    beat = 60 / 90
    pulse = np.zeros(N, dtype=np.float32)
    for k in range(int(TL["total"] / beat) + 1):
        s = int(k * beat * SR)
        L = int(0.16 * SR)
        if s + L >= N:
            break
        seg = np.arange(L) / SR
        kick = np.sin(2 * np.pi * (58 - 22 * seg / 0.16) * seg) * np.exp(-seg * 26)
        pulse[s:s + L] += kick.astype(np.float32) * (0.16 if k % 2 == 0 else 0.09)
        if k % 2 == 1:
            Lh = int(0.05 * SR)
            hh = highpass(rng.normal(0, 1, Lh).astype(np.float32), 6000) * np.exp(-np.arange(Lh) / SR * 90)
            pulse[s:s + Lh] += hh * 0.05
    pulse = lowpass(pulse, 3000)

    # --- вуши на стыках сцен ---
    whoosh = np.zeros(N, dtype=np.float32)
    for sc in TL["scenes"][1:]:
        s = int((sc["start"] - 0.16) * SR)
        L = int(0.42 * SR)
        if s < 0 or s + L >= N:
            continue
        seg = np.arange(L) / SR
        nz = rng.normal(0, 1, L).astype(np.float32)
        nz = highpass(nz, 900)
        env = np.sin(np.pi * seg / (L / SR)) ** 2.2
        whoosh[s:s + L] += nz * env * 0.0  # вуши убраны
    # акцент на финале
    s = int((TL["scenes"][-1]["start"] + 0.1) * SR)
    L = int(0.9 * SR)
    if s + L < N:
        seg = np.arange(L) / SR
        boom = np.sin(2 * np.pi * 46 * seg) * np.exp(-seg * 4.2)
        whoosh[s:s + L] += boom.astype(np.float32) * 0.10

    music = pad + air + pulse + whoosh
    # музыка тише под речью
    duck = np.ones(N, dtype=np.float32)
    for sc in TL["scenes"]:
        a, b = int((sc["voice_start"] - 0.1) * SR), int((sc["voice_end"] + 0.15) * SR)
        duck[max(0, a):min(N, b)] = 0.33
    k = int(0.08 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same").astype(np.float32)
    mix = voice + music * duck
    mix = np.tanh(mix * 1.02) * 0.97

    raw = os.path.join(OUT, "mix_raw.wav")
    with open(raw, "wb") as f:
        f.write(b"")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1",
                    "-i", "pipe:0", "-af",
                    "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2",
                    os.path.join(OUT, "mix.wav")],
                   input=mix.astype(np.float32).tobytes(), check=True)
    # версия без музыки — на случай трендового звука в приложении
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "f32le", "-ar", str(SR), "-ac", "1",
                    "-i", "pipe:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2",
                    os.path.join(OUT, "voice_only.wav")],
                   input=voice.astype(np.float32).tobytes(), check=True)
    print("mix.wav ready", round(N / SR, 2), "s")


if __name__ == "__main__":
    main()
