"""Обложка эпизода «История ChatGPT» — без скриншота, только типографика и таймлайн."""
import os, sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "src"))
from gfx import (W, H, CYAN, LIME, TEXT, MUTED, CARD, CARD_HI, BORDER, font, measure,
                 fit_size, rounded, blit, blit_text, grad_text_sprite, make_bg, make_halo, glow_dot)

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EP = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(EP, "out")
M, CW, CX = 72, 936, 540


def cover():
    os.makedirs(OUT, exist_ok=True)
    img = make_bg()
    blit(img, make_halo(780, CYAN, 48), 700 - 390, 300 - 390, 0.9)
    blit(img, make_halo(560, LIME, 20), -180, 1280, 0.45)

    blit(img, rounded(360, 62, 31, CARD, BORDER, 2), M, 150)
    blit(img, glow_dot(7, LIME, 10), M + 30, 181, 1.0, anchor="mm")
    blit_text(img, "ART INTEL", "monob", 28, M + 52, 181, TEXT, 1, anchor="lm")
    blit_text(img, "короткие видео про ИИ", "mono", 26, W - M, 181, MUTED, 0.85, anchor="rm")

    size = fit_size("ИСТОРИЯ", "disp", CW, 150)
    blit_text(img, "ИСТОРИЯ", "disp", size, M, 300, TEXT, 1)
    size2 = fit_size("CHATGPT", "disp", CW, 176)
    spr = grad_text_sprite("CHATGPT", "disp", size2, CYAN, LIME)
    ox, oy = spr._off
    blit(img, spr, M - ox, 470 - oy, 1)

    sub = "как прототип собрал 100 млн за два месяца"
    blit_text(img, sub, "sb", fit_size(sub, "sb", CW, 38), M, 700, TEXT)
    blit_text(img, "2015 → 2018 → 2019 → 2020 → 2022", "mono", 30, M, 770, CYAN, 0.95)

    # три ключевые цифры
    stats = [("1 млн", "за 5 дней"), ("100 млн", "за 2 месяца"), ("$1 млрд", "от Microsoft")]
    for i, (big, small) in enumerate(stats):
        y = 900 + i * 200
        blit(img, rounded(CW, 160, 28, CARD_HI, BORDER, 2), M, y)
        blit_text(img, big, "disp", 64, M + 34, y + 52, LIME, 1)
        blit_text(img, small, "sb", 32, M + 34, y + 118, MUTED, 1)

    blit(img, rounded(560, 96, 48, LIME, None, 0), CX - 280, 1620)
    blit_text(img, "Смотри до конца", "b", 38, CX, 1668, (10, 18, 12), 1, anchor="mm")

    p = os.path.join(OUT, "cover_1080x1920.png")
    img.save(p)
    print("cover:", p)


if __name__ == "__main__":
    cover()
