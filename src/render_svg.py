#!/usr/bin/env python3
"""Векторный рендер сцен (стиль B: градиент) для Art Intel.

Кадр = SVG, собранный из timeline.json (слова с абсолютными таймингами),
растеризуется rsvg-convert. Тайминги берутся из аудио, ничего не считается
на глаз.

    EPISODE_DIR=episodes/qwen-agent python3 src/render_svg.py
    # результат: <EP>/out/base_svg.mp4
"""
import json, math, os, subprocess, sys, time
from PIL import ImageFont
import illustrations

W, H = 1080, 1920
FPS_DEFAULT = 30

BG = "#1B1035"
INK = "#FFFFFF"
DIM = "#F1E6FF"
MUTED = "#B9A7D6"
FONT_T = "Unbounded"
FONT_B = "Manrope"
FONT_M = "JetBrains Mono"

GRADS = [
    ("#FF8A3D", "#FF4D8D"),
    ("#FF4D8D", "#7C4DFF"),
    ("#FFB86B", "#FF5C7A"),
]

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EP = os.environ.get("EPISODE_DIR") or ROOT
if not os.path.isabs(EP):
    EP = os.path.join(ROOT, EP)
OUT = os.path.join(EP, "out")
FRAMES = os.path.join(OUT, "frames_svg")
os.makedirs(FRAMES, exist_ok=True)

TL = json.load(open(os.path.join(EP, "timeline.json"), encoding="utf-8"))
try:
    _SCRIPT = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))
    VIS = {x["scene"]: x.get("visual") for x in _SCRIPT.get("scenes", [])}
except Exception:
    VIS = {}
AUDIO_DIR = os.environ.get("AUDIO_DIR") or os.path.join(EP, "audio")
if not os.path.isabs(AUDIO_DIR):
    AUDIO_DIR = os.path.join(ROOT, AUDIO_DIR)
RMS = {}
for _sc in TL["scenes"]:
    _p = os.path.join(AUDIO_DIR, _sc.get("audio", ""))
    if _sc.get("audio") and os.path.exists(_p):
        try:
            RMS[_sc["name"]] = illustrations.load_rms(_p)
        except Exception:
            pass
try:
    _META = json.load(open(os.path.join(EP, "script.json"), encoding="utf-8"))
except Exception:
    _META = {}
TITLE = (_META.get("title") or os.environ.get("EPISODE_TITLE", "")).upper()
HUD = (_META.get("hud") or "ART INTEL").upper()
CTA = (_META.get("cta") or "ПОДПИСАТЬСЯ").upper()
SCENES = TL["scenes"]
FPS = TL.get("fps", FPS_DEFAULT)
TOTAL = TL["total"]
N = int(round(TOTAL * FPS))


def _f(fam, weight="normal"):
    r = subprocess.run(["fc-match", "-f", "%{file}", f"{fam}:{weight}"],
                       capture_output=True, text=True)
    return r.stdout.strip().strip("\n")


P_BOLD = _f(FONT_T, "bold")
P_MED = _f(FONT_B, "medium")
_cache = {}


def pf(path, size, wght=None):
    k = (path, int(size), wght)
    if k not in _cache:
        f = ImageFont.truetype(path, int(size))
        if wght:
            try:                      # variable font: match the SVG font-weight
                f.set_variation_by_axes([wght])
            except Exception:
                pass
        _cache[k] = f
    return _cache[k]


W_TXT = 800          # font-weight used in the SVG; measurement must use the same axis


def tw(s, size, bold=True):
    return pf(P_BOLD if bold else P_MED, size, W_TXT if bold else None).getlength(s)


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


def esc(s):
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
             .replace('"', "&quot;"))


# ---------- text layout ----------
STOP = {"и", "в", "на", "с", "к", "по", "а", "но", "что", "не", "из", "за",
        "от", "до", "у", "о", "же", "ли", "как", "так", "для", "при"}


