"""Графические примитивы: кэш шрифтов/спрайтов, свечения, карточки, easing."""
import os, math
from PIL import Image, ImageDraw, ImageFont, ImageFilter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень проекта (файлы лежат в src/)
FONTS = os.path.join(ROOT, "assets", "fonts")
W, H = 1080, 1920

BG_TOP = (7, 11, 20)
BG_BOT = (13, 20, 36)
CYAN = (77, 225, 255)
LIME = (182, 255, 61)
RED = (255, 92, 108)
TEXT = (238, 244, 255)
MUTED = (139, 158, 191)
CARD = (18, 26, 45)
CARD_HI = (24, 34, 58)
BORDER = (38, 52, 84)

_fcache, _scache = {}, {}


def font(kind, size):
    key = (kind, size)
    if key not in _fcache:
        files = {"disp": "Unbounded-800.ttf", "disp6": "Unbounded-600.ttf",
                 "b": "Manrope-800.ttf", "sb": "Manrope-600.ttf", "r": "Manrope-400.ttf",
                 "mono": "JBMono-400.ttf", "monob": "JBMono-700.ttf"}
        _fcache[key] = ImageFont.truetype(os.path.join(FONTS, files[kind]), size)
    return _fcache[key]


def measure(text, kind, size):
    f = font(kind, size)
    return f.getlength(text)


def fit_size(text, kind, max_w, start):
    s = start
    while s > 12 and measure(text, kind, s) > max_w:
        s -= 2
    return s


# ---------- easing ----------
def clamp(x, a=0.0, b=1.0):
    return a if x < a else (b if x > b else x)


def out_cubic(x):
    x = clamp(x)
    return 1 - (1 - x) ** 3


def out_back(x, s=1.7):
    x = clamp(x)
    return 1 + (s + 1) * (x - 1) ** 3 + s * (x - 1) ** 2


def out_expo(x):
    x = clamp(x)
    return 1 if x >= 1 else 1 - 2 ** (-10 * x)


def pulse(t, period=1.6, lo=0.55, hi=1.0):
    return lo + (hi - lo) * (0.5 + 0.5 * math.sin(2 * math.pi * t / period))


def appear(t, t0, dur=0.35):
    """0→1 после момента t0."""
    return out_cubic((t - t0) / dur) if t > t0 else 0.0


