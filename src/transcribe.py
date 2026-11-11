"""Транскрипция голосовых сообщений (faster-whisper, CPU).

python3 src/transcribe.py /путь/к/файлу.ogg [--model small]

Декодируем через ffmpeg в numpy и отдаём модели массивом: PyAV 19 не совместим
с вызовом из faster-whisper (metadata_errors), а этот путь работает всегда.
"""
import argparse, subprocess, sys
import numpy as np

SR = 16000


def decode(path):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--model", default="small")
    a = ap.parse_args()

    from faster_whisper import WhisperModel
    x = decode(a.path)
    print(f"длительность {len(x)/SR:.1f} с")
    m = WhisperModel(a.model, device="cpu", compute_type="int8")
    segs, _ = m.transcribe(x, language="ru", vad_filter=True, beam_size=5)
    for s in segs:
        print(f"[{s.start:6.1f}] {s.text.strip()}")


if __name__ == "__main__":
    main()
