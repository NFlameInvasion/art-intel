#!/usr/bin/env python3
"""Быстрая проверка вариантов озвучки: расшифровка набора mp3."""
import glob, os, subprocess, sys
import numpy as np
from faster_whisper import WhisperModel

m = WhisperModel("small", device="cpu", compute_type="int8")
for p in sorted(glob.glob(sys.argv[1] + "/*.mp3")):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", p, "-f", "f32le",
                                   "-ac", "1", "-ar", "16000", "-"])
    audio = np.frombuffer(raw, dtype=np.float32).copy()
    segs, _ = m.transcribe(audio, language="ru", vad_filter=False)
    print(os.path.basename(p), round(len(audio) / 16000, 2), "s →", " ".join(s.text.strip() for s in segs))
