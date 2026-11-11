"""Мультяшные иллюстрации для презентации: робот-агент, реплика, файл, стрелки.

Всё рисуется примитивами Pillow в том же неоновом стиле, что и остальные кадры:
никаких внешних картинок и стоковых иконок.
"""
import math
from PIL import Image, ImageDraw

CYAN = (77, 225, 255)
LIME = (182, 255, 61)
TEXT = (238, 244, 255)
MUTED = (139, 158, 191)
CARD = (18, 26, 45)
CARD_HI = (24, 34, 58)
BORDER = (38, 52, 84)


def glow(base, draw_fn, r=18, alpha=120):
    """Рисует фигуру на отдельном слое и подмешивает свечение."""
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw_fn(ImageDraw.Draw(layer))
    from PIL import ImageFilter
    halo = layer.filter(ImageFilter.GaussianBlur(r))
    if alpha < 255:
        halo.putalpha(halo.getchannel("A").point(lambda v: int(v * alpha / 255)))
    base.alpha_composite(halo)
    base.alpha_composite(layer)


def robot(img, cx, cy, s=1.0, t=0.0, accent=LIME, label=None):
    """Дружелюбный робот-исполнитель: голова, антенна, глаза, руки-манипуляторы."""
    d = ImageDraw.Draw(img)
    hw, hh = 210 * s, 176 * s          # голова
    bw, bh = 150 * s, 120 * s          # корпус
    x0, y0 = cx - hw / 2, cy - hh / 2 - 40 * s

    # антенна
    ax = cx
    ay = y0 - 54 * s
    d.line([(ax, y0), (ax, ay)], fill=CYAN, width=max(3, int(5 * s)))
    blink = 0.55 + 0.45 * math.sin(t * 4.2)
    r = 13 * s
    d.ellipse([ax - r, ay - r, ax + r, ay + r], fill=LIME)
    d.ellipse([ax - r * 1.9, ay - r * 1.9, ax + r * 1.9, ay + r * 1.9],
              outline=(182, 255, 61, int(90 * blink)), width=max(2, int(3 * s)))

    # корпус
    d.rounded_rectangle([cx - bw / 2, y0 + hh - 6 * s, cx + bw / 2, y0 + hh + bh],
                        radius=int(34 * s), fill=CARD_HI, outline=BORDER, width=max(2, int(3 * s)))
    # голова
    d.rounded_rectangle([x0, y0, x0 + hw, y0 + hh], radius=int(42 * s),
                        fill=CARD, outline=CYAN, width=max(3, int(4 * s)))

    # глаза: моргают, зрачки бегают
    look = math.sin(t * 1.7) * 6 * s
    ey = y0 + hh * 0.42
    for sign in (-1, 1):
        ex = cx + sign * hw * 0.22 + look
        rr = 25 * s
        d.ellipse([ex - rr, ey - rr, ex + rr, ey + rr], fill=(10, 18, 32), outline=CYAN,
                  width=max(2, int(3 * s)))
        pr = 10 * s
        d.ellipse([ex - pr + sign * 3 * s, ey - pr, ex + pr + sign * 3 * s, ey + pr], fill=LIME)

    # улыбка
    d.arc([cx - 46 * s, y0 + hh * 0.55, cx + 46 * s, y0 + hh * 0.92],
          start=18, end=162, fill=TEXT, width=max(2, int(4 * s)))

    # руки: печатают
    for sign in (-1, 1):
        px = cx + sign * (bw / 2 + 34 * s)
        py = y0 + hh + 44 * s
        bob = math.sin(t * 5.2 + (0 if sign < 0 else 1.2)) * 9 * s
        d.line([(cx + sign * bw / 2, py - 30 * s), (px, py + bob)],
               fill=CYAN, width=max(4, int(7 * s)))
        rr = 11 * s
        d.ellipse([px - rr, py + bob - rr, px + rr, py + bob + rr], fill=accent)

    if label:
        d.rounded_rectangle([cx - 96 * s, y0 + hh + bh + 22 * s, cx + 96 * s, y0 + hh + bh + 74 * s],
                            radius=int(26 * s), fill=(26, 44, 28), outline=(56, 84, 62),
                            width=max(2, int(3 * s)))


