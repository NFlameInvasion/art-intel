#!/usr/bin/env python3
"""Иллюстрации для векторных сцен (стиль B).

Каждая функция рисует SVG-примитивы внутри области 100..980 x 330..830
и анимирует их от времени сцены. Ничего не растягивается: всё пересчитывается
на кадр, поэтому линии и текст остаются резкими.
"""
import math, os, subprocess
import numpy as np

BG_INK = "#FFFFFF"
DIM = "#B9A7D6"

# ---------- easing ----------
def clamp(v, a=0.0, b=1.0):
    return max(a, min(b, v))


def seg(t, t0, d):
    return clamp((t - t0) / d) if d > 0 else (1.0 if t >= t0 else 0.0)


def out_cubic(p):
    return 1 - (1 - p) ** 3


def in_out_cubic(p):
    return 4 * p ** 3 if p < .5 else 1 - (-2 * p + 2) ** 3 / 2


def out_expo(p):
    return 1.0 if p >= 1 else 1 - 2 ** (-10 * p)


def out_back(p, s=1.6):
    return 1 + (s + 1) * (p - 1) ** 3 + s * (p - 1) ** 2


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# ---------- audio envelope ----------
def load_rms(path, wps=40):
    """RMS-огибающая сцены: 40 точек в секунду."""
    raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", path,
                                   "-f", "f32le", "-ac", "1", "-ar", "8000", "-"])
    x = np.frombuffer(raw, dtype=np.float32)
    hop = max(1, 8000 // wps)
    n = max(1, len(x) // hop)
    blk = x[:n * hop].reshape(n, hop)
    r = np.sqrt((blk ** 2).mean(axis=1))
    r = r / (r.max() or 1.0)
    return np.convolve(r, np.ones(3) / 3, mode="same")


def env_at(rms, t_rel, sc_dur):
    if rms is None or len(rms) == 0:
        return 0.4 + 0.3 * math.sin(t_rel * 6)
    i = int(clamp(t_rel / max(0.01, sc_dur), 0, 1) * (len(rms) - 1))
    return float(rms[i])


# ---------- primitives ----------
def rect(x, y, w, h, r=0, fill="none", stroke=None, sw=0, op=1.0):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0.1, w):.1f}" height="{max(0.1, h):.1f}" '
            f'rx="{r}" fill="{fill}"{st} opacity="{op:.3f}"/>')


def line(x1, y1, x2, y2, stroke, sw=3, op=1.0, dash=None, cap="round"):
    da = f' stroke-dasharray="{dash}"' if dash else ""
    return (f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{stroke}" '
            f'stroke-width="{sw}" stroke-linecap="{cap}" opacity="{op:.3f}"{da}/>')


def circle(cx, cy, r, fill="none", stroke=None, sw=0, op=1.0):
    st = f' stroke="{stroke}" stroke-width="{sw}"' if stroke else ""
    return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" fill="{fill}"{st} opacity="{op:.3f}"/>'


def txt(x, y, s, size=28, fill=BG_INK, op=1.0, anchor="middle", ls=0, weight=700, font="JetBrains Mono"):
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
            f'fill="{fill}" opacity="{op:.3f}" text-anchor="{anchor}" letter-spacing="{ls}">{esc(s)}</text>')


def group(items, op=1.0, tf=""):
    return f'<g opacity="{op:.3f}" transform="{tf}">' + "".join(items) + "</g>"


def arrow(x1, y1, x2, y2, p, color, sw=5, op=1.0, head=16):
    """Линия со стрелкой, дорисованная до доли p."""
    if p <= 0:
        return ""
    mx, my = x1 + (x2 - x1) * p, y1 + (y2 - y1) * p
    ang = math.atan2(y2 - y1, x2 - x1)
    ax, ay = mx - head * math.cos(ang), my - head * math.sin(ang)
    lx, ly = -math.sin(ang) * head * 0.55, math.cos(ang) * head * 0.55
    return (line(x1, y1, ax, ay, color, sw, op) +
            f'<path d="M {mx:.1f} {my:.1f} L {ax+lx:.1f} {ay+ly:.1f} L {ax-lx:.1f} {ay-ly:.1f} Z" '
            f'fill="{color}" opacity="{op:.3f}"/>')


