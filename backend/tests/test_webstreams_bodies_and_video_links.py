"""Webstreams: the transcript is the body, and past meetings get a verified video link (7 Oct 2026).

Bodies were metadata alone (208 stored transcripts never served) and read
"Status: TranscriptStatusEnum.PENDING". Since June meetings arrived with no video_url, so
the transcriber (which only takes rows that have one) did nothing while reporting success.
"""
import importlib.util
import pathlib
import sys
from datetime import datetime
from types import SimpleNamespace

from models.committee_meeting_transcript import TranscriptStatusEnum

_SCRIPT = pathlib.Path(__file__).resolve().parents[1] / "scripts" / "transcribe_pending_committees.py"


def _row(**kw):
    base = dict(id="x", committee_code="CULT", title="CULT Committee Meeting", meeting_date=datetime(2026, 9, 29),
                multimedia_url="https://multimedia.europarl.europa.eu/en/cult-committee-meeting_20260929-1000-COMMITTEE-CULT_vd",
                video_url=None, event_id=None, language="en", duration_seconds=None, speaker_count=None,
                word_count=None, status=TranscriptStatusEnum.PENDING, related_procedure_refs=[],
                transcribed_at=None, last_updated=datetime(2026, 10, 7), transcript_text=None)
    base.update(kw)
    return SimpleNamespace(**base)


def test_the_body_carries_the_status_value_and_the_transcript():
    from api.v1.webstreams import _row_to_item
    pending = _row_to_item(_row())
    assert "TranscriptStatusEnum" not in pending.body_txt
    done = _row_to_item(_row(status=TranscriptStatusEnum.COMPLETED,
                             transcript_text="Chair: good morning.\nThe meeting is open."))
    assert "Transcript:" in done.body_txt and "The meeting is open." in done.body_txt
    assert "<p>The meeting is open.</p>" in done.body_html


def test_a_video_link_is_stored_only_when_the_packager_serves_audio(monkeypatch):
    spec = importlib.util.spec_from_file_location("tpc", _SCRIPT)
    tpc = importlib.util.module_from_spec(spec)
    sys.modules["tpc"] = tpc
    spec.loader.exec_module(tpc)

    live, gone = _row(), _row(multimedia_url=_row().multimedia_url.replace("CULT_vd", "ENVI_vd"))

    class Q:
        def __init__(self, rows): self.rows = rows
        def filter(self, *a): return self
        def order_by(self, *a): return self
        def limit(self, n): return self
        def all(self): return self.rows

    class Session:
        committed = False
        def query(self, model): return Q([live, gone])
        def commit(self): Session.committed = True

    class Resp:
        def __init__(self, body): self.body = body
        def read(self, n=-1): return self.body

    def fake_urlopen(url, timeout=30):
        if "COMMITTEE-CULT" in url:
            return Resp(b'#EXTM3U\n#EXT-X-MEDIA:TYPE=AUDIO,LANGUAGE="en"\n')
        raise OSError("404")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    assert tpc._resolve_video_urls(Session(), limit=10) == 1
    assert live.video_url.endswith("/20260929-1000-COMMITTEE-CULT_,360p,540p,720p,1080p,.mp4/master.m3u8")
    assert gone.video_url is None and Session.committed


def test_a_refused_segment_is_never_transcribed(monkeypatch, tmp_path):
    import asyncio
    import subprocess
    from services import committee_transcription_service as cts

    def fake_run(cmd, capture_output=True, timeout=600):
        with open(cmd[-1], "wb") as f:
            f.write(b"\0" * 5000)  # a non-empty file, as ffmpeg leaves one
        return subprocess.CompletedProcess(cmd, 0, b"", b"[https] HTTP error 403 Forbidden\nSegment 2 failed too many times, skipping")

    monkeypatch.setattr(cts.subprocess, "run", fake_run)
    svc = cts.CommitteeTranscriptionService.__new__(cts.CommitteeTranscriptionService)
    assert asyncio.run(svc._extract_audio("https://vod/master.m3u8")) is None
