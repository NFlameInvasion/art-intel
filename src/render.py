"""Рендер кадров 1080x1920 и сборка видео. python3 render.py [--stills]"""
import json, math, os, subprocess, sys
from PIL import Image, ImageDraw
from gfx import (W, H, CYAN, LIME, RED, TEXT, MUTED, CARD, CARD_HI, BORDER,
                 font, measure, fit_size, clamp, out_cubic, out_back, out_expo, pulse,
                 appear, text_sprite, grad_text_sprite, rounded, glow_dot, blit,
                 blit_text, blit_block, wrap, typewriter, make_bg, make_halo)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень проекта (файлы лежат в src/)
EP = os.environ.get("EPISODE_DIR") or ROOT
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
OUT = os.path.join(EP, "out")
os.makedirs(OUT, exist_ok=True)
TL = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
SCRIPT = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))
HUD_LABEL = SCRIPT.get("hud", "ART INTEL")
FPS = TL["fps"]
TOTAL = TL["total"]
NFRAMES = int(round(TOTAL * FPS))
FRAMES = NFRAMES  # для подписей в кадре
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
    blit_text(img, HUD_LABEL, "monob", 26, M + 46, 226, CYAN, 1, anchor="lm")
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
        blit_block(img, [(l, kind, size, color)], tx, y + dy, h, alpha=a)
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
    blit(img, rounded(CW, 320, 36, CARD, BORDER, 2), M, 430 + (1 - a) * 22, a)
    if a > 0.2:
        d = ImageDraw.Draw(img)
        d.ellipse([M + 40, 470, M + 100, 530], fill=(34, 48, 80))
        blit_text(img, "ТЫ", "monob", 22, M + 70, 500, CYAN, a, anchor="mm")
        blit_text(img, "ты", "sb", 30, M + 120, 500, MUTED, a, anchor="lm")
        full = "сделай минутный ролик на русском, с озвучкой и субтитрами"
        shown, done = typewriter(full, t, 0.28, 44)
        lines = wrap(full, "sb", 44, 856)
        yy, left = 556, len(shown)
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
            yy += 60
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
    cmd, done = typewriter("npx skills add video-stack", t, 0.1, 42)
    blit_text(img, "$", "monob", 32, M, 512, LIME, appear(t, 0.4, 0.2))
    blit_text(img, cmd, "mono", 32, M + 34, 512, TEXT, 1)
    if not done:
        cx = M + 34 + measure(cmd, "mono", 32) + 6
        ImageDraw.Draw(img).rectangle([cx, 516, cx + 14, 546], fill=CYAN)
    cards = [("ОЗВУЧКА", "живой русский голос", "voice"),
             ("ГРАФИКА", "кадры и типографика", "gfx"),
             ("МОНТАЖ", "склейка и субтитры", "film")]
    for i, (nm, ds, ic) in enumerate(cards):
        t0 = 0.55 + i * 0.55
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
    terminal(img, y=430, h=470)
    tline(img, "$ apt-get install ffmpeg", 508, t, 0.30, CYAN, typed=True)
    tline(img, "  ✓ ffmpeg 5.1 готов", 550, t, 1.15, LIME, size=30)
    tline(img, "$ pip install pillow", 594, t, 1.45, CYAN, typed=True)
    tline(img, "  ✓ pillow готов", 636, t, 2.15, LIME, size=30)
    tline(img, "$ render --size 1080x1920 --fps 30", 678, t, 2.45, CYAN, typed=True, cps=52)
    p = clamp((t - 2.75) / 1.3)
    if p > 0:
        d = ImageDraw.Draw(img)
        d.rounded_rectangle([M + 36, 730, M + CW - 36, 748], 9, fill=(24, 34, 58))
        d.rounded_rectangle([M + 36, 730, M + 36 + int((CW - 72) * p), 748], 9, fill=CYAN)
        blit_text(img, f"кадры {int(FRAMES*p)}/{FRAMES}", "mono", 26, M + 36, 768, MUTED)
        blit_text(img, f"{int(p*100)}%", "monob", 26, M + CW - 36, 768, CYAN, anchor="rt")
    tline(img, "  ✓ рендер завершён", 820, t, 3.9, LIME, size=30)
    blit_text(img, "ни одного клика мышкой", "mono", 28, M, 960, MUTED, appear(t, 3.2, 0.4) * 0.9)


