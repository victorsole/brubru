#!/usr/bin/env python3.12
"""Transcribe a webinar you attended and turn it into structured notes.

Built 25 August 2026 for the Spaak session on 16 September, but it is not
specific to it: point it at any recording of a session you sat in on.

WHAT IT DOES

    python3.12 scripts/webinar_notes.py /path/to/recording.m4a \
        --title "Leveraging AI for Policy Monitoring & Insights" \
        --date 2026-09-16 \
        --speakers "Cyrille Mai Thanh|Diane Mievis|Mihailo Jovetic|Maria Negut" \
        --out docs/marketing/competitors/2026-09-16-spaak-webinar.md

1. Transcribes **locally** with faster-whisper -- the same engine and settings
   the committee-transcription service already uses (CPU, int8, chunked for
   long audio). Nothing is uploaded, no API is called, the audio never leaves
   this machine. That is deliberate: see the note on scope below.
2. Writes a timestamped transcript.
3. Runs the transcript through Brubru's own open-model chain to produce a
   structured competitive-intelligence note -- claims, product capabilities,
   roadmap signals, how the practitioners actually describe their workflow, and
   anything that is a direct comparison to what we do.

CAPTURE IS NOT THIS SCRIPT'S JOB, and that is on purpose. Capture what you
yourself hear, on your own machine:

    1. Install BlackHole (free, open source): brew install blackhole-2ch
    2. Audio MIDI Setup -> create a Multi-Output Device (your speakers +
       BlackHole) so you can still hear the session.
    3. Record BlackHole as the input, either in QuickTime (New Audio Recording,
       pick BlackHole) or:
           ffmpeg -f avfoundation -i ":BlackHole 2ch" -ac 1 -ar 16000 out.wav
    4. Feed the file to this script.

This routes your own machine's audio output to a file. It does not touch Teams,
does not join the meeting, and does not use any platform recording API -- so it
is invisible to the other participants by construction rather than by evading
anything. That distinction matters and it is the only version of "quiet" this
script supports.

SCOPE, briefly, because Brubru sells EU compliance

The speakers are identifiable people employed by named companies, so a
recording of them is personal data and retaining it engages the GDPR. Three
things keep this proportionate, and the script is built around them:
  - the session is public ("Anyone can view and join"), and this is marketing
    content its authors want circulated;
  - the transcript stays LOCAL and is never sent to a third-party service;
  - the output is an internal note. Do not publish the transcript, do not quote
    the individuals by name in anything external, and delete the audio once the
    note is written (--delete-audio does this for you).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from datetime import date as _date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

logger = logging.getLogger("webinar-notes")

_ANALYSIS_PROMPT = """You are analysing a transcript of a competitor's public webinar for an
internal briefing. Be precise and sceptical. Never invent a claim that is not in the transcript.

Session: {title}
Date: {date}
Speakers present: {speakers}

Produce these sections, in British English, with no institutional codes in the prose:

## What they claimed
Every substantive product or capability claim, quoted or closely paraphrased, with who said it
where that is clear from context. Separate FACTS (a number, a named source, a shipped feature)
from POSITIONING (an aspiration or a slogan). If a claim is checkable, say how you would check it.

## How the practitioners actually work
The client-side speakers describe a real workflow. Capture it: what they monitor, how often, what
they do with it, what they complain about. This is the most valuable part of the transcript,
because it is unfiltered demand-side evidence and it is not a sales pitch.

## Where they are weak
Anything they hedge, decline to answer, or describe as coming later. Note the questions that were
asked and NOT answered.

## Direct comparisons
Anything that reads as a contrast with what we do: depth of legal corpus, languages, national
versus EU coverage, API access, citation quality, freshness.

## What to do about it
Concrete actions, each tagged COUNTERATTACK, DIFFERENTIATE, COPY, INITIATIVE or INFO.

## Open questions
What the transcript does not settle and would be worth finding out.

