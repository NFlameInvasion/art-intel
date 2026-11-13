"""Рендер вертикального ролика в светлом стиле референса (1080x1920).

Стиль: тёплый белый фон с сеткой точек, белая карточка с мягкой тенью,
тёмная плашка «терминала», крупный Manrope ExtraBold, один красный акцент,
розовая подложка под ключевым словом. Субтитры — по словам, активное слово красное.

    python3 src/render_light.py --episode episodes/agent-video
"""
import argparse, json, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H = 1080, 1920
BG = (242, 241, 238)
DOT = (222, 218, 210)
INK = (20, 18, 15)
RED = (192, 91, 77)
PINK = (247, 201, 196)
CARD = (255, 255, 255)
DARK = (20, 22, 26)
DARK_TXT = (232, 230, 225)
FONTS = os.path.join(ROOT, "assets", "fonts")

HEAD = {
    "hook":   ["Агент открыт.", "А что писать?"],
    "scope":  ["От пустой папки", "до готового файла"],
    "step1":  ["01", "Папка ролика"],
    "inside": ["Сценарий · озвучка", "кадры · видео"],
    "why":    ["Агент видит,", "где материал"],
    "step2":  ["02", "Консоль и библиотеки"],
    "key":    ["Теперь", "самое важное"],
    "key2":   ["Не «смонтируй", "красиво»"],
    "refs":   ["Два референса", "разбери по секундам"],
    "quest":  ["Крючок · кадр ·", "слово для текста"],
    "guide":  ["Гайд по стилю —", "в файл"],
    "steps":  ["Сценарий → озвучка", "→ кадры → субтитры"],
    "review": ["Говори", "как монтажёру"],
    "fix":    ["«На 12-й секунде", "рано»"],
    "payoff": ["Одна папка.", "Один промпт."],
    "cta":    ["Промпт —", "в описании"],
}
# сцены, где в карточке показываем «терминал», а не только текст
TERM = {
    "step1": ["$ mkdir reel", "$ cd reel", "script.json  audio/  frames/"],
    "step2": ["$ ffmpeg -version", "$ python3 render.py", "ok  frames 1080x1920"],
    "fix":   ["12.0s  text early", "→ move to 14.2s", "rebuilt  ✓"],
    "cta":   ["prompt.md", "→ в описании"],
}


def font(size, weight="800"):
    return ImageFont.truetype(os.path.join(FONTS, f"Manrope-{weight}.ttf"), size)


def mono(size, weight="400"):
    return ImageFont.truetype(os.path.join(FONTS, f"JBMono-{weight}.ttf"), size)


def dot_grid(d):
    for y in range(0, H, 48):
        for x in range(0, W, 48):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=DOT)


def shadow_card(img, box, radius, blur=38, alpha=34, dy=18):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0 + dy, x1, y1 + dy], radius=radius, fill=(0, 0, 0, alpha))
    layer = layer.filter(ImageFilter.GaussianBlur(blur))
    img.alpha_composite(layer)


def fit(text, max_w, start=118, low=52):
    size = start
    while size > low:
        f = font(size)
        if f.getlength(text) <= max_w:
            return f
        size -= 6
    return font(low)


def wrap(lines, max_w, size):
    f = font(size)
    out = []
    for ln in lines:
        if f.getlength(ln) <= max_w:
            out.append(ln)
            continue
        words, cur = ln.split(), ""
        for w in words:
            t = (cur + " " + w).strip()
            if f.getlength(t) <= max_w:
                cur = t
            else:
                out.append(cur)
                cur = w
        if cur:
            out.append(cur)
    return out


