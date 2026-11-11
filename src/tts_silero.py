"""Озвучка сцен нейроголосом Silero (RU). Паузы между фразами, чистые стыки.

python3 src/tts_silero.py --speaker eugene --model voices/v5_ru.pt
Каждая фраза синтезируется отдельно — между предложениями получается ровная пауза,
а не слипшаяся речь. Края обрезаются по порогу, тихий шум гасится гейтом.
"""
import argparse, json, os, re, wave
import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "voices", "v5_ru.pt")
MODEL_V4 = os.path.join(ROOT, "voices", "v4_ru.pt")
URLS = {MODEL: "https://models.silero.ai/models/tts/ru/v5_ru.pt",
        MODEL_V4: "https://models.silero.ai/models/tts/ru/v4_ru.pt"}
SR = 48000

LEAD = 0.15     # тишина в начале фрагмента
GAP = 0.34      # пауза между предложениями внутри сцены
TAIL = 0.28     # тишина в конце фрагмента

SENT = re.compile(r"(?<=[.!?…])\s+")

# тексты сцен — один источник правды: script.json
SCRIPT = json.load(open(os.path.join(ROOT, "script.json"), encoding="utf-8"))
SCENES = [(s["scene"], s["audio"], s["text"]) for s in SCRIPT["scenes"]]


def ensure_model(path):
    if os.path.exists(path):
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    import urllib.request
    url = URLS.get(path)
    if not url:
        raise FileNotFoundError(f"нет модели {path} и не знаю, откуда качать")
    print("качаю модель Silero…")
    urllib.request.urlretrieve(url, path)


def trim_edges(x, sr, thresh=0.010, pad_ms=70):
    """Обрезает тишину по краям, оставляя небольшой запас."""
    if len(x) == 0:
        return x
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * sr), dtype=np.float32)
    pad = int(pad_ms / 1000 * sr)
    return x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]


def denoise_low(x, sr, thresh=0.0045, win_ms=18):
    """Гейт: окна, где громкость ниже порога (шум между фразами), гасятся в ноль."""
    win = max(1, int(win_ms / 1000 * sr))
    n = len(x) // win
    if n == 0:
        return x
    body = x[:n * win].reshape(n, win)
    rms = np.sqrt((body ** 2).mean(axis=1))
    gain = np.clip((rms - thresh) / (thresh * 2), 0, 1).astype(np.float32)
    gain = np.convolve(gain, np.ones(5) / 5, mode="same")
    return np.concatenate([(body * gain[:, None]).reshape(-1), x[n * win:]]).astype(np.float32)


def synth_sentences(model, text, speaker, sr):
    parts = [p.strip() for p in SENT.split(text) if p.strip()]
    chunks = []
    for p in parts:
        a = model.apply_tts(text=p, speaker=speaker, sample_rate=sr)
        x = a.numpy().astype(np.float32) if hasattr(a, "numpy") else np.asarray(a, dtype=np.float32)
        chunks.append(denoise_low(trim_edges(x, sr), sr))
    out = [np.zeros(int(LEAD * sr), dtype=np.float32)]
    for i, x in enumerate(chunks):
        out.append(x)
        pad = GAP if i < len(chunks) - 1 else TAIL
        out.append(np.zeros(int(pad * sr), dtype=np.float32))
    y = np.concatenate(out)
    peak = float(np.max(np.abs(y)))
    return y / peak * 0.92 if peak > 0 else y


def save_wav(path, x, sr=SR):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="eugene")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--out", default=None, help="папка для wav (по умолчанию audio/)")
    ap.add_argument("--speed", type=float, default=1.0, help="ускорение речи (atempo)")
    args = ap.parse_args()

    ensure_model(args.model)
    torch.set_num_threads(4)
    model = torch.package.PackageImporter(args.model).load_pickle("tts_models", "model")

    out_dir = args.out or os.path.join(ROOT, "audio")
    if not os.path.isabs(out_dir):
        out_dir = os.path.join(ROOT, out_dir)
    os.makedirs(out_dir, exist_ok=True)
    for _name, fn, text in SCENES:
        y = synth_sentences(model, text, args.speaker, SR)
        path = os.path.join(out_dir, fn)
        dur = len(y) / SR
        save_wav(path, y)
        if abs(args.speed - 1.0) > 0.01:
            tmp = path + ".tmp.wav"
            os.system(f'ffmpeg -y -v error -i "{path}" -filter:a atempo={args.speed} -ar {SR} "{tmp}"')
            os.replace(tmp, path)
            y = np.zeros(1)
        print(f"{fn:14s} {dur:5.2f}s  {text[:46]}…")


if __name__ == "__main__":
    main()
