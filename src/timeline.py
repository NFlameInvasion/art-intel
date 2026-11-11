"""Строит таймлайн сцен и пословные тайминги из реальных аудиофайлов.
Паузы внутри речи берём из silencedetect, слова распределяем по слогам.
"""
import json, re, subprocess, glob, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # корень проекта (файлы лежат в src/)
AUD = os.environ.get("AUDIO_DIR") or os.path.join(ROOT, "audio")
if not os.path.isabs(AUD):
    AUD = os.path.join(ROOT, AUD)
FPS = 30
LEAD = 0.35          # тишина перед первой репликой
GAP = 0.35           # пауза между сценами
TAIL = 1.45          # держим финальный кадр

SCENES = [
    ("hook", "01_hook.wav", "Это видео сделал не человек. Его собрал агент."),
    ("ui", "02_ui.wav", "Это Кьюэн. У него появился новый режим — агент."),
    ("compare", "03_compare.wav", "Чат-бот отвечает текстом. Агент получает задачу и доводит её до результата."),
    ("prompt", "04_prompt.wav", "Одна задача: сделай ролик на русском — сценарий, голос, кадры, субтитры."),
    ("flow", "05_flow.wav", "Задача уходит агенту. Обратно приходит готовый файл."),
    ("skills", "06_skills.wav", "Скиллы он подключил сам: озвучка, графика, монтаж."),
    ("steps", "07_steps.wav", "Сам сделал раскадровку: восемь сцен, тайминг по словам."),
    ("tools", "08_tools.wav", "Сам собрал голос и отрисовал полторы тысячи кадров."),
    ("fix", "09_fix.wav", "Ошибка? Прочитал лог, поправил код, пересобрал."),
    ("file", "10_file.wav", "На выходе — готовый файл. Без съёмок и монтажа."),
    ("outro", "11_outro.wav", "Это не чат-бот. Это режим агента. Подписывайся на Арт Интел, если хочешь знать больше про нейросети."),
]

VOWELS = set("аеёиоуыэюяАЕЁИОУЫЭЮЯ")


def probe(path):
    out = subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                   "format=duration", "-of", "csv=p=0", path])
    return float(out.strip())


def silences(path):
    p = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path,
                        "-af", "silencedetect=n=-45dB:d=0.12", "-f", "null", "-"],
                       capture_output=True, text=True)
    starts = [float(m) for m in re.findall(r"silence_start: ([\d.]+)", p.stderr)]
    ends = [float(m) for m in re.findall(r"silence_end: ([\d.]+)", p.stderr)]
    iv, si = [], 0
    for s in starts:
        e = ends[si] if si < len(ends) else None
        si += 1
        iv.append((s, e))
    return iv


def speech_segments(path, dur):
    """Непрерывные куски речи = дополнение к интервалам тишины."""
    segs, cur = [], 0.0
    for s, e in silences(path):
        if s - cur > 0.09:
            segs.append((cur, s))
        cur = e if e is not None else dur
    if dur - cur > 0.09:
        segs.append((cur, dur))
    return segs or [(0.0, dur)]


def split_phrases(text, n):
    """Подгоняем число фраз под число речевых сегментов."""
    strong = [p.strip() for p in re.split(r"(?<=[.!?:])\s+", text) if p.strip()]
    if len(strong) == n:
        return strong
    fine = [p.strip() for p in re.split(r"(?<=[.!?:,])\s+|(?<=—)\s*", text) if p.strip()]
    fine = [p for p in fine if re.search(r"[а-яА-ЯёЁ]", p)]
    if len(fine) == n:
        return fine
    if len(strong) > n:                      # склеиваем лишнее
        out = strong[:n - 1] + [" ".join(strong[n - 1:])]
        return out
    return None                              # отдаём пропорциональное распределение


def weight(word):
    w = re.sub(r"[^а-яА-ЯёЁa-zA-Z]", "", word)
    syl = sum(1 for c in w if c in VOWELS) or 1
    return syl + 0.35


def words_with_timing(text, seg_start, seg_end):
    words = text.split()
    ws = [weight(w) for w in words]
    total = sum(ws)
    span = seg_end - seg_start
    t, out = seg_start, []
    for w, ww in zip(words, ws):
        d = span * ww / total
        out.append({"w": w, "s": round(t, 3), "e": round(t + d, 3)})
        t += d
    return out