def s_fix(img, t, sc):
    kicker(None, img, "// самопроверка", t)
    alert = clamp(1 - (t - 1.1) / 1.1) if t < 2.2 else 0.0
    terminal(img, y=430, h=470, alert=alert, title="sandbox · bash — retry")
    tline(img, "✗ Error: шрифт без кириллицы", 508, t, 0.20, RED, size=29)
    if 0.2 < t < 0.65:
        f = clamp(1 - (t - 0.2) / 0.45) * 0.14
        ov = Image.new("RGB", (W, H), RED)
        img.paste(Image.blend(img, ov, f), (0, 0))
    tline(img, "→ читаю лог и правлю код", 550, t, 1.2, CYAN, size=29)
    a = appear(t, 2.1, 0.35)
    if a > 0:
        blit(img, rounded(CW - 72, 136, 20, (20, 26, 42), BORDER, 2), M + 36, 588, a)
        blit(img, rounded(CW - 72, 66, 18, (46, 24, 32), None, 0), M + 36, 589, a * 0.9)
        blit(img, rounded(CW - 72, 66, 18, (26, 44, 28), None, 0), M + 36, 657, a * 0.9)
        blit_text(img, "- DejaVuSans.ttf", "mono", 28, M + 68, 622, RED, a, anchor="lm")
        blit_text(img, "+ LiberationSans.ttf", "mono", 28, M + 68, 690, LIME, a, anchor="lm")
    tline(img, "$ retry render", 748, t, 2.9, CYAN, typed=True)
    tline(img, f"  ✓ {FRAMES} кадров · 0 ошибок", 804, t, 3.7, LIME, size=28)
    blit_text(img, "я не участвовал", "mono", 28, M, 960, MUTED, appear(t, 4.1, 0.4) * 0.9)


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


def s_title(img, t, sc):
    kicker(None, img, "// 30 ноября 2022", t)
    size = fit_size("CHATGPT", "disp", CW, 190)
    a = appear(t, 0.18, 0.45)
    if a > 0:
        s_ = 0.92 + 0.08 * out_back((t - 0.18) / 0.6)
        spr = grad_text_sprite("CHATGPT", "disp", size, CYAN, LIME)
        ox, oy = spr._off
        wpx = measure("CHATGPT", "disp", size)
        blit(img, spr, CX - wpx / 2 - ox, 470 - oy, a, s_)
    blit_text(img, "история одного прототипа", "sb", 44, CX, 680, TEXT,
              appear(t, 0.9, 0.4), anchor="mt")
    chips(img, ["OpenAI", "GPT-3.5", "бесплатно"], 800, t, [1.6, 1.9, 2.2], dot=LIME)


TIMELINE_ROWS = [("2015", "лаборатория в Сан-Франциско"), ("2018", "GPT-1"),
                 ("2019", "Microsoft · $1 млрд"), ("2020", "GPT-3"), ("2022", "ChatGPT")]


def s_timeline(img, t, sc):
    kicker(None, img, "// как всё началось", t)
    for i, (yr, lab) in enumerate(TIMELINE_ROWS):
        t0 = 0.22 + i * 0.5
        a = appear(t, t0, 0.35)
        if a <= 0:
            continue
        y = 400 + i * 150
        dx = (1 - out_cubic((t - t0) / 0.4)) * 30
        blit(img, rounded(CW, 118, 24, CARD, BORDER, 2), M + dx, y, a)
        blit_block(img, [(yr, "monob", 44, CYAN)], M + dx + 34, y, 118, alpha=a)
        blit_block(img, [(lab, "sb", 32, TEXT)], M + dx + 220, y, 118, alpha=a)


MODELS = [("GPT-1", "117 млн параметров", 150, ""), ("GPT-2", "1,5 млрд параметров", 420, "×13"),
          ("GPT-3", "175 млрд параметров", 840, "×117")]


def s_models(img, t, sc):
    kicker(None, img, "// три модели подряд", t)
    for i, (name, sub, w, mult) in enumerate(MODELS):
        t0 = 0.25 + i * 0.55
        a = appear(t, t0, 0.4)
        if a <= 0:
            continue
        y = 460 + i * 240
        g = out_cubic((t - t0) / 0.9)
        blit_text(img, name, "monob", 42, M, y, TEXT, a)
        blit_text(img, sub, "mono", 27, M, y + 54, MUTED, a)
        ww = max(70, int(w * g))
        blit(img, rounded(ww, 46, 23, CYAN if i < 2 else LIME, None, 0), M, y + 96, a * 0.95)
        if mult:
            blit_text(img, mult, "mono", 26, M + ww + 22, y + 119, MUTED, a)


