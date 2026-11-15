#!/usr/bin/env python3
"""Микс эпизода: голос + synthwave-бит (100 BPM, ля минор) + вжухи на акцентах.

    EPISODE_DIR=episodes/hermes-agent python3 src/audio_mix_sw.py

Пишет out/mix.wav (голос + музыка, −14 LUFS) и out/voice_only.wav.
"""
import json, os, subprocess
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EP = os.environ.get("EPISODE_DIR") or ROOT
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
OUT = os.path.join(EP, "out")
os.makedirs(OUT, exist_ok=True)
TL = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
AUDIO_DIR = os.environ.get("AUDIO_DIR") or os.path.join(EP, "audio")
if not os.path.isabs(AUDIO_DIR):
    AUDIO_DIR = os.path.join(ROOT, AUDIO_DIR)
SR = 48000
TOTAL = float(TL["total"])
N = int(TOTAL * SR)

BPM = 100.0
BEAT = 60.0 / BPM          # 0.6 c
BAR = BEAT * 4             # 2.4 c


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


def add(buf, sig, at):
    """Наложить сигнал в буфер с указанной секунды."""
    s = int(at * SR)
    if s >= len(buf) or s < 0:
        return
    e = min(len(buf), s + len(sig))
    buf[s:e] += sig[:e - s]


def env_ad(n, attack=0.005, decay=8.0):
    t = np.arange(n) / SR
    a = np.clip(t / max(attack, 1e-4), 0, 1)
    return (a * np.exp(-t * decay)).astype(np.float32)


# ---------------- барабаны ----------------
def kick(dur=0.32):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 48 + 110 * np.exp(-t * 24)
    ph = 2 * np.pi * np.cumsum(f) / SR
    body = np.sin(ph) * np.exp(-t * 9)
    click = np.exp(-t * 260) * 0.25
    return (body + click).astype(np.float32)


def snare(dur=0.22, rng=None):
    n = int(dur * SR)
    rng = rng or np.random.default_rng(3)
    nz = highpass(rng.normal(0, 1, n).astype(np.float32), 1200)
    tone = np.sin(2 * np.pi * 190 * np.arange(n) / SR) * 0.35
    return ((nz * 0.6 + tone) * env_ad(n, 0.002, 22)).astype(np.float32)


def hat(dur=0.06, rng=None, open_=False):
    n = int((0.16 if open_ else dur) * SR)
    rng = rng or np.random.default_rng(5)
    nz = highpass(rng.normal(0, 1, n).astype(np.float32), 7000)
    return (nz * env_ad(n, 0.001, 60 if open_ else 110) * 0.9).astype(np.float32)


def whoosh(dur=0.55, rng=None, up=True):
    n = int(dur * SR)
    rng = rng or np.random.default_rng(9)
    t = np.arange(n) / SR
    x = t / dur
    # шумовой слой + тон-свип: вместе даёт «вжух»
    nz = rng.normal(0, 1, n).astype(np.float32)
    nz = highpass(lowpass(nz, 9000), 700) * 0.55
    f0, f1 = (500, 3200) if up else (3200, 500)
    f = f0 + (f1 - f0) * x ** 1.6
    tone = np.sin(2 * np.pi * np.cumsum(f) / SR) * 0.45
    env = np.sin(np.pi * x) ** 1.6
    return ((nz + tone) * env).astype(np.float32)


def boom(dur=0.9):
    n = int(dur * SR)
    t = np.arange(n) / SR
    f = 42 + 30 * np.exp(-t * 6)
    ph = 2 * np.pi * np.cumsum(f) / SR
    return (np.sin(ph) * np.exp(-t * 3.2)).astype(np.float32)


# ---------------- гармония ----------------
PROG = [  # ля минор: Am, F, C, G — по такту
    [220.00, 261.63, 329.63],
    [174.61, 220.00, 261.63],
    [130.81, 196.00, 261.63],
    [196.00, 246.94, 293.66],
]


