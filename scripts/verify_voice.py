#!/usr/bin/env python3
"""Проверка озвучки: расшифровка faster-whisper против текста сценария."""
import json, os, re, sys

EP = sys.argv[1] if len(sys.argv) > 1 else "episodes/hermes-agent"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
tl = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
script = " ".join(s["text"] for s in tl["scenes"])

import subprocess
import numpy as np

from faster_whisper import WhisperModel
m = WhisperModel("small", device="cpu", compute_type="int8")
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", os.path.join(EP, "out", "voice_only.wav"),
                               "-f", "f32le", "-ac", "1", "-ar", "16000", "-"])
audio = np.frombuffer(raw, dtype=np.float32).copy()
segs, info = m.transcribe(audio, language="ru", vad_filter=False)
heard = " ".join(s.text.strip() for s in segs)


def norm(s):
    s = s.lower().replace("ё", "е")
    s = re.sub(r"[^а-яa-z0-9 ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


a, b = norm(script).split(), norm(heard).split()
import difflib
sm = difflib.SequenceMatcher(None, a, b)
print("слов в сценарии:", len(a), "| в расшифровке:", len(b),
      "| совпадение:", round(100 * sm.ratio(), 1), "%")
for tag, i1, i2, j1, j2 in sm.get_opcodes():
    if tag != "equal":
        print(f"  {tag}: сценарий={a[i1:i2]} → услышано={b[j1:j2]}")
print("\n--- расшифровка ---\n" + heard)
