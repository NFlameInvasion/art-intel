#!/usr/bin/env bash
# Полная сборка ролика: тайминги → звук → кадры → монтаж
set -euo pipefail
cd "$(dirname "$0")"

echo "[1/4] тайминги из аудио"
python3 src/timeline.py

echo "[2/4] сведение звука"
python3 src/audio_mix.py

echo "[3/4] рендер кадров"
python3 src/render.py

echo "[4/4] финальные файлы"
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 \
  -c:v copy -c:a aac -b:a 192k -movflags +faststart out/agent_mode_ru_9x16.mp4
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 -i out/voice_only.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -movflags +faststart out/agent_mode_ru_9x16_clean.mp4
ffprobe -v error -show_entries format=duration,size:stream=width,height,r_frame_rate \
  -of default=nw=1 out/agent_mode_ru_9x16.mp4
echo "готово: out/agent_mode_ru_9x16.mp4"
