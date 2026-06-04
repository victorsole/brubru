"""
Committee Meeting Transcription Service

Full pipeline: discover meeting -> select language track (if HLS master) ->
extract audio (ffmpeg) -> transcribe -> map agenda to timestamps -> store in DB.

Engines (in preference order when not pinned):
  * faster-whisper (local, FREE) -- medium model, CPU int8, no file-size cap.
    Set FASTER_WHISPER_MODEL env var to override model size (default: medium).
  * Voxtral (Mistral API, voxtral-mini-2507) -- $0.006/min. Set MISTRAL_API_KEY.
    NOTE: requires Mistral Business plan; gives 401 on developer/free tier.
  * OpenAI Whisper (whisper-1 API) -- $0.006/min. Set OPENAI_API_KEY.

Language tracks:
  EP committee HLS masters expose one AUDIO track per interpretation booth
  (floor `qaj/qar/qac`, en, fr, es, it, nl, ...). `language` selects the
  EXT-X-MEDIA LANGUAGE attribute. 'floor' picks the floor (original mix);
  default 'en' picks the English booth.

Created: April 2026
Updated: May 2026 -- HLS language-track selection + Voxtral primary.
Updated: May 2026 -- faster-whisper local engine added (free, no API cost).
"""

import logging
import os
import re
import subprocess
import tempfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Whisper / Voxtral API: 25 MB per file limit
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024

VOXTRAL_API_URL = "https://api.mistral.ai/v1/audio/transcriptions"
VOXTRAL_DEFAULT_MODEL = "voxtral-mini-2507"
FLOOR_LANGUAGES = {"qaj", "qar", "qac", "mul"}
FASTER_WHISPER_DEFAULT_MODEL = "medium"  # tiny/base/small/medium/large-v2/large-v3

# Module-level faster-whisper model singleton (loaded lazily on first use)
_faster_whisper_model = None
_faster_whisper_model_name: Optional[str] = None

# Inter-segment silence (seconds) above which we start a new paragraph.
# Profiled on the SANT 23 April 2026 transcript: 1,460 gaps split bimodally
# at <1s (intra-utterance) vs >=2s (speaker handover).
# Only treat a sizeable pause as a paragraph break (timestamp gaps vary by engine,
# so keep this conservative — the primary driver is length+sentence below).
PARAGRAPH_GAP_SECONDS = 2.5
# Target paragraph length: once exceeded, break at the next sentence end. Gives
# uniform medium paragraphs regardless of ASR engine.
PARAGRAPH_TARGET_CHARS = 450
# Hard cap: break even without sentence-final punctuation past this, to avoid a
# runaway wall-of-text on long monologues.
PARAGRAPH_MAX_CHARS = 800
# Phrases at the start of a segment that almost always mark a speaker change.
# Lowercased; matched as `text_lower.lstrip().startswith(cue)`.
_SPEAKER_CUES = (
    "thank you,",
    "thank you so much",
    "thank you very much",
    "thank you chair",
    "thank you, chair",
    "thank you, madam chair",
    "thank you, madam president",
    "thank you, mr president",
    "i give the floor",
    "i'll give the floor",
    "give the floor to",
    "the floor is yours",
    "please, the floor",
    "the next item",
    "next item on the agenda",
    "we now go",
    "we go to",
    "moving on",
    "moving to",
    "and now,",
    "and now to",
    "and then to",
    "and then,",
    "now to ",
    "now, ",
    "madam chair,",
    "madam president,",
    "mr president,",
    "mr. president,",
    "dear chair",
    "dear colleagues",
    "dear members",
    "honourable members",
    "honorable members",
    "grazie",
    "danke",
    "merci",
    "bonjour",
    "good morning",
    "next slide",
    "the vote is open",
    "final vote",
    "compromise number",
    "amendment number",
    "adopted.",
    "rejected.",
)


