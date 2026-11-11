"""Рендер кадров 1080x1920 и сборка видео. python3 render.py [--stills]"""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw
from gfx import (W, H, CYAN, LIME, RED, TEXT, MUTED, CARD, CARD_HI, BORDER,
                 font, measure, fit_size, clamp, out_cubic, out_back, out_expo, pulse,
                 appear, text_sprite, grad_text_sprite, rounded, glow_dot, blit,
                 blit_text, wrap, typewriter, make_bg, make_halo)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень проекта (файлы лежат в src/)
OUT = os.path.join(ROOT, "out")
TL = json.load(open(os.path.join(ROOT, "timeline.json"), encoding="utf-8"))
FPS = TL["fps"]
TOTAL = TL["total"]
NFRAMES = int(round(TOTAL * FPS))
M, CW, CX = 72, 936, 540

BG = make_bg()
HALO = make_halo(760, CYAN, 46)
HALO2 = make_halo(620, LIME, 22)
THUMB = None
tp = os.path.join(OUT, "still_hook.png")
if os.path.exists(tp):
    THUMB = Image.open(tp).convert("RGB").resize((300, 533), Image.LANCZOS)


def kicker(d, img, txt, t, t0=0.05):
    a = appear(t, t0, 0.3)
    blit_text(img, txt, "mono", 28, M, 352, CYAN, a * 0.9)


def hud(img, t, sc):
    d = ImageDraw.Draw(img)
    blit(img, rounded(292, 60, 30, CARD_HI, (44, 78, 110), 2), M, 196)
    blit(img, glow_dot(8, RED, 12), M + 22, 226, pulse(t, 1.1, 0.45, 1.0), anchor="mm")
    blit_text(img, "AGENT MODE", "monob", 26, M + 46, 226, CYAN, 1, anchor="lm")
    tc = f"00:{int(t):02d} / 00:{int(round(TOTAL)):02d}"
    blit_text(img, tc, "mono", 26, W - M, 226, MUTED, 0.85, anchor="rm")
    d.rounded_rectangle([M, 288, M + CW, 294], 3, fill=(26, 38, 62))
    p = clamp(t / TOTAL)
    if p > 0.005:
        d.rounded_rectangle([M, 288, M + int(CW * p), 294], 3, fill=CYAN)