def s_money(img, t, sc):
    kicker(None, img, "// 2019", t)
    size = fit_size("$1 МЛРД", "disp", CW, 210)
    a = appear(t, 0.18, 0.45)
    if a > 0:
        s_ = 0.9 + 0.1 * out_back((t - 0.18) / 0.6)
        blit_text(img, "$1 МЛРД", "disp", size, CX, 440, LIME, a, s_, anchor="mt")
    blit_text(img, "инвестиции Microsoft", "sb", 44, CX, 720, TEXT, appear(t, 0.9, 0.4), anchor="mt")
    blit_text(img, "лаборатория становится компанией", "mono", 30, CX, 800, MUTED,
              appear(t, 1.5, 0.4), anchor="mt")


def s_rlhf(img, t, sc):
    kicker(None, img, "// что решило дело", t)
    blit_text(img, "RLHF", "disp", 150, M, 420, TEXT, appear(t, 0.15, 0.4))
    blit_text(img, "обучение на оценках людей", "sb", 40, M, 620, TEXT, appear(t, 0.7, 0.4))
    steps = ["модель отвечает", "человек ставит оценку", "модель дообучается"]
    for i, txt in enumerate(steps):
        a = appear(t, 1.3 + i * 0.55, 0.35)
        if a <= 0:
            continue
        y = 760 + i * 130
        blit(img, rounded(CW, 96, 24, CARD, BORDER, 2), M, y, a)
        blit_block(img, [(str(i + 1), "monob", 32, LIME)], M + 36, y, 96, alpha=a)
        blit_block(img, [(txt, "sb", 34, TEXT)], M + 100, y, 96, alpha=a)


def s_chat(img, t, sc):
    kicker(None, img, "// диалог вместо текста", t)
    a0 = appear(t, 0.1, 0.4)
    if a0 > 0:
        blit(img, rounded(CW, 500, 34, CARD, BORDER, 2), M, 400, a0)
        blit_text(img, "chat.openai.com", "mono", 24, M + 34, 436, MUTED, a0 * 0.9)
    a1 = appear(t, 0.5, 0.35)
    if a1 > 0:
        blit(img, rounded(620, 96, 24, CARD_HI, BORDER, 2), M + 40, 500, a1)
        blit_text(img, "объясни, как работает GPT", "sb", 32, M + 68, 548, TEXT, a1, anchor="lm")
    a2 = appear(t, 1.3, 0.35)
    if a2 > 0:
        blit(img, rounded(700, 230, 24, (16, 24, 40), BORDER, 2), M + 40, 620, a2)
        shown, done = typewriter("Представь, что модель прочитала почти весь интернет и учится предсказывать следующее слово…", t, 1.5, 34)
        lines = wrap(shown, "sb", 30, 630)
        yy = 652
        for ln in lines[:6]:
            blit_text(img, ln, "sb", 30, M + 68, yy, TEXT, a2)
            yy += 42
        if not done and (t * 2) % 1 < 0.6:
            ImageDraw.Draw(img).rectangle([M + 68, yy + 4, M + 74, yy + 34], fill=CYAN)


def s_growth(img, t, sc):
    kicker(None, img, "// скорость роста", t)
    blit_text(img, "1 МЛН", "disp", 150, M, 420, LIME, appear(t, 0.15, 0.4))
    blit_text(img, "пользователей за 5 дней", "sb", 38, M, 600, TEXT, appear(t, 0.7, 0.4))
    rows = [("ChatGPT", "2 месяца", 300), ("TikTok", "9 месяцев", 840)]
    for i, (name, dur, w) in enumerate(rows):
        t0 = 1.5 + i * 0.7
        a = appear(t, t0, 0.4)
        if a <= 0:
            continue
        y = 780 + i * 200
        blit_text(img, name, "monob", 38, M, y, TEXT, a)
        blit_text(img, dur, "mono", 28, M + CW, y + 6, MUTED, a, anchor="rt")
        g = out_cubic((t - t0) / 0.9)
        blit(img, rounded(max(60, int(w * g)), 42, 21, CYAN if i == 0 else BORDER, None, 0), M, y + 62, a * 0.95)


