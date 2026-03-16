"""
EP Plenary Debate Transcripts (CRE) Client

Fetches and parses official CRE (Compte Rendu in Extenso) XML files from
the European Parliament's Doceo system. CRE files contain the verbatim
record of all plenary debates including speaker names, political groups,
and full speech text.

URL pattern: https://www.europarl.europa.eu/doceo/document/CRE-{TERM}-{DATE}_{LANG}.xml
Term 10 = 2024-2029 legislature.
Publication delay: 3-5 days after plenary session.

Created: March 2026
"""

import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional, Tuple

import httpx

logger = logging.getLogger(__name__)

CRE_BASE_URL = "https://www.europarl.europa.eu/doceo/document"
CRE_TERM = 10  # 2024-2029 legislature

# Political group display names
PP_NAMES = {
    "PPE": "EPP", "S-D": "S&D", "RE": "Renew", "Verts/ALE": "Greens/EFA",
    "ECR": "ECR", "GUE/NGL": "The Left", "PfE": "PfE", "NI": "NI",
    "ESN": "ESN", "ID": "ID",
}

# Speakers with MEPID=0 or PP=NULL are typically institutional
INSTITUTIONAL_ROLES = {"president", "vice-president", "chair", "presidency", "commissioner"}


@dataclass
class Speaker:
    name: str
    mepid: str
    political_group: str  # Normalised group name (EPP, S&D, etc.)
    political_group_raw: str  # Raw from XML (PPE, S-D, etc.)
    language: str
    text: str
    is_institutional: bool = False
    role: str = ""  # e.g. "Commissioner", "Council Presidency"


@dataclass
class Debate:
    title: str
    chapter_number: int
    procedure_refs: List[str] = field(default_factory=list)
    speakers: List[Speaker] = field(default_factory=list)
    vod_start: Optional[str] = None
    vod_end: Optional[str] = None

    @property
    def speaker_count(self) -> int:
        return len(self.speakers)

    def speakers_by_group(self) -> Dict[str, List[Speaker]]:
        """Group speakers by political group."""
        groups: Dict[str, List[Speaker]] = {}
        for s in self.speakers:
            key = s.political_group or "Other"
            if key not in groups:
                groups[key] = []
            groups[key].append(s)
        return groups

    def institutional_speakers(self) -> List[Speaker]:
        return [s for s in self.speakers if s.is_institutional]

    def mep_speakers(self) -> List[Speaker]:
        return [s for s in self.speakers if not s.is_institutional]


@dataclass
class PlenarySession:
    date: date
    debates: List[Debate] = field(default_factory=list)
    source_url: str = ""

    @property
    def debate_count(self) -> int:
        return len(self.debates)

    @property
    def total_speakers(self) -> int:
        return sum(d.speaker_count for d in self.debates)