def bubble(img, cx, top, w, h, t, text=None, fill=CARD_HI, border=BORDER, dot_color=MUTED):
    """Реплика-облачко с «печатающими» точками."""
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([cx - w / 2, top, cx + w / 2, top + h], radius=int(h / 2),
                        fill=fill, outline=border, width=3)
    # хвостик
    d.polygon([(cx - 18, top + h - 4), (cx + 18, top + h - 4), (cx - 2, top + h + 26)], fill=fill)
    if text:
        from gfx import blit_text
        blit_text(img, text, "sb", 32, cx, top + h / 2, TEXT, 1, anchor="mm")
    else:
        phase = (t * 1.6) % 1.0
        for i in range(3):
            on = 0.35 + 0.65 * max(0.0, 1 - abs(phase - i * 0.22) * 3)
            rr = 9
            x = cx - 40 + i * 40
            col = tuple(int(MUTED[j] * on + dot_color[j] * (1 - on) * 0) for j in range(3))
            d.ellipse([x - rr, top + h / 2 - rr, x + rr, top + h / 2 + rr],
                      fill=tuple(int(v * on) for v in (200, 214, 240)))


def file_icon(img, cx, cy, s=1.0, t=0.0, ok=False):
    """Документ с загнутым углом и кнопкой play — «готовый файл»."""
    d = ImageDraw.Draw(img)
    w, h = 200 * s, 250 * s
    x0, y0 = cx - w / 2, cy - h / 2
    d.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=int(22 * s), fill=CARD_HI,
                        outline=CYAN, width=max(3, int(4 * s)))
    fold = 46 * s
    d.polygon([(x0 + w - fold, y0), (x0 + w, y0 + fold), (x0 + w - fold, y0 + fold)],
              fill=(30, 44, 70), outline=CYAN)
    # play
    px, py = cx, y0 + h * 0.45
    pr = 40 * s
    d.ellipse([px - pr, py - pr, px + pr, py + pr], outline=LIME, width=max(3, int(4 * s)))
    d.polygon([(px - 13 * s, py - 18 * s), (px - 13 * s, py + 18 * s), (px + 20 * s, py)],
              fill=LIME)
    # подпись-строки
    for i in range(2):
        yy = y0 + h * 0.76 + i * 26 * s
        d.rounded_rectangle([x0 + 26 * s, yy, x0 + w - 26 * s - i * 34 * s, yy + 12 * s],
                            radius=int(6 * s), fill=(46, 62, 96))
    if ok:
        k = 1.0 + 0.04 * math.sin(t * 3.4)
        rr = 46 * s * k
        cxx, cyy = x0 + w - 10 * s, y0 + 10 * s
        d.ellipse([cxx - rr, cyy - rr, cxx + rr, cyy + rr], fill=(26, 44, 28), outline=LIME,
                  width=max(3, int(4 * s)))
        d.line([(cxx - 20 * s, cyy), (cxx - 6 * s, cyy + 15 * s), (cxx + 20 * s, cyy - 14 * s)],
               fill=LIME, width=max(4, int(7 * s)))


def arrow(img, x, y0, y1, t, p=1.0, color=CYAN):
    """Вертикальная стрелка с бегущим пунктиром."""
    if p <= 0:
        return
    d = ImageDraw.Draw(img)
    y_end = y0 + (y1 - y0) * min(1.0, p)
    step = 22
    y = y0
    while y < y_end - 12:
        d.line([(x, y), (x, min(y + 11, y_end - 12))], fill=color, width=4)
        y += step
    d.polygon([(x - 13, y_end - 14), (x + 13, y_end - 14), (x, y_end + 6)], fill=color)


def chip(img, cx, y, text, size=28, kind="mono", fill=(24, 34, 58), border=BORDER,
         color=TEXT, pad=28, h=54):
    from gfx import measure, blit_text
    w = measure(text, kind, size) + pad * 2
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([cx - w / 2, y, cx + w / 2, y + h], radius=int(h / 2), fill=fill,
                        outline=border, width=2)
    blit_text(img, text, kind, size, cx, y + h / 2, color, 1, anchor="mm")