def s_gpt4(img, t, sc):
    kicker(None, img, "// 14 марта 2023", t)
    size = fit_size("GPT-4", "disp", CW, 220)
    a = appear(t, 0.18, 0.45)
    if a > 0:
        s_ = 0.9 + 0.1 * out_back((t - 0.18) / 0.6)
        blit_text(img, "GPT-4", "disp", size, CX, 430, TEXT, a, s_, anchor="mt")
    blit_text(img, "следующее поколение", "sb", 44, CX, 720, TEXT, appear(t, 0.9, 0.4), anchor="mt")
    chips(img, ["текст", "изображения", "код"], 830, t, [1.5, 1.8, 2.1], dot=CYAN)


def s_end(img, t, sc):
    for txt, y, t0 in [("С ЭТОГО", 470, 0.2), ("НАЧАЛОСЬ", 640, 0.45)]:
        size = fit_size(txt, "disp", CW, 150)
        a = appear(t, t0, 0.35)
        if a <= 0:
            continue
        s_ = 0.9 + 0.1 * out_back((t - t0) / 0.5)
        spr = grad_text_sprite(txt, "disp", size, CYAN, LIME)
        ox, oy = spr._off
        wpx = measure(txt, "disp", size)
        blit(img, spr, CX - wpx / 2 - ox + (1 - s_) * wpx / 2, y - oy, a, s_)
    blit_text(img, "хочешь знать больше о нейросетях?", "sb", 42, CX, 860, TEXT,
              appear(t, 1.7, 0.4), anchor="mt")
    a = appear(t, 2.9, 0.4)
    if a > 0:
        s_ = 1 + 0.02 * math.sin(t * 3.2)
        blit(img, rounded(660, 100, 50, LIME, None, 0), CX - 330 * s_, 1010 - (s_ - 1) * 50, a, s_)
        wpx = measure("Подписаться · Арт Интел", "b", 40)
        blit_block(img, [("Подписаться · Арт Интел", "b", 40, (10, 18, 12))],
                   CX - wpx / 2, 1010, 100, alpha=a)
    blit_text(img, "telegram · короткие видео про ИИ", "mono", 26, CX, 1150, MUTED,
              appear(t, 3.6, 0.4) * 0.9, anchor="mt")


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
        blit(img, rounded(660, 100, 50, LIME, None, 0), CX - 330 * s_, 1000 - (s_ - 1) * 50, a, s_)
        wpx = measure("Подписаться · Арт Интел", "b", 40)
        blit_block(img, [("Подписаться · Арт Интел", "b", 40, (10, 18, 12))],
                   CX - wpx / 2, 1000, 100, alpha=a)
    blit_text(img, "telegram · короткие видео про ИИ", "mono", 26, CX, 1140, MUTED,
              appear(t, 4.0, 0.4) * 0.9, anchor="mt")


def s_flow(img, t, sc):
    """Мультяшная схема: задача → агент → готовый файл."""
    import doodles as dd
    kicker(None, img, "// как это работает", t)

    a1 = appear(t, 0.15, 0.4)
    if a1 > 0:
        dd.bubble(img, CX, 428, 640, 100, t, text="сделай ролик")

    a2 = appear(t, 0.8, 0.3)
    dd.arrow(img, CX, 610, 700, t, a2)

    a3 = appear(t, 1.15, 0.45)
    if a3 > 0:
        dd.robot(img, CX, 880, s=0.86, t=t)
        blit_text(img, "АГЕНТ", "monob", 34, CX, 1084, LIME, a3, anchor="mt")

    a4 = appear(t, 2.4, 0.3)
    dd.arrow(img, CX, 1150, 1205, t, a4, color=LIME)

    a5 = appear(t, 2.8, 0.45)
    if a5 > 0:
        dd.file_icon(img, CX, 1322, s=0.62, t=t, ok=t > 3.4)


