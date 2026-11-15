#!/usr/bin/env python3
"""Обрезка тишины по краям сцен edge-tts: сцена = wav без ведущей и хвостовой тишины."""
import glob, os, subprocess, sys

AUD = sys.argv[1] if len(sys.argv) > 1 else "episodes/hermes-agent/audio"
filt = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
        "areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.04,"
        "areverse")
total = 0.0
for src in sorted(glob.glob(os.path.join(AUD, "*.mp3"))):
    wav = src[:-4] + ".wav"
    tmp = wav + ".trim.wav"
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", src,
                    "-af", filt, "-ar", "48000", "-ac", "1", tmp], check=True)
    os.replace(tmp, wav)
    d = float(subprocess.check_output(["ffprobe", "-v", "error", "-show_entries",
                                       "format=duration", "-of", "csv=p=0", wav]))
    total += d
    print(os.path.basename(wav), round(d, 2))
print("sum", round(total, 2), "проект", round(total + 0.35 * 9 + 0.35 + 1.45, 2))