def chip(d, xy, text, fnt, pad=22, fill=(255, 255, 255), fg=INK):
    x, y = xy
    tw = fnt.getlength(text)
    h = fnt.size + pad * 2 - 10
    d.rounded_rectangle([x, y, x + tw + pad * 2, y + h], radius=h // 2, fill=fill)
    d.text((x + pad, y + pad - 6), text, font=fnt, fill=fg)
    return h


def render_slide(scene, idx, total, out_path):
    img = Image.new("RGBA", (W, H), BG + (255,))
    d = ImageDraw.Draw(img)
    dot_grid(d)

    top = font(30, "600")
    d.text((72, 92), "ART INTEL", font=top, fill=(120, 114, 104))
    d.text((W - 72 - top.getlength(f"{idx:02d} / {total:02d}"), 92), f"{idx:02d} / {total:02d}",
           font=top, fill=(120, 114, 104))

    lines = HEAD.get(scene, ["", ""])
    is_term = scene in TERM

    max_w = W - 2 * 64 - 96
    size = 112
    while True:
        f = font(size)
        wrapped = wrap(lines, max_w, size)
        line_h = int(size * 1.14)
        text_h = line_h * len(wrapped)
        limit = 520 if not is_term else 420
        if (len(wrapped) <= len(lines) and text_h <= limit) or size <= 54:
            break
        size -= 6

    content_h = text_h + (300 if is_term else 0)
    card_h = max(560, min(content_h + 190, 1000))
    y0 = 400
    card_box = (64, y0, W - 64, y0 + card_h)
    shadow_card(img, card_box, 56)
    d.rounded_rectangle(card_box, radius=56, fill=CARD)

    start = y0 + (card_h - content_h) // 2

    if is_term:
        inner = (card_box[0] + 44, start, card_box[2] - 44, start + 260)
        d.rounded_rectangle(inner, radius=28, fill=DARK)
        for i, cx in enumerate((inner[0] + 34, inner[0] + 70, inner[0] + 106)):
            d.ellipse([cx - 9, inner[1] + 26, cx + 9, inner[1] + 44],
                      fill=(235, 96, 84) if i == 0 else (232, 190, 92) if i == 1 else (108, 190, 120))
        mf = mono(36)
        yy = inner[1] + 82
        for ln in TERM[scene]:
            d.text((inner[0] + 34, yy), ln, font=mf, fill=RED if ln[:1].isdigit() else DARK_TXT)
            yy += 56
        ty = start + 300
    else:
        ty = start

    for i, ln in enumerate(wrapped):
        x = card_box[0] + 48
        bbox = d.textbbox((x, ty), ln, font=f)
        is_key = ("одна папка" in ln.lower()) or ln.lower().startswith("промпт") \
                 or ln.lower().startswith("самое") or (scene in ("step1", "step2") and i == 0)
        color = RED if (scene in ("step1", "step2") and i == 0) else INK
        d.text((x, ty), ln, font=f, fill=color)
        ty += line_h

    img.convert("RGB").save(out_path, quality=95)


def build_captions(ep, scenes, out_ass):
    """Караоке по словам: тайминги из faster-whisper, привязка к сценам по времени."""
    import wave as wv
    audio = os.path.join(ep, "voice_agent_video.mp3")
    wav16 = "/tmp/cap16.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", audio, "-ar", "16000", "-ac", "1", wav16], check=True)

    from faster_whisper import WhisperModel
    with wv.open(wav16) as wf:
        n = wf.getnframes()
        pcm = np.frombuffer(wf.readframes(n), dtype=np.int16).astype(np.float32) / 32768.0
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(pcm, language="ru", beam_size=1, word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            t = w.word.strip()
            if t:
                words.append((t, w.start, w.end))

    lines = []
    cur = []
    for t, a, b in words:
        cur.append((t, a, b))
        if len(cur) == 3 or t.endswith((".", "?", "!", "…")):
            lines.append(cur)
            cur = []
    if cur:
        lines.append(cur)

    def ts(x):
        h = int(x // 3600); mnt = int(x % 3600 // 60); s = x % 60
        return f"{h:d}:{mnt:02d}:{s:05.2f}"

    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Manrope ExtraBold,66,&H000F1214,&H000F1214,&H00FFFFFF,&H00000000,-1,0,0,0,100,100,0,0,1,0,0,2,60,60,250,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ev = []
    for ln in lines:
        for i, (t, a, b) in enumerate(ln):
            end = ln[i + 1][1] if i + 1 < len(ln) else b + 0.12
            parts = []
            for j, (tt, _, _) in enumerate(ln):
                if j == i:
                    parts.append(r"{\c&H4D5BC0&}" + tt + r"{\c&H0F1214&}")
                else:
                    parts.append(tt)
            ev.append(f"Dialogue: 0,{ts(a)},{ts(end)},Cap,,0,0,0,,{' '.join(parts)}")
    open(out_ass, "w", encoding="utf-8").write(head + "\n".join(ev) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--audio", default="voice_agent_video.mp3")
    a = ap.parse_args()
    ep = a.episode if os.path.isabs(a.episode) else os.path.join(ROOT, a.episode)

    script = json.load(open(os.path.join(ep, "script.json"), encoding="utf-8"))
    scenes = script["scenes"]
    out = os.path.join(ep, "out"); os.makedirs(out, exist_ok=True)
    slides = os.path.join(out, "slides"); os.makedirs(slides, exist_ok=True)

    durs = []
    for sc in scenes:
        p = os.path.join(ep, "audio_vosk", sc["audio"])
        with wave.open(p) as w:
            durs.append(w.getnframes() / w.getframerate())

    for i, sc in enumerate(scenes, 1):
        render_slide(sc["scene"], i, len(scenes), os.path.join(slides, f"{i:02d}.png"))
    print("слайды готовы", len(scenes))

    # видео из статичных слайдов с плавным наездом
    parts = []
    for i, (sc, dur) in enumerate(zip(scenes, durs), 1):
        p = os.path.join(out, f"part_{i:02d}.mp4")
        d = max(dur + 0.22, 1.2)
        frames = int(round(d * 30))
        subprocess.run([
            "ffmpeg", "-y", "-v", "error", "-loop", "1", "-i", os.path.join(slides, f"{i:02d}.png"),
            "-t", f"{d:.3f}", "-r", "30",
            "-vf", f"scale=1188:2112,zoompan=z='min(zoom+0.0006,1.06)':d={frames}:s=1080x1920:fps=30,"
                   f"fade=t=in:st=0:d=0.18,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", p], check=True)
        parts.append(p)

    lst = os.path.join(out, "parts.txt")
    open(lst, "w").write("\n".join(f"file '{p}'" for p in parts) + "\n")
    base = os.path.join(out, "base.mp4")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "concat", "-safe", "0", "-i", lst,
                    "-c", "copy", base], check=True)

    ass = os.path.join(out, "captions.ass")
    build_captions(ep, scenes, ass)
    print("субтитры готовы")

    final = os.path.join(out, "final.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", base, "-i", os.path.join(ep, a.audio),
        "-map", "0:v", "-map", "1:a",
        "-vf", f"ass={ass}:fontsdir={FONTS}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
        "-shortest", final], check=True)

    dur = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", final]).decode().strip()
    print("ГОТОВО", final, dur, "с")


if __name__ == "__main__":
    main()