# ---------- illustrations ----------
def timeline(t, dur, g1, g2, rms=None):
    out = []
    y = 600
    out.append(line(100, y, 980, y, BG_INK, 3, 0.18))
    for k in range(10):                      # риски
        x = 100 + k * 97.7
        out.append(line(x, y - 10, x, y + 10, BG_INK, 2, 0.18))
    widths = [150, 190, 120, 210, 150]
    x = 100
    for i, w in enumerate(widths):
        p = out_back(seg(t, 0.15 + i * 0.11, 0.55))
        if p > 0:
            h = (76 if i % 2 else 100) * p
            fill = f"url(#acc)" if i % 2 == 0 else "none"
            out.append(rect(x, y - h / 2, w, h, 10, fill,
                            None if i % 2 == 0 else BG_INK, 0 if i % 2 == 0 else 2,
                            min(1, p)))
            out.append(line(x + 14, y - h / 2 + 18, x + w - 14, y - h / 2 + 18, BG_INK, 3,
                            0.35 * p))
        x += w + 15
    ph = 100 + 880 * clamp(t / dur)
    out.append(line(ph, y - 130, ph, y + 130, BG_INK, 2, 0.55))
    out.append(circle(ph, y - 130, 9, f"url(#acc)"))
    out.append(txt(100, 760, "00:00", 22, DIM, 0.9, "start", 2, 500))
    out.append(txt(980, 760, f"00:{int(dur):02d}", 22, DIM, 0.9, "end", 2, 500))
    return out


def grid(t, dur, g1, g2, rms=None):
    out, cells = [], [(0, 0), (1, 0), (2, 0), (0, 1), (1, 1), (2, 1)]
    cw, ch, gx = 260, 140, 20
    x0 = 540 - (3 * cw + 2 * gx) / 2
    y0 = 430
    for i, (cx, cy) in enumerate(cells):
        p = out_back(seg(t, 0.1 + i * 0.09, 0.5))
        if p <= 0:
            continue
        x, y = x0 + cx * (cw + gx), y0 + cy * (ch + gx)
        out.append(rect(x, y, cw * p, ch * p, 14, "none", BG_INK, 2, 0.55))
        out.append(rect(x + 16, y + 16, (cw - 32) * p, 10, 5, f"url(#acc)", op=0.9))
        out.append(rect(x + 16, y + 40, (cw - 90) * p, 8, 4, BG_INK, op=0.28))
        out.append(rect(x + 16, y + 60, (cw - 130) * p, 8, 4, BG_INK, op=0.18))
        if i == len(cells) - 1:              # play-метка на последней ячейке
            out.append(circle(x + cw - 34, y + ch - 34, 16, "none", f"url(#acc)", 2, 0.9))
            out.append(f'<path d="M {x+cw-38} {y+ch-44} L {x+cw-28} {y+ch-34} L {x+cw-38} {y+ch-24} Z" '
                       f'fill="none" stroke="url(#acc)" stroke-width="2" opacity="0.9"/>')
    return out


def waveform(t, dur, g1, g2, rms=None):
    out, n, bw, gap = [], 30, 12, 17
    total = n * bw + (n - 1) * gap
    x0 = 540 - total / 2
    base = 640
    for i in range(n):
        v = 0.12 + 0.88 * min(1.0, env_at(rms, t - (i / n) * 0.9, dur) * 1.15)
        h = 18 + 210 * v
        x = x0 + i * (bw + gap)
        p = out_cubic(seg(t, 0.05 + i * 0.012, 0.4))
        col = f"url(#acc)" if 8 <= i <= 21 else "#FFFFFF"
        out.append(rect(x, base - h * p / 2, bw, h * p, bw / 2, col, op=0.9 if 8 <= i <= 21 else 0.35))
    out.append(line(100, base, 980, base, BG_INK, 2, 0.15))
    out.append(txt(540, 760, "ГОЛОС → ТАЙМИНГИ", 22, DIM, 0.9, "middle", 4, 500))
    return out


def frames(t, dur, g1, g2, rms=None):
    out, n, s, gap = [], 5, 150, 22
    total = n * s + (n - 1) * gap
    x0 = 540 - total / 2
    y = 470
    for i in range(n):
        p = out_back(seg(t, 0.1 + i * 0.1, 0.5))
        if p <= 0:
            continue
        x = x0 + i * (s + gap)
        out.append(rect(x, y, s * p, s * p, 12, "none", BG_INK, 2, 0.5))
        if i % 3 == 0:
            out.append(rect(x + 10, y + 10, (s - 20) * p, (s - 20) * p, 8, f"url(#acc)", op=0.55))
        out.append(txt(x + s / 2, y + s + 34, f"{i+1:02d}", 20, DIM, 0.8 * p, "middle", 2, 500))
    out.append(rect(540 - 90, 700, 180, 54, 27, "none", f"url(#acc)", 2, 0.9))
    out.append(txt(540, 736, "30 FPS", 22, BG_INK, 0.95, "middle", 3))
    return out


