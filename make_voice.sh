#!/usr/bin/env bash
# Сборка ролика с выбранным голосом: bash make_voice.sh aidar
# Готовит только озвученный вариант (кадры те же), финальный файл — out/agent_mode_ru_9x16_<voice>.mp4
set -euo pipefail
cd "$(dirname "$0")"
VOICE=${1:?укажи голос: aidar | baya | eugene}
DIR="audio_${VOICE}"
[ -d "$DIR" ] || { echo "нет папки $DIR — сначала: python3 src/tts_silero.py --speaker $VOICE --out $DIR"; exit 1; }

echo "[1/5] тайминги"
AUDIO_DIR="$DIR" python3 src/timeline.py
echo "[2/5] сведение"
AUDIO_DIR="$DIR" python3 src/audio_mix.py
echo "[3/5] рендер кадров"
python3 src/render.py
echo "[4/5] субтитры + финал"
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 -i out/mix.wav -map 0:v -map 1:a \
  -vf "ass=out/captions_ru.ass:fontsdir=assets/fonts" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -profile:v high -level 4.1 \
  -af "loudnorm=I=-14:TP=-1.5:LRA=11" -c:a aac -b:a 192k -movflags +faststart \
  "out/agent_mode_ru_9x16_${VOICE}.mp4"
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 -i out/voice_only.wav -map 0:v -map 1:a \
  -c:v copy -af "loudnorm=I=-14:TP=-1.5:LRA=11" -c:a aac -b:a 192k -movflags +faststart \
  "out/agent_mode_ru_9x16_${VOICE}_clean.mp4"
echo "[5/5] готово"
ffprobe -v error -show_entries format=duration,size -of default=nw=1 "out/agent_mode_ru_9x16_${VOICE}.mp4"
