"""Живой рендер: посценная анимация вместо статичных слайдов.

Каждый кадр рисуется в PIL и уходит в ffmpeg потоком (без тысяч PNG на диске).
Мотивы сцен: текст, терминал, папка, схема из блоков, скриншот с рамкой, чипы.

    python3 src/render_motion.py --episode episodes/agent-video
"""
import argparse, json, math, os, subprocess, wave
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
W, H, FPS = 1080, 1920, 30
BG = (242, 241, 238)
DOT = (222, 218, 210)
INK = (20, 18, 15)
RED = (192, 91, 77)
CARD = (255, 255, 255)
DARK = (20, 22, 26)
DARK_TXT = (232, 230, 225)
MUTED = (122, 115, 104)
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

MOTIF = {
    "hook": "type", "scope": "folder", "step1": "folder", "inside": "blocks",
    "why": "blocks", "step2": "terminal", "key": "type", "key2": "type",
    "refs": "shot", "quest": "chips", "guide": "file", "steps": "blocks",
    "review": "shot", "fix": "shot", "payoff": "chips", "cta": "type",
}

TERM = {
    "step2": ["$ ffmpeg -version", "$ python3 render.py", "frames 1080x1920  ok"],
}
BLOCKS = {
    "inside": [("script", "Сценарий"), ("voice", "Озвучка"), ("frames", "Кадры")],
    "why":    [("folder", "Папка"), ("agent", "Агент"), ("out", "Материал")],
    "steps":  [("script", "Сценарий"), ("voice", "Озвучка"), ("frames", "Кадры"), ("subs", "Субтитры")],
}
CHIPS = {
    "quest":  ["Крючок", "Смена кадра", "Слово для текста"],
    "payoff": ["Папка", "Гайд", "Промпт"],
}
SHOT = {
    "refs":   ("referens.mp4", ["крючок 0:00", "кадр 0:03", "текст 0:07"], 0.18, 0.42),
    "review": ("draft_v3.mp4", ["00:12 текст рано", "00:14 «переход»", "ждёт правку"], 0.30, 0.30),
    "fix":    ("draft_v4.mp4", ["00:12 свободно", "00:14 «переход» ✓", "готово"], 0.46, 0.26),
}


def text_alpha(img, xy, text, f, color, alpha):
    """Рисует текст с прозрачностью: поверх RGBA-картинки нужен отдельный слой."""
    if alpha <= 0:
        return
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(layer).text(xy, text, font=f, fill=color + (int(255 * alpha),))
    img.alpha_composite(layer)


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


def ease_io(t):
    t = max(0.0, min(1.0, t))
    return 3 * t * t - 2 * t * t * t


def pop(t, over=1.06):
    t = max(0.0, min(1.0, t))
    s = 1 - (1 - t) ** 3
    return s * over if t < 0.85 else s


def font(size, weight="800"):
    return ImageFont.truetype(os.path.join(FONTS, f"Manrope-{weight}.ttf"), size)


def mono(size, weight="400"):
    return ImageFont.truetype(os.path.join(FONTS, f"JBMono-{weight}.ttf"), size)


def dot_grid(img):
    d = ImageDraw.Draw(img)
    for y in range(0, H, 48):
        for x in range(0, W, 48):
            d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=DOT)


def card_shadow(img, box, radius, alpha=34):
    layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    x0, y0, x1, y1 = box
    d.rounded_rectangle([x0, y0 + 18, x1, y1 + 18], radius=radius, fill=(0, 0, 0, alpha))
    img.alpha_composite(layer.filter(ImageFilter.GaussianBlur(34)))


def wrap(lines, max_w, size):
    f = font(size)
    out = []
    for ln in lines:
        if f.getlength(ln) <= max_w:
            out.append(ln)
            continue
        cur = ""
        for w in ln.split():
            t = (cur + " " + w).strip()
            if f.getlength(t) <= max_w:
                cur = t
            else:
                out.append(cur); cur = w
        if cur:
            out.append(cur)
    return out


def draw_headline(img, lines, box, t, t0=0.05, stagger=0.10, color=INK, red_first=False, size=None):
    d = ImageDraw.Draw(img)
    max_w = box[2] - box[0] - 96
    s = size or 112
    while True:
        f = font(s)
        wrapped = wrap(lines, max_w, s)
        lh = int(s * 1.14)
        if (len(wrapped) <= len(lines) and lh * len(wrapped) <= 520) or s <= 54:
            break
        s -= 6
    total_h = lh * len(wrapped)
    ty = box[3] - 90 - total_h
    for i, ln in enumerate(wrapped):
        a = ease((t - t0 - i * stagger) / 0.55)
        if a <= 0:
            continue
        dy = int((1 - a) * 46)
        col = RED if (red_first and i == 0) else color
        text_alpha(img, (box[0] + 48, ty + dy), ln, f, col, a)
        ty += lh
    return s