def subtitle(t, dur, g1, g2, rms=None, words=None, measure=None):
    out = []
    w, h = 800, 190
    x, y = 540 - w / 2, 470
    p = out_cubic(seg(t, 0.05, 0.45))
    out.append(rect(x, y, w * p, h, 24, "none", BG_INK, 2, 0.35))
    out.append(rect(x + 26, y + 24, 62, 30, 8, f"url(#acc)", op=0.9 * p))
    out.append(txt(x + 57, y + 46, "CC", 17, "#1B1035", 0.95 * p, "middle", 1))
    ws = (words or [])[:6]
    m = measure or (lambda s_: len(s_) * 16.0)
    rows = [ws[:3], ws[3:6]]
    for ri, row in enumerate(rows):
        if not row:
            continue
        gap = 16.0
        total = sum(m(wt["w"]) for wt in row) + gap * (len(row) - 1)
        cx = 540 - total / 2
        for wt in row:
            wpx = m(wt["w"])
            if t < wt["s"] - 0.05:
                cx += wpx + gap
                continue
            act = wt["s"] - 0.05 <= t <= wt["e"] + 0.12
            out.append(txt(cx, y + 96 + ri * 56, wt["w"], 32, f"url(#acc)" if act else BG_INK,
                           0.95, "start", 0, 500, "Manrope"))
            cx += wpx + gap
    out.append(txt(540, y + h + 56, "СУБТИТРЫ НА ТЕХ ЖЕ ТАЙМИНГАХ", 20, DIM, 0.85, "middle", 3, 500))
    return out


def meter(t, dur, g1, g2, rms=None):
    out, n, bw, gap = [], 22, 18, 10
    total = n * bw + (n - 1) * gap
    x0 = 540 - total / 2
    base = 680
    for i in range(n):
        # огибающая с памятью: пауза в речи не роняет индикатор в ноль
        win = [env_at(rms, t - (i * 0.02) - k * 0.05, dur) for k in range(8)]
        v = max(win) * 0.75 + (sum(win) / len(win)) * 0.25
        shape = 0.82 + 0.28 * math.sin(i * 0.9 + t * 2.6)
        h = 56 + 210 * min(1.0, 1.15 * v * shape)
        p = out_cubic(seg(t, 0.05 + i * 0.02, 0.45))
        out.append(rect(x0 + i * (bw + gap), base - h * p, bw, h * p, 6, f"url(#acc)", op=0.85))
    out.append(line(100, base, 980, base, BG_INK, 2, 0.2))
    for k, lab in ((0, "0"), (1, "−18")):
        yy = base - k * 200
        out.append(line(100, yy, 980, yy, BG_INK, 1, 0.12, "6 8"))
        out.append(txt(988, yy + 6, lab, 18, DIM, 0.8, "start", 1, 500))
    return out


def encode(t, dur, g1, g2, rms=None):
    out = []
    p = in_out_cubic(seg(t, 0.1, 1.6))
    cx, cy, r = 330, 580, 118
    circ = 2 * math.pi * r
    out.append(circle(cx, cy, r, "none", BG_INK, 10, 0.15))
    out.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="none" stroke="url(#acc)" stroke-width="10" '
               f'stroke-linecap="round" stroke-dasharray="{circ:.1f}" '
               f'stroke-dashoffset="{circ*(1-p):.1f}" transform="rotate(-90 {cx} {cy})"/>')
    out.append(txt(cx, cy + 12, f"{int(p*100)}%", 44, BG_INK, 0.95, "middle", 1, 800,
                   "Unbounded"))
    chips = ["H.264", "30 FPS", "−14 LUFS"]
    for i, c in enumerate(chips):
        q = out_back(seg(t, 0.9 + i * 0.22, 0.5))
        if q <= 0:
            continue
        cy2 = 470 + i * 100
        out.append(rect(540, cy2 - 40 * q, 300 * q, 80 * q, 40, "none", BG_INK, 2, 0.45))
        out.append(txt(690, cy2 + 10, c, 26, BG_INK, 0.9 * q, "middle", 3))
    return out


def split(t, dur, g1, g2, rms=None):
    out = []
    for i, (x, label) in enumerate(((100, "БЫЛО"), (600, "СТАЛО"))):
        p = out_cubic(seg(t, 0.1 + i * 0.25, 0.5))
        if p <= 0:
            continue
        out.append(rect(x, 430, 380 * p, 280, 20, "none", BG_INK, 2, 0.4))
        out.append(txt(x + 24, 400, label, 20, DIM, 0.9 * p, "start", 3, 500))
        for k in range(3):
            out.append(rect(x + 26, 470 + k * 62, (300 - k * 70) * p, 12, 6,
                            BG_INK if i == 0 else f"url(#acc)", op=0.4))
    p = out_expo(seg(t, 0.75, 0.6))
    out.append(arrow(496, 570, 584, 570, p, "#FF8A3D", 5, 0.95))
    return out


def flow(t, dur, g1, g2, rms=None):
    out, labels = [], ["ЗАДАЧА", "АГЕНТ", "ФАЙЛ"]
    for i, lab in enumerate(labels):
        p = out_back(seg(t, 0.1 + i * 0.35, 0.5))
        if p <= 0:
            continue
        x = 100 + i * 300
        out.append(rect(x, 500, 240 * p, 140, 20,
                        "none" if i != 1 else "url(#acc)", BG_INK if i != 1 else None,
                        2 if i != 1 else 0, 0.55 if i != 1 else 0.9))
        out.append(txt(x + 120, 582, lab, 22,
                       BG_INK if i != 1 else "#1B1035", 0.95, "middle", 3))
        if i > 0:
            q = out_expo(seg(t, 0.3 + (i - 1) * 0.35, 0.45))
            out.append(arrow(x - 58, 570, x - 8, 570, q, BG_INK, 4, 0.6))
    return out