def chips(img, labels, y, t, times, kind="sb", size=30, padx=26, h=66, gap=14,
          fill=CARD_HI, border=BORDER, color=TEXT, dot=None):
    widths = [measure(l, kind, size) + padx * 2 + (22 if dot else 0) for l in labels]
    total = sum(widths) + gap * (len(labels) - 1)
    x = CX - total / 2
    for l, w, t0 in zip(labels, widths, times):
        a = appear(t, t0, 0.32)
        if a <= 0:
            x += w + gap
            continue
        dy = (1 - out_cubic((t - t0) / 0.32)) * 16
        blit(img, rounded(int(w), h, h // 2, fill, border, 2), x, y + dy, a)
        tx = x + padx
        if dot:
            blit(img, glow_dot(5, dot, 8), x + padx + 2, y + dy + h / 2, a, anchor="mm")
            tx += 22
        blit_text(img, l, kind, size, tx, y + dy + h / 2, color, a, anchor="lm")
        x += w + gap


def terminal(img, y=420, h=780, alert=0.0, title="sandbox · bash"):
    border = tuple(int(BORDER[i] + (RED[i] - BORDER[i]) * alert) for i in range(3))
    blit(img, rounded(CW, h, 28, (11, 17, 30), border, 2), M, y)
    d = ImageDraw.Draw(img)
    for i, c in enumerate([(90, 60, 66), (92, 84, 58), (66, 92, 70)]):
        d.ellipse([M + 34 + i * 30, y + 32, M + 48 + i * 30, y + 46], fill=c)
    blit_text(img, title, "mono", 26, M + 148, y + 39, MUTED, 0.9, anchor="lm")
    d.line([M + 20, y + 70, M + CW - 20, y + 70], fill=BORDER, width=2)


def tline(img, txt, y, t, t0, color=TEXT, size=32, typed=False, cps=42, x=M + 36):
    if t < t0:
        return
    a = appear(t, t0, 0.18)
    if typed:
        shown, done = typewriter(txt, t, t0, cps)
        blit_text(img, shown, "mono", size, x, y, color, 1)
        if not done:
            cx = x + measure(shown, "mono", size) + 6
            ImageDraw.Draw(img).rectangle([cx, y + 4, cx + 14, y + size - 2], fill=CYAN)
    else:
        blit_text(img, txt, "mono", size, x, y, color, a)


def check_mark(img, x, y, s, a, prog):
    d = ImageDraw.Draw(img)
    p1, p2, p3 = (x + s * 0.24, y + s * 0.52), (x + s * 0.44, y + s * 0.72), (x + s * 0.78, y + s * 0.30)
    if prog > 0:
        k = clamp(prog / 0.5)
        d.line([p1, (p1[0] + (p2[0] - p1[0]) * k, p1[1] + (p2[1] - p1[1]) * k)], fill=(12, 20, 14), width=7)
    if prog > 0.5:
        k = clamp((prog - 0.5) / 0.5)
        d.line([p2, (p2[0] + (p3[0] - p2[0]) * k, p2[1] + (p3[1] - p2[1]) * k)], fill=(12, 20, 14), width=7)


# ---------------- СЦЕНЫ ----------------
def s_hook(img, t, sc):
    kicker(None, img, "// без лица · без камеры", t)
    words = [("ЭТО", -0.25, False), ("СДЕЛАЛ", 0.15, False), ("АГЕНТ", 0.45, True)]
    y = 430
    for txt, t0, hero in words:
        size = fit_size(txt, "disp", CW, 142)
        a = appear(t, t0, 0.30)
        sc_ = 0.88 + 0.12 * out_back((t - t0) / 0.42)
        if a > 0:
            if hero:
                spr = grad_text_sprite(txt, "disp", size, CYAN, LIME)
                ox, oy = spr._off
                blit(img, spr, M - ox + (1 - sc_) * measure(txt, "disp", size) / 2, y - oy, a, sc_)
            else:
                blit_text(img, txt, "disp", size, M, y, TEXT, a, sc_)
        y += 158
    chips(img, ["сценарий", "голос", "кадры", "монтаж"], 980, t,
          [2.85, 3.25, 3.65, 4.05], dot=LIME)
    a = appear(t, 4.55, 0.4)
    blit_text(img, "00:50 · 1080×1920 · 30 fps", "mono", 28, CX, 1120, MUTED, a * 0.9, anchor="mt")


def s_prompt(img, t, sc):
    kicker(None, img, "// задача", t)
    a = appear(t, 0.12, 0.35)
    blit(img, rounded(CW, 366, 36, CARD, BORDER, 2), M, 430 + (1 - a) * 22, a)
    if a > 0.2:
        d = ImageDraw.Draw(img)
        d.ellipse([M + 40, 470, M + 100, 530], fill=(34, 48, 80))
        blit_text(img, "ТЫ", "monob", 22, M + 70, 500, CYAN, a, anchor="mm")
        blit_text(img, "ты", "sb", 30, M + 120, 500, MUTED, a, anchor="lm")
        full = "сделай минутный ролик на русском, с озвучкой и субтитрами"
        shown, done = typewriter(full, t, 0.55, 22)
        lines = wrap(full, "sb", 46, 856)
        yy, left = 570, len(shown)
        for ln in lines:
            take = ln[:max(0, left)]
            if take:
                blit_text(img, take, "sb", 46, M + 40, yy, TEXT, 1)
            if left <= len(ln) and not done:
                cx = M + 40 + measure(take, "sb", 46) + 8
                if (t * 2) % 1 < 0.6:
                    d.rectangle([cx, yy + 6, cx + 4, yy + 48], fill=CYAN)
                break
            left -= len(ln) + 1
            yy += 64
    a2 = appear(t, 3.4, 0.35)
    blit_text(img, "1 сообщение · 0 уточнений", "mono", 30, M, 850, MUTED, a2 * 0.9)
    a3 = appear(t, 3.9, 0.3)
    if a3 > 0:
        d = ImageDraw.Draw(img)
        c = tuple(int(v * a3) for v in CYAN)
        d.line([CX - 20, 925, CX, 945, CX + 20, 925], fill=c, width=5)
    a4 = appear(t, 4.2, 0.35)
    if a4 > 0:
        blit(img, rounded(260, 76, 38, CARD_HI, CYAN, 2), CX - 130, 980, a4)
        blit_text(img, "АГЕНТ", "monob", 32, CX, 1018, CYAN, a4 * pulse(t, 1.4, 0.75, 1.0), anchor="mm")


def s_plan(img, t, sc):
    kicker(None, img, "// план", t)
    size = fit_size("РАБОТАЕТ САМ", "disp6", CW, 74)
    blit_text(img, "РАБОТАЕТ САМ", "disp6", size, M, 412, TEXT, appear(t, 0.1, 0.35))
    labels = ["Сценарий", "Голос", "Кадры", "Субтитры"]
    checks = [2.4, 4.0, 5.4, 6.2]
    for i, (lb, ct) in enumerate(zip(labels, checks)):
        y = 560 + i * 136
        a = appear(t, 0.3 + i * 0.14, 0.35)
        dx = (1 - out_cubic((t - (0.3 + i * 0.14)) / 0.35)) * -36
        if a <= 0:
            continue
        done = t >= ct
        blit(img, rounded(CW, 112, 26, CARD_HI if done else CARD,
                          (56, 84, 62) if done else BORDER, 2), M + dx, y, a)
        blit(img, rounded(56, 56, 16, LIME if done else (26, 36, 60),
                          None, 0), M + dx + 32, y + 28, a)
        if done:
            check_mark(img, M + dx + 32, y + 28, 56, a, clamp((t - ct) / 0.28))
        blit_text(img, lb, "b", 44, M + dx + 124, y + 56, TEXT, a, anchor="lm")
        blit_text(img, "готово" if done else "в работе", "mono", 26,
                  M + CW - 34, y + 56, LIME if done else MUTED, a * 0.95, anchor="rm")
    blit_text(img, "всё без моего участия", "mono", 28, M, 1150, MUTED, appear(t, 6.3, 0.4) * 0.9)


def s_skills(img, t, sc):
    kicker(None, img, "// скиллы", t)
    size = fit_size("ГОТОВЫЕ НАВЫКИ", "disp6", CW, 66)
    blit_text(img, "ГОТОВЫЕ НАВЫКИ", "disp6", size, M, 410, TEXT, appear(t, 0.1, 0.35))
    cmd, done = typewriter("npx skills add video-stack", t, 0.5, 30)
    blit_text(img, "$", "monob", 32, M, 512, LIME, appear(t, 0.4, 0.2))
    blit_text(img, cmd, "mono", 32, M + 34, 512, TEXT, 1)
    if not done:
        cx = M + 34 + measure(cmd, "mono", 32) + 6
        ImageDraw.Draw(img).rectangle([cx, 516, cx + 14, 546], fill=CYAN)
    cards = [("ОЗВУЧКА", "живой русский голос", "voice"),
             ("ГРАФИКА", "кадры и типографика", "gfx"),
             ("МОНТАЖ", "склейка и субтитры", "film")]
    for i, (nm, ds, ic) in enumerate(cards):
        t0 = 3.0 + i * 0.75
        a = appear(t, t0, 0.4)
        if a <= 0:
            continue
        y = 600 + i * 212
        dx = (1 - out_cubic((t - t0) / 0.4)) * 34
        blit(img, rounded(CW, 180, 28, CARD, BORDER, 2), M + dx, y, a)
        blit(img, rounded(96, 96, 24, (26, 38, 66), None, 0), M + dx + 32, y + 42, a)
        d = ImageDraw.Draw(img)
        bx, by = M + dx + 32, y + 42
        if ic == "voice":
            for j, hh in enumerate([20, 40, 58, 34, 22]):
                ph = 1 + 0.35 * math.sin(t * 6 + j)
                hh *= ph
                d.rounded_rectangle([bx + 22 + j * 12, by + 48 - hh / 2, bx + 28 + j * 12, by + 48 + hh / 2],
                                    3, fill=CYAN)
        elif ic == "gfx":
            d.ellipse([bx + 20, by + 22, bx + 50, by + 52], outline=LIME, width=4)
            d.rectangle([bx + 46, by + 44, bx + 76, by + 74], outline=CYAN, width=4)
        else:
            d.rounded_rectangle([bx + 20, by + 26, bx + 76, by + 70], 6, outline=CYAN, width=4)
            for j in range(3):
                d.rectangle([bx + 26 + j * 18, by + 32, bx + 32 + j * 18, by + 38], fill=CYAN)
                d.rectangle([bx + 26 + j * 18, by + 58, bx + 32 + j * 18, by + 64], fill=CYAN)
        blit_text(img, nm, "b", 42, M + dx + 164, y + 62, TEXT, a)
        blit_text(img, ds, "r", 30, M + dx + 164, y + 116, MUTED, a)


def s_tools(img, t, sc):
    kicker(None, img, "// инструменты", t)
    terminal(img)
    tline(img, "$ apt-get install ffmpeg", 530, t, 0.35, CYAN, typed=True)
    tline(img, "  ✓ ffmpeg 5.1 готов", 586, t, 1.45, LIME)
    tline(img, "$ pip install pillow", 650, t, 1.75, CYAN, typed=True)
    tline(img, "  ✓ pillow готов", 706, t, 2.55, LIME)
    tline(img, "$ render --size 1080x1920 --fps 30", 770, t, 2.85, CYAN, typed=True, cps=48)
    p = clamp((t - 3.15) / 1.5)
    if p > 0:
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([M + 36, 860, M + CW - 36, 880], 10, fill=(24, 34, 58))
        d.rounded_rectangle([M + 36, 860, M + 36 + int((CW - 72) * p), 880], 10, fill=CYAN)
        blit_text(img, f"кадры {int(1498*p)}/1498", "mono", 28, M + 36, 906, MUTED)
        blit_text(img, f"{int(p*100)}%", "monob", 28, M + CW - 36, 906, CYAN, anchor="rt")
    tline(img, "  ✓ рендер завершён", 980, t, 4.55, LIME)
    blit_text(img, "ни одного клика мышкой", "mono", 28, M, 1250, MUTED, appear(t, 3.6, 0.4) * 0.9)


def s_fix(img, t, sc):
    kicker(None, img, "// самопроверка", t)
    alert = clamp(1 - (t - 1.4) / 1.2) if t < 2.6 else 0.0
    terminal(img, alert=alert, title="sandbox · bash — retry")
    tline(img, "✗ Error: шрифт без кириллицы", 530, t, 0.25, RED, size=31)
    if 0.25 < t < 0.75:
        f = clamp(1 - (t - 0.25) / 0.5) * 0.16
        ov = Image.new("RGB", (W, H), RED)
        img.paste(Image.blend(img, ov, f), (0, 0))
    tline(img, "→ читаю лог и правлю код", 600, t, 1.55, CYAN, size=31)
    a = appear(t, 2.9, 0.35)
    if a > 0:
        blit(img, rounded(CW - 72, 152, 20, (20, 26, 42), BORDER, 2), M + 36, 664, a)
        blit(img, rounded(CW - 72, 74, 20, (46, 24, 32), None, 0), M + 36, 665, a * 0.9)
        blit(img, rounded(CW - 72, 74, 20, (26, 44, 28), None, 0), M + 36, 741, a * 0.9)
        blit_text(img, "- DejaVuSans.ttf", "mono", 30, M + 68, 702, RED, a, anchor="lm")
        blit_text(img, "+ Unbounded-800.ttf", "mono", 30, M + 68, 778, LIME, a, anchor="lm")
    tline(img, "$ retry render", 862, t, 3.95, CYAN, typed=True)
    tline(img, "  ✓ 1498 кадров · 0 ошибок", 926, t, 4.95, LIME, size=31)
    blit_text(img, "я не участвовал", "mono", 28, M, 1250, MUTED, appear(t, 5.6, 0.4) * 0.9)


def s_result(img, t, sc):
    kicker(None, img, "// результат", t)
    a = appear(t, 0.35, 0.45)
    if a > 0:
        s_ = 0.92 + 0.08 * out_back((t - 0.35) / 0.6)
        pw, ph = 324, 576
        card = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
        card.paste(rounded(pw, ph, 32, CARD, BORDER, 2), (0, 0))
        if THUMB:
            mask = Image.new("L", (300, 533), 0)
            ImageDraw.Draw(mask).rounded_rectangle([0, 0, 299, 532], 22, fill=255)
            card.paste(THUMB, (12, 12), mask)
        else:
            card.paste(rounded(300, 533, 22, (24, 34, 58), None, 0), (12, 12))
        d = ImageDraw.Draw(card)
        d.ellipse([pw // 2 - 42, ph // 2 - 42, pw // 2 + 42, ph // 2 + 42], fill=(10, 16, 28, 190))
        d.polygon([(pw // 2 - 14, ph // 2 - 22), (pw // 2 - 14, ph // 2 + 22), (pw // 2 + 24, ph // 2)],
                  fill=(255, 255, 255, 235))
        blit(img, card, CX - (pw * s_) / 2, 400 + (ph * (1 - s_)) / 2, a, s_)
    blit_text(img, "agent_mode_ru.mp4", "monob", 40, CX, 1024, TEXT, appear(t, 1.5, 0.35), anchor="mt")
    blit_text(img, "1080×1920 · 30 fps · 00:50", "mono", 28, CX, 1082, MUTED, appear(t, 1.8, 0.35), anchor="mt")
    a3 = appear(t, 2.7, 0.4)
    if a3 > 0:
        blit(img, rounded(440, 74, 37, (24, 42, 28), LIME, 2), CX - 220, 1140, a3)
        blit_text(img, "✓ ПРОВЕРЕНО АГЕНТОМ", "monob", 28, CX, 1177, LIME, a3, anchor="mm")
    chips(img, ["без камеры", "без лица", "без монтажа"], 1262, t, [4.0, 4.5, 5.0],
          size=28, h=60, color=MUTED, dot=RED)


def s_outro(img, t, sc):
    for txt, y, t0 in [("РЕЖИМ", 500, 0.25), ("АГЕНТА", 668, 0.5)]:
        size = fit_size(txt, "disp", CW, 152)
        a = appear(t, t0, 0.35)
        if a <= 0:
            continue
        s_ = 0.9 + 0.1 * out_back((t - t0) / 0.5)
        spr = grad_text_sprite(txt, "disp", size, CYAN, LIME)
        ox, oy = spr._off
        wpx = measure(txt, "disp", size)
        blit(img, spr, CX - wpx / 2 - ox + (1 - s_) * wpx / 2, y - oy, a, s_)
    blit_text(img, "одна задача → готовый результат", "sb", 42, CX, 880, TEXT,
              appear(t, 1.9, 0.4), anchor="mt")
    a = appear(t, 3.1, 0.4)
    if a > 0:
        s_ = 1 + 0.02 * math.sin(t * 3.2)
        blit(img, rounded(520, 96, 48, LIME, None, 0), CX - 260 * s_, 1000 - (s_ - 1) * 48, a, s_)
        blit_text(img, "Сохрани и попробуй", "b", 40, CX, 1048, (10, 18, 12), a, s_, anchor="mm")
    blit_text(img, "сделано агентом · без съёмок", "mono", 26, CX, 1140, MUTED,
              appear(t, 4.0, 0.4) * 0.9, anchor="mt")


def _shot_card(src, zoom, fx, fy, target_h):
    """Кроп вокруг фокуса с зумом + ресайз под карточку. Возвращает (img, k, (x0,y0))."""
    SW, SH = src.size
    z = max(1.0, zoom)
    cw, ch = SW / z, SH / z
    x0 = clamp(fx * SW - cw / 2, 0, SW - cw)
    y0 = clamp(fy * SH - ch / 2, 0, SH - ch)
    box = (int(x0), int(y0), int(x0 + cw), int(y0 + ch))
    out = src.crop(box)
    scale = target_h / out.height
    return out.resize((int(out.width * scale), target_h), Image.LANCZOS), scale, (x0, y0)


def s_shot(img, t, sc, key):
    k = SHOTS[key]
    d = sc["end"] - sc["start"]
    e = out_cubic(clamp(t / max(d, 0.01)) ** 0.85)
    zoom = k["zoom"][0] + (k["zoom"][1] - k["zoom"][0]) * e
    fx = k["path"][0][0] + (k["path"][1][0] - k["path"][0][0]) * e
    fy = k["path"][0][1] + (k["path"][1][1] - k["path"][0][1]) * e
    shot, scale, off = _shot_card(SHOT_SRC, zoom, fx, fy, CARD_H)

    a = appear(t, 0.08, 0.45)
    if a <= 0:
        return
    dy = (1 - out_cubic((t - 0.08) / 0.5)) * 26
    card = Image.new("RGBA", (shot.width + 4, shot.height + 4), (0, 0, 0, 0))
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], 26, fill=255)
    card.paste(shot, (2, 2), mask)
    scrim = Image.new("RGBA", card.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(scrim)
    for gy in range(card.height):
        kk = max(0.0, (gy - card.height * 0.62) / (card.height * 0.38))
        sd.line([(0, gy), (card.width, gy)], fill=(6, 10, 20, int(150 * kk * kk)))
    card = Image.alpha_composite(card, scrim)

    ImageDraw.Draw(card).rounded_rectangle([1, 1, card.width - 2, card.height - 2], 26,
                                           outline=BORDER + (255,), width=2)

    # подсветка нужной области
    if k.get("ring"):
        rx0, ry0, rx1, ry1 = [v * scale for v in k["ring"]]
        p = clamp((t - k["ring_at"]) / 0.45)
        if p > 0:
            dd = ImageDraw.Draw(card)
            col = LIME + (int(235 * min(1, p * 1.4)),)
            pad = 6
            dd.rounded_rectangle([rx0 - off[0] * scale - pad + 2, ry0 - off[1] * scale - pad + 2,
                                  rx1 - off[0] * scale + pad + 2, ry1 - off[1] * scale + pad + 2],
                                 10, outline=col, width=max(3, int(4 * min(1, p * 2))))

    blit(img, card, M, CARD_Y + dy, a)

    # подпись-чип под карточкой
    cap = k.get("label")
    a2 = appear(t, 0.55, 0.4)
    if cap and a2 > 0:
        wpx = measure(cap, "mono", 26) + 56
        blit(img, rounded(int(wpx), 52, 26, CARD_HI, BORDER, 2), CX - wpx / 2, CARD_Y + CARD_H + 26, a2)
        blit_text(img, cap, "mono", 26, CX, CARD_Y + CARD_H + 52, MUTED, a2, anchor="mm")


SHOT_SRC = Image.open(os.path.join(ROOT, "assets", "shots", "qwen_agent_01.jpg")).convert("RGB")
_SW, _SH = SHOT_SRC.size
CARD_H = 860
CARD_Y = 400
CARD_W = int(CARD_H * _SW / _SH)

SHOTS = {
    "ui": dict(zoom=(1.05, 2.20), path=((0.46, 0.55), (0.31, 0.93)),
               ring=(288, 1140, 478, 1180), ring_at=1.5, label="qwen · режим агента включён"),
    "steps": dict(zoom=(1.55, 1.85), path=((0.50, 0.15), (0.50, 0.32)),
                  ring=None, label="реальный лог: 8 шагов, 4 размышления"),
    "file": dict(zoom=(2.00, 2.18), path=((0.47, 0.37), (0.47, 0.37)),
                 ring=(308, 404, 900, 480), ring_at=1.1, label="agent_mode_ru_9x16.mp4 · готов"),
}


SCENES = {"hook": s_hook, "prompt": s_prompt, "plan": s_plan, "skills": s_skills,
          "tools": s_tools, "fix": s_fix, "result": s_result, "outro": s_outro,
          "ui": lambda img, t, sc: s_shot(img, t, sc, "ui"),
          "steps": lambda img, t, sc: s_shot(img, t, sc, "steps"),
          "file": lambda img, t, sc: s_shot(img, t, sc, "file")}


SCENE_REF = {"hook": 4.85, "plan": 6.5, "skills": 5.15, "tools": 4.8, "fix": 5.2, "outro": 4.2}


def draw_frame(i):
    t = i / FPS
    img = BG.copy()
    hx = 700 + 90 * math.sin(t * 0.22)
    hy = 120 + 70 * math.cos(t * 0.17)
    blit(img, HALO, hx - 380, hy - 380, 0.85)
    blit(img, HALO2, 120 + 60 * math.sin(t * 0.13) - 310, 1450 + 60 * math.cos(t * 0.11) - 310, 0.5)
    sc = next((s for s in TL["scenes"] if s["start"] <= t < s["end"]), TL["scenes"][-1])
    lt = t - sc["start"]
    d = sc["end"] - sc["start"]
    # анимации в сцене рассчитаны на «эталонную» длину — подгоняем под реальную озвучку
    ref = SCENE_REF.get(sc["name"])
    lt_anim = lt * (d / ref) if ref else lt
    hud(img, t, sc)
    SCENES[sc["name"]](img, lt if sc["name"] in ("ui", "steps", "file") else lt_anim, sc)
    if lt < 0.26:  # быстрый скан-вайп на стыке сцен
        k = lt / 0.26
        y = int(320 + k * 1080)
        c = tuple(int(v * (1 - k) * 0.55) for v in CYAN)
        ImageDraw.Draw(img).line([M, y, M + CW, y], fill=c, width=3)
    return img


def stills():
    os.makedirs(OUT, exist_ok=True)
    sc_by = {s["name"]: s for s in TL["scenes"]}
    picks = {"hook": 0.72, "ui": 0.95, "steps": 0.92, "skills": 0.93,
             "tools": 0.95, "fix": 0.95, "file": 0.9, "outro": 0.75}
    for name, frac in picks.items():
        sc = sc_by[name]
        tt = sc["start"] + (sc["end"] - sc["start"]) * frac
        img = draw_frame(int(tt * FPS))
        p = os.path.join(OUT, f"still_{name}.png")
        img.save(p)
        print("saved", p)


def render():
    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
           "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
           "-i", (os.path.join(OUT, "mix.wav") if os.path.exists(os.path.join(OUT, "mix.wav"))
                  else os.path.join(OUT, "mix_final.wav")),
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "19", "-pix_fmt", "yuv420p",
           "-profile:v", "high", "-level", "4.1", "-g", "60",
           "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-shortest",
           "-movflags", "+faststart", os.path.join(OUT, "base.mp4")]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    import time
    t0 = time.time()
    for i in range(NFRAMES):
        p.stdin.write(draw_frame(i).tobytes())
        if i % 150 == 0:
            el = time.time() - t0
            print(f"frame {i}/{NFRAMES}  {el:.1f}s  ({(i+1)/max(el,0.01):.1f} fps)", flush=True)
    p.stdin.close()
    p.wait()
    print("DONE base.mp4", time.time() - t0, "s", flush=True)


if __name__ == "__main__":
    if "--stills" in sys.argv:
        stills()
    else:
        render()
