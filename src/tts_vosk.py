"""Синтез русским мужским голосом Vosk TTS (модель ru 0.9 multi).

Модель грузится один раз на весь ролик: отдельный запуск CLI на каждую сцену
стоит ~2.5 минуты на загрузку 750 МБ на одном ядре.

    python3 src/tts_vosk.py --episode episodes/harness --speaker 3
"""
import argparse, json, os, sys, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL_NAME = "vosk-model-tts-ru-0.9-multi"
SR = 48000
LEAD, TAIL = 0.04, 0.20


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", default=os.environ.get("EPISODE_DIR", "."))
    ap.add_argument("--speaker", type=int, default=3, help="3 = male_0, 4 = male_1")
    ap.add_argument("--speed", default="1.0")
    ap.add_argument("--out", default="audio_vosk")
    ap.add_argument("--text", default=None, help="озвучить одну фразу и выйти")
    a = ap.parse_args()

    from vosk_tts import Model, Synth
    model = Model(model_name=MODEL_NAME)
    synth = Synth(model)
    print("модель загружена", flush=True)

    if a.text:
        synth.synth(clean(a.text), "/tmp/vosk_one.wav", speaker_id=a.speaker)
        print("/tmp/vosk_one.wav")
        return

    ep = a.episode if os.path.isabs(a.episode) else os.path.join(ROOT, a.episode)
    script = json.load(open(os.path.join(ep, "script.json"), encoding="utf-8"))
    out_dir = os.path.join(ep, a.out)
    os.makedirs(out_dir, exist_ok=True)

    total = 0.0
    for sc in script["scenes"]:
        tmp = f"/tmp/vosk_{sc['scene']}.wav"
        synth.synth(clean(sc["text"]), tmp, speaker_id=a.speaker)
        x = read_wav(tmp)
        y = polish(x)
        save_wav(os.path.join(out_dir, sc["audio"]), y)
        total += len(y) / SR
        print(f"{sc['audio']:16s} {len(y)/SR:5.2f}s  {sc['text'][:40]}", flush=True)
    print(f"ИТОГО {total:.1f}s")


def clean(text):
    """Vosk падает на «ёлочках» и других типографских кавычках: в его phoneme map их нет."""
    for a, b in (("«", ""), ("»", ""), ("„", ""), ("“", ""), ("”", ""), ("—", ",")):
        text = text.replace(a, b)
    return text.replace("  ", " ").strip()


def read_wav(path):
    with wave.open(path, "rb") as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(axis=1)
    if sr != SR:
        # линейная передискретизация: 22050 -> 48000
        idx = np.linspace(0, len(x) - 1, int(len(x) * SR / sr))
        x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
    return x


def polish(x, thresh=0.006, pad_ms=40):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    x = x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]
    y = np.concatenate([np.zeros(int(LEAD * SR), dtype=np.float32), x,
                        np.zeros(int(TAIL * SR), dtype=np.float32)])
    peak = float(np.max(np.abs(y))) or 1.0
    return (y / peak * 0.92).astype(np.float32)


def save_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    main()