def steps(t, dur, g1, g2, rms=None):
    out = []
    for i in range(3):
        p = out_cubic(seg(t, 0.12 + i * 0.2, 0.5))
        if p <= 0:
            continue
        y = 430 + i * 120
        out.append(txt(110, y + 44, f"{i+1:02d}", 34, f"url(#acc)", 0.95 * p, "start", 1, 800))
        out.append(rect(200, y + 16, 780 * p, 12, 6, BG_INK, op=0.5))
        out.append(rect(200, y + 44, (560 - i * 90) * p, 10, 5, BG_INK, op=0.25))
    return out




def prompt(t, dur, g1, g2, rms=None):
    """Окно с промптом: печатается построчно."""
    out = []
    x, y, w = 100, 400, 880
    lines = ["сделай ролик про Hermes", "стиль B · 9:16 · 115 секунд",
             "голос: silero aidar", "графика: svg + rsvg + ffmpeg"]
    h = 120 + len(lines) * 58
    p = out_cubic(seg(t, 0.05, 0.45))
    out.append(rect(x, y, w * p, h, 24, "none", BG_INK, 2, 0.45))
    if p > 0.9:
        out.append(line(x, y + 64, x + w, y + 64, BG_INK, 2, 0.25))
        for k in range(3):
            out.append(circle(x + 34 + k * 26, y + 32, 6, BG_INK, op=0.35))
        out.append(txt(x + 130, y + 40, "prompt.txt", 20, DIM, 0.8, "start", 2, 500))
        cx = x + 40
        for i, ln in enumerate(lines):
            t0 = 0.5 + i * 0.55
            chars = int(max(0, (t - t0)) * 42)
            if chars <= 0:
                break
            shown = ln[:chars]
            out.append(txt(cx, y + 120 + i * 58, ">", 26, "#FF4D8D", 0.9, "start", 0, 700))
            out.append(txt(cx + 30, y + 120 + i * 58, shown, 26, BG_INK, 0.92, "start", 0, 500))
            if t > t0 + len(ln) / 42 and t < t0 + len(ln) / 42 + 0.5:
                out.append(rect(cx + 32 + len(shown) * 14, y + 98 + i * 58, 12, 26, 0,
                                f"url(#acc)", op=0.9))
    return out


def chat(t, dur, g1, g2, rms=None):
    """Переписка в Телеграме: запрос и ответ."""
    out = []
    p1 = out_cubic(seg(t, 0.1, 0.4))
    p2 = out_cubic(seg(t, 1.6, 0.4))
    if p1 > 0:
        bx, by, bw, bh = 110, 430, 520, 120
        out.append(rect(bx, by + (1 - p1) * 20, bw, bh, 26, BG_INK, op=0.10 * p1))
        out.append(txt(bx + 28, by + 52 + (1 - p1) * 20, "ты", 20, DIM, 0.85 * p1, "start", 2, 500))
        out.append(txt(bx + 28, by + 88 + (1 - p1) * 20, "собери ролик про гермес",
                       28, BG_INK, 0.95 * p1, "start", 0, 600, "Manrope"))
    if p2 > 0:
        bx, by, bw, bh = 450, 600, 530, 170
        out.append(rect(bx, by + (1 - p2) * 20, bw, bh, 26, "url(#acc)", op=0.92 * p2))
        out.append(txt(bx + 28, by + 52 + (1 - p2) * 20, "агент", 20, "#1B1035", 0.8 * p2, "start", 2, 600))
        out.append(txt(bx + 28, by + 98 + (1 - p2) * 20, "готово: 95 с, 1080×1920",
                       28, "#1B1035", 0.95 * p2, "start", 0, 600, "Manrope"))
        out.append(txt(bx + 28, by + 136 + (1 - p2) * 20, "звук −14 LUFS",
                       24, "#1B1035", 0.75 * p2, "start", 0, 500, "Manrope"))
    return out


def stack(t, dur, g1, g2, rms=None):
    """Слои стека: сценарий, голос, кадры, сборка."""
    out = []
    labels = ["сценарий · json", "голос · silero", "кадры · svg/rsvg", "сборка · ffmpeg"]
    bw, bh, gap = 700, 86, 34
    x = 540 - bw / 2
    y0 = 400
    for i, lab in enumerate(labels):
        p = out_back(seg(t, 0.1 + i * 0.18, 0.5))
        if p <= 0:
            continue
        y = y0 + i * (bh + gap)
        out.append(rect(x + (1 - p) * -40, y, bw * p, bh, 18,
                        "none" if i % 2 else "url(#acc)", BG_INK if i % 2 else None,
                        2 if i % 2 else 0, 0.9 if i % 2 else 0.75))
        out.append(txt(x + 30, y + 56, lab, 26,
                       BG_INK if i % 2 else "#1B1035", 0.95 * min(1, p), "start", 1))
        if i:
            q = out_expo(seg(t, 0.25 + i * 0.18, 0.35))
            out.append(arrow(540, y - gap + 4, 540, y - 6, q, BG_INK, 3, 0.45, head=11))
    return out


