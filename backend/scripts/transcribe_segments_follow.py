#!/usr/bin/env python
"""Transcribe a growing directory of seg_NNNN.wav files as they close.

Companion to capture_live_audio.py, kept SEPARATE on purpose: the recorder and
the transcriber have different dependency needs, and coupling them means a
missing dependency in one kills the other. On 16 September 2026 the in-process
transcription thread died on a faster_whisper import while ffmpeg kept running
happily -- the audio survived only because the two were independent processes
in practice. This script makes that separation explicit, so a transcription
crash can never cost you the recording.

Run it with the interpreter that actually HAS faster_whisper. On this machine
that is /opt/anaconda3/bin/python3.12, NOT the python.org 3.12 that a
PATH-restoring `export PATH=/usr/bin:...` selects.

    /opt/anaconda3/bin/python3.12 scripts/transcribe_segments_follow.py \
        --dir /tmp/soteu-2026 --language en --model small --segment-seconds 300

A segment is only transcribed once a LATER segment exists, because ffmpeg is
still writing the newest file. Pass --finish to drain the last one after the
recorder has stopped.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import re
import sys
import time


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--language", default="en")
    ap.add_argument("--model", default="small")
    ap.add_argument("--segment-seconds", type=int, default=300)
    ap.add_argument("--finish", action="store_true",
                    help="also transcribe the final, newest segment and exit")
    ap.add_argument("--poll", type=float, default=5.0)
    a = ap.parse_args()

    d = pathlib.Path(a.dir)
    transcript = d / "transcript.txt"
    done_marker = d / ".transcribed"
    done = set()
    if done_marker.exists():
        done = set(done_marker.read_text().split())

    from faster_whisper import WhisperModel
    print(f"[whisper] loading '{a.model}' (CPU, int8) ...", flush=True)
    model = WhisperModel(a.model, device="cpu", compute_type="int8")
    print("[whisper] ready", flush=True)

    while True:
        wavs = sorted(d.glob("seg_*.wav"))
        # Everything except the newest is closed; --finish includes the newest.
        closed = wavs if a.finish else wavs[:-1]
        todo = [w for w in closed if w.name not in done and w.stat().st_size > 1000]
        for w in todo:
            t0 = time.time()
            m = re.search(r"_(\d+)\.wav$", w.name)
            base = (int(m.group(1)) if m else 0) * a.segment_seconds
            segs, _info = model.transcribe(
                str(w), language=a.language, vad_filter=True,
                beam_size=1, condition_on_previous_text=False,
            )
            lines = []
            for s in segs:
                stamp = str(_dt.timedelta(seconds=int(base + s.start)))
                txt = s.text.strip()
                if txt:
                    lines.append(f"[{stamp}] {txt}")
            with transcript.open("a", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + ("\n" if lines else ""))
            done.add(w.name)
            done_marker.write_text(" ".join(sorted(done)))
            print(f"[whisper] {w.name}: {len(lines)} lines in {time.time()-t0:.0f}s", flush=True)
        if a.finish and not todo:
            break
        time.sleep(a.poll)
    print(f"[OK] {transcript}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
