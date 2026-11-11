"""Обложка 1080x1920 для ролика: заголовок, канал, кадр со скриншотом."""
import os, sys
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gfx import (W, H, CYAN, LIME, TEXT, MUTED, CARD, BORDER, font, measure, fit_size,
                 rounded, blit, blit_text, grad_text_sprite, make_bg, make_halo, glow_dot)

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "out")
M, CW, CX = 72, 936, 540


def cover(out_path=None, channel="ART INTEL", kicker="Qwen · режим агента"):
    img = make_bg()
    halo = make_halo(760, CYAN, 46)
    blit(img, halo, 700 - 380, 260 - 380, 0.85)
    blit(img, make_halo(560, LIME, 20), -180, 1300, 0.45)

    # шапка канала
    blit(img, rounded(360, 62, 31, CARD, BORDER, 2), M, 150)
    blit(img, glow_dot(7, LIME, 10), M + 30, 181, 1.0, anchor="mm")
    blit_text(img, channel, "monob", 28, M + 52, 181, TEXT, 1, anchor="lm")
    blit_text(img, kicker, "mono", 26, W - M, 181, MUTED, 0.9, anchor="rm")

    # заголовок
    y = 300
    for txt, t in [("РЕЖИМ", 0), ("АГЕНТА", 1)]:
        size = fit_size(txt, "disp", CW, 150)
        spr = grad_text_sprite(txt, "disp", size, CYAN, LIME)
        ox, oy = spr._off
        wpx = measure(txt, "disp", size)
        blit(img, spr, M - ox + (1 - 1.0) * 0, y - oy)
        y += 168

    blit_text(img, "ИИ сам сделал этот ролик", "sb", 44, M, 690, TEXT)
    blit_text(img, "сценарий · голос · кадры · монтаж", "mono", 28, M, 754, MUTED, 0.9)

    # кадр скриншота
    shot = Image.open(os.path.join(ROOT, "assets", "shots", "qwen_agent_01.jpg")).convert("RGB")
    sw = 860
    shot = shot.resize((sw, int(shot.height * sw / shot.width)), Image.LANCZOS)
    card = Image.new("RGBA", (sw + 4, shot.height + 4), (0, 0, 0, 0))
    mask = Image.new("L", shot.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, shot.width - 1, shot.height - 1], 28, fill=255)
    card.paste(shot, (2, 2), mask)
    ImageDraw.Draw(card).rounded_rectangle([1, 1, card.width - 2, card.height - 2], 28,
                                           outline=BORDER + (255,), width=2)
    blit(img, card, M, 830)

    d = ImageDraw.Draw(img)
    d.rounded_rectangle([M + 40, 890, M + 40 + 520, 890 + 76], 38, fill=(10, 16, 30, 235))
    blit_text(img, "0 съёмок · 0 монтажа", "sb", 34, M + 70, 928, TEXT, 1, anchor="lm")

    blit(img, rounded(470, 92, 46, LIME, None, 0), CX - 235, 1720)
    blit_text(img, "Смотри до конца", "b", 38, CX, 1766, (10, 18, 12), 1, anchor="mm")

    p = out_path or os.path.join(OUT, "cover_1080x1920.png")
    img.save(p)
    print("cover:", p)


if __name__ == "__main__":
    cover()