def numbers(t, dur, g1, g2, rms=None):
    """Крупные цифры производства."""
    out = []
    items = [("30", "кадров в секунду"), ("0.7", "секунды на кадр"),
             ("3 444", "кадра в ролике"), ("−14", "LUFS на выходе")]
    for i, (num, lab) in enumerate(items):
        p = out_cubic(seg(t, 0.12 + i * 0.2, 0.45))
        if p <= 0:
            continue
        cx = 300 if i % 2 == 0 else 780
        cy = 450 + (i // 2) * 220
        out.append(txt(cx, cy, num, 96, f"url(#acc)" if i % 2 == 0 else BG_INK,
                       0.95 * p, "middle", 0, 800, "Unbounded"))
        out.append(txt(cx, cy + 44, lab, 24, DIM, 0.85 * p, "middle", 2, 500, "Manrope"))
    return out


def none_(t, dur, g1, g2, rms=None):
    return []


def _card(x, y, w, h, p, accent=0.75, r=22):
    """Карточка с появлением: масштаб от p."""
    if p <= 0:
        return ""
    yy = y + (1 - p) * 18
    fill = f"url(#acc)" if accent > 0.7 else "none"
    stroke = None if accent > 0.7 else BG_INK
    return rect(x, yy, w, h, r, fill, stroke, 0 if stroke is None else 2,
                (0.92 if fill != "none" else 0.5) * min(1, p))


def _check(cx, cy, p, color=None):
    """Галочка, дорисовывающаяся по доле p."""
    if p <= 0:
        return ""
    col = color or "url(#acc)"
    a = (cx - 9, cy)
    b = (cx - 2, cy + 7)
    c = (cx + 10, cy - 8)
    out = []
    if p < 0.5:
        q = p / 0.5
        out.append(line(a[0], a[1], a[0] + (b[0] - a[0]) * q, a[1] + (b[1] - a[1]) * q, col, 5, 0.95))
    else:
        q = (p - 0.5) / 0.5
        out.append(line(a[0], a[1], b[0], b[1], col, 5, 0.95))
        out.append(line(b[0], b[1], b[0] + (c[0] - b[0]) * q, b[1] + (c[1] - b[1]) * q, col, 5, 0.95))
    return "".join(out)


def handoff(t, dur, g1, g2, rms=None):
    """Чат: модель отвечает кодом, а запускать его тебе."""
    out = []
    p1 = out_cubic(seg(t, 0.15, 0.5))
    if p1 > 0:
        out.append(_card(110, 380 + (1 - p1) * -14, 560, 132, p1, 0.25))
        out.append(txt(140, 424, "ТЫ", 18, DIM, 0.9 * p1, "start", 4, 700))
        out.append(txt(140, 472, "разбери двести строк логов", 26, BG_INK, 0.95 * p1, "start", 0, 600, "Manrope"))
    p2 = out_cubic(seg(t, 1.35, 0.5))
    if p2 > 0:
        out.append(_card(410, 570 + (1 - p2) * 14, 570, 180, p2, 0.9))
        out.append(txt(440, 614, "НЕЙРОСЕТЬ", 18, "#1B1035", 0.85 * p2, "start", 4, 700))
        out.append(txt(440, 664, "вот готовый скрипт", 27, "#1B1035", 0.96 * p2, "start", 0, 600, "Manrope"))
        out.append(txt(440, 712, "запусти сам", 27, "#1B1035", 0.96 * p2, "start", 0, 700, "Manrope"))
    p3 = out_expo(seg(t, 2.5, 0.6))
    out.append(arrow(600, 540, 700, 560, p3, "#FF8A3D", 4, 0.9, head=14))
    return out


def manual(t, dur, g1, g2, rms=None):
    """Ручная рутина: чек-лист и тикающий таймер."""
    out = []
    items = ["скопировать", "вставить", "проверить", "собрать в кучу"]
    out.append(txt(100, 360, f"00:{int(8 + t * 3):02d}", 26, DIM, 0.6, "start", 3, 700))
    out.append(txt(240, 360, "руками", 20, DIM, 0.45, "start", 4, 500))
    for i, lab in enumerate(items):
        p = out_cubic(seg(t, 0.1 + i * 0.42, 0.35))
        if p <= 0:
            continue
        y = 400 + i * 96
        q = out_cubic(seg(t, 0.25 + i * 0.42, 0.3))
        out.append(rect(100, y, 44, 44, 12, "none", BG_INK, 2, 0.4))
        out.append(_check(122, y + 22, q))
        out.append(txt(170, y + 34, lab, 34, BG_INK, 0.92 if q > 0 else 0.45, "start", 0, 600, "Manrope"))
        if q > 0.5:
            wpx = 300 * out_cubic(seg(t, 0.25 + i * 0.42, 0.5))
            out.append(rect(500, y + 14, wpx, 10, 5, f"url(#acc)", op=0.55))
    return out


def talk(t, dur, g1, g2, rms=None):
    """Слева — говорит. Справа — пустой терминал."""
    out = []
    p1 = out_cubic(seg(t, 0.1, 0.5))
    if p1 > 0:
        out.append(txt(100, 400, "ГОВОРИТ", 20, DIM, 0.7 * p1, "start", 5, 700))
        out.append(_card(100, 430, 380, 250, p1, 0.25))
        dots = "".join(circle(170 + k * 34, 555, 10, BG_INK, op=0.85 * p1 * (0.45 + 0.55 * (0.5 + 0.5 * math.sin(t * 5 - k * 0.9))))
                       for k in range(3))
        out.append(dots)
        for k in range(3):
            w = [300, 250, 200][k]
            out.append(rect(130, 470 + k * 34, w * p1, 12, 6, BG_INK, op=0.22))
    p2 = out_cubic(seg(t, 0.9, 0.5))
    if p2 > 0:
        out.append(txt(600, 400, "ДЕЛАЕТ", 20, DIM, 0.7 * p2, "start", 5, 700))
        out.append(_card(600, 430, 380, 250, p2, 0.25))
        out.append(rect(628, 462, 324, 18, 6, BG_INK, op=0.18 * p2))
        out.append(rect(628, 498, 240, 18, 6, BG_INK, op=0.12 * p2))
        out.append(txt(790, 638, "0", 92, f"url(#acc)", 0.95 * p2, "middle", 0, 800, "Manrope"))
        out.append(txt(790, 668, "команд", 20, DIM, 0.7 * p2, "middle", 3, 500))
    return out


def hub(t, dur, g1, g2, rms=None):
    """Агент в центре, вокруг — сервисы; импульсы бегут по линиям."""
    out = []
    cx, cy = 540, 590
    nodes = ["БРАУЗЕР", "БАЗА", "КОД", "ФАЙЛЫ", "API", "ТЕРМИНАЛ"]
    pos = []
    for i in range(6):
        a = math.radians(-90 + i * 60)
        pos.append((cx + 330 * math.cos(a), cy + 205 * math.sin(a) * 1.0))
    r_in, phw, phh = 120.0, 84 + 10, 30 + 10   # выход из кольца и отступ от пилюли
    for i, (x, y) in enumerate(pos):
        p = out_expo(seg(t, 0.12 + i * 0.12, 0.45))
        if p <= 0:
            continue
        dx, dy = x - cx, y - cy
        L = math.hypot(dx, dy) or 1.0
        ux, uy = dx / L, dy / L
        # обрезка по рамке пилюли: линия не заходит внутрь блока
        t_end = min(phw / abs(ux) if abs(ux) > 1e-6 else 1e9,
                    phh / abs(uy) if abs(uy) > 1e-6 else 1e9)
        sx_, sy_ = cx + ux * r_in, cy + uy * r_in
        ex_, ey_ = x - ux * t_end, y - uy * t_end
        out.append(line(sx_, sy_, sx_ + (ex_ - sx_) * p, sy_ + (ey_ - sy_) * p, BG_INK, 2, 0.28))
        # импульс бежит от кольца до границы блока
        if p > 0.9:
            k = ((t * 0.9 + i * 0.17) % 1.0)
            px, py = sx_ + (ex_ - sx_) * k, sy_ + (ey_ - sy_) * k
            out.append(circle(px, py, 5, "url(#acc)", op=0.9))
        q = out_back(seg(t, 0.3 + i * 0.12, 0.4))
        if q > 0:
            bw = 168 * min(1, q)
            out.append(rect(x - bw / 2, y - 30, bw, 60, 30, "none", BG_INK, 2, 0.55 * min(1, q)))
            out.append(txt(x, y + 9, nodes[i], 19, BG_INK, 0.9 * min(1, q), "middle", 2, 600))
    pc = out_back(seg(t, 0.02, 0.5))
    r = 96 * min(1, pc) * (1 + 0.03 * math.sin(t * 4))
    out.append(circle(cx, cy, r, "url(#acc)", op=0.92))
    out.append(circle(cx, cy, r + 18, "none", "url(#acc)", 2, 0.35 * min(1, pc)))
    out.append(txt(cx, cy + 4, "АГЕНТ", 26, "#1B1035", 0.96 * min(1, pc), "middle", 3, 800))
    out.append(txt(cx, cy + 34, "действует", 17, "#1B1035", 0.7 * min(1, pc), "middle", 2, 500, "Manrope"))
    return out


def logo(t, dur, g1, g2, rms=None):
    """Карточка с названием."""
    out = []
    p = out_back(seg(t, 0.15, 0.6))
    if p <= 0:
        return out
    w, h = 760 * (0.94 + 0.06 * min(1, p)), 340
    x, y = 540 - w / 2, 430
    out.append(rect(x, y, w, h, 34, "none", BG_INK, 2, 0.4 * min(1, p)))
    out.append(rect(x + 26, y + 26, 74, 26, 8, "url(#acc)", op=0.9 * min(1, p)))
    out.append(txt(x + 63, y + 46, "AGENT", 15, "#1B1035", 0.95 * min(1, p), "middle", 1, 800))
    out.append(txt(540, y + 170, "HERMES", 96, "url(#acc)", min(1, p), "middle", 0, 800, "Unbounded"))
    out.append(txt(540, y + 236, "AGENT", 54, BG_INK, 0.95 * min(1, p), "middle", 16, 800, "Unbounded"))
    q = out_cubic(seg(t, 0.9, 0.5))
    if q > 0:
        out.append(line(340, y + 268, 740, y + 268, BG_INK, 2, 0.18 * q))
        out.append(txt(540, y + 306, "не чат-бот · автономная система", 22, DIM, 0.85 * q, "middle", 2, 500, "Manrope"))
    return out


def fncall(t, dur, g1, g2, rms=None):
    """Окно терминала: JSON-вызов инструмента печатается построчно."""
    out = []
    x, y, w, h = 100, 350, 880, 470
    p = out_cubic(seg(t, 0.08, 0.4))
    if p <= 0:
        return out
    out.append(rect(x, y, w * min(1, p), h, 24, "#000000", "#FFFFFF", 2, 0.22))
    if p > 0.85:
        for k in range(3):
            out.append(circle(x + 36 + k * 26, y + 34, 6, BG_INK, op=0.3))
        out.append(txt(x + 130, y + 41, "tool_call", 19, DIM, 0.8, "start", 3, 500))
        out.append(line(x, y + 64, x + w, y + 64, BG_INK, 1, 0.18))
    lines = ['{', '  "tool": "browser.open",', '  "args": {"url": "..."},',
             '  "step": 1,', '  "status": "running"', '}']
    cx = x + 44
    for i, ln in enumerate(lines):
        t0 = 0.45 + i * 0.30
        if t < t0:
            break
        n = int(max(0, t - t0) * 46)
        shown = ln[:n]
        col = BG_INK
        if '"browser.open"' in ln:
            col = "url(#acc)"
        out.append(txt(cx, y + 112 + i * 50, shown, 26, col, 0.94, "start", 0, 500))
    q = out_expo(seg(t, 2.35, 0.5))
    if q > 0:
        bw = 330 * q
        out.append(rect(540 - bw / 2, y + h - 66, bw, 50, 25, "url(#acc)", op=0.92))
        out.append(txt(540, y + h - 33, "✓ инструмент вызван", 21, "#1B1035", 0.95 * q, "middle", 1, 700, "Manrope"))
    return out


def plan(t, dur, g1, g2, rms=None):
    """План агента: шаги отмечаются по одному."""
    out = []
    steps_ = ["прочитать задачу", "найти данные", "написать код", "запустить", "проверить"]
    for i, lab in enumerate(steps_):
        p = out_cubic(seg(t, 0.1 + i * 0.5, 0.3))
        if p <= 0:
            continue
        y = 360 + i * 92
        done = t > 0.55 + i * 0.5
        out.append(rect(100, y, 40, 40, 11, "none" if not done else f"url(#acc)", BG_INK, 2, 0.45 * p))
        if done:
            out.append(_check(120, y + 20, out_cubic(seg(t, 0.55 + i * 0.5, 0.3)), "#1B1035"))
        out.append(txt(166, y + 32, lab, 32, BG_INK, (0.95 if done else 0.5) * p, "start", 0, 600, "Manrope"))
        out.append(txt(940, y + 30, f"{i+1:02d}", 22, DIM, 0.5 * p, "end", 3, 500))
        out.append(line(100, y + 62, 980, y + 62, BG_INK, 1, 0.10 * p))
    return out


def tools(t, dur, g1, g2, rms=None):
    """Инструменты слева, контекст справа: связи держатся."""
    out = []
    items = ["БАЗА ДАННЫХ", "БРАУЗЕР", "КОД", "ФАЙЛЫ", "ТЕРМИНАЛ", "API"]
    for i, lab in enumerate(items):
        p = out_back(seg(t, 0.08 + i * 0.12, 0.4))
        if p <= 0:
            continue
        y = 360 + i * 74
        w = 380 * min(1, p)
        out.append(rect(100, y, w, 58, 16, "none", BG_INK, 2, 0.45))
        out.append(circle(132, y + 29, 7, f"url(#acc)", op=0.9 * min(1, p)))
        out.append(txt(154, y + 37, lab, 20, BG_INK, 0.9 * min(1, p), "start", 2, 600))
        q = out_expo(seg(t, 0.7 + i * 0.12, 0.5))
        if q > 0:
            x2 = 600 + (752 - 600) * q
            out.append(line(480, y + 29, x2, y + 29, "#FF8A3D", 2, 0.35 * q))
    pc = out_back(seg(t, 1.0, 0.5))
    if pc > 0:
        hh = 428 * min(1, pc)          # высота блока = высота колонки чипов (360..788)
        out.append(rect(760, 360, 220, hh, 24, "none", BG_INK, 2, 0.5))
        fade = clamp((pc - 0.15) / 0.6)
        out.append(txt(870, 400, "КОНТЕКСТ", 19, DIM, 0.85 * fade, "middle", 3, 600))
        for k in range(6):          # шесть полос — по числу инструментов слева
            out.append(rect(786, 436 + k * 40, (168 - k * 14) * fade, 12, 6, "url(#acc)", op=0.55))
        out.append(line(786, 668, 954, 668, BG_INK, 1, 0.15 * fade))
        out.append(txt(870, 704, "не теряется", 18, DIM, 0.7 * fade, "middle", 2, 500, "Manrope"))
    return out


def delegate(t, dur, g1, g2, rms=None):
    """Кнопка «запустить агента» и курсор, который её нажимает."""
    out = []
    p = out_back(seg(t, 0.1, 0.5))
    if p <= 0:
        return out
    bw, bh = 620 * min(1, p), 132
    bx, by = 540 - bw / 2, 500
    pressed = t > 1.55
    dy = 6 if 1.55 < t < 1.75 else 0
    out.append(rect(bx, by + dy, bw, bh, bh / 2, "url(#acc)", op=0.95))
    out.append(txt(540, by + dy + 82, "ЗАПУСТИТЬ АГЕНТА", 34, "#1B1035", 0.97 * min(1, p), "middle", 2, 800))
    # курсор
    q = out_cubic(seg(t, 0.55, 1.0))
    cxp = 300 + (700 - 300) * q
    cyp = 760 - (760 - (by + bh - 8)) * q
    out.append(f'<path d="M {cxp:.1f} {cyp:.1f} l 8 34 l 9 -13 l 15 2 z" fill="#FFFFFF" opacity="0.95" '
               f'stroke="#1B1035" stroke-width="2"/>')
    if pressed:
        r = 40 + 140 * clamp((t - 1.55) / 0.6)
        out.append(circle(cxp, cyp, r, "none", "#FFFFFF", 3, 0.5 * (1 - clamp((t - 1.55) / 0.6))))
    out.append(txt(540, by + bh + 92, "цель → план → шаги", 22, DIM, 0.75 * clamp((t - 0.6) / 0.5), "middle", 3, 500, "Manrope"))
    return out


KINDS = {
    "handoff": handoff, "manual": manual, "talk": talk, "hub": hub, "logo": logo,
    "fncall": fncall, "plan": plan, "tools": tools, "delegate": delegate,
    "timeline": timeline, "grid": grid, "waveform": waveform, "frames": frames,
    "subtitle": subtitle, "meter": meter, "encode": encode, "split": split,
    "flow": flow, "steps": steps, "prompt": prompt, "chat": chat,
    "stack": stack, "numbers": numbers, "none": none_,
}

# какие иллюстрации подходят сценам по имени
BY_SCENE = {
    # продуктовые эпизоды
    "hook": "timeline", "ui": "grid", "compare": "split", "prompt": "flow",
    "flow": "flow", "skills": "grid", "steps": "steps", "tools": "frames",
    "fix": "split", "file": "encode", "outro": "none",
    # исторические эпизоды
    "title": "timeline", "timeline": "timeline", "models": "steps", "money": "meter",
    "rlhf": "split", "chat": "flow", "growth": "meter", "gpt4": "encode", "end": "none",
    # «как монтируется ролик»
    "grid_": "grid", "voice": "waveform", "timing": "timeline", "subs": "subtitle",
    "frames": "frames",
    "sound": "meter", "render": "encode",
}


def kind_for(scene_name, explicit=None):
    if explicit and explicit in KINDS:
        return explicit
    return BY_SCENE.get(scene_name, "grid")


def draw(t, t_rel, dur, scene_name, g1, g2, rms=None, words=None, visual=None,
         sc_start=0.0, measure=None):
    kind = kind_for(scene_name, visual)
    fn = KINDS.get(kind, grid)
    if kind == "subtitle":
        rel = [{"w": w["w"], "s": w["s"] - sc_start, "e": w["e"] - sc_start}
               for w in (words or [])]
        return fn(t_rel, dur, g1, g2, rms, words=rel, measure=measure)
    return fn(t_rel, dur, g1, g2, rms)
