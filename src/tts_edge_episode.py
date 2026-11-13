"""Озвучка сцен голосом edge-tts (Microsoft, ru-RU-DmitryNeural) через ru-vm.

С этого хоста Microsoft отдаёт 403, поэтому синтез идёт по ssh на ru-vm,
а файлы возвращаются сюда. Каждое предложение — отдельный запрос с ретраями:
edge-tts периодически отдаёт пустой файл / NoAudioReceived, без ретраев
половина сцен остаётся без звука.

    EPISODE_DIR=episodes/harness python3 src/tts_edge_episode.py --rate=+8%
"""
import argparse, json, os, re, subprocess, time, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_KEY = os.path.expanduser("~/.ssh/id_ru_vm_new")
SSH_HOST = "root@83.220.175.52"
REMOTE_BIN = "/tmp/ttsv/bin/edge-tts"
SR = 48000
LEAD, GAP, TAIL = 0.05, 0.22, 0.25
SENT = re.compile(r"(?<=[.!?…])\s+")

SSH = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", SSH_HOST]
SCP = ["scp", "-q", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no"]

REMOTE = r'''
import json, os, subprocess, time, sys
jobs = json.load(open("/tmp/edge_jobs.json"))
fail = 0
for it in jobs:
    ok = False
    for attempt in range(8):
        if os.path.exists(it["path"]):
            os.remove(it["path"])
        r = subprocess.run([BIN, "--voice", it["voice"], "--rate", it["rate"], "--pitch", it["pitch"],
                            "--text", it["text"], "--write-media", it["path"]],
                           capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(it["path"]) and os.path.getsize(it["path"]) > 2500:
            ok = True
            break
        time.sleep(2.2)
    if not ok:
        fail += 1
        print("FAIL", it["path"], it["text"][:40], file=sys.stderr)
    time.sleep(0.6)
print("done fail=%d" % fail, file=sys.stderr)
'''


def synth(ep, voice, rate, pitch):
    script = json.load(open(os.path.join(ep, "script.json"), encoding="utf-8"))
    out_dir = os.path.join(ep, "audio_dmitry")
    os.makedirs(out_dir, exist_ok=True)

    jobs, plan = [], []
    for sc in script["scenes"]:
        idxs = []
        for j, part in enumerate(p.strip() for p in SENT.split(sc["text"]) if p.strip()):
            remote = f"/tmp/ev/{sc['scene']}_{j}.mp3"
            jobs.append({"voice": voice, "text": part, "path": remote, "rate": rate, "pitch": pitch})
            idxs.append(remote)
        plan.append((sc["audio"], idxs))

    subprocess.run(SSH + ["mkdir -p /tmp/ev"], check=True)
    with open("/tmp/edge_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
    subprocess.run(SCP + ["/tmp/edge_jobs.json", f"{SSH_HOST}:/tmp/edge_jobs.json"], check=True)

    remote_py = REMOTE.replace("BIN", repr(REMOTE_BIN))
    env = os.environ.get("RATE_ARG")
    r = subprocess.run(SSH + [f"python3 - <<'PY'\n{remote_py}\nPY"], capture_output=True, text=True)
    print(r.stdout.strip()[-300:], r.stderr.strip()[-300:])
    if "fail=" not in r.stderr:
        raise SystemExit("remote synth failed")

    total = 0.0
    for fn, idxs in plan:
        chunks = []
        for remote in idxs:
            local = os.path.join("/tmp", os.path.basename(remote))
            subprocess.run(SCP + [f"{SSH_HOST}:{remote}", local], check=True)
            raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", local,
                                           "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
            chunks.append(trim_gate(np.frombuffer(raw, dtype=np.float32).copy()))
        y = join(chunks)
        save_wav(os.path.join(out_dir, fn), y)
        total += len(y) / SR
        print(f"{fn:16s} {len(y)/SR:5.2f}s")
    print(f"ИТОГО {total:.1f}s")


def trim_gate(x, thresh=0.006, pad_ms=60):
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
    ap.add_argument("--rate", default="+8%")
    ap.add_argument("--pitch", default="+0Hz")
    ap.add_argument("--episode", default=os.environ.get("EPISODE_DIR", "."))
    a = ap.parse_args()
    ep = a.episode if os.path.isabs(a.episode) else os.path.join(ROOT, a.episode)
    synth(ep, a.voice, a.rate, a.pitch)
