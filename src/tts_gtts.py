#!/usr/bin/env python3
"""Озвучка эпизода через gTTS (когда нет torch/silero и edge-tts отдаёт 403).

    EPISODE_DIR=episodes/montazh python3 src/tts_gtts.py
Пишет wav с именами из script.json ("audio") в EPISODE_DIR/audio,
48 кГц моно — формат, который ждёт timeline.py.
"""
import json, os, subprocess, tempfile
from gtts import gTTS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EP = os.environ.get("EPISODE_DIR") or ROOT
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
AUD = os.environ.get("AUDIO_DIR") or os.path.join(EP, "audio")
if not os.path.isabs(AUD):
    AUD = os.path.join(ROOT, AUD)
os.makedirs(AUD, exist_ok=True)

SCRIPT = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))

for sc in SCRIPT["scenes"]:
    text, fn = sc["text"], sc["audio"]
    wav = os.path.join(AUD, fn)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as tf:
        mp3 = tf.name
    gTTS(text, lang="ru").save(mp3)
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", mp3,
                    "-ar", "48000", "-ac", "1", wav], check=True)
    os.unlink(mp3)
    dur = float(subprocess.check_output(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", wav]).strip())
    print(f"{fn:14s} {dur:5.2f}s  {text[:46]}…", flush=True)