def format_segments_as_paragraphs(
    segments: List[Dict[str, Any]],
    gap_seconds: float = PARAGRAPH_GAP_SECONDS,
    max_chars: int = PARAGRAPH_MAX_CHARS,
) -> str:
    """Join verbose_json segments into a readable multi-paragraph transcript.

    Heuristics for inserting a paragraph break BEFORE the current segment:
      (1) gap (seg.start - prev.end) >= `gap_seconds` -- natural pause / speaker
          handover. Whisper chunks produce a clean bimodal gap distribution.
      (2) segment text starts with a known speaker-transition cue ("Thank you,",
          "I give the floor to", "Madam Chair", ...).
      (3) the running paragraph exceeds `max_chars` AND ends in sentence-final
          punctuation -- prevents wall-of-text in long monologues.
    """
    if not segments:
        return ""

    paragraphs: List[List[str]] = [[]]
    prev_end = 0.0
    for idx, seg in enumerate(segments):
        text = (seg.get("text") or "").strip()
        if not text:
            continue
        start = float(seg.get("start") or 0.0)
        end = float(seg.get("end") or start)
        gap = start - prev_end if idx > 0 else 0.0

        text_lower_l = text.lower().lstrip()
        starts_cue = any(text_lower_l.startswith(c) for c in _SPEAKER_CUES)
        current_text = " ".join(paragraphs[-1])
        ended_sentence = current_text.rstrip().endswith((".", "?", "!", ":"))
        # Primary, engine-independent driver: pack to a target length, break at the
        # next sentence end; hard-cap runaway monologues.
        reached_target = len(current_text) >= PARAGRAPH_TARGET_CHARS and ended_sentence
        hard_cap = len(current_text) >= max_chars
        new_para = idx > 0 and bool(paragraphs[-1]) and (
            starts_cue or reached_target or hard_cap or gap >= gap_seconds
        )

        if new_para:
            paragraphs.append([])
        paragraphs[-1].append(text)
        prev_end = end

    return "\n\n".join(" ".join(p).strip() for p in paragraphs if p)