TRANSCRIPT
----------
{transcript}
"""


async def _transcribe(audio_path: Path, model_name: str, language: str | None) -> tuple[str, list]:
    """Local faster-whisper, same settings as the committee service."""
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("faster-whisper is not installed. pip install faster-whisper", file=sys.stderr)
        raise SystemExit(2)

    print(f"[transcribe] loading {model_name} (cpu/int8) ...", file=sys.stderr)
    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    print(f"[transcribe] {audio_path.name} ...", file=sys.stderr)
    segments, info = model.transcribe(
        str(audio_path),
        language=language,          # None = autodetect
        vad_filter=True,            # drop silence; a webinar has a lot of it
        beam_size=5,
    )
    out, lines = [], []
    for seg in segments:
        mm, ss = divmod(int(seg.start), 60)
        hh, mm = divmod(mm, 60)
        stamp = f"[{hh:02d}:{mm:02d}:{ss:02d}]"
        text = seg.text.strip()
        out.append(f"{stamp} {text}")
        lines.append({"start": seg.start, "end": seg.end, "text": text})
        if len(lines) % 25 == 0:
            print(f"[transcribe] {len(lines)} segments, {int(seg.end)}s ...", file=sys.stderr)
    print(f"[transcribe] done: {len(lines)} segments, detected language "
          f"{getattr(info, 'language', '?')}", file=sys.stderr)
    return "\n".join(out), lines


async def _analyse(transcript: str, title: str, when: str, speakers: str) -> str:
    """Structured note via Brubru's own provider chain. No third-party notetaker."""
    from services.ai.multi_provider_service import MultiProviderService
    svc = MultiProviderService()
    prompt = _ANALYSIS_PROMPT.format(
        title=title, date=when, speakers=speakers,
        transcript=transcript[:120_000],
    )
    print("[analyse] sending to the open-model chain ...", file=sys.stderr)
    result = await svc.generate(
        system_prompt="You write internal competitive briefings. Precise, sceptical, never invent.",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=4000,
        temperature=0.2,
    )
    # generate() returns a ProviderResponse dataclass whose text is `.message`.
    # Checked rather than assumed: str(result) would have written the repr of
    # the dataclass into the note and looked almost plausible.
    text = getattr(result, "message", None)
    if text:
        provider = getattr(result, "provider", "?")
        model = getattr(result, "model", "?")
        return f"{text}\n\n_Analysis generated by {provider} / {model}._"
    if isinstance(result, dict):
        return result.get("message") or result.get("content") or ""
    raise RuntimeError(f"provider returned no message: {type(result).__name__}")


def main() -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("audio", help="audio or video file you recorded of a session you attended")
    ap.add_argument("--title", default="Untitled session")
    ap.add_argument("--date", default=str(_date.today()))
    ap.add_argument("--speakers", default="", help="pipe-separated names, for attribution context")
    ap.add_argument("--model", default=os.environ.get("WHISPER_MODEL", "medium"),
                    help="faster-whisper model (tiny/base/small/medium/large-v3). Default medium.")
    ap.add_argument("--language", default=None, help="force a language code; default autodetect")
    ap.add_argument("--out", help="write the note here (default: alongside the audio)")
    ap.add_argument("--transcript-only", action="store_true", help="skip the analysis pass")
    ap.add_argument("--delete-audio", action="store_true",
                    help="delete the source audio once the note is written")
    args = ap.parse_args()

    logging.basicConfig(level=logging.WARNING)
    audio = Path(args.audio).expanduser()
    if not audio.exists():
        print(f"no such file: {audio}", file=sys.stderr)
        return 1

    transcript, segments = asyncio.run(_transcribe(audio, args.model, args.language))
    if not segments:
        # Say so. An empty transcript must not be written out as a clean note.
        print("[FAIL] no speech segments produced. Check the recording actually captured audio "
              "(a silent file is the usual cause: the Multi-Output Device was not selected).",
              file=sys.stderr)
        return 1

    out = Path(args.out) if args.out else audio.with_suffix(".notes.md")
    out.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        f"# {args.title}",
        "",
        f"**{args.date}** — internal note. Transcribed locally; audio never left this machine.",
        "**Confidential. Do not publish. Do not quote the individuals externally.**",
        "",
        f"Speakers: {args.speakers or 'not recorded'}",
        f"Segments: {len(segments)} — duration ~{int(segments[-1]['end'] // 60)} min",
        "",
    ]

    if not args.transcript_only:
        try:
            parts += ["## Analysis", "", asyncio.run(
                _analyse(transcript, args.title, args.date, args.speakers)), ""]
        except Exception as exc:  # noqa: BLE001
            # The transcript is the valuable artefact; never lose it because the
            # analysis pass failed.
            parts += ["## Analysis", "",
                      f"_Analysis pass failed ({type(exc).__name__}: {exc}). "
                      f"The transcript below is complete and unaffected._", ""]
            print(f"[WARN] analysis failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    parts += ["---", "", "## Transcript", "", "```", transcript, "```", ""]
    out.write_text("\n".join(parts), encoding="utf-8")
    print(f"[OK] {out}  ({out.stat().st_size:,} bytes)")

    if args.delete_audio:
        audio.unlink()
        print(f"[OK] deleted {audio}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