def wrap_words(words, size, maxw=880):
    """words: list of dicts with 'w'. Greedy wrap by measured width."""
    lines, cur, curw = [], [], 0.0
    sp = tw(" ", size)
    for w in words:
        ww = tw(w["w"], size)
        add = ww if not cur else sp + ww
        if cur and curw + add > maxw:
            lines.append([list(cur), curw])
            cur, curw = [w], ww
        else:
            cur.append(w)
            curw += add
    if cur:
        lines.append([list(cur), curw])

    # висячие предлоги: не оставлять служебное слово в конце строки
    for i in range(len(lines) - 1):
        ln, _ = lines[i]
        if len(ln) > 1 and ln[-1]["w"].lower().strip(".,!?—:;") in STOP:
            lines[i + 1][0].insert(0, ln.pop())
    # одиночное слово в последней строке — перекинуть одно сверху
    if len(lines) > 1 and len(lines[-1][0]) == 1 and len(lines[-2][0]) > 2:
        lines[-1][0].insert(0, lines[-2][0].pop())

    sp = tw(" ", size)
    out = []
    for ln, _ in lines:
        w_ = sum(tw(x["w"], size) for x in ln) + sp * (len(ln) - 1)
        out.append((ln, w_))
    return out


def layout(words, maxw=880, maxlines=5):
    for size in (108, 100, 92, 84, 76, 68, 60):
        lines = wrap_words(words, size, maxw)
        if len(lines) <= maxlines and all(l[1] <= maxw for l in lines):
            return size, lines
    return 60, wrap_words(words, 60, maxw)


# ---------- frame ----------
def scene_art(t, sc_i):
    sc = SCENES[sc_i]
    g1, g2 = GRADS[sc_i % len(GRADS)]
    words = sc.get("words") or []
    s_start = sc["start"]

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">']
    s.append("<defs>")
    s.append(f'<linearGradient id="acc" x1="0" y1="0" x2="1" y2="1">'
             f'<stop offset="0%" stop-color="{g1}"/><stop offset="100%" stop-color="{g2}"/></linearGradient>')
    s.append(f'<radialGradient id="blob1"><stop offset="0%" stop-color="{g1}" stop-opacity="0.55"/>'
             f'<stop offset="60%" stop-color="{g2}" stop-opacity="0.18"/>'
             f'<stop offset="100%" stop-color="{g2}" stop-opacity="0"/></radialGradient>')
    s.append(f'<radialGradient id="blob2"><stop offset="0%" stop-color="#7C4DFF" stop-opacity="0.5"/>'
             f'<stop offset="65%" stop-color="#4B2A8A" stop-opacity="0.16"/>'
             f'<stop offset="100%" stop-color="#4B2A8A" stop-opacity="0"/></radialGradient>')
    s.append('<radialGradient id="vig" cx="50%" cy="45%" r="72%">'
             '<stop offset="55%" stop-color="#000" stop-opacity="0"/>'
             '<stop offset="100%" stop-color="#000" stop-opacity="0.55"/></radialGradient>')
    s.append("</defs>")

    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="{BG}"/>')

    drift = math.sin(t * 0.35) * 40
    s.append(f'<ellipse cx="{260 + drift:.0f}" cy="{430 - drift*0.5:.0f}" rx="560" ry="470" fill="url(#blob1)"/>')
    s.append(f'<ellipse cx="{860 - drift:.0f}" cy="{1420 + drift*0.4:.0f}" rx="600" ry="520" fill="url(#blob2)"/>')

    # фон без счётчика кадров и номеров сцен
    s.append(f'<text x="72" y="112" font-family="{FONT_M}" font-size="26" font-weight="700" '
             f'fill="{MUTED}" letter-spacing="4">{esc(HUD)}</text>')

    # полоса сцены: заливка по времени внутри сцены
    sc_end = sc["end"]
    prog = clamp((t - s_start) / max(0.01, sc_end - s_start))
    s.append(f'<rect x="72" y="146" width="{W-144}" height="4" rx="2" fill="#FFFFFF" fill-opacity="0.12"/>')
    if prog > 0:
        s.append(f'<rect x="72" y="146" width="{(W-144)*prog:.1f}" height="4" rx="2" fill="url(#acc)" fill-opacity="0.95"/>')

    if not words:
        s.append("</svg>")
        return "".join(s)

    s.extend(illustrations.draw(t, t - s_start, sc_end - s_start, sc["name"],
                                g1, g2, rms=RMS.get(sc["name"]), words=words,
                                visual=VIS.get(sc["name"]), sc_start=s_start,
                                measure=lambda s_: tw(s_, 32, bold=False)))

    size, lines = layout(words)
    lh = size * 1.30
    block_h = lh * len(lines)
    top = 1152 - block_h / 2 + size * 0.82
    sp = tw(" ", size)

    for li, (line, lw) in enumerate(lines):
        x = 540 - lw / 2
        y = top + li * lh
        for w in line:
            e = out_cubic(seg(t, w["s"], 0.26))
            dy = 22 * (1 - e)
            on = 0.055 + 0.875 * e          # ещё не сказанное видно призраком
            active = w["s"] - 0.05 <= t <= w["e"] + 0.12
            fill = "url(#acc)" if active else INK
            s.append(f'<g opacity="{on:.3f}" transform="translate(0 {dy:.2f})">'
                     f'<text x="{x:.1f}" y="{y:.1f}" font-family="{FONT_T}" font-size="{size}" '
                     f'font-weight="800" fill="{fill}">{esc(w["w"])}</text></g>')
            x += tw(w["w"], size) + sp

    # финальная сцена: CTA
    if sc_i == len(SCENES) - 1:
        p = out_expo(seg(t, sc["end"] - 2.6, 0.7))
        if p > 0:
            bh = 108
            bmax = tw(CTA, 34) + 120
            bw = max(460, bmax) * (0.9 + 0.1 * p)
            bx, by = 540 - bw / 2, 1530
            s.append(f'<g opacity="{p:.3f}" transform="translate(540 {by + bh/2}) scale({0.96 + 0.04*p:.3f}) translate(-540 {-(by + bh/2)})">')
            s.append(f'<rect x="{bx:.1f}" y="{by}" width="{bw:.1f}" height="{bh}" rx="{bh/2}" fill="url(#acc)"/>')
            s.append(f'<text x="540" y="{by + 68}" font-family="{FONT_T}" font-size="34" font-weight="800" '
                     f'fill="#1B1035" text-anchor="middle" letter-spacing="1">{esc(CTA)}</text>')
            s.append("</g>")

    if TITLE:
        s.append(f'<text x="72" y="{H-64}" font-family="{FONT_M}" font-size="24" font-weight="500" '
                 f'fill="{MUTED}" fill-opacity="0.7" letter-spacing="3">{TITLE}</text>')
    s.append(f'<rect x="0" y="0" width="{W}" height="{H}" fill="url(#vig)"/>')
    s.append(f'<rect x="0" y="{H-8}" width="{W*t/TOTAL:.1f}" height="8" fill="url(#acc)" fill-opacity="0.85"/>')
    s.append("</svg>")
    return "".join(s)


