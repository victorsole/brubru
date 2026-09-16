#!/usr/bin/env python
"""Attribute transcript lines to speakers using the EP 'Speakers list' PDF.

The EP publishes, for every plenary debate, a speaker list with each
intervention's ROLE, LENGTH and wall-clock START/END. That turns speaker
attribution from guesswork into arithmetic, provided one thing is known: the
wall-clock time at which the recording started. capture_live_audio.py writes
that into the transcript header, so the two line up.

    wall_clock(line) = capture_start + offset_in_transcript

TWO HONEST LIMITS, both surfaced rather than hidden:

1. The list's times are a SCHEDULE. Debates drift: speakers overrun, the
   President interjects, points of order appear. The further into the sitting,
   the more the planned time diverges from reality.
2. Attribution by clock alone cannot notice that it has drifted.

So this script also does a CONFIRMATION pass: for each speaker it looks for
their surname in the transcript near their slot (the President announces every
speaker by name, and the interpretation booth relays it). A hit both confirms
the slot and measures the drift; the offset is then carried forward to later
speakers. Anything that cannot be confirmed is marked `~` (inferred from the
schedule alone), never presented as certain.

    python scripts/align_speakers.py \
        --transcript /tmp/soteu-2026/transcript.txt \
        --speakers   data/soteu_2026/speakers_list.txt \
        --out        data/soteu_2026/attributed.md
"""
from __future__ import annotations

import argparse
import datetime as dt
import pathlib
import re
import sys
import unicodedata

ROW = re.compile(
    r"^(?P<name>.+?)\s{2,}(?P<role>[A-Za-zА-Яа-я/&\-\. ]+?)\s{2,}"
    r"(?P<len>\d{2}:\d{2}:\d{2})\s+(?P<start>\d{2}:\d{2}:\d{2})\s+(?P<end>\d{2}:\d{2}:\d{2})\s*$"
)
CATCH = re.compile(r"CATCH THE EYE\s+(?P<len>\d{2}:\d{2}:\d{2})\s+(?P<start>\d{2}:\d{2}:\d{2})\s+(?P<end>\d{2}:\d{2}:\d{2})")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def parse_speakers(path: pathlib.Path, day: dt.date) -> list[dict]:
    out: list[dict] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        m = CATCH.search(line)
        if m:
            name, role = "CATCH THE EYE", "-"
        else:
            m = ROW.match(line.strip())
            if not m:
                continue
            name, role = m.group("name").strip(), m.group("role").strip()
            if name.lower().startswith("speaker"):
                continue
        def t(v: str) -> dt.datetime:
            h, mi, s = (int(x) for x in v.split(":"))
            return dt.datetime.combine(day, dt.time(h, mi, s))
        out.append({"name": name, "role": role,
                    "start": t(m.group("start")), "end": t(m.group("end"))})
    return out


def surname(full: str) -> str:
    """The EP prints surnames in CAPITALS; that is the reliable search token."""
    caps = [w for w in full.split() if len(w) > 2 and w == w.upper() and w.isalpha()]
    return strip_accents(caps[-1]).lower() if caps else strip_accents(full.split()[-1]).lower()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--transcript", required=True)
    ap.add_argument("--speakers", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--confirm-window", type=int, default=90,
                    help="seconds around a slot start in which to look for the announced surname")
    a = ap.parse_args()

    tp = pathlib.Path(a.transcript)
    text = tp.read_text(encoding="utf-8")
    m = re.search(r"# captured (\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2}):(\d{2})", text)
    if not m:
        print("[ERROR] transcript header has no capture timestamp", file=sys.stderr)
        return 2
    day = dt.date.fromisoformat(m.group(1))
    start = dt.datetime.combine(day, dt.time(int(m.group(2)), int(m.group(3)), int(m.group(4))))

    lines: list[tuple[dt.datetime, str]] = []
    for ln in text.splitlines():
        mm = re.match(r"^\[(\d+):(\d{2}):(\d{2})\]\s*(.+)$", ln)
        if not mm:
            continue
        off = dt.timedelta(hours=int(mm.group(1)), minutes=int(mm.group(2)), seconds=int(mm.group(3)))
        lines.append((start + off, mm.group(4).strip()))

    speakers = parse_speakers(pathlib.Path(a.speakers), day)
    if not speakers or not lines:
        print(f"[ERROR] speakers={len(speakers)} lines={len(lines)}", file=sys.stderr)
        return 2

    covered = [s for s in speakers if s["end"] >= lines[0][0] and s["start"] <= lines[-1][0]]

    # --- confirmation pass: find the announced surname near each slot start ---
    drift = dt.timedelta(0)
    for s in covered:
        if s["name"] == "CATCH THE EYE":
            s["confirmed"] = False
            continue
        sn = surname(s["name"])
        target = s["start"] + drift
        best = None
        for when, txt in lines:
            if abs((when - target).total_seconds()) <= a.confirm_window:
                if sn in strip_accents(txt).lower():
                    best = when
                    break
        if best is not None:
            s["confirmed"] = True
            drift = best - s["start"]
        else:
            s["confirmed"] = False
        s["adj_start"] = s["start"] + drift
        s["adj_end"] = s["end"] + drift
    for s in covered:
        s.setdefault("adj_start", s["start"] + drift)
        s.setdefault("adj_end", s["end"] + drift)

    conf = sum(1 for s in covered if s.get("confirmed"))
    out = [f"# SOTEU 2026 attributed transcript",
           f"", f"Capture started **{start:%H:%M:%S}**. Transcript covers "
           f"**{lines[0][0]:%H:%M:%S} to {lines[-1][0]:%H:%M:%S}**.",
           f"Slots in range: **{len(covered)}**, of which **{conf} confirmed** by the announced "
           f"surname; the rest are marked `~` and rest on the schedule alone.", ""]

    unattributed = 0
    for s in covered:
        body = [t for w, t in lines if s["adj_start"] <= w < s["adj_end"]]
        if not body:
            continue
        mark = "" if s.get("confirmed") else " `~`"
        out.append(f"## {s['name']} ({s['role']}) {s['adj_start']:%H:%M:%S}-{s['adj_end']:%H:%M:%S}{mark}")
        out.append("")
        out.append(" ".join(body))
        out.append("")
        if not s.get("confirmed"):
            unattributed += 1

    first = covered[0]["adj_start"] if covered else None
    orphan = [t for w, t in lines if first and w < first]
    if orphan:
        out.insert(4, f"**{len(orphan)} lines fall before the first slot in range and are unattributed.**\n")

    pathlib.Path(a.out).write_text("\n".join(out), encoding="utf-8")
    print(f"[OK] {a.out}")
    print(f"     {len(covered)} slots, {conf} confirmed, {unattributed} inferred-only")
    return 0


if __name__ == "__main__":
    sys.exit(main())