def s_compare(img, t, sc):
    """Чат-бот отвечает — агент доводит задачу до результата. С мультяшными иконками."""
    import doodles as dd
    kicker(None, img, "// в чём разница", t)
    rows = [
        ("ЧАТ-БОТ", "отвечает текстом и ждёт вопроса", MUTED, BORDER, 0.25, (26, 32, 48)),
        ("АГЕНТ", "получает задачу и доводит её до результата", LIME, (56, 84, 62), 2.15, CARD_HI),
    ]
    for i, (name, desc, col, brd, t0, fill) in enumerate(rows):
        a = appear(t, t0, 0.4)
        if a <= 0:
            continue
        y = 500 + i * 330
        dx = (1 - out_cubic((t - t0) / 0.45)) * 30
        blit(img, rounded(CW, 268, 30, fill, brd, 2), M + dx, y, a)
        blit_text(img, name, "monob", 46, M + dx + 40, y + 46, col, a)
        blit_text(img, desc, "r", 32, M + dx + 40, y + 108, TEXT if i else MUTED, a)
        if i == 0:
            dd.bubble(img, M + dx + CW - 120, y + 96, 140, 70, t, dot_color=MUTED)
        else:
            dd.robot(img, M + dx + CW - 140, y + 130, s=0.34, t=t)
            sx = M + dx + 44
            for j, step in enumerate(["скиллы", "раскадровка", "голос", "монтаж"]):
                ca = appear(t, t0 + 0.5 + j * 0.3, 0.3)
                if ca > 0:
                    blit_text(img, step, "mono", 25, sx, y + 208, TEXT, ca * 0.95)
                sx += measure(step, "mono", 25) + 46
    a = appear(t, 3.0, 0.4)
    if a > 0:
        blit_text(img, "разница — не в ответе, а в результате", "mono", 28, CX, 1230, MUTED,
                  a * 0.9, anchor="mt")


def _shot_card(src, box, zoom, target_h):
    """Кроп заданной области (в пикселях исходника) + лёгкий наезд. Возвращает (img, scale, (x0,y0))."""
    x0, y0, x1, y1 = box
    cw, ch = (x1 - x0), (y1 - y0)
    # лёгкий зум внутри кропа
    zw, zh = cw / zoom, ch / zoom
    cx, cy = x0 + cw / 2, y0 + ch / 2
    bx0 = int(clamp(cx - zw / 2, 0, src.width - zw))
    by0 = int(clamp(cy - zh / 2, 0, src.height - zh))
    out = src.crop((bx0, by0, int(bx0 + zw), int(by0 + zh)))
    scale = min(target_h / out.height, CARD_W / out.width)
    return out.resize((int(out.width * scale), int(out.height * scale)), Image.LANCZOS), scale, (bx0, by0)