def build():
    scenes, t = [], LEAD
    for name, fn, text in SCENES:
        path = os.path.join(AUD, fn)
        dur = probe(path)
        segs = speech_segments(path, dur)
        phrases = split_phrases(text, len(segs))
        words = []
        if phrases:
            for ph, (a, b) in zip(phrases, segs):
                words += words_with_timing(ph, t + a, t + b)
        else:
            words = words_with_timing(text, t + segs[0][0], t + segs[-1][1])
        scenes.append({
            "name": name, "audio": fn, "dur": round(dur, 3),
            "start": round(t - LEAD if not scenes else t - GAP, 3),
            "voice_start": round(t, 3), "voice_end": round(t + dur, 3),
            "text": text, "words": words,
        })
        t += dur + GAP
    total = t - GAP + TAIL
    for i, sc in enumerate(scenes):
        sc["end"] = scenes[i + 1]["start"] if i + 1 < len(scenes) else round(total, 3)
    return {"fps": FPS, "total": round(total, 3), "lead": LEAD, "gap": GAP, "scenes": scenes}


def caption_groups(scenes, max_words=3, max_chars=22):
    """Группы субтитров: 2-3 слова, разрыв на знаках препинания."""
    groups = []
    for sc in scenes:
        buf = []
        for i, w in enumerate(sc["words"]):
            buf.append(w)
            chars = sum(len(x["w"]) + 1 for x in buf)
            hard = bool(re.search(r"[.!?:]$", w["w"]))
            soft = bool(re.search(r"[,—]$", w["w"])) and len(buf) >= 2
            last = i == len(sc["words"]) - 1
            if hard or soft or last or len(buf) >= max_words or chars >= max_chars:
                groups.append({"s": buf[0]["s"], "e": buf[-1]["e"], "words": buf[:]})
                buf = []
        if buf:
            groups.append({"s": buf[0]["s"], "e": buf[-1]["e"], "words": buf[:]})
    # хвост группы держим до начала следующей (без дыр)
    for i in range(len(groups) - 1):
        groups[i]["e"] = max(groups[i]["e"], min(groups[i + 1]["s"] - 0.02, groups[i]["e"] + 0.35))
    return groups


def ts(t, comma=True):
    h = int(t // 3600); m = int(t % 3600 // 60); s = t % 60
    return f"{h:02d}:{m:02d}:{s:06.3f}".replace(".", "," if comma else ".")


def ass_ts(t):
    """ASS требует ровно 2 знака (санти­секунды): H:MM:SS.cc"""
    cs = int(round(t * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, c = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{c:02d}"


def write_srt(groups, path):
    with open(path, "w", encoding="utf-8") as f:
        for i, g in enumerate(groups, 1):
            txt = " ".join(w["w"] for w in g["words"])
            f.write(f"{i}\n{ts(g['s'])} --> {ts(g['e'])}\n{txt}\n\n")


def write_ass(groups, path):
    head = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,Liberation Sans,72,&H00FFFFFF,&H00FFFFFF,&H00101418,&H90000000,-1,0,0,0,100,100,0.6,0,1,5,3,2,90,90,430,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lime = "&H003DFFB6&"     # BGR: B6FF3D
    white = "&H00FFFFFF&"
    lines = []
    for g in groups:
        words = g["words"]
        for i, w in enumerate(words):
            a = w["s"] if i else g["s"]
            b = words[i + 1]["s"] if i + 1 < len(words) else g["e"]
            if b - a < 0.05:
                b = a + 0.05
            parts = []
            for j, x in enumerate(words):
                clean = x["w"].replace("{", "").replace("}", "")
                parts.append(("{\\c" + lime + "}" + clean + "{\\c" + white + "}") if j == i else clean)
            txt = " ".join(parts)
            if i == 0:
                txt = "{\\fad(70,0)\\fscx96\\fscy96\\t(0,130,\\fscx100\\fscy100)}" + txt
            lines.append(f"Dialogue: 0,{ass_ts(a)},{ass_ts(b)},Cap,,0,0,0,,{txt}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(head + "\n".join(lines) + "\n")


if __name__ == "__main__":
    tl = build()
    groups = caption_groups(tl["scenes"])
    tl["captions"] = groups
    with open(os.path.join(ROOT, "timeline.json"), "w", encoding="utf-8") as f:
        json.dump(tl, f, ensure_ascii=False, indent=1)
    write_srt(groups, os.path.join(ROOT, "out", "captions_ru.srt"))
    write_ass(groups, os.path.join(ROOT, "out", "captions_ru.ass"))
    print(f"TOTAL {tl['total']}s  frames={int(tl['total']*FPS)}")
    for sc in tl["scenes"]:
        print(f"  {sc['name']:7s} {sc['start']:6.2f} → {sc['end']:6.2f}  (voice {sc['voice_start']:.2f}-{sc['voice_end']:.2f}, {len(sc['words'])} слов)")
    print("caption groups:", len(groups))
    for g in groups[:6]:
        print("   ", round(g["s"], 2), round(g["e"], 2), " ".join(w["w"] for w in g["words"]))
