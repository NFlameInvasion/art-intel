#!/usr/bin/env python3
"""Собирает эпизод из готового видео: берёт его озвучку и режет на сцены.

    python3 src/prepare_from_video.py <video.mp4> episodes/<slug>

Пишет episodes/<slug>/{script.json,timeline.json,audio/*.wav,audio_full.wav}.
Тайминги — из whisper (пословные), поэтому текст на экране совпадает с речью
один в один. Стиль кадра выбирается по смыслу фразы (visual).
"""
import json, os, re, subprocess, sys
import numpy as np

SR = 48000
WSR = 16000

VIS_RULES = [
    (("монтаж", "режисс", "склей", "таймлайн"), "timeline"),
    (("голос", "озвуч", "речь", "аудио"), "waveform"),
    (("тайминг", "слово", "синхрон"), "timeline"),
    (("кадр", "рису", "сцен"), "frames"),
    (("субтитр", "текст на экран", "подпис"), "subtitle"),
    (("звук", "громк", "пад", "вуш", "музык"), "meter"),
    (("кодек", "энкод", "люфс", "h.264", "аш двести", "битрейт"), "encode"),
    (("сетк", "план", "структур"), "grid"),
    (("было", "стало", "вместо", "против"), "split"),
    (("поток", "задач", "агент", "файл"), "flow"),
]


def decode(path, sr):
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"])
    return np.frombuffer(raw, dtype=np.float32).copy()


def transcribe(x):
    from faster_whisper import WhisperModel
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(x, language="ru", vad_filter=True, beam_size=5,
                           word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append({"w": t, "s": float(w.start), "e": float(w.end)})
    return words


def split_scenes(words):
    scenes, cur = [], []
    for i, w in enumerate(words):
        cur.append(w)
        nxt = words[i + 1] if i + 1 < len(words) else None
        dur = cur[-1]["e"] - cur[0]["s"]
        gap = (nxt["s"] - w["e"]) if nxt else 99
        punct = bool(re.search(r"[.!?…]$", w["w"]))
        if (punct and (len(cur) >= 6 or gap > 0.25)) or (gap > 0.55 and len(cur) >= 4) or dur > 9.0:
            scenes.append(cur)
            cur = []
    if cur:
        if scenes and len(cur) < 4:
            scenes[-1].extend(cur)
        else:
            scenes.append(cur)
    return scenes


def visual_for(text):
    low = text.lower()
    for keys, kind in VIS_RULES:
        if any(k in low for k in keys):
            return kind
    return "steps"


def main():
    video, ep = sys.argv[1], sys.argv[2]
    os.makedirs(os.path.join(ep, "audio"), exist_ok=True)
    os.makedirs(os.path.join(ep, "out"), exist_ok=True)

    full = os.path.join(ep, "audio_full.wav")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", video, "-vn",
                    "-ac", "1", "-ar", str(SR), full], check=True)
    x = decode(video, WSR)
    print("длительность", round(len(x) / WSR, 2), "с — распознаю…", flush=True)
    cache = os.path.join(ep, "words.json")
    if os.path.exists(cache):
        words = json.load(open(cache, encoding="utf-8"))
        print("слов из кэша:", len(words), flush=True)
    else:
        words = transcribe(x)
        json.dump(words, open(cache, "w", encoding="utf-8"), ensure_ascii=False)
        print("слов:", len(words), flush=True)

    groups = split_scenes(words)
    # укрупняем: не больше TARGET сцен, каждый раз сливаем самую короткую с соседом
    TARGET = int(os.environ.get("TARGET_SCENES", "11"))
    while len(groups) > TARGET:
        durs = [g[-1]["e"] - g[0]["s"] for g in groups]
        i = int(np.argmin(durs[:-1] if len(groups) > 2 else durs))
        j = i + 1 if i + 1 < len(groups) and (i == 0 or
             (groups[i+1][-1]["e"] - groups[i+1][0]["s"]) <= (groups[i-1][-1]["e"] - groups[i-1][0]["s"])) else i - 1
        a, b = min(i, j), max(i, j)
        groups[a:b+1] = [groups[a] + groups[b]]
    print("сцен:", len(groups), flush=True)
    audio = decode(full, SR)
    total = len(audio) / SR

    scenes, t0 = [], 0.0
    for i, g in enumerate(groups):
        name = f"{i+1:02d}"
        text = " ".join(w["w"] for w in g)
        start = g[0]["s"] - 0.12
        end = g[-1]["e"] + 0.25
        if i == 0:
            start = 0.0
        if i == len(groups) - 1:
            end = total
        fn = f"{name}.wav"
        a, b = int(max(0, start) * SR), int(min(total, end) * SR)
        seg = audio[a:b]
        import wave
        with wave.open(os.path.join(ep, "audio", fn), "wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(SR)
            wf.writeframes((np.clip(seg, -1, 1) * 32767).astype(np.int16).tobytes())
        scenes.append({
            "scene": name, "name": name, "audio": fn, "text": text, "visual": visual_for(text),
            "start": round(start, 3), "end": round(end, 3),
            "voice_start": round(g[0]["s"], 3), "voice_end": round(g[-1]["e"], 3),
            "dur": round(end - start, 3),
            "words": [{"w": w["w"], "s": round(w["s"], 3), "e": round(w["e"], 3)} for w in g],
        })

    json.dump({"fps": 30, "title": os.path.basename(ep).replace("_", " ").upper(),
               "channel": "Art Intel", "hud": "ART INTEL",
               "scenes": [{k: s[k] for k in ("scene", "audio", "text", "visual")}
                          for s in scenes]},
              open(os.path.join(ep, "script.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    json.dump({"fps": 30, "total": round(total, 3), "lead": 0.0, "gap": 0.0,
               "scenes": scenes, "captions": []},
              open(os.path.join(ep, "timeline.json"), "w", encoding="utf-8"),
              ensure_ascii=False)
    for s in scenes:
        print(f"  {s['scene']} {s['start']:6.2f}→{s['end']:6.2f} {s['visual']:9s} {s['text'][:60]}")


if __name__ == "__main__":
    main()
