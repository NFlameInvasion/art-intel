"""Дозаписывает озвучку сцен по частям: Vosk упирается в лимит памяти
(~950 МБ) примерно на десятом предложении и его убивает cgroup.
Процесс идёт по сценам, пропускает уже готовые файлы и выходит после --max.

    python3 src/fill_missing.py --episode episodes/agent-video --max 6
"""
import argparse, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tts_vosk as T

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--episode", required=True)
    ap.add_argument("--speaker", type=int, default=3)
    ap.add_argument("--max", type=int, default=6)
    ap.add_argument("--out", default="audio_vosk")
    a = ap.parse_args()

    ep = a.episode if os.path.isabs(a.episode) else os.path.join(ROOT, a.episode)
    script = json.load(open(os.path.join(ep, "script.json"), encoding="utf-8"))
    out_dir = os.path.join(ep, a.out)
    os.makedirs(out_dir, exist_ok=True)

    todo = [s for s in script["scenes"] if not os.path.exists(os.path.join(out_dir, s["audio"]))]
    if not todo:
        print("всё готово")
        return
    todo = todo[: a.max]

    from vosk_tts import Model, Synth
    model = Model(model_name="vosk-model-tts-ru-0.9-multi")
    synth = Synth(model)
    print("модель загружена", flush=True)

    for sc in todo:
        tmp = f"/tmp/v_{sc['scene']}.wav"
        synth.synth(T.clean(sc["text"]), tmp, speaker_id=a.speaker)
        y = T.polish(T.read_wav(tmp))
        T.save_wav(os.path.join(out_dir, sc["audio"]), y)
        print(f"{sc['audio']} {len(y)/T.SR:.1f}s", flush=True)


if __name__ == "__main__":
    main()
