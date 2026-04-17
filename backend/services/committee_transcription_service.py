"""
Committee Meeting Transcription Service

Full pipeline: discover meeting -> download audio (ffmpeg) ->
transcribe (OpenAI Whisper API) -> map agenda to timestamps -> store in DB.

Whisper API: $0.006/min. A 2-hour meeting costs ~$0.72.
Audio extraction requires ffmpeg in the system PATH.

Created: April 2026
"""

import logging
import os
import re
import subprocess
import tempfile
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# Whisper API has a 25 MB file size limit
MAX_AUDIO_SIZE_BYTES = 25 * 1024 * 1024


class CommitteeTranscriptionService:
    """Transcribes EP committee meeting recordings using OpenAI Whisper API."""

    def __init__(self):
        api_key = os.getenv("OPENAI_API_KEY")
        self._openai = AsyncOpenAI(api_key=api_key) if api_key else None

    async def transcribe_meeting(
        self,
        video_url: str,
        committee_code: str,
        meeting_date: date,
        title: str,
        agenda_items: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Full transcription pipeline.

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
            "transcription_model": "whisper-1",
            "status": "processing",
            "error_message": None,
        }

        if not self._openai:
            result["status"] = "failed"
            result["error_message"] = "OPENAI_API_KEY not configured"
            return result

        # Step 1: download and extract audio
        logger.info("[TRANSCRIBE] Downloading audio from %s", video_url)
        audio_path = None
        try:
            audio_path = await self._extract_audio(video_url)
            if not audio_path:
                result["status"] = "failed"
                result["error_message"] = "Failed to extract audio from video URL"
                return result

            audio_size = os.path.getsize(audio_path)
            logger.info("[TRANSCRIBE] Audio extracted: %d bytes (%.1f MB)", audio_size, audio_size / 1024 / 1024)

            # Step 2: transcribe with Whisper API
            if audio_size > MAX_AUDIO_SIZE_BYTES:
                logger.info("[TRANSCRIBE] Audio > 25 MB, chunking required")
                segments, full_text, duration = await self._transcribe_chunked(audio_path)
            else:
                segments, full_text, duration = await self._transcribe_single(audio_path)

            result["transcript_text"] = full_text
            result["transcript_segments"] = segments
            result["word_count"] = len(full_text.split()) if full_text else 0
            result["duration_seconds"] = int(duration) if duration else 0

            # Cost: $0.006 per minute
            minutes = (duration or 0) / 60
            result["transcription_cost"] = round(minutes * 0.006, 4)

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

    async def _transcribe_single(
        self, audio_path: str
    ) -> Tuple[List[Dict[str, Any]], str, float]:
        """Transcribe a single audio file (< 25 MB) with Whisper API."""
        with open(audio_path, "rb") as f:
            response = await self._openai.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                response_format="verbose_json",
                timestamp_granularities=["segment"],
                language="en",  # committee meetings are interpreted to English
            )

        segments = []
        full_text_parts = []
        duration = getattr(response, "duration", 0) or 0

        for seg in getattr(response, "segments", []) or []:
            segment = {
                "start": seg.get("start", 0),
                "end": seg.get("end", 0),
                "text": (seg.get("text") or "").strip(),
            }
            segments.append(segment)
            if segment["text"]:
                full_text_parts.append(segment["text"])

        full_text = " ".join(full_text_parts)
        return segments, full_text, duration

    async def _transcribe_chunked(
        self, audio_path: str
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
                    segments, text, dur = await self._transcribe_single(chunk_path)

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

        full_text = " ".join(all_text_parts)
        return all_segments, full_text, total_duration

    def _extract_procedure_refs(self, text: str) -> List[str]:
        """Extract EU procedure references from transcript text."""
        # Pattern: 2024/0123(COD), 2025/0419(COD), etc.
        refs = re.findall(r"\d{4}/\d{4}\s*\([A-Z]{2,4}\)", text)
        return list(set(refs))

    def _map_agenda_to_timestamps(
        self,
        agenda_items: List[Dict[str, Any]],
        segments: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """Map agenda items to approximate transcript timestamps using keyword matching.

        For each agenda item, find the first segment whose text contains
        enough keywords from the agenda title. This gives an approximate
        start time for each agenda topic in the recording.
        """
        if not segments:
            return agenda_items

        stop_words = {"the", "a", "an", "of", "on", "in", "for", "and", "to", "with",
                      "by", "at", "from", "this", "that", "its"}

        mapped = []
        for item in agenda_items:
            title = item.get("title", "")
            keywords = {
                w.lower().strip(".,;:!?()[]\"'")
                for w in title.split()
                if len(w) > 3 and w.lower() not in stop_words
            }

            if not keywords:
                mapped.append(item)
                continue

            best_seg = None
            best_score = 0
            for seg in segments:
                seg_text = seg.get("text", "").lower()
                score = sum(1 for kw in keywords if kw in seg_text)
                if score > best_score:
                    best_score = score
                    best_seg = seg

            item_copy = dict(item)
            if best_seg and best_score >= 2:
                item_copy["start_time"] = best_seg.get("start")
                item_copy["end_time"] = best_seg.get("end")

            mapped.append(item_copy)

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
