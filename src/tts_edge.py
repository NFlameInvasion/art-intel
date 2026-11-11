"""Озвучка через edge-tts (нейроголос Microsoft) — запускается на ru-vm по ssh.

Зачем через сервер: с этого хоста Microsoft отдаёт 403. На ru-vm голос работает.
Каждая фраза синтезируется отдельно, паузы вставляются локально — как в tts_silero.

python3 src/tts_edge.py --voice ru-RU-DmitryNeural --out audio_dmitry
"""
import argparse, json, os, re, subprocess, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_KEY = os.path.expanduser("~/.ssh/id_ru_vm_new")
SSH_HOST = "root@83.220.175.52"
SR = 48000
LEAD, GAP, TAIL = 0.15, 0.34, 0.28
SENT = re.compile(r"(?<=[.!?…])\s+")

SCENES = [
    ("01_hook.wav",   "Это видео сделал не человек. Его собрал агент."),
    ("02_ui.wav",     "Это Qwen. У него появился новый режим — агент."),
    ("03_compare.wav", "Чат-бот отвечает текстом. Агент получает задачу и доводит её до результата."),
    ("04_prompt.wav", "Одна задача: сделай ролик на русском — сценарий, голос, кадры, субтитры."),
    ("05_flow.wav",   "Задача уходит агенту. Обратно приходит готовый файл."),
    ("06_skills.wav", "Скиллы он подключил сам: озвучка, графика, монтаж."),
    ("07_steps.wav",  "Сам сделал раскадровку: восемь сцен, тайминг по словам."),
    ("08_tools.wav",  "Сам выбрал голос и отрисовал полторы тысячи кадров."),
    ("09_fix.wav",    "Ошибка? Прочитал лог, поправил код, пересобрал."),
    ("10_file.wav",   "На выходе — готовый файл. Без съёмок и монтажа."),
    ("11_outro.wav",  "Это не чат-бот. Это режим агента. Подписывайся на Art Intel — здесь про нейросети без воды."),
]

REMOTE = r'''
import json, subprocess, time, sys
data = json.load(open("/tmp/edge_jobs.json"))
for item in data:
    for attempt in range(4):
        r = subprocess.run(["/tmp/ttsv/bin/edge-tts", "--voice", item["voice"],
                            "--text", item["text"], "--write-media", item["path"]],
                           capture_output=True, text=True)
        if r.returncode == 0 and __import__("os").path.getsize(item["path"]) > 2000:
            break
        time.sleep(1.5)
    print(item["path"], r.returncode)
'''


def sh(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def synth(voice, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    jobs, plan = [], []
    for fn, text in SCENES:
        parts = [p.strip() for p in SENT.split(text) if p.strip()]
        idxs = []
        for j, p in enumerate(parts):
            remote = f"/tmp/ev/{fn[:-4]}_{j}.mp3"
            jobs.append({"voice": voice, "text": p, "path": remote})
            idxs.append(remote)
        plan.append((fn, idxs))

    sh(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", SSH_HOST, "mkdir -p /tmp/ev"])
    tmp = "/tmp/edge_jobs.json"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
    subprocess.run(["scp", "-q", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", tmp, f"{SSH_HOST}:/tmp/edge_jobs.json"], check=True)
    out = subprocess.run(["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", SSH_HOST,
                          "python3 - <<'PY'\n" + REMOTE + "\nPY"], capture_output=True, text=True)
    print(out.stdout[-800:])

    for fn, idxs in plan:
        chunks = []
        for remote in idxs:
            local = os.path.join("/tmp", os.path.basename(remote))
            subprocess.run(["scp", "-q", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no",
                            f"{SSH_HOST}:{remote}", local], check=True)
            raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", local,
                                           "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
            chunks.append(trim_gate(np.frombuffer(raw, dtype=np.float32).copy()))
        y = join(chunks)
        save_wav(os.path.join(out_dir, fn), y)
        print(f"{fn:16s} {len(y)/SR:5.2f}s")


def trim_gate(x, thresh=0.006, pad_ms=70):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    x = x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]
    win = int(0.018 * SR)
    n = len(x) // win
    if n:
        body = x[:n * win].reshape(n, win)
        rms = np.sqrt((body ** 2).mean(axis=1))
        gain = np.clip((rms - 0.0022) / 0.0044, 0, 1).astype(np.float32)
        gain = np.convolve(gain, np.ones(5) / 5, mode="same")
        x = np.concatenate([(body * gain[:, None]).reshape(-1), x[n * win:]])
    return x.astype(np.float32)


def join(chunks):
    out = [np.zeros(int(LEAD * SR), dtype=np.float32)]
    for i, c in enumerate(chunks):
        out.append(c)
        out.append(np.zeros(int((GAP if i < len(chunks) - 1 else TAIL) * SR), dtype=np.float32))
    y = np.concatenate(out)
    peak = float(np.max(np.abs(y))) or 1.0
    return y / peak * 0.92


def save_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((np.clip(x, -1, 1) * 32767).astype(np.int16).tobytes())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--voice", default="ru-RU-DmitryNeural")
    ap.add_argument("--out", default=os.path.join(ROOT, "audio_dmitry"))
    a = ap.parse_args()
    synth(a.voice, a.out)
