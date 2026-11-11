#!/usr/bin/env bash
# Полная сборка ролика: озвучка → тайминги → звук → кадры → вшитые субтитры → обложка
set -euo pipefail
cd "$(dirname "$0")"

VOICE_MODEL=${VOICE_MODEL:-voices/v5_ru.pt}
VOICE_SPEAKER=${VOICE_SPEAKER:-eugene}

echo "[1/6] озвучка ($VOICE_SPEAKER)"
python3 src/tts_silero.py --speaker "$VOICE_SPEAKER" --model "$VOICE_MODEL" || \
  echo "  пропускаю: аудио уже есть"

echo "[2/6] тайминги из аудио"
python3 src/timeline.py

echo "[3/6] сведение звука"
python3 src/audio_mix.py

echo "[4/6] рендер кадров (долго: ~1500 кадров)"
python3 src/render.py

echo "[5/6] вшитые караоке-субтитры + финальные файлы"
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 \
  -vf "ass=out/captions_ru.ass:fontsdir=assets/fonts" \
  -c:v libx264 -preset medium -crf 18 -pix_fmt yuv420p -profile:v high -level 4.1 \
  -c:a aac -b:a 192k -movflags +faststart out/agent_mode_ru_9x16.mp4
ffmpeg -y -hide_banner -loglevel error -i out/base.mp4 -i out/voice_only.wav \
  -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -movflags +faststart out/agent_mode_ru_9x16_clean.mp4

echo "[6/6] обложка"
python3 src/cover.py

ffprobe -v error -show_entries format=duration,size:stream=width,height,r_frame_rate \
  -of default=nw=1 out/agent_mode_ru_9x16.mp4
echo "готово: out/agent_mode_ru_9x16.mp4"