# ---------- sprites ----------
def text_sprite(text, kind, size, fill=TEXT, glow=None, glow_r=18, glow_a=150, stroke=0, stroke_fill=None):
    key = ("t", text, kind, size, fill, glow, glow_r, glow_a, stroke, stroke_fill)
    if key in _scache:
        return _scache[key]
    f = font(kind, size)
    pad = (glow_r * 2 + 8) if glow else 8
    bbox = f.getbbox(text, stroke_width=stroke)
    tw = int(bbox[2] - bbox[0]) + 2
    th = int(bbox[3] - bbox[1]) + 2
    img = Image.new("RGBA", (tw + pad * 2, th + pad * 2), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ox, oy = pad - bbox[0], pad - bbox[1]
    if glow:
        gl = Image.new("RGBA", img.size, (0, 0, 0, 0))
        ImageDraw.Draw(gl).text((ox, oy), text, font=f, fill=glow + (glow_a,), stroke_width=stroke + 2)
        gl = gl.filter(ImageFilter.GaussianBlur(glow_r))
        img = Image.alpha_composite(img, gl)
        d = ImageDraw.Draw(img)
    d.text((ox, oy), text, font=f, fill=fill + (255,),
           stroke_width=stroke, stroke_fill=(stroke_fill or fill) + (255,))
    img._off = (pad, pad)
    _scache[key] = img
    return img


def grad_text_sprite(text, kind, size, c1=CYAN, c2=LIME, glow=True):
    key = ("gt", text, kind, size, c1, c2, glow)
    if key in _scache:
        return _scache[key]
    f = font(kind, size)
    bbox = f.getbbox(text)
    pad = 40
    tw, th = int(bbox[2] - bbox[0]) + 2, int(bbox[3] - bbox[1]) + 2
    mask = Image.new("L", (tw + pad * 2, th + pad * 2), 0)
    ImageDraw.Draw(mask).text((pad - bbox[0], pad - bbox[1]), text, font=f, fill=255)
    grad = Image.new("RGBA", mask.size)
    gd = ImageDraw.Draw(grad)
    for x in range(mask.size[0]):
        k = x / max(1, mask.size[0] - 1)
        gd.line([(x, 0), (x, mask.size[1])],
                fill=tuple(int(c1[i] + (c2[i] - c1[i]) * k) for i in range(3)) + (255,))
    grad.putalpha(mask)
    if glow:
        gl = Image.new("RGBA", mask.size, (0, 0, 0, 0))
        gl.putalpha(mask.point(lambda v: int(v * 0.65)))
        solid = Image.new("RGBA", mask.size, CYAN + (0,))
        solid.putalpha(mask.point(lambda v: int(v * 0.6)))
        gl = Image.alpha_composite(gl, solid).filter(ImageFilter.GaussianBlur(26))
        grad = Image.alpha_composite(gl, grad)
    grad._off = (pad, pad)
    _scache[key] = grad
    return grad


def rounded(w, h, r=28, fill=CARD, border=BORDER, bw=2, alpha=255):
    key = ("r", w, h, r, fill, border, bw, alpha)
    if key in _scache:
        return _scache[key]
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle([0, 0, w - 1, h - 1], r, fill=fill + (alpha,))
    if border and bw:
        d.rounded_rectangle([0, 0, w - 1, h - 1], r, outline=border + (255,), width=bw)
    _scache[key] = img
    return img


def glow_dot(r, color, blur=14):
    key = ("gd", r, color, blur)
    if key in _scache:
        return _scache[key]
    s = r * 2 + blur * 4
    img = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([s / 2 - r, s / 2 - r, s / 2 + r, s / 2 + r], fill=color + (255,))
    halo = img.filter(ImageFilter.GaussianBlur(blur))
    img = Image.alpha_composite(halo, img)
    _scache[key] = img
    return img


def blit(base, spr, x, y, alpha=1.0, scale=1.0, anchor="lt"):
    """anchor: lt / mm / mt / rt / lm / rm — куда ставим точку (x,y)."""
    if alpha <= 0.01:
        return
    if scale != 1.0:
        nw, nh = max(1, int(spr.width * scale)), max(1, int(spr.height * scale))
        spr = spr.resize((nw, nh), Image.BILINEAR)
    if alpha < 0.995:
        spr = spr.copy()
        spr.putalpha(spr.getchannel("A").point(lambda v: int(v * alpha)))
    ax, ay = anchor[0], anchor[1]
    px = x - (spr.width // 2 if ax == "m" else (spr.width if ax == "r" else 0))
    py = y - (spr.height // 2 if ay == "m" else (spr.height if ay == "b" else 0))
    base.paste(spr, (int(px), int(py)), spr)


def blit_text(base, text, kind, size, x, y, fill=TEXT, alpha=1.0, scale=1.0,
              anchor="lt", glow=None, glow_r=18, glow_a=150):
    spr = text_sprite(text, kind, size, fill, glow, glow_r, glow_a)
    ox, oy = spr._off
    if anchor[0] == "m":
        x -= (spr.width // 2 - ox)
    elif anchor[0] == "r":
        x -= (spr.width - ox)
    else:
        x -= ox
    if anchor[1] == "m":
        y -= (spr.height // 2 - oy)
    elif anchor[1] == "b":
        y -= (spr.height - oy)
    else:
        y -= oy
    blit(base, spr, x, y, alpha, scale, "lt")


def wrap(text, kind, size, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if measure(test, kind, size) <= max_w or not cur:
            cur = test
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def typewriter(text, t, t0, cps=34):
    n = int(max(0, (t - t0)) * cps)
    return text[:n], n >= len(text)


# ---------- фон ----------
def make_bg():
    import numpy as np
    y = np.linspace(0, 1, H)[:, None]
    x = np.linspace(0, 1, W)[None, :]
    arr = np.zeros((H, W, 3), dtype=np.float32)
    for i in range(3):
        arr[:, :, i] = BG_TOP[i] + (BG_BOT[i] - BG_TOP[i]) * y
    # мягкое радиальное свечение сверху-справа
    dx, dy = (x - 0.78) * 1.0, (y - 0.16) * 1.9
    r = np.sqrt(dx ** 2 + dy ** 2)
    halo = np.clip(1 - r / 0.85, 0, 1) ** 2 * 26
    arr[:, :, 0] += halo * 0.20
    arr[:, :, 1] += halo * 0.75
    arr[:, :, 2] += halo * 1.00
    # сетка точек
    gy, gx = np.mgrid[0:H, 0:W]
    dots = ((gx % 60 == 0) & (gy % 60 == 0)).astype(np.float32) * 9
    arr += dots[:, :, None] * np.array([0.5, 0.8, 1.0])[None, None, :]
    # виньетка
    vx, vy = (x - 0.5) * 2, (y - 0.5) * 2
    vig = np.clip(1 - 0.30 * (vx ** 2 + vy ** 2) / 2, 0.55, 1)
    arr *= vig[:, :, None]
    # зерно
    rng = np.random.default_rng(7)
    arr += rng.normal(0, 2.2, (H, W, 1))
    return Image.fromarray(np.clip(arr, 0, 255).astype("uint8"), "RGB")


def make_halo(size=760, color=CYAN, strength=52):
    import numpy as np
    yy, xx = np.mgrid[0:size, 0:size]
    c = size / 2
    r = np.sqrt((xx - c) ** 2 + (yy - c) ** 2) / c
    a = np.clip(1 - r, 0, 1) ** 2.4 * strength
    img = Image.new("RGBA", (size, size), color + (0,))
    img.putalpha(Image.fromarray(a.astype("uint8"), "L"))
    return img