# ---------- мотивы ----------

def m_folder(img, d, box, t, label="reel/"):
    x0 = box[0] + 90
    y0 = box[1] + 10
    w = box[2] - box[0] - 180
    h = 380
    p = ease(t / 0.7)
    # задняя панель и ярлычок
    d.rounded_rectangle([x0, y0 + 22, x0 + 190, y0 + 86], radius=20, fill=(226, 220, 209, 255))
    d.rounded_rectangle([x0, y0 + 44, x0 + w, y0 + h], radius=28, fill=(233, 228, 218, 255))
    # файлы внутри
    for i, name in enumerate(("script.json", "audio.wav", "frames/")):
        k = ease((t - 0.18 - i * 0.12) / 0.5)
        if k <= 0:
            continue
        fy = y0 + 96 + i * 66 - int(k * 14)
        d.rounded_rectangle([x0 + 30, fy, x0 + w - 30, fy + 56], radius=14,
                            fill=(255, 255, 255, int(240 * k)))
        d.text((x0 + 50, fy + 14), name, font=mono(26), fill=(60, 56, 50, int(255 * k)))
    # передняя створка раскрывается вниз
    fy0 = y0 + 150 + int((1 - p) * 120)
    d.rounded_rectangle([x0, fy0, x0 + w, y0 + h + 30], radius=28, fill=(247, 244, 236, 255),
                        outline=(210, 203, 190, 255), width=2)
    d.text((x0 + 36, fy0 + 28), label, font=font(40, "800"), fill=INK + (255,))
    d.text((x0 + 36, fy0 + 84), "3 файла · 1 папка", font=font(26, "600"), fill=MUTED + (255,))


def m_blocks(img, d, box, items, t):
    n = len(items)
    gap = 34
    bw = (box[2] - box[0] - 96 - gap * (n - 1)) // n
    bh = 232
    y = box[1] + 76
    for i, (_, label) in enumerate(items):
        k = ease((t - 0.08 - i * 0.16) / 0.45)
        if k <= 0:
            continue
        s = pop((t - 0.08 - i * 0.16) / 0.45)
        cx = box[0] + 48 + i * (bw + gap)
        cw, chh = int(bw * s), int(bh * s)
        ox = cx + (bw - cw) // 2
        oy = y + (bh - chh) // 2
        d.rounded_rectangle([ox, oy, ox + cw, oy + chh], radius=26,
                            fill=(255, 255, 255, int(255 * k)), outline=(220, 214, 203, 255), width=2)
        d.ellipse([ox + 26, oy + 40, ox + 70, oy + 84], fill=RED + (int(255 * k),))
        d.text((ox + 22, oy + 112), label, font=font(32, "800"), fill=INK + (int(255 * k),))
        if i < n - 1:
            q = ease((t - 0.08 - i * 0.16 - 0.28) / 0.4)
            if q > 0:
                ax0, ax1 = cx + bw + 6, cx + bw + gap - 6
                yy = y + bh // 2
                xe = ax0 + (ax1 - ax0) * q
                d.line([ax0, yy, xe, yy], fill=(150, 143, 130, 255), width=4)
                if q > 0.8:
                    d.polygon([(xe, yy - 8), (xe + 12, yy), (xe, yy + 8)], fill=(150, 143, 130, 255))


def m_terminal(img, d, box, lines, t):
    x0, y0 = box[0] + 48, box[1] + 56
    x1, y1 = box[2] - 48, box[1] + 336
    d.rounded_rectangle([x0, y0, x1, y1], radius=28, fill=DARK + (255,))
    for i, cx in enumerate((x0 + 34, x0 + 70, x0 + 106)):
        d.ellipse([cx - 9, y0 + 24, cx + 9, y0 + 42],
                  fill=[(235, 96, 84), (232, 190, 92), (108, 190, 120)][i] + (255,))
    f = mono(30)
    total = sum(len(s) for s in lines) or 1
    shown = int(total * min(1.0, t / 0.72))
    acc = 0
    yy = y0 + 74
    for i, ln in enumerate(lines):
        take = max(0, min(len(ln), shown - acc))
        acc += len(ln)
        if take:
            d.text((x0 + 30, yy), ln[:take], font=f,
                   fill=(RED if i == 2 else DARK_TXT) + (255,))
            if take < len(ln) or i == len(lines) - 1:
                cx = x0 + 30 + f.getlength(ln[:take]) + 4
                if int(t * 6) % 2 == 0:
                    d.rectangle([cx, yy + 2, cx + 14, yy + 30], fill=DARK_TXT + (220,))
        yy += 52


