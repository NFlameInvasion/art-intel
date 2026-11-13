"""Озвучка сцен голосом edge-tts (ru-RU-DmitryNeural) через ru-vm.

С этого хоста Microsoft отдаёт 403, поэтому синтез идёт по ssh на ru-vm,
файлы возвращаются сюда.

Один запрос = одна сцена целиком, а не одно предложение. Microsoft отдаёт
пустой файл примерно в половине случаев, и на посценном дроблении ролик из
двадцати с лишним запросов вязнет в ретраях. Двенадцать запросов с тремя
проходами (каждый следующий — с длинной паузой) укладываются в минуты.

    python3 src/tts_edge_scene.py --episode episodes/harness --rate=+8%
"""
import argparse, json, os, subprocess, wave
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SSH_KEY = os.path.expanduser("~/.ssh/id_ru_vm_new")
SSH_HOST = "root@83.220.175.52"
REMOTE_BIN = "/tmp/ttsv/bin/edge-tts"
SR = 48000
LEAD, TAIL = 0.04, 0.20

SSH = ["ssh", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no", "-o", "BatchMode=yes", SSH_HOST]
SCP = ["scp", "-q", "-i", SSH_KEY, "-o", "StrictHostKeyChecking=no"]

REMOTE = r'''
import json, os, subprocess, time, sys
jobs = json.load(open("/tmp/edge_jobs.json"))
BIN = "__BIN__"

def speak(it, attempts, sleep_s):
    for _ in range(attempts):
        p = it["path"]
        if os.path.exists(p):
            os.remove(p)
        r = subprocess.run([BIN, "--voice", it["voice"], "--rate", it["rate"], "--pitch", it["pitch"],
                            "--text", it["text"], "--write-media", p],
                           capture_output=True, text=True)
        if r.returncode == 0 and os.path.exists(p) and os.path.getsize(p) > 3000:
            return True
        time.sleep(sleep_s)
    return False

left = jobs
for r in range(4):
    bad = []
    for it in left:
        if not speak(it, 5 if r == 0 else 3, 1.5 if r == 0 else 5.0):
            bad.append(it)
    print("pass %d left=%d" % (r, len(bad)), file=sys.stderr)
    left = bad
    if not left:
        break
for it in left:
    print("FAIL", it["path"], it["text"][:50], file=sys.stderr)
print("done fail=%d" % len(left), file=sys.stderr)
'''


def synth(ep, voice, rate, pitch):
    script = json.load(open(os.path.join(ep, "script.json"), encoding="utf-8"))
    out_dir = os.path.join(ep, "audio_dmitry")
    os.makedirs(out_dir, exist_ok=True)

    jobs, plan = [], []
    for i, sc in enumerate(script["scenes"]):
        remote = f"/tmp/ev3/{i:02d}_{sc['scene']}.mp3"
        jobs.append({"voice": voice, "text": sc["text"], "path": remote, "rate": rate, "pitch": pitch})
        plan.append((sc["audio"], remote))

    subprocess.run(SSH + ["mkdir -p /tmp/ev3"], check=True)
    with open("/tmp/edge_jobs.json", "w", encoding="utf-8") as f:
        json.dump(jobs, f, ensure_ascii=False)
    subprocess.run(SCP + ["/tmp/edge_jobs.json", f"{SSH_HOST}:/tmp/edge_jobs.json"], check=True)

    remote_py = REMOTE.replace("__BIN__", REMOTE_BIN)
    r = subprocess.run(SSH + [f"python3 - <<'PY'\n{remote_py}\nPY"], capture_output=True, text=True)
    print((r.stdout + r.stderr).strip()[-500:])
    if "done fail=0" not in r.stderr:
        raise SystemExit("не все сцены озвучены, смотри FAIL выше")

    total = 0.0
    for fn, remote in plan:
        local = os.path.join("/tmp", os.path.basename(remote))
        subprocess.run(SCP + [f"{SSH_HOST}:{remote}", local], check=True)
        raw = subprocess.check_output(["ffmpeg", "-v", "error", "-i", local,
                                       "-f", "f32le", "-ac", "1", "-ar", str(SR), "-"])
        y = polish(np.frombuffer(raw, dtype=np.float32).copy())
        save_wav(os.path.join(out_dir, fn), y)
        total += len(y) / SR
        print(f"{fn:16s} {len(y)/SR:5.2f}s")
    print(f"ИТОГО {total:.1f}s")


def polish(x, thresh=0.006, pad_ms=40):
    idx = np.where(np.abs(x) > thresh)[0]
    if len(idx) == 0:
        return np.zeros(int(0.05 * SR), dtype=np.float32)
    pad = int(pad_ms / 1000 * SR)
    x = x[max(0, idx[0] - pad): min(len(x), idx[-1] + pad)]
    y = np.concatenate([np.zeros(int(LEAD * SR), dtype=np.float32), x,
                        np.zeros(int(TAIL * SR), dtype=np.float32)])
    peak = float(np.max(np.abs(y))) or 1.0
    return (y / peak * 0.92).astype(np.float32)


def save_wav(path, x):
    with wave.open(path, "wb") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(SR)
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