def s_shot(img, t, sc, key):
    k = SHOTS[key]
    d = sc["end"] - sc["start"]
    e = out_cubic(clamp(t / max(d, 0.01)) ** 0.85)
    zoom = k["zoom"][0] + (k["zoom"][1] - k["zoom"][0]) * e
    shot, scale, off = _shot_card(SHOT_SRC, k["crop"], zoom, k.get("max_h", 900))

    ta = appear(t, 0.05, 0.4)
    if k.get("title") and ta > 0:
        size = fit_size(k["title"], "disp6", CW, 78)
        blit_text(img, k["title"], "disp6", size, M, 430, TEXT, ta)
        if k.get("sub"):
            blit_text(img, k["sub"], "mono", 28, M, 520, MUTED, appear(t, 0.3, 0.4) * 0.9)

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
        kk = max(0.0, (gy - card.height * 0.72) / (card.height * 0.28))
        sd.line([(0, gy), (card.width, gy)], fill=(6, 10, 20, int(120 * kk * kk)))
    card = Image.alpha_composite(card, scrim)

    ImageDraw.Draw(card).rounded_rectangle([1, 1, card.width - 2, card.height - 2], 26,
                                           outline=BORDER + (255,), width=2)

    # подсветка нужной области (координаты — в пикселях исходного скриншота)
    if k.get("ring"):
        rx0, ry0, rx1, ry1 = k["ring"]
        p = clamp((t - k["ring_at"]) / 0.45)
        if p > 0:
            dd = ImageDraw.Draw(card)
            col = LIME + (int(235 * min(1, p * 1.4)),)
            pad = 7
            dd.rounded_rectangle([(rx0 - off[0]) * scale - pad + 2, (ry0 - off[1]) * scale - pad + 2,
                                  (rx1 - off[0]) * scale + pad + 2, (ry1 - off[1]) * scale + pad + 2],
                                 12, outline=col, width=max(4, int(5 * min(1, p * 2))))

    card_y = 620 if k.get("title") else CARD_Y + max(0, (900 - card.height) // 2)
    blit(img, card, (W - card.width) // 2, card_y + dy, a)

    # нижняя поясняющая строка
    fa = appear(t, 1.1, 0.45)
    if k.get("foot") and fa > 0:
        blit_text(img, k["foot"], "sb", 34, M, 1180, MUTED, fa * 0.95)

    # подпись-чип под карточкой
    cap = k.get("label")
    a2 = appear(t, 0.55, 0.4)
    if cap and a2 > 0:
        wpx = measure(cap, "mono", 27) + 56
        chip_y = card_y + card.height + 22
        blit(img, rounded(int(wpx), 54, 27, CARD_HI, BORDER, 2), CX - wpx / 2, chip_y, a2)
        blit_text(img, cap, "mono", 27, CX, chip_y + 27, MUTED, a2, anchor="mm")


_shot_path = os.path.join(EP, "assets", "shots", "qwen_agent_01.jpg")
if not os.path.exists(_shot_path):
    _shot_path = os.path.join(ROOT, "assets", "shots", "qwen_agent_01.jpg")
SHOT_SRC = Image.open(_shot_path).convert("RGB")
_SW, _SH = SHOT_SRC.size
CARD_H = 860
CARD_Y = 400
CARD_W = 1010

SHOTS = {
    # нижняя полоса чата: поле ввода + кнопка «Режим агента»
    "ui": dict(crop=(250, 1052, 1020, 1195), zoom=(1.0, 1.05), title="РЕЖИМ АГЕНТА", sub="новый режим в Qwen Chat", foot="включается кнопкой · задача — одна строка",
               ring=(288, 1136, 486, 1188), ring_at=1.1,
               label="qwen · режим агента включён"),
    # лог шагов агента
    "steps": dict(crop=(300, 70, 1120, 400), zoom=(1.0, 1.06), title="ВОСЕМЬ ШАГОВ", sub="агент делает их сам", foot="сам ставит пакеты, правит код, перезапускает рендер",
                  ring=None, label="реальный лог: шаги и размышления"),
    # карточка готового файла
    "file": dict(crop=(300, 372, 940, 492), zoom=(1.0, 1.05), title="ГОТОВЫЙ ФАЙЛ", sub="проверен агентом", foot="1080×1920 · 30 fps · 49 секунд",
                 ring=(308, 380, 900, 486), ring_at=0.9,
                 label="agent_mode_ru_9x16.mp4 · готов"),
}


SCENES = {"hook": s_hook, "prompt": s_prompt, "plan": s_plan, "skills": s_skills,
          "tools": s_tools, "fix": s_fix, "result": s_result, "outro": s_outro, "compare": s_compare, "flow": s_flow,
          "title": s_title, "timeline": s_timeline, "models": s_models, "money": s_money,
          "rlhf": s_rlhf, "chat": s_chat, "growth": s_growth, "gpt4": s_gpt4, "end": s_end,
          "ui": lambda img, t, sc: s_shot(img, t, sc, "ui"),
          "steps": lambda img, t, sc: s_shot(img, t, sc, "steps"),
          "file": lambda img, t, sc: s_shot(img, t, sc, "file")}



FOOT = {
    "title": "30 ноября 2022 · первый день",
    "timeline": "семь лет до взрыва",
    "models": "от 117 миллионов до 175 миллиардов параметров",
    "money": "миллиард — и партнёрство с Microsoft",
    "rlhf": "оценки людей вместо гонки параметров",
    "chat": "диалог вместо текстового поля",
    "growth": "быстрее, чем TikTok, Instagram и WhatsApp",
    "gpt4": "через четыре месяца после запуска",
}

SCENE_REF = {"hook": 4.0, "plan": 6.5, "skills": 5.2, "tools": 5.2, "fix": 5.0, "outro": 4.2, "compare": 4.6, "flow": 4.4,
              "title": 3.2, "timeline": 3.2, "models": 2.8, "money": 2.4,
              "rlhf": 3.2, "chat": 3.2, "growth": 3.8, "gpt4": 2.8, "end": 3.8}


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
    ft = FOOT.get(sc["name"])
    if ft:
        fa = appear(lt, 1.15, 0.45)
        if fa > 0:
            blit_text(img, ft, "mono", 30, M, 1180, MUTED, fa * 0.9)
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
    picks = {name: 0.9 for name in sc_by}
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
