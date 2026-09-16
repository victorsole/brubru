#!/usr/bin/env python3.12
"""Record live system audio from BlackHole into complete, timestamped segments.

Built 16 September 2026 for the State of the European Union debate; reused for
any live stream played on this machine (plenary, committee webstream, webinar,
Council press conference).

RECORDING ONLY. Transcribe with the separate follower:

    /opt/anaconda3/bin/python3.12 scripts/transcribe_segments_follow.py \
        --dir <out-dir> --language en --model small --segment-seconds 300

They are separate processes on purpose. On 16 September the transcription ran
as a thread inside this script, died on a missing import, and the recording
survived only because ffmpeg happened to be a subprocess. A crash in the
repeatable half (transcription) must never cost the irreplaceable half (the
live recording).

HOW AUDIO IS CAPTURED, AND WHY NOT FFMPEG'S AVFOUNDATION INPUT

ffmpeg's `-f avfoundation` audio input silently dropped about 12% of the audio:
segments closing every 300 wall-clock seconds held only 257 to 265 seconds of
sound, with no warning logged. Queue size, native sample rate and freeing the
CPU made no difference. This script therefore records through `bhrec`
(tools/audio/bhrec.c), a CoreAudio AudioQueue recorder, and uses ffmpeg only to
resample and cut segments:

    bhrec "BlackHole 2ch" 48000  |  ffmpeg -f f32le -ar 48000 -ac 2 -i - ... segment

The binary is compiled on first use (clang, no Swift toolchain needed).

ROUTING (macOS cannot record its own output without a loopback device)

    tools/audio/mkmulti "MacBook Pro Speakers"   # hear it AND capture it
    tools/audio/setout  "BlackHole 2ch"          # capture silently

Muting the video player mutes the capture too. Leave the player unmuted and
send the output to BlackHole instead.

USAGE

    python3.12 scripts/capture_live_audio.py --check
    python3.12 scripts/capture_live_audio.py --out-dir /tmp/spaak-2026-09-16 \
        --title "Spaak webinar" --segment-seconds 300

Each finished segment's audio length is compared with its segment length and a
shortfall is printed as a dropout warning, so an incomplete recording is
reported while it happens instead of discovered afterwards.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import pathlib
import re
import shutil
import signal
import subprocess
import sys
import time
from typing import Optional

_BACKEND = pathlib.Path(__file__).resolve().parents[1]
AUDIO_TOOLS = _BACKEND / "tools" / "audio"
CACHE = pathlib.Path.home() / ".cache" / "brubru" / "audio"
DEVICE = "BlackHole 2ch"
RATE = 48000
SILENCE_DBFS = -60.0
DROPOUT_TOLERANCE_S = 3.0


def _ffmpeg() -> str:
    exe = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not pathlib.Path(exe).exists():
        sys.exit("[ERROR] ffmpeg not found. brew install ffmpeg")
    return exe


def _ffprobe() -> str:
    exe = shutil.which("ffprobe") or "/opt/homebrew/bin/ffprobe"
    return exe


def build_tool(name: str) -> pathlib.Path:
    """Compile tools/audio/<name>.c into the cache when missing or older than its source."""
    src = AUDIO_TOOLS / f"{name}.c"
    out = CACHE / name
    if not src.exists():
        sys.exit(f"[ERROR] missing source {src}")
    if out.exists() and out.stat().st_mtime >= src.stat().st_mtime:
        return out
    CACHE.mkdir(parents=True, exist_ok=True)
    cmd = ["clang", "-O2", "-o", str(out), str(src),
           "-framework", "AudioToolbox", "-framework", "CoreAudio", "-framework", "CoreFoundation"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        sys.exit(f"[ERROR] could not build {name}:\n{proc.stderr}")
    print(f"[OK] built {out}")
    return out


def probe_peak(seconds: float = 4.0) -> Optional[float]:
    """Record a short probe through bhrec and return its peak level in dBFS."""
    bhrec = build_tool("bhrec")
    rec = subprocess.Popen([str(bhrec), DEVICE, str(RATE)], stdout=subprocess.PIPE,
                           stderr=subprocess.DEVNULL)
    ff = subprocess.Popen(
        [_ffmpeg(), "-hide_banner", "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "-",
         "-t", str(seconds), "-af", "volumedetect", "-f", "null", "-"],
        stdin=rec.stdout, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
    )
    # Close the parent's copy of the pipe. Otherwise, once ffmpeg has its N seconds and
    # exits, bhrec keeps writing into a pipe nobody reads, blocks inside its audio
    # callback when the buffer fills, and never sees the stop signal (16 Sep 2026).
    rec.stdout.close()
    _, err = ff.communicate(timeout=seconds + 30)
    rec.terminate()
    try:
        rec.wait(timeout=5)
    except subprocess.TimeoutExpired:
        rec.kill()
        rec.wait()
    m = re.search(r"max_volume:\s*(-?[\d.]+) dB", err)
    return float(m.group(1)) if m else None


def cmd_check() -> int:
    print("[1/3] ffmpeg       :", _ffmpeg())
    print("[2/3] bhrec        :", build_tool("bhrec"))
    print(f"[3/3] probing 4s of '{DEVICE}' ...")
    peak = probe_peak()
    if peak is None:
        print("[ERROR] no level read. Is the device present? (brew install blackhole-2ch, then reboot)")
        return 2
    print(f"      peak level: {peak:.1f} dBFS")
    if peak <= SILENCE_DBFS:
        print("[FAIL] BlackHole is SILENT: system output is not reaching it, or the player is muted.\n"
              f"       Route it: {AUDIO_TOOLS}/mkmulti.c (hear + capture) or setout.c (capture silently).\n"
              "       Silence now means a silent recording later, so this is a hard stop.")
        return 1
    print("[OK] audio is reaching BlackHole. Safe to start the capture.")
    return 0


def _segment_seconds(path: pathlib.Path) -> Optional[float]:
    proc = subprocess.run([_ffprobe(), "-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", str(path)], capture_output=True, text=True)
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def cmd_capture(args: argparse.Namespace) -> int:
    out_dir = pathlib.Path(args.out_dir).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)

    peak = probe_peak(3.0)
    if (peak is None or peak <= SILENCE_DBFS) and not args.force:
        print("[FAIL] BlackHole is silent: refusing to start (use --force to override). Run --check.")
        return 1

    transcript = out_dir / "transcript.txt"
    if not transcript.exists():
        transcript.write_text(
            f"# {args.title}\n"
            f"# captured {_dt.datetime.now().isoformat(timespec='seconds')} local, "
            f"language={args.language}, segment={args.segment_seconds}s\n\n",
            encoding="utf-8",
        )

    bhrec = build_tool("bhrec")
    rec = subprocess.Popen([str(bhrec), DEVICE, str(RATE)], stdout=subprocess.PIPE,
                           stderr=open(out_dir / "bhrec.log", "w"))
    ff = subprocess.Popen(
        [_ffmpeg(), "-hide_banner", "-loglevel", "warning",
         "-f", "f32le", "-ar", str(RATE), "-ac", "2", "-i", "-",
         "-ac", "1", "-ar", "16000",
         "-f", "segment", "-segment_time", str(args.segment_seconds), "-reset_timestamps", "1",
         str(out_dir / "seg_%04d.wav")],
        stdin=rec.stdout, stderr=open(out_dir / "ffmpeg.log", "w"),
    )
    rec.stdout.close()  # ffmpeg owns the pipe; bhrec sees SIGPIPE if ffmpeg exits

    print(f"[capture] recording '{DEVICE}' into {out_dir}")
    print("[capture] transcribe in a SEPARATE terminal with:")
    print(f"  /opt/anaconda3/bin/python3.12 scripts/transcribe_segments_follow.py --dir {out_dir} "
          f"--language {args.language} --model small --segment-seconds {args.segment_seconds}")
    print("[capture] Ctrl-C to stop.")

    stopping = {"flag": False}

    def _stop(signum, frame):  # noqa: ANN001
        stopping["flag"] = True

    signal.signal(signal.SIGINT, _stop)
    signal.signal(signal.SIGTERM, _stop)

    checked: set = set()
    try:
        while not stopping["flag"] and ff.poll() is None and rec.poll() is None:
            segs = sorted(out_dir.glob("seg_*.wav"))
            for s in segs[:-1]:  # the newest segment is still being written
                if s.name in checked:
                    continue
                checked.add(s.name)
                dur = _segment_seconds(s)
                if dur is None:
                    continue
                gap = args.segment_seconds - dur
                tag = "[WARN] dropout" if gap > DROPOUT_TOLERANCE_S else "[OK]"
                print(f"{tag} {s.name}: {dur:.1f}s of {args.segment_seconds}s", flush=True)
            time.sleep(5)
    finally:
        rec.send_signal(signal.SIGINT)
        try:
            rec.wait(timeout=10)
        except subprocess.TimeoutExpired:
            rec.kill()
        try:
            ff.wait(timeout=30)
        except subprocess.TimeoutExpired:
            ff.kill()
    if ff.returncode not in (0, 255, None) or rec.returncode not in (0, None, -2):
        print(f"[WARN] recorder exit codes: bhrec={rec.returncode} ffmpeg={ff.returncode}; see logs in {out_dir}")
    n = len(list(out_dir.glob("seg_*.wav")))
    print(f"[OK] stopped. {n} segment(s) in {out_dir}. Finish transcription with --finish on the follower.")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--check", action="store_true", help="verify tools and that audio is flowing, then exit")
    p.add_argument("--out-dir", default="/tmp/live-capture")
    p.add_argument("--title", default="Live capture")
    p.add_argument("--segment-seconds", type=int, default=300)
    p.add_argument("--language", default="en", help="the interpretation channel you selected")
    p.add_argument("--force", action="store_true", help="start even if BlackHole reads silent")
    a = p.parse_args()
    return cmd_check() if a.check else cmd_capture(a)


if __name__ == "__main__":
    sys.exit(main())