class CREClient:
    """Client to fetch and parse EP plenary debate transcripts (CRE XML)."""

    def __init__(self, timeout: float = 20.0):
        self.timeout = timeout

    def _build_url(self, session_date: date, lang: str = "EN") -> str:
        date_str = session_date.strftime("%Y-%m-%d")
        return f"{CRE_BASE_URL}/CRE-{CRE_TERM}-{date_str}_{lang.upper()}.xml"

    async def fetch_session(self, session_date: date, lang: str = "EN") -> Optional[PlenarySession]:
        """Fetch and parse a full plenary session's CRE transcript."""
        url = self._build_url(session_date, lang)
        logger.info(f"[CRE] Fetching {url}")

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                resp = await client.get(url, headers={"Accept": "application/xml"})
                if resp.status_code == 404:
                    logger.info(f"[CRE] No transcript for {session_date} (404)")
                    return None
                resp.raise_for_status()
                xml_text = resp.text
        except httpx.HTTPError as e:
            logger.warning(f"[CRE] Failed to fetch {url}: {e}")
            return None

        return self._parse_session(xml_text, session_date, url)

    def _parse_session(self, xml_text: str, session_date: date, source_url: str) -> PlenarySession:
        """Parse CRE XML into structured PlenarySession."""
        root = ET.fromstring(xml_text)
        session = PlenarySession(date=session_date, source_url=source_url)

        chapters = root.findall(".//CHAPTER")
        for chapter in chapters:
            debate = self._parse_chapter(chapter)
            if debate and debate.speaker_count > 0:
                session.debates.append(debate)

        logger.info(f"[CRE] Parsed {session.debate_count} debates, {session.total_speakers} speakers for {session_date}")
        return session

    def _parse_chapter(self, chapter: ET.Element) -> Optional[Debate]:
        """Parse a CHAPTER element into a Debate."""
        try:
            chapter_num = int(float(chapter.get("NUMBER", "0")))
        except (ValueError, TypeError):
            chapter_num = 0

        # Get English title
        title = ""
        for tl in chapter.findall(".//TL-CHAP"):
            if tl.get("VL") == "EN":
                title = (tl.text or "").strip()
                break
        if not title:
            # Fallback to first title
            first_tl = chapter.find(".//TL-CHAP")
            if first_tl is not None:
                title = (first_tl.text or "").strip()

        # Skip procedural chapters
        skip_titles = {
            "opening of the session", "opening of the sitting", "resumption of the sitting",
            "closure of the sitting", "approval of the minutes", "agenda",
            "written declarations", "corrigenda", "membership of committees",
            "one-minute speeches", "order of business",
        }
        if title.lower() in skip_titles:
            return None

        # Get VOD timestamps from first NUMERO element
        vod_start = None
        vod_end = None
        first_num = chapter.find(".//NUMERO")
        if first_num is not None:
            vod_start = first_num.get("VOD-START")
        last_nums = chapter.findall(".//NUMERO")
        if last_nums:
            vod_end = last_nums[-1].get("VOD-END")

        # Extract procedure references from title
        procedure_refs = re.findall(r'\d{4}/\d{4}\([A-Z]+\)', title)

        debate = Debate(
            title=title,
            chapter_number=chapter_num,
            procedure_refs=procedure_refs,
            vod_start=vod_start,
            vod_end=vod_end,
        )

        # Parse interventions
        for intv in chapter.findall(".//INTERVENTION"):
            speaker = self._parse_intervention(intv)
            if speaker and speaker.text.strip():
                debate.speakers.append(speaker)

        return debate

    def _parse_intervention(self, intervention: ET.Element) -> Optional[Speaker]:
        """Parse an INTERVENTION element into a Speaker."""
        orateur = intervention.find("ORATEUR")
        if orateur is None:
            return None

        # Name from LIB attribute (pipe-separated: "First | Last")
        lib = orateur.get("LIB", "")
        name = lib.replace("|", "").strip() if lib else ""

        # Fallback: EMPHAS child text
        if not name:
            emphas = orateur.find("EMPHAS")
            if emphas is not None:
                name = (emphas.text or "").strip().rstrip(".,:")

        if not name:
            return None

        mepid = orateur.get("MEPID", "0")
        pp_raw = orateur.get("PP", "") or ""
        lang_el = orateur.find("LG")
        lang = (lang_el.text or "").strip() if lang_el is not None else orateur.get("LG", "")
        speaker_type = orateur.get("SPEAKER_TYPE", "")

        # Normalise political group
        pp_normalised = PP_NAMES.get(pp_raw, pp_raw)
        if pp_raw in ("NULL", ""):
            pp_normalised = ""

        # Extract text from PARA elements
        text_parts = []
        for para in intervention.findall(".//PARA"):
            # Get direct text + tail text from child elements
            parts = [para.text or ""]
            for child in para:
                parts.append(child.text or "")
                parts.append(child.tail or "")
            text_parts.append(" ".join(p for p in parts if p))

        full_text = " ".join(text_parts)
        # Clean up whitespace
        full_text = re.sub(r'\s+', ' ', full_text).strip()
        # Remove leading dash/hyphen (chair introductions)
        full_text = re.sub(r'^[\s\-\u2013\u2014]+', '', full_text).strip()

        # Determine if institutional speaker
        is_institutional = False
        role = ""

        # Commission speaker
        if speaker_type and "commission" in speaker_type.lower():
            is_institutional = True
            role = "Commission"
        elif speaker_type and ("council" in speaker_type.lower() or "presidency" in speaker_type.lower()):
            is_institutional = True
            role = "Council"
        elif mepid == "0":
            is_institutional = True
            role = "Commission"  # MEPID=0 is typically Commission
        elif pp_raw in ("NULL", ""):
            # Has MEPID but no group = Chair/President
            if speaker_type and "rapporteur" in speaker_type.lower():
                is_institutional = False
                role = "Rapporteur"
            elif speaker_type and "nom du groupe" in speaker_type.lower():
                is_institutional = False
                role = "Group spokesperson"
            else:
                is_institutional = True
                role = "Chair"

        return Speaker(
            name=name,
            mepid=mepid,
            political_group=pp_normalised,
            political_group_raw=pp_raw,
            language=lang,
            text=full_text,
            is_institutional=is_institutional,
            role=role,
        )

    def search_debate_by_topic(self, session: PlenarySession, topic: str) -> Optional[Debate]:
        """Find the best matching debate for a topic query."""
        if not session or not session.debates:
            return None

        topic_lower = topic.lower().strip()
        # Clean punctuation and stop words for matching
        clean_words = set()
        stop = {"the", "a", "an", "in", "on", "of", "for", "and", "to", "with", "by", "at", "from"}
        for w in topic_lower.split():
            w = w.strip(".,;:!?()[]\"'")
            if w and w not in stop and len(w) > 1:
                clean_words.add(w)

        if not clean_words:
            return None

        best_match = None
        best_score = 0

        for debate in session.debates:
            title_lower = debate.title.lower()

            # Exact substring match (clean topic)
            clean_topic = " ".join(sorted(clean_words))
            if all(w in title_lower for w in clean_words):
                return debate

            # Word overlap score
            title_words = set(
                w.strip(".,;:!?()[]\"'") for w in title_lower.split()
                if len(w.strip(".,;:!?()[]\"'")) > 1
            )
            overlap = len(clean_words & title_words)
            if overlap > best_score:
                best_score = overlap
                best_match = debate

        # Require at least 1 meaningful word overlap
        return best_match if best_score >= 1 else None

    def format_debate_for_context(self, debate: Debate, max_chars: int = 4000) -> str:
        """Format a debate into a context string for AI injection."""
        lines = []
        lines.append(f"EP PLENARY DEBATE TRANSCRIPT (official CRE record)")
        lines.append(f"Topic: {debate.title}")
        if debate.procedure_refs:
            lines.append(f"Procedure: {', '.join(debate.procedure_refs)}")
        lines.append(f"Speakers: {debate.speaker_count}")
        lines.append("")

        # Institutional speakers first (Commission, Council)
        for speaker in debate.institutional_speakers():
            if speaker.role in ("Commission", "Council") and speaker.text:
                text = speaker.text[:500]
                lines.append(f"{speaker.role.upper()} ({speaker.name}):")
                lines.append(f"  {text}")
                lines.append("")

        # MEP speakers by group (max 3 per group, max 200 chars each)
        groups = debate.speakers_by_group()
        # Sort groups by speaker count (largest first)
        sorted_groups = sorted(
            [(g, speakers) for g, speakers in groups.items() if g and g != "Other"],
            key=lambda x: len(x[1]),
            reverse=True,
        )

        for group_name, speakers in sorted_groups:
            mep_speakers = [s for s in speakers if not s.is_institutional]
            if not mep_speakers:
                continue
            lines.append(f"{group_name} ({len(mep_speakers)} speaker{'s' if len(mep_speakers) != 1 else ''}):")
            for s in mep_speakers[:3]:
                text = s.text[:200]
                lines.append(f"  - {s.name}: {text}")
            if len(mep_speakers) > 3:
                lines.append(f"  - ... and {len(mep_speakers) - 3} more")
            lines.append("")

        result = "\n".join(lines)

        # Truncate if over max_chars
        if len(result) > max_chars:
            result = result[:max_chars - 50] + "\n\n[Transcript truncated for length]"

        return result

    def format_session_overview(self, session: PlenarySession) -> str:
        """Format a session overview listing all debates."""
        lines = []
        lines.append(f"EP PLENARY SESSION: {session.date.strftime('%A, %d %B %Y')}")
        lines.append(f"Debates: {session.debate_count} | Total speakers: {session.total_speakers}")
        lines.append(f"Source: {session.source_url}")
        lines.append("")

        for i, debate in enumerate(session.debates, 1):
            refs = f" [{', '.join(debate.procedure_refs)}]" if debate.procedure_refs else ""
            lines.append(f"  {i}. {debate.title}{refs} ({debate.speaker_count} speakers)")

        return "\n".join(lines)


# Module-level singleton
_cre_client: Optional[CREClient] = None


def get_cre_client() -> CREClient:
    global _cre_client
    if _cre_client is None:
        _cre_client = CREClient()
    return _cre_client
