#!/usr/bin/env bash
# Сборка эпизода: bash build_episode.sh episodes/chatgpt-history episodes/chatgpt-history/audio chatgpt_history
set -euo pipefail
cd "$(dirname "$0")/.."

EP=${1:?укажи папку эпизода, например episodes/chatgpt-history}
AUD=${2:-$EP/audio}
NAME=${3:-$(basename "$EP")}

echo "[1/5] тайминги"
EPISODE_DIR="$EP" AUDIO_DIR="$AUD" python3 src/timeline.py

echo "[2/5] сведение"
EPISODE_DIR="$EP" AUDIO_DIR="$AUD" python3 src/audio_mix.py

echo "[3/5] рендер кадров"
EPISODE_DIR="$EP" python3 src/render.py

echo "[4/5] субтитры + финал"
ffmpeg -y -hide_banner -loglevel error -i "$EP/out/base.mp4" -i "$EP/out/mix.wav" -map 0:v -map 1:a \
  -vf "ass=$EP/out/captions_ru.ass:fontsdir=assets/fonts" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -profile:v high -level 4.1 \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -movflags +faststart \
  "$EP/out/${NAME}_9x16.mp4"
ffmpeg -y -hide_banner -loglevel error -i "$EP/out/base.mp4" -i "$EP/out/voice_only.wav" -map 0:v -map 1:a \
  -c:v copy -af "loudnorm=I=-14:TP=-1.5:LRA=11" -ar 48000 -c:a aac -b:a 192k -movflags +faststart \
  "$EP/out/${NAME}_9x16_clean.mp4"

echo "[5/5] готово"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "$EP/out/${NAME}_9x16.mp4"