def m_shot(img, d, box, name, rows, hx, hy, t):
    x0, y0 = box[0] + 56, box[1] + 46
    x1, y1 = box[2] - 56, box[1] + 380
    k = ease(t / 0.45)
    if k <= 0:
        return
    d.rounded_rectangle([x0, y0, x1, y1], radius=24, fill=(255, 255, 255, int(255 * k)),
                        outline=(222, 216, 205, 255), width=2)
    d.rectangle([x0 + 2, y0 + 2, x1 - 2, y0 + 52], fill=(246, 243, 236, 255))
    for i, cx in enumerate((x0 + 26, x0 + 50, x0 + 74)):
        d.ellipse([cx - 7, y0 + 20, cx + 7, y0 + 34], fill=(214, 208, 197, 255))
    d.text((x0 + 100, y0 + 16), name, font=mono(22), fill=MUTED + (255,))
    yy = y0 + 78
    for i, row in enumerate(rows):
        q = ease((t - 0.25 - i * 0.12) / 0.4)
        if q <= 0:
            continue
        d.rounded_rectangle([x0 + 26, yy, x0 + 26 + int((x1 - x0 - 52) * q), yy + 40],
                            radius=10, fill=(239, 235, 227, 255))
        d.text((x0 + 40, yy + 14), row, font=mono(26), fill=(70, 65, 58, int(255 * q)))
        yy += 68
    q = ease((t - 0.55) / 0.4)
    if q > 0:
        bw, bh = (x1 - x0 - 60) * 0.42, 60
        bx, by = x0 + 24 + (x1 - x0 - 60) * hx, y0 + 70 + hy * 120
        d.rounded_rectangle([bx, by, bx + bw * q, by + bh], radius=10,
                            outline=RED + (255,), width=4)


def m_chips(img, d, box, items, t):
    y = box[1] + 70
    for i, label in enumerate(items):
        k = ease((t - 0.10 - i * 0.18) / 0.45)
        if k <= 0:
            continue
        s = pop((t - 0.10 - i * 0.18) / 0.45)
        f = font(int(46 * s), "800")
        tw = f.getlength(label)
        w = tw + 120
        x = box[0] + (box[2] - box[0] - w) / 2
        h = 88 * s
        yy = y + (88 - h) / 2
        d.rounded_rectangle([x, yy, x + w, yy + h], radius=h / 2,
                            fill=(255, 255, 255, int(255 * k)), outline=(222, 216, 205, 255), width=2)
        d.ellipse([x + 22, yy + h / 2 - 9 * s, x + 22 + 18 * s, yy + h / 2 + 9 * s],
                  fill=RED + (int(255 * k),))
        d.text((x + 56, yy + h / 2 - 26 * s), label, font=f, fill=INK + (int(255 * k),))
        y += 112


GLYPH = {"hook": "?", "key": "!", "key2": "×", "cta": "→"}


def m_type(img, d, box, sc, t):
    g = GLYPH.get(sc)
    if not g:
        return
    k = ease(t / 0.6)
    if k <= 0:
        return
    size = int(430 * (0.9 + 0.1 * k))
    f = font(size)
    x = box[2] - 60 - f.getlength(g)
    y = box[1] + 30 - size * 0.16
    text_alpha(img, (x, y), g, f, RED, 0.22 * k)


def m_file(img, d, box, t):
    x0, y0 = box[0] + 110, box[1] + 60
    w, h = box[2] - box[0] - 220, 380
    k = ease(t / 0.5)
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=18, fill=(255, 255, 255, int(255 * k)),
                        outline=(222, 216, 205, 255), width=2)
    d.polygon([(x0 + w - 54, y0), (x0 + w, y0 + 54), (x0 + w - 54, y0 + 54)],
              fill=(238, 234, 226, 255))
    for i in range(4):
        q = ease((t - 0.25 - i * 0.10) / 0.4)
        if q <= 0:
            continue
        d.rounded_rectangle([x0 + 30, y0 + 60 + i * 48, x0 + 30 + int((w - 90) * q), y0 + 92 + i * 48],
                            radius=8, fill=(232, 228, 219, 255))
    d.text((x0 + 30, y0 + h - 62), "style_guide.md", font=mono(24), fill=MUTED + (255,))


# ---------- сцена ----------