def synth_saw(f, n, harmonics=7, detune=0.0):
    t = np.arange(n) / SR
    s = np.zeros(n, dtype=np.float32)
    for k in range(1, harmonics + 1):
        s += (np.sin(2 * np.pi * f * k * (1 + detune) * t) / k).astype(np.float32)
    return s


def build_music():
    music = np.zeros(N, dtype=np.float32)
    rng = np.random.default_rng(11)

    nbars = int(TOTAL / BAR) + 2
    for b in range(nbars):
        t0 = b * BAR
        ch = PROG[b % 4]
        root = ch[0] / 2 if ch[0] > 200 else ch[0]

        # кик на каждую четверть, на 4-й доле снейр
        for q in range(4):
            add(music, kick() * 0.9, t0 + q * BEAT)
        add(music, snare(rng=rng) * 0.5, t0 + 1 * BEAT)
        add(music, snare(rng=rng) * 0.5, t0 + 3 * BEAT)
        # хэты восьмыми, каждая вторая тише
        for h in range(8):
            add(music, hat(rng=rng) * (0.16 if h % 2 == 0 else 0.09), t0 + h * BEAT / 2)

        # бас восьмыми: корень, октава, квинта
        pat = [1.0, 1.0, 2.0, 1.0, 1.0, 1.5, 1.0, 2.0]
        for i, mul in enumerate(pat):
            n = int(BEAT / 2 * SR)
            sig = synth_saw(root * mul, n, 5)
            sig = lowpass(sig, 420) * env_ad(n, 0.004, 9) * 0.30
            add(music, sig.astype(np.float32), t0 + i * BEAT / 2)

        # арпеджио шестнадцатыми по аккорду, верхняя октава
        for i in range(16):
            f = ch[i % 3] * 2
            n = int(0.14 * SR)
            sig = synth_saw(f, n, 4) * env_ad(n, 0.002, 26) * 0.075
            add(music, sig.astype(np.float32), t0 + i * BEAT / 4)

        # пэд: аккорд на такт
        n = int((BAR + 0.35) * SR)
        pad = np.zeros(n, dtype=np.float32)
        for f in ch:
            for d in (0.997, 1.003):
                pad += (np.sin(2 * np.pi * f * d * np.arange(n) / SR) * 0.25).astype(np.float32)
        tt = np.arange(n) / SR
        penv = np.minimum(1, tt / 0.5) * np.minimum(1, (n / SR - tt) / 0.7).clip(0, 1)
        pad = lowpass(pad, 1100) * penv * 0.055
        add(music, pad.astype(np.float32), t0)

    # вжухи на стыках сцен-суперсил и финала
    acc = [sc["start"] for sc in TL["scenes"]]
    for i, t0 in enumerate(acc):
        if i == 0:
            continue
        add(music, whoosh(rng=rng) * 0.10, t0 - 0.22)
    add(music, boom() * 0.22, TL["scenes"][-1]["start"] + 0.05)
    return music


def main():
    voice = np.zeros(N, dtype=np.float32)
    for sc in TL["scenes"]:
        a = decode(os.path.join(AUDIO_DIR, sc["audio"]))
        add(voice, a, sc["voice_start"])
    voice /= max(1e-6, np.max(np.abs(voice))) / 0.92

    music = build_music()
    music /= max(1e-6, np.max(np.abs(music))) / 0.7

    duck = np.ones(N, dtype=np.float32)
    for sc in TL["scenes"]:
        a, b = int((sc["voice_start"] - 0.12) * SR), int((sc["voice_end"] + 0.18) * SR)
        duck[max(0, a):min(N, b)] = 0.30
    k = int(0.06 * SR)
    duck = np.convolve(duck, np.ones(k) / k, mode="same").astype(np.float32)

    mix = voice + music * duck
    mix = np.tanh(mix * 1.05) * 0.97

    for path, sig in ((os.path.join(OUT, "mix.wav"), mix),
                      (os.path.join(OUT, "voice_only.wav"), voice)):
        subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
                        "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "pipe:0",
                        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-ac", "2", path],
                       input=sig.astype(np.float32).tobytes(), check=True)
    print("mix ready", round(N / SR, 2), "s")


if __name__ == "__main__":
    main()
