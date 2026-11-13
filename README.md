# Art Intel — вертикальные видео про ИИ без лица

Пайплайн для коротких роликов 1080×1920 (TikTok / YouTube Shorts): сценарий → синтез речи →
кадры, отрисованные кодом → караоке-субтитры → сведение звука → MP4.

Первый ролик — про **режим агента** в Qwen Chat: агент сам написал сценарий, озвучил,
отрисовал 1498 кадров, поставил инструменты, поймал ошибку рендера и починил её.

## Что в репозитории

```
src/timeline.py    тайминги сцен и слов — из реальных аудиофайлов (silencedetect)
src/gfx.py         графические примитивы: шрифты, свечения, карточки, easing
src/render.py      отрисовка кадров (Pillow) → ffmpeg → base.mp4
src/audio_mix.py   сведение голоса с эмбиентом, −14 LUFS / −1.5 dBTP
audio/             озвучка по сценам (01_hook.wav … 07_outro.wav)
assets/fonts/      Unbounded, Manrope, JetBrains Mono (кириллица)
assets/shots/      реальные скриншоты Qwen (кадры «с камерой»)
out/               результат: MP4, SRT, ASS, обложка
```

## Сборка

```bash
python3 -m pip install pillow numpy          # зависимости рендера
bash build.sh                                # timeline → mix → render
```

`build.sh` по шагам:

```bash
python3 src/timeline.py     # timeline.json + out/captions_ru.{srt,ass}
python3 src/audio_mix.py    # out/mix.wav (голос + музыка), out/voice_only.wav
python3 src/render.py       # out/base.mp4 (1498 кадров, 30 fps)
```

Финальный файл — `out/agent_mode_ru_9x16.mp4`, чистая версия без субтитров и музыки —
`out/agent_mode_ru_9x16_clean.mp4` (для трендового звука в TikTok).

## Правила ролика

- Вертикаль 1080×1920, 30 fps, H.264 high + AAC 192k, `+faststart`.
- Длина ≤ 60 с (текущий — 48.8 с).
- Тайминг сцены = длина её аудио + пауза 0.60 с; слова распределены по слогам внутри
  речевых сегментов, найденных через `silencedetect`, а не «на глаз».
- Субтитры 2–3 слова, активное слово подсвечивается лаймом; safe zone — верх 180 px, низ 320 px.
- Звук: голос + тихий синтезированный пэд (без вушей и шума), дакинг под речь, −14 LUFS / −1.5 dBTP.
- Речь: каждая фраза синтезируется отдельно, пауза 0.34 с между фразами, края обрезаются, тихий шум гасится гейтом.

## Следующий ролик за 5 минут

1. `src/tts_silero.py` — блок `SCENES`: список `(имя_сцены, файл, текст)`. Меняется только текст.
2. `src/timeline.py` — тот же список (тайминг берётся из реальных аудиофайлов).
3. `bash build.sh` — озвучка → тайминги → сведение → рендер → вшитые субтитры → обложка.

Визуал сцены выбирается её именем в `src/render.py` (словарь `SCENES`): `hook`, `ui`, `compare`,
`prompt`, `flow` (мультяшная схема с роботом), `skills`, `steps`, `tools`, `fix`, `file`, `outro`.
Скриншоты — `assets/shots/*.jpg`, области кропа и подсветки задаются в `SHOTS`.

Тайминги нигде не проставляются руками: если текст стал длиннее, аудио стало длиннее,
сцены и субтитры пересчитаются сами.

## Эпизоды (новый пайплайн, 2026-06)

Каждый ролик — папка `episodes/<slug>/` со своим `script.json`:

```
episodes/agent-video/script.json   сцены: scene, audio, text
episodes/agent-video/audio_vosk/   озвучка по сценам (в git не попадает)
episodes/agent-video/out/          slides/, part_*.mp4, captions.ass, final.mp4
```

Сборка одного ролика:

```bash
# 1. озвучка локальным русским голосом (Vosk TTS, 5 дикторов, male_0 = 3)
python3 src/fill_missing.py --episode episodes/agent-video --max 6   # дозаписывает недостающие сцены
# 2. склейка + −16 LUFS
cd episodes/agent-video && ffmpeg -f concat -safe 0 -i list.txt \
  -af "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" -ar 48000 -ac 1 \
  -c:a libmp3lame -b:a 128k voice_agent_video.mp3
# 3. рендер в светлом стиле + караоке-субтитры
cd - && /usr/bin/python3 src/render_light.py --episode episodes/agent-video
```

Что важно знать:

- **Память.** Vosk-модель ~750 МБ, процесс убивает при ~950 МБ RSS. `fill_missing.py`
  берёт по нескольку сцен за запуск и продолжает с места обрыва, поэтому его можно
  гонять в цикле. Без swap на 1.9 ГБ машине он падает на загрузке модели.
- **Кавычки.** Vosk падает с `KeyError: '»'` на типографских кавычках — `tts_vosk.clean()`
  их вырезает. Писать текст можно как обычно.
- **Латиница.** И Silero, и edge-tts, и Vosk ломают латинские названия: «Google»
  превращается в «вучат», «TikTok» исчезает. В тексте для озвучки — только кириллица:
  «в Гугле», «ТикТок», «джи-пи-ти».
- **Субтитры.** `render_light.py` берёт пословные тайминги из faster-whisper по готовому
  аудио, а не делит время сцены поровну — иначе к концу фразы караоке отстаёт.
  Передавать в `transcribe()` надо numpy-массив: с этой сборкой PyAV путь к файлу
  падает на `metadata_errors`.

Стиль `render_light.py`: тёплый белый фон с сеткой точек, белая карточка с мягкой тенью,
тёмная плашка «терминала» на шагах, Manrope ExtraBold, один красный акцент (#C05B4D).
Заголовки слайдов — словарь `HEAD`, «терминальные» сцены — `TERM`.

## Брендбук

`brand/brandbook.html` — исходник, `brand/brandbook.pdf` — 8 страниц A4: палитра, типографика,
сетка и разметка кадра, четыре типа слайда, субтитры и правила «можно/нельзя».

Сборка PDF:

```bash
chrome --headless --no-pdf-header-footer --print-to-pdf=brand/brandbook.pdf \
  --virtual-time-budget=3000 file://$PWD/brand/brandbook.html
```

## Публикация

Описания, заголовки, теги и обложки — в `publish_ru.md`.

## Лицензия

Код — MIT. Шрифты — SIL Open Font License (Unbounded, Manrope, JetBrains Mono).
