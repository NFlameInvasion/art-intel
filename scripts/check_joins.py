#!/usr/bin/env python3
"""Финальная проверка ролика: стыки (щелчки), средняя яркость кадров по секундам."""
import json, os, subprocess, sys
import numpy as np

EP = sys.argv[1]
tl = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", os.path.join(EP, "out", "mix.wav"),
                               "-f", "f32le", "-ac", "1", "-ar", "48000", "-"])
x = np.frombuffer(raw, dtype=np.float32)
SR = 48000
print("аудио:", round(len(x) / SR, 2), "с")
worst = 0.0
for sc in tl["scenes"][1:]:
    i = int(sc["start"] * SR)
    jump = abs(float(x[i]) - float(x[i - 1]))
    worst = max(worst, jump)
    print(f"  стык {sc['name']}: скачок {jump:.4f}")
print("макс скачок:", round(worst, 4), "OK" if worst < 0.05 else "ЩЕЛЧОК")
