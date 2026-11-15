#!/usr/bin/env python3
"""Черновой таймлайн без аудио — чтобы проверить кадры до синтеза."""
import json, os, sys

EP = sys.argv[1]
sc = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))
D = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
scenes, t = [], 0.0
for i, s in enumerate(sc["scenes"]):
    words = s["text"].split()
    ws = [max(1, sum(c in "аеёиоуыэюяАЕЁИОУЫЭЮЯaeiouyAEIOUY" for c in w)) + 0.35 for w in words]
    tot = sum(ws)
    tt = t + 0.1
    out = []
    for w, k in zip(words, ws):
        d = (D - 0.2) * k / tot
        out.append({"w": w, "s": round(tt, 3), "e": round(tt + d, 3)})
        tt += d
    scenes.append({"name": s["scene"], "audio": s["audio"], "dur": D,
                   "start": round(t, 3), "voice_start": round(t + 0.1, 3),
                   "voice_end": round(t + D - 0.1, 3),
                   "text": s["text"], "words": out, "end": round(t + D, 3)})
    t += D
json.dump({"fps": 30, "total": round(t, 3), "lead": 0.1, "gap": 0.0, "scenes": scenes},
          open(os.path.join(EP, "timeline.json"), "w"), ensure_ascii=False, indent=1)
print("draft timeline", round(t, 2), "s")