class CommitteeTranscriptionService:
    """Transcribes EP committee meeting recordings."""

    def __init__(self):
        # Keys live in pydantic `settings` (loaded from ../.env); os.environ is NOT
        # populated under uvicorn, so os.getenv alone returns None and the service
        # falls back to slow local CPU faster-whisper (or fails). Read settings too.
        try:
            from core.config import settings as _settings
        except Exception:
            _settings = None

        def _key(name):
            return os.getenv(name) or (getattr(_settings, name, None) if _settings else None)

        openai_key = _key("OPENAI_API_KEY")
        self._openai = AsyncOpenAI(api_key=openai_key) if openai_key else None
        self._mistral_key = _key("MISTRAL_API_KEY")
        self._voxtral_model = _key("VOXTRAL_MODEL") or VOXTRAL_DEFAULT_MODEL
        self._fw_model_name = _key("FASTER_WHISPER_MODEL") or FASTER_WHISPER_DEFAULT_MODEL

    def _get_faster_whisper_model(self):
        """Load (or return cached) faster-whisper model."""
        global _faster_whisper_model, _faster_whisper_model_name
        if _faster_whisper_model is None or _faster_whisper_model_name != self._fw_model_name:
            try:
                from faster_whisper import WhisperModel
                logger.info("[TRANSCRIBE] Loading faster-whisper model '%s' (CPU int8)...", self._fw_model_name)
                _faster_whisper_model = WhisperModel(
                    self._fw_model_name, device="cpu", compute_type="int8"
                )
                _faster_whisper_model_name = self._fw_model_name
                logger.info("[TRANSCRIBE] faster-whisper model loaded.")
            except ImportError:
                return None
        return _faster_whisper_model

    def _engine_order(self, prefer: Optional[str] = None) -> List[str]:
        """Return ordered list of engines to try given env + preference."""
        if prefer == "faster-whisper":
            return ["faster-whisper"]
        if prefer == "whisper":
            order = []
            if self._openai:
                order.append("whisper")
            if self._mistral_key:
                order.append("voxtral")
            return order
        if prefer == "voxtral":
            # API-only, EU-sovereign first — for ON-DEMAND (fast; never the slow
            # local CPU engine). Falls back to OpenAI Whisper if Voxtral is down.
            order = []
            if self._mistral_key:
                order.append("voxtral")
            if self._openai:
                order.append("whisper")
            return order
        # Default (batch/CLI): faster-whisper first (free, local), then APIs.
        order = ["faster-whisper"]
        if self._mistral_key:
            order.append("voxtral")
        if self._openai:
            order.append("whisper")
        return order

    async def transcribe_meeting(
        self,
        video_url: str,
        committee_code: str,
        meeting_date: date,
        title: str,
        agenda_items: Optional[List[Dict[str, Any]]] = None,
        language: str = "en",
        engine: Optional[str] = None,
        progress_cb=None,
    ) -> Dict[str, Any]:
        """Full transcription pipeline.

        ``progress_cb(stage: str, pct: float)`` is an optional callback for UI
        progress (stage in {'preparing','transcribing'}); no-op when omitted.

        Returns a dict ready to populate a CommitteeMeetingTranscript row:
        {
            transcript_text, transcript_segments, word_count, duration_seconds,
            agenda_items (with timestamps), related_procedure_refs,
            transcription_cost, status, error_message
        }
        """
        result: Dict[str, Any] = {
            "transcript_text": None,
            "transcript_segments": [],
            "word_count": 0,
            "duration_seconds": 0,
            "agenda_items": agenda_items or [],
            "related_procedure_refs": [],
            "transcription_cost": 0.0,
            "transcription_model": None,
            "transcription_language": language,
            "status": "processing",
            "error_message": None,
        }

        def _p(stage: str, pct: float):
            if progress_cb:
                try:
                    progress_cb(stage, pct)
                except Exception:
                    pass

        _p("preparing", 0)
        engines = self._engine_order(prefer=engine)
        if not engines:
            result["status"] = "failed"
            result["error_message"] = "No ASR engine configured (set MISTRAL_API_KEY or OPENAI_API_KEY)"
            return result

        # Step 1: resolve the audio track URL (HLS master -> language booth)
        source_url = video_url
        if video_url.endswith(".m3u8"):
            track_url = await self._select_audio_track(video_url, language=language)
            if track_url:
                source_url = track_url
                logger.info("[TRANSCRIBE] Selected %s booth: %s", language, track_url[:120])
            else:
                logger.info("[TRANSCRIBE] No %s booth in master; using master URL", language)

        # Step 2: download and extract audio
        logger.info("[TRANSCRIBE] Downloading audio from %s", source_url[:120])
        audio_path = None
        try:
            audio_path = await self._extract_audio(source_url)
            if not audio_path:
                result["status"] = "failed"
                result["error_message"] = "Failed to extract audio from video URL"
                return result

            audio_size = os.path.getsize(audio_path)
            logger.info("[TRANSCRIBE] Audio extracted: %d bytes (%.1f MB)", audio_size, audio_size / 1024 / 1024)
            _p("transcribing", 0)

            # Step 3: transcribe (engines tried in order)
            segments: List[Dict[str, Any]] = []
            full_text: str = ""
            duration: float = 0.0
            used_engine: Optional[str] = None
            last_error: Optional[str] = None
            for eng in engines:
                try:
                    # faster-whisper runs locally — no file size cap, no chunking needed
                    if eng == "faster-whisper":
                        logger.info("[TRANSCRIBE] Transcribing via faster-whisper (local, free)")
                        segments, full_text, duration = await self._transcribe_single(audio_path, engine=eng, language=language)
                    elif audio_size > MAX_AUDIO_SIZE_BYTES:
                        logger.info("[TRANSCRIBE] Audio > 25 MB, chunking via %s", eng)
                        segments, full_text, duration = await self._transcribe_chunked(audio_path, engine=eng, language=language, progress_cb=progress_cb)
                    else:
                        segments, full_text, duration = await self._transcribe_single(audio_path, engine=eng, language=language)
                    if full_text:
                        used_engine = eng
                        break
                except Exception as exc:
                    last_error = f"{eng}: {exc}"
                    logger.warning("[TRANSCRIBE] Engine %s failed: %s", eng, exc)
                    continue
            if not used_engine:
                result["status"] = "failed"
                result["error_message"] = last_error or "All ASR engines failed"
                return result

            # Re-render the transcript as paragraphs using segment timestamps,
            # so the stored text is readable (not one massive wall).
            if segments:
                paragraphed = format_segments_as_paragraphs(segments)
                if paragraphed:
                    full_text = paragraphed

            result["transcript_text"] = full_text
            result["transcript_segments"] = segments
            result["word_count"] = len(full_text.split()) if full_text else 0
            result["duration_seconds"] = int(duration) if duration else 0
            if used_engine == "faster-whisper":
                result["transcription_model"] = f"faster-whisper-{self._fw_model_name}"
                result["transcription_cost"] = 0.0  # local, free
            elif used_engine == "voxtral":
                result["transcription_model"] = self._voxtral_model
                result["transcription_cost"] = round((duration or 0) / 60 * 0.006, 4)
            else:
                result["transcription_model"] = "whisper-1"
                result["transcription_cost"] = round((duration or 0) / 60 * 0.006, 4)

            # Step 3: extract procedure references from transcript
            result["related_procedure_refs"] = self._extract_procedure_refs(full_text or "")

            # Step 4: map agenda items to transcript timestamps
            if agenda_items and segments:
                result["agenda_items"] = self._map_agenda_to_timestamps(
                    agenda_items, segments
                )

            result["status"] = "completed"
            logger.info(
                "[TRANSCRIBE] Complete: %d words, %d segments, %d sec, $%.4f",
                result["word_count"], len(segments), result["duration_seconds"],
                result["transcription_cost"],
            )

        except Exception as exc:
            logger.error("[TRANSCRIBE] Pipeline failed: %s", exc)
            result["status"] = "failed"
            result["error_message"] = str(exc)[:500]

        finally:
            # Clean up temp file
            if audio_path and os.path.exists(audio_path):
                os.unlink(audio_path)

        return result

    async def _extract_audio(self, video_url: str) -> Optional[str]:
        """Download video and extract audio track using ffmpeg.

        Returns path to temporary .mp3 file, or None on failure.
        """
        # Create temp file for output
        tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
        tmp_path = tmp.name
        tmp.close()

        try:
            # ffmpeg: extract audio, convert to mp3, mono, 16kHz (Whisper optimal)
            cmd = [
                "ffmpeg", "-y",
                "-i", video_url,
                "-vn",                  # no video
                "-acodec", "libmp3lame",
                "-ar", "16000",         # 16kHz sample rate (Whisper optimal)
                "-ac", "1",             # mono
                "-b:a", "64k",          # 64kbps (keeps size small)
                "-t", "10800",          # max 3 hours safety cap
                tmp_path,
            ]

            logger.info("[TRANSCRIBE] Running ffmpeg: %s", " ".join(cmd[:6]) + " ...")
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=600,  # 10 min timeout
            )

            if proc.returncode != 0:
                stderr = proc.stderr.decode("utf-8", errors="replace")[-500:]
                logger.error("[TRANSCRIBE] ffmpeg failed (code %d): %s", proc.returncode, stderr)
                os.unlink(tmp_path)
                return None

            if not os.path.exists(tmp_path) or os.path.getsize(tmp_path) < 1000:
                logger.error("[TRANSCRIBE] ffmpeg produced empty output")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)
                return None

            return tmp_path

        except subprocess.TimeoutExpired:
            logger.error("[TRANSCRIBE] ffmpeg timed out (>600s)")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None
        except FileNotFoundError:
            logger.error("[TRANSCRIBE] ffmpeg not found in PATH. Install it: apt-get install -y ffmpeg")
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            return None

    async def _select_audio_track(self, master_url: str, language: str = "en") -> Optional[str]:
        """Parse an HLS master playlist and return the URL of the audio track for `language`.

        `language='floor'` picks the original/floor mix (LANGUAGE in FLOOR_LANGUAGES).
        Returns None if the master can't be parsed or the language isn't present.
        """
        try:
            async with httpx.AsyncClient(timeout=20.0, headers={"User-Agent": "Brubru/1.0"}) as c:
                resp = await c.get(master_url, follow_redirects=True)
                if resp.status_code != 200:
                    logger.warning("[TRANSCRIBE] HLS master %d: %s", resp.status_code, master_url[:120])
                    return None
                text = resp.text
        except httpx.HTTPError as exc:
            logger.warning("[TRANSCRIBE] HLS master fetch failed: %s", exc)
            return None

        tracks: List[Tuple[str, str]] = []  # (language, uri)
        for line in text.splitlines():
            if not line.startswith("#EXT-X-MEDIA") or 'TYPE=AUDIO' not in line:
                continue
            lang_match = re.search(r'LANGUAGE="([^"]+)"', line)
            uri_match = re.search(r'URI="([^"]+)"', line)
            if not (lang_match and uri_match):
                continue
            tracks.append((lang_match.group(1).lower(), uri_match.group(1)))

        if not tracks:
            return None

        want = language.lower().strip()
        picked: Optional[str] = None
        if want == "floor":
            for lang, uri in tracks:
                if lang in FLOOR_LANGUAGES:
                    picked = uri
                    break
        else:
            for lang, uri in tracks:
                if lang == want:
                    picked = uri
                    break
        if not picked:
            return None

        # Resolve relative URI against master URL base
        if picked.startswith("http"):
            return picked
        base = master_url.rsplit("/", 1)[0]
        return f"{base}/{picked}"

    async def _transcribe_single(
        self, audio_path: str, engine: str = "voxtral", language: str = "en",
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        """Transcribe a single audio file via the chosen engine."""
        if engine == "faster-whisper":
            return await self._transcribe_single_faster_whisper(audio_path, language=language)
        if engine == "voxtral":
            return await self._transcribe_single_voxtral(audio_path, language=language)
        return await self._transcribe_single_whisper(audio_path, language=language)

    async def _transcribe_single_faster_whisper(
        self, audio_path: str, language: str = "en",
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        """Transcribe via local faster-whisper (free, no file size limit)."""
        import asyncio

        model = self._get_faster_whisper_model()
        if model is None:
            raise RuntimeError("faster-whisper not installed (pip install faster-whisper)")

        fw_lang = None if language in ("floor", "auto") else language

        def _run():
            seg_gen, info = model.transcribe(
                audio_path,
                language=fw_lang,
                beam_size=5,
                vad_filter=True,           # skip silence chunks
                vad_parameters={"min_silence_duration_ms": 500},
            )
            segs = []
            parts = []
            for seg in seg_gen:
                text = (seg.text or "").strip()
                segs.append({"start": seg.start, "end": seg.end, "text": text})
                if text:
                    parts.append(text)
            full_text = " ".join(parts)
            return segs, full_text, float(info.duration or 0)

        return await asyncio.to_thread(_run)

    async def _transcribe_single_whisper(
        self, audio_path: str, language: str = "en",
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        if not self._openai:
            raise RuntimeError("OPENAI_API_KEY not configured")
        whisper_lang = None if language in ("floor", "auto") else language
        with open(audio_path, "rb") as f:
            kwargs = dict(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
            )
            if whisper_lang:
                kwargs["language"] = whisper_lang
            response = await self._openai.audio.transcriptions.create(**kwargs)

        segments = []
        full_text_parts = []
        duration = float(getattr(response, "duration", 0) or 0)

        # OpenAI SDK >=1.0 returns Pydantic TranscriptionSegment objects (not dicts).
        for seg in getattr(response, "segments", []) or []:
            start = getattr(seg, "start", None)
            end = getattr(seg, "end", None)
            text = (getattr(seg, "text", "") or "").strip()
            if start is None and isinstance(seg, dict):  # belt-and-braces
                start = seg.get("start", 0)
                end = seg.get("end", 0)
                text = (seg.get("text") or "").strip()
            segment = {
                "start": float(start or 0),
                "end": float(end or 0),
                "text": text,
            }
            segments.append(segment)
            if segment["text"]:
                full_text_parts.append(segment["text"])

        full_text = (getattr(response, "text", None) or " ".join(full_text_parts) or "").strip()
        return segments, full_text, duration

    async def _transcribe_single_voxtral(
        self, audio_path: str, language: str = "en",
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        """Transcribe via Mistral Voxtral API. Returns (segments, full_text, duration)."""
        if not self._mistral_key:
            raise RuntimeError("MISTRAL_API_KEY not configured")
        # ffprobe for duration (Voxtral doesn't always return it)
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, timeout=30,
            )
            duration = float(probe.stdout.decode().strip() or "0")
        except Exception:
            duration = 0.0

        async with httpx.AsyncClient(
            timeout=300.0,
            headers={"Authorization": f"Bearer {self._mistral_key}"},
        ) as c:
            with open(audio_path, "rb") as fh:
                files = {"file": (os.path.basename(audio_path), fh, "audio/mpeg")}
                data: Dict[str, str] = {
                    "model": self._voxtral_model,
                    "timestamp_granularities": "segment",
                    "response_format": "verbose_json",
                }
                if language and language not in ("floor", "auto"):
                    data["language"] = language
                resp = await c.post(VOXTRAL_API_URL, files=files, data=data)
            if resp.status_code >= 400:
                raise RuntimeError(f"Voxtral HTTP {resp.status_code}: {resp.text[:200]}")
            payload = resp.json()

        segments: List[Dict[str, Any]] = []
        full_text_parts: List[str] = []
        for seg in (payload.get("segments") or []):
            t = (seg.get("text") or "").strip()
            segments.append({
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": t,
            })
            if t:
                full_text_parts.append(t)
        full_text = payload.get("text") or " ".join(full_text_parts)
        if not duration:
            duration = float(payload.get("duration", 0) or 0)
        return segments, full_text, duration

    async def _transcribe_chunked(
        self, audio_path: str, engine: str = "voxtral", language: str = "en", progress_cb=None,
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        """Split audio into chunks and transcribe each, stitching timestamps.

        Chunks overlap by 30 seconds to avoid cutting mid-sentence.
        """
        # Get audio duration via ffprobe
        try:
            probe = subprocess.run(
                ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", audio_path],
                capture_output=True, timeout=30,
            )
            total_duration = float(probe.stdout.decode().strip())
        except Exception:
            total_duration = 10800  # fallback: 3 hours

        # Calculate chunk size: target 20 MB per chunk (leave margin)
        file_size = os.path.getsize(audio_path)
        bytes_per_second = file_size / total_duration if total_duration > 0 else 10000
        chunk_seconds = int(20 * 1024 * 1024 / bytes_per_second)
        chunk_seconds = max(300, min(chunk_seconds, 3600))  # 5 min to 1 hour
        overlap = 30

        all_segments: List[Dict[str, Any]] = []
        all_text_parts: List[str] = []
        offset = 0.0

        chunk_idx = 0
        while offset < total_duration:
            chunk_end = min(offset + chunk_seconds, total_duration)

            # Extract chunk with ffmpeg
            chunk_path = audio_path + f".chunk{chunk_idx}.mp3"
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", audio_path,
                     "-ss", str(offset), "-t", str(chunk_seconds + overlap),
                     "-acodec", "libmp3lame", "-ar", "16000", "-ac", "1", "-b:a", "64k",
                     chunk_path],
                    capture_output=True, timeout=120,
                )

                if os.path.exists(chunk_path) and os.path.getsize(chunk_path) > 1000:
                    segments, text, dur = await self._transcribe_single(
                        chunk_path, engine=engine, language=language,
                    )

                    # Adjust timestamps by offset
                    for seg in segments:
                        seg["start"] += offset
                        seg["end"] += offset
                        all_segments.append(seg)

                    if text:
                        all_text_parts.append(text)

            except Exception as exc:
                logger.warning("[TRANSCRIBE] Chunk %d failed: %s", chunk_idx, exc)
            finally:
                if os.path.exists(chunk_path):
                    os.unlink(chunk_path)

            offset += chunk_seconds  # advance (overlap handled in extraction)
            chunk_idx += 1
            if progress_cb and total_duration > 0:
                try:
                    progress_cb("transcribing", min(99.0, offset / total_duration * 100.0))
                except Exception:
                    pass

        full_text = " ".join(all_text_parts)
        return all_segments, full_text, total_duration

    def _extract_procedure_refs(self, text: str) -> List[str]:
        """Extract EU procedure references from transcript text."""
        # Pattern: 2024/0123(COD), 2025/0419(COD), etc.
        refs = re.findall(r"\d{4}/\d{4}\s*\([A-Z]{2,4}\)", text)
        return list(set(refs))

    _AGENDA_STOP = {"the", "a", "an", "of", "on", "in", "for", "and", "to", "with",
                    "by", "at", "from", "this", "that", "its", "as", "regards"}

    def _map_agenda_to_timestamps(
        self,
        agenda_items: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map agenda items to transcript timestamps with an ORDERED, cue-based sweep.

        Committee meetings work the agenda in order, so each item's start must come
        after the previous item's. For each item we score candidate segments (only
        those after the last assigned one) on three signals:
          * title keyword overlap,
          * the rapporteur's surname being spoken (strong),
          * an explicit "point/item N" chair cue matching the item number (strongest).
        The best segment above threshold becomes the item's start; end is the next
        mapped item's start. Items genuinely not reached (draft agendas deviate) get
        no timestamp rather than a wrong one. Assumes ``agenda_items`` are already
        filtered to one recording session (see committee_agenda_pdf.items_for_session).
        """
        if not segments or not agenda_items:
            return agenda_items

        n = len(segments)
        last_idx = -1
        mapped: List[Dict[str, Any]] = []

        for item in agenda_items:
            title = item.get("title", "")
            keywords = {
                w.lower().strip(".,;:!?()[]\"'’“”")
                for w in title.split()
                if len(w) > 3 and w.lower() not in self._AGENDA_STOP
            }
            rapp = item.get("rapporteur") or ""
            rapp_tokens = {
                w.lower() for w in re.split(r"[\s,()]+", rapp)
                if len(w) > 3 and w.lower() not in self._AGENDA_STOP
            }
            num = item.get("number")
            num_cue = re.compile(rf"\b(?:point|item|number|punto|punkt)\s+(?:no\.?\s*)?{num}\b", re.I) if num else None

            best_idx, best_score = None, 0
            for idx in range(last_idx + 1, n):
                txt = (segments[idx].get("text") or "").lower()
                if not txt:
                    continue
                score = sum(1 for kw in keywords if kw in txt)
                score += 2 * sum(1 for kw in rapp_tokens if kw in txt)
                if num_cue and num_cue.search(txt):
                    score += 4
                if score > best_score:
                    best_score, best_idx = score, idx

            item_copy = dict(item)
            # Accept on a strong single cue (number/rapporteur) or >=2 title keywords.
            if best_idx is not None and best_score >= 2:
                item_copy["start_time"] = segments[best_idx].get("start")
                last_idx = best_idx
            mapped.append(item_copy)

        # end_time = the next mapped item's start_time
        for i, it in enumerate(mapped):
            if it.get("start_time") is None:
                continue
            for j in range(i + 1, len(mapped)):
                if mapped[j].get("start_time") is not None:
                    it["end_time"] = mapped[j]["start_time"]
                    break

        return mapped

    def format_transcript_for_context(
        self,
        transcript_text: str,
        committee_code: str,
        meeting_date: date,
        title: str,
        agenda_items: Optional[List[Dict[str, Any]]] = None,
        procedure_ref: Optional[str] = None,
        max_chars: int = 4000,
    ) -> str:
        """Format a transcript for AI context injection.

        Follows the same pattern as cre_client.format_debate_for_context().
        If procedure_ref is given, tries to extract only the relevant section.
        """
        lines = []
        lines.append("COMMITTEE MEETING TRANSCRIPT (AI-transcribed from EP Multimedia Centre recording)")
        lines.append(f"Committee: {committee_code}")
        lines.append(f"Date: {meeting_date.strftime('%A, %d %B %Y')}")
        lines.append(f"Title: {title}")
        lines.append("")

        # If agenda items are available, list them
        if agenda_items:
            lines.append("Agenda:")
            for item in agenda_items:
                refs = item.get("procedure_refs", [])
                ref_str = f" [{', '.join(refs)}]" if refs else ""
                timestamp = ""
                if item.get("start_time") is not None:
                    mins = int(float(item["start_time"]) / 60)
                    timestamp = f" (at {mins} min)"
                lines.append(f"  {item.get('number', '-')}. {item.get('title', '')}{ref_str}{timestamp}")
            lines.append("")

        # If filtering by procedure reference, extract relevant portion
        text = transcript_text or ""
        if procedure_ref and text:
            # Try to find the section around the procedure reference
            ref_idx = text.lower().find(procedure_ref.lower().split("(")[0])
            if ref_idx > 0:
                # Take 2000 chars before and after
                start = max(0, ref_idx - 1000)
                end = min(len(text), ref_idx + 3000)
                text = "..." + text[start:end] + "..."
                lines.append(f"[Filtered to discussion of {procedure_ref}]")
                lines.append("")

        # Truncate transcript text to fit within budget
        header_len = len("\n".join(lines))
        text_budget = max_chars - header_len - 100
        if len(text) > text_budget:
            text = text[:text_budget] + "\n\n[Transcript truncated for length]"

        lines.append(text)
        return "\n".join(lines)


# Module-level singleton
_service: Optional[CommitteeTranscriptionService] = None


def get_committee_transcription_service() -> CommitteeTranscriptionService:
    global _service
    if _service is None:
        _service = CommitteeTranscriptionService()
    return _service