def scene_at(t):
    for i, sc in enumerate(SCENES):
        if sc["start"] <= t < sc["end"]:
            return i
    return len(SCENES) - 1


def main():
    rng = os.environ.get("RANGE")
    if rng:
        a, b = (int(x) for x in rng.split("-"))
        os.environ["ONLY_FRAMES"] = ",".join(str(i) for i in range(a, b + 1))
    only = os.environ.get("ONLY_FRAMES")
    want = {int(x) for x in only.split(",")} if only else None
    t0 = time.time()
    for i in range(N):
        if want is not None and i not in want:
            continue
        t = i / FPS
        svg = scene_art(t, scene_at(t))
        sp = os.path.join(OUT, "frame.svg")
        open(sp, "w", encoding="utf-8").write(svg)
        subprocess.run(["rsvg-convert", "-w", str(W), "-h", str(H),
                        "-o", os.path.join(FRAMES, f"{i:05d}.png"), sp], check=True)
        if i % 120 == 0:
            el = time.time() - t0
            print(f"{i}/{N} {el:.0f}s  {el/max(1,i+1)*1000:.0f} ms/frame", flush=True)
    print("frames done", round(time.time() - t0, 1), "s", flush=True)

    if want is not None:
        return
    mp4 = os.path.join(OUT, "base_svg.mp4")
    print("encode ->", mp4, flush=True)
    subprocess.run([
        "ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
        "-framerate", str(FPS), "-i", os.path.join(FRAMES, "%05d.png"),
        "-c:v", "libx264", "-preset", "medium", "-crf", "18",
        "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
        "-movflags", "+faststart", mp4,
    ], check=True)
    print("ok", mp4, os.path.getsize(mp4) // 1024, "KB")


if __name__ == "__main__":
    main()
