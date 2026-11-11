"""Озвучка сцен локальным нейроголосом Silero (RU, без акцента).

python3 src/tts_silero.py --speaker aidar
Модель качается один раз в voices/v4_ru.pt (40 МБ).
"""
import argparse, os, wave
import numpy as np
import torch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODEL = os.path.join(ROOT, "voices", "v4_ru.pt")
URL = "https://models.silero.ai/models/tts/ru/v4_ru.pt"
SR = 48000

# (файл, текст) — порядок = порядок сцен
SCENES = [
    ("01_hook.wav",   "Это видео целиком сделал агент. Сценарий, голос, кадры и монтаж."),
    ("02_ui.wav",     "Я написал одну строчку — и включил режим агента."),
    ("03_steps.wav",  "Дальше он работает сам. Пишет сценарий. Подбирает голос. Рисует кадры."),
    ("04_skills.wav", "Он подключает скиллы — готовые навыки: озвучка, графика, монтаж."),
    ("05_tools.wav",  "Нужных инструментов нет? Он ставит их сам и запускает рендер."),
    ("06_fix.wav",    "Ошибка? Он читает лог, правит код и пробует снова. Без меня."),
    ("07_file.wav",   "Потом проверяет результат и отдаёт готовый файл. Ни камеры, ни лица, ни монтажа вручную."),
    ("08_outro.wav",  "Это режим агента. Одна задача — и он доводит её до конца."),
]


def ensure_model():
    if os.path.exists(MODEL):
        return
    os.makedirs(os.path.dirname(MODEL), exist_ok=True)
    import urllib.request
    print("качаю модель Silero…")
    urllib.request.urlretrieve(URL, MODEL)


def save_wav(path, audio):
    x = (audio.numpy() * 32767).astype(np.int16) if hasattr(audio, "numpy") else (audio * 32767).astype(np.int16)
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(x.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="aidar", help="aidar / eugene / baya / kseniya / random")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()

    ensure_model()
    torch.set_num_threads(4)
    model = torch.package.PackageImporter(args.model).load_pickle("tts_models", "model")

    out_dir = os.path.join(ROOT, "audio")
    os.makedirs(out_dir, exist_ok=True)
    for fn, text in SCENES:
        a = model.apply_tts(text=text, speaker=args.speaker, sample_rate=SR)
        save_wav(os.path.join(out_dir, fn), a)
        print(f"{fn:14s} {len(a)/SR:5.2f}s  {text[:48]}…")


if __name__ == "__main__":
    main()