def render_frame(sc, t, total, idx):
    img = Image.new("RGBA", (W, H), BG + (255,))
    dot_grid(img)
    d = ImageDraw.Draw(img)

    top = font(30, "600")
    d.text((72, 92), "ART INTEL", font=top, fill=MUTED + (255,))
    d.text((W - 72 - top.getlength(f"{idx:02d} / {total:02d}"), 92),
           f"{idx:02d} / {total:02d}", font=top, fill=MUTED + (255,))

    lines = HEAD.get(sc, ["", ""])
    motif = MOTIF.get(sc, "type")

    card_in = ease(t / 0.32)
    dy = int((1 - card_in) * 40)
    y0 = 400 + dy
    card_box = (64, y0, W - 64, y0 + 820)
    if card_in > 0:
        card_shadow(img, card_box, 56, alpha=int(34 * card_in))
        d.rounded_rectangle(card_box, radius=56, fill=CARD + (int(255 * card_in),))

    inner = (card_box[0], card_box[1] + 30, card_box[2], card_box[1] + 470)
    if motif == "folder":
        m_folder(img, d, inner, t)
    elif motif == "blocks":
        m_blocks(img, d, inner, BLOCKS[sc], t)
    elif motif == "terminal":
        m_terminal(img, d, inner, TERM[sc], t)
    elif motif == "shot":
        m_shot(img, d, inner, *SHOT[sc], t)
    elif motif == "chips":
        m_chips(img, d, inner, CHIPS[sc], t)
    elif motif == "file":
        m_file(img, d, inner, t)
    elif motif == "type":
        m_type(img, d, inner, sc, t)

    draw_headline(img, lines, card_box, t, t0=0.18,
                  red_first=(sc in ("step1", "step2")),
                  size=110 if motif == "type" else 92)

    return img.convert("RGB")


def build_captions(ep, audio, out_ass):
    import wave as wv
    from faster_whisper import WhisperModel
    wav16 = "/tmp/cap16.wav"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", audio, "-ar", "16000", "-ac", "1", wav16], check=True)
    with wv.open(wav16) as wf:
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
    m = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = m.transcribe(pcm, language="ru", beam_size=1, word_timestamps=True)
    words = []
    for s in segs:
        for w in (s.words or []):
            tt = w.word.strip()
            if tt:
                words.append((tt, w.start, w.end))

    lines, cur = [], []
    for tt, a, b in words:
        cur.append((tt, a, b))
        if len(cur) == 3 or tt.endswith((".", "?", "!", "…")):
            lines.append(cur); cur = []
    if cur:
        lines.append(cur)

    def ts(x):
        h = int(x // 3600); mn = int(x % 3600 // 60); s = x % 60
        return f"{h:d}:{mn:02d}:{s:05.2f}"

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
        for i, (tt, a, b) in enumerate(ln):
            end = ln[i + 1][1] if i + 1 < len(ln) else b + 0.10
            parts = []
            for j, (x, _, _) in enumerate(ln):
                parts.append(r"{\c&H4D5BC0&}" + x + r"{\c&H0F1214&}" if j == i else x)
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

    durs = []
    for sc in scenes:
        with wave.open(os.path.join(ep, "audio_vosk", sc["audio"])) as w:
            durs.append(w.getnframes() / w.getframerate())

    base = os.path.join(out, "base_motion.mp4")
    cmd = ["ffmpeg", "-y", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p", base]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)

    total = len(scenes)
    for i, (sc, dur) in enumerate(zip(scenes, durs), 1):
        d = max(dur + 0.22, 1.2)
        n = int(round(d * FPS))
        for f in range(n):
            t = f / FPS
            u = t / d
            if u > 0.94:                      # мягкий уход в конце сцены
                k = (u - 0.94) / 0.06
                img = render_frame(sc["scene"], t, total, i)
                img = Image.blend(img, Image.new("RGB", (W, H), BG), 0.35 * k)
            else:
                img = render_frame(sc["scene"], t, total, i)
            proc.stdin.write(img.tobytes())
        print(f"сцена {i:02d}/{total} {sc['scene']:9s} {d:.1f}s", flush=True)

    proc.stdin.close()
    proc.wait()
    print("база готова", base)

    ass = os.path.join(out, "captions.ass")
    build_captions(ep, os.path.join(ep, a.audio), ass)
    print("субтитры готовы")

    final = os.path.join(out, "final_motion.mp4")
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-i", base, "-i", os.path.join(ep, a.audio),
        "-map", "0:v", "-map", "1:a", "-vf", f"ass={ass}:fontsdir={FONTS}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-ar", "48000", "-c:a", "aac", "-b:a", "192k",
        "-shortest", final], check=True)

    dur = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", final]).decode().strip()
    print("ГОТОВО", final, dur, "с")


if __name__ == "__main__":
    main()
