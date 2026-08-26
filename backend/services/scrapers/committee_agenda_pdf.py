"""
EP Committee draft-agenda (OJ) PDF parser + URL discovery.

The committee "ordre du jour" (OJ / draft agenda) is the spine that links a
webstreaming recording to its content: it carries the ordered list of agenda
items, each with a procedure reference, dossier reference, rapporteur, action,
and the time-block (date + clock window) it belongs to. A multi-day meeting OJ
fans out across several recordings; the time-block header assigns each item to
the right session.

Two public helpers:
  * ``parse_agenda_pdf(pdf_bytes)`` -> structured {sessions, items}. pypdf only
    (no poppler dependency), tolerant regex anchors.
  * ``discover_agenda(committee_code, meeting_date)`` -> the redmap OJ PDF URL
    for that meeting (read from the committee meeting-documents page; the opaque
    redmap token is never reconstructed, always read from the href). No WAF.

NO Anthropic / NO LLM - pure text parsing. Used by the Transcripts pipeline to
attach an agenda (and, after alignment, per-item timestamps) to a recording.
"""

from __future__ import annotations

import io
import logging
import re
from datetime import date, datetime
from typing import Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)

_UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/151.0 Safari/537.36")

_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

# ---- line-level patterns ---------------------------------------------------

# Time-block header: "2 June 2026, 9.00 – 12.30"  (en dash or hyphen; . or :)
_BLOCK = re.compile(
    r"^(\d{1,2})\s+(" + "|".join(m.capitalize() for m in _MONTHS) + r")\s+(\d{4}),\s*"
    r"(\d{1,2})[.:](\d{2})\s*[–--]\s*(\d{1,2})[.:](\d{2})", re.I)
# Numbered item start: "6. Amending Regulation ..."
_ITEM = re.compile(r"^(\d{1,2})\.\s+(.*\S)")
# Dossier ref on its own line: "AGRI/10/03690"
_DOSSIER = re.compile(r"^[A-Z]{2,6}/\d{1,2}/\d{3,6}$")
# Procedure ref: "2025/0237(COD)"
_PROC = re.compile(r"\b(\d{4}/\d{4}\([A-Z]{2,4}\))")
# Procedure type marker: "***I", "***II", "***III", "***"
_PTYPE = re.compile(r"(\*\s?\*\s?\*\s?I{0,3})")
# COM / JOIN / C-docs
_COM = re.compile(r"\b((?:COM|JOIN|SWD|C)\(\d{4}\)\d{3,4}|C\d{1,2}[–-]\d{4}/\d{4})")
# PE working documents with their kind: "PR – PE788.831v01-00", "AM – PE...", "PA – PE..."
_PEDOC = re.compile(r"\b(PR|PA|AM|RR|AD|DT|RE)\s*[–-]\s*(PE\d{3}\.\d{3}[vV]\d{2}-\d{2})")
# Meeting code in the header: "AGRI(2026)0601_1"
_MEETING_CODE = re.compile(r"\b([A-Z]{2,6}\(\d{4}\)\d{4}_\d+)\b")
# Action bullet
_ACTION = re.compile(r"^[·•‧▪∙]\s*(.+\S)")
# Footer / header noise
_NOISE = re.compile(
    r"(United in diversity|^OJ\\PE|^\d+/\d+$|^PE\d{3}\.\d{3}|European Parliament|^\d{4}-\d{4}$|"
    r"^DRAFT AGENDA$|^Committee meeting$|^Brussels$|^Room:|^EN$)", re.I)
# Leading glued "EN" from page breaks: strip only before known tokens.
_GLUED_EN = re.compile(r"^EN(?=(AM|PA|PR|RR|AD|DT|RE)\b|Rapporteur|Responsible|Consideration|Exchange)")


def _clean_line(s: str) -> str:
    s = s.replace("\xa0", " ").rstrip()
    s = _GLUED_EN.sub("", s)
    return s.strip()


def _is_meta(line: str) -> bool:
    """A line that ends the title block of an item."""
    low = line.lower()
    return bool(
        _DOSSIER.match(line) or _PROC.search(line) or _COM.search(line)
        or low.startswith("rapporteur") or low.startswith("responsible")
        or _ACTION.match(line) or _BLOCK.match(line) or _ITEM.match(line)
        or line.strip().startswith("*")
    )


# ---- PDF text extraction ---------------------------------------------------

def _extract_text(pdf_bytes: bytes) -> List[str]:
    import pypdf
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    out: List[str] = []
    for page in reader.pages:
        for raw in (page.extract_text() or "").splitlines():
            line = _clean_line(raw)
            if line and not _NOISE.match(line):
                out.append(line)
    return out


def fetch_pdf(url: str) -> Optional[bytes]:
    """Fetch an OJ PDF. redmap links are plain httpx; doceo links are WAF-walled
    (HTTP 202 + empty), so fall back to an in-page browser fetch for those."""
    try:
        r = httpx.get(url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=45)
        if r.status_code == 200 and "pdf" in r.headers.get("content-type", "").lower():
            return r.content
        logger.info("[AGENDA-PDF] httpx %s -> HTTP %s (%s); trying browser",
                    url[:90], r.status_code, r.headers.get("content-type", ""))
    except Exception as e:
        logger.warning("[AGENDA-PDF] httpx failed %s: %s", url[:90], e)
    if "doceo" in url or "europarl.europa.eu" in url:
        return _fetch_pdf_via_browser(url)
    return None


def _fetch_pdf_via_browser(url: str) -> Optional[bytes]:
    """Clear the EP WAF (page.goto a europarl page sets the challenge cookie), then
    fetch the PDF in-page and return the raw bytes (base64 round-trip)."""
    import base64
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None
    js = (
        "async (u) => { const r = await fetch(u, {credentials:'include'}); "
        "if (!r.ok) return null; const a = await r.arrayBuffer(); "
        "const b = new Uint8Array(a); let s=''; "
        "for (let i=0;i<b.length;i++) s += String.fromCharCode(b[i]); return btoa(s); }"
    )
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            try:
                page = browser.new_page(user_agent=_UA)
                # Navigate to the PDF URL itself: the EP WAF challenge is keyed to
                # the /doceo/document path, so goto returns 202, the challenge JS
                # sets the cookie, then the in-page fetch of the same URL returns 200.
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
                data = page.evaluate(js, url)
                return base64.b64decode(data) if data else None
            finally:
                browser.close()
    except Exception as e:
        logger.warning("[AGENDA-PDF] browser fetch failed %s: %s", url[:90], e)
        return None


# ---- parse -----------------------------------------------------------------

def parse_agenda_pdf(pdf_bytes: bytes) -> Dict:
    """Parse a committee OJ PDF into {meeting_code, committee_code, sessions, items}."""
    lines = _extract_text(pdf_bytes)

    meeting_code = None
    committee_code = None
    for ln in lines[:25]:
        mc = _MEETING_CODE.search(ln)
        if mc:
            meeting_code = mc.group(1)
            committee_code = mc.group(1).split("(")[0]
            break

    sessions: List[Dict] = []
    items: List[Dict] = []
    cur_session_idx = -1
    cur_item: Optional[Dict] = None

    def _finish_item():
        nonlocal cur_item
        if cur_item:
            cur_item["title"] = re.sub(r"\s+", " ", cur_item["title"]).strip()
            cur_item["procedure_refs"] = [cur_item["procedure_ref"]] if cur_item.get("procedure_ref") else []
            items.append(cur_item)
        cur_item = None

    i = 0
    while i < len(lines):
        ln = lines[i]

        bm = _BLOCK.match(ln)
        if bm:
            _finish_item()
            d, mon, y, h1, m1, h2, m2 = bm.groups()
            try:
                sess_date = date(int(y), _MONTHS[mon.lower()], int(d))
                sessions.append({
                    "date": sess_date.isoformat(),
                    "start": f"{int(h1):02d}:{m1}",
                    "end": f"{int(h2):02d}:{m2}",
                })
                cur_session_idx = len(sessions) - 1
            except (ValueError, KeyError):
                pass
            i += 1
            continue

        im = _ITEM.match(ln)
        if im:
            _finish_item()
            sess = sessions[cur_session_idx] if 0 <= cur_session_idx < len(sessions) else {}
            cur_item = {
                "number": int(im.group(1)),
                "session_index": cur_session_idx,
                "session_date": sess.get("date"),
                "session_start": sess.get("start"),
                "title": im.group(2),
                "procedure_ref": None,
                "procedure_type": None,
                "doc_refs": [],
                "dossier_ref": None,
                "rapporteur": None,
                "responsible": [],
                "actions": [],
                "pe_docs": [],
            }
            i += 1
            continue

        if cur_item is not None:
            # accumulate title until the first metadata line
            if not _is_meta(ln) and not cur_item["procedure_ref"] and not cur_item["dossier_ref"] \
                    and not cur_item["actions"] and not cur_item["rapporteur"]:
                cur_item["title"] += " " + ln
                i += 1
                continue

            if _DOSSIER.match(ln):
                cur_item["dossier_ref"] = ln.strip()
            pm = _PROC.search(ln)
            if pm:
                cur_item["procedure_ref"] = pm.group(1)
                pt = _PTYPE.search(ln)
                if pt and pt.start() < pm.start():
                    cur_item["procedure_type"] = re.sub(r"\s+", "", pt.group(1))
            for cm in _COM.finditer(ln):
                ref = cm.group(1)
                if ref not in cur_item["doc_refs"]:
                    cur_item["doc_refs"].append(ref)
            for pd in _PEDOC.finditer(ln):
                tag = f"{pd.group(1)} - {pd.group(2)}"
                if tag not in cur_item["pe_docs"]:
                    cur_item["pe_docs"].append(tag)
            low = ln.lower()
            if low.startswith("rapporteur"):
                # name is usually the next non-meta line (may carry a trailing PE doc)
                if i + 1 < len(lines):
                    nm = re.split(r"\s{2,}|\bP[READ]\s*[–-]", lines[i + 1])[0].strip()
                    if nm and not _is_meta(lines[i + 1]):
                        cur_item["rapporteur"] = nm
            elif low.startswith("responsible"):
                # committee codes follow (this line and/or the next)
                for cand in (ln, lines[i + 1] if i + 1 < len(lines) else ""):
                    for code in re.findall(r"\b([A-Z]{3,5})\b", cand):
                        if code not in ("COM", "PE") and code not in cur_item["responsible"]:
                            cur_item["responsible"].append(code)
            am = _ACTION.match(ln)
            if am:
                cur_item["actions"].append(am.group(1).strip())

        i += 1

    _finish_item()

    return {
        "meeting_code": meeting_code,
        "committee_code": committee_code,
        "sessions": sessions,
        "items": items,
    }


# ---- discovery -------------------------------------------------------------

# Any OJ PDF link (redmap reference form OR doceo archive form).
_OJ_LINK = re.compile(
    r'href="(https?://[^"]*?/([A-Z]{2,6})-OJ-(\d{4})-(\d{2})-(\d{2})-\d+[^"]*?_(?:en|EN)\.pdf)"')


def _committee_url_path(committee_code: str) -> Optional[str]:
    try:
        from knowledge_base.ep_committees import EP_COMMITTEE_BY_CODE
        c = EP_COMMITTEE_BY_CODE.get(committee_code.upper())
        if c and getattr(c, "url_path", None):
            return c.url_path
    except Exception:
        pass
    return committee_code.lower()


def discover_agenda(committee_code: str, meeting_date: date) -> Optional[Dict]:
    """Find the OJ PDF URL for a committee meeting by reading its meeting-documents
    page (no WAF), then confirm by parsing that the OJ covers ``meeting_date``.

    Returns {url, parsed} or None.
    """
    path = _committee_url_path(committee_code)
    # meeting-documents = current meetings (redmap links, no WAF);
    # latest-documents  = months of archive (doceo links, WAF-walled PDFs).
    pages = [
        f"https://www.europarl.europa.eu/committees/en/{path}/meetings/meeting-documents",
        f"https://www.europarl.europa.eu/committees/en/{path}/documents/latest-documents",
    ]
    html = ""
    for page_url in pages:
        try:
            r = httpx.get(page_url, headers={"User-Agent": _UA}, follow_redirects=True, timeout=30)
            if r.status_code == 200:
                html += "\n" + r.text
        except Exception as e:
            logger.warning("[AGENDA-PDF] page fetch failed %s: %s", page_url, e)
    if not html:
        return None

    # Candidate OJ links whose filename start-date is near the meeting date.
    # Key by the OJ basename so we can prefer the redmap form over doceo (no WAF).
    by_oj: Dict[str, tuple] = {}
    for m in _OJ_LINK.finditer(html):
        url, code, y, mo, d = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
        if code.upper() != committee_code.upper():
            continue
        try:
            start = date(int(y), int(mo), int(d))
        except ValueError:
            continue
        delta = (meeting_date - start).days
        if not (-1 <= delta <= 4):   # OJ start date is the first day of a multi-day meeting
            continue
        oj_key = f"{code}-OJ-{y}-{mo}-{d}"
        is_redmap = "redmap" in url
        prev = by_oj.get(oj_key)
        # Prefer a redmap URL (no WAF) when the same OJ appears on both pages.
        if prev is None or (is_redmap and "redmap" not in prev[2]):
            by_oj[oj_key] = (abs(delta), start, url)

    candidates = sorted(by_oj.values())
    for _, _start, url in candidates:
        pdf = fetch_pdf(url)
        if not pdf:
            continue
        parsed = parse_agenda_pdf(pdf)
        sess_dates = {s.get("date") for s in parsed.get("sessions", [])}
        if meeting_date.isoformat() in sess_dates or not sess_dates:
            parsed["url"] = url
            return {"url": url, "parsed": parsed}
    logger.info("[AGENDA-PDF] no matching OJ for %s on %s (%d candidates)",
                committee_code, meeting_date, len(candidates))
    return None


def items_for_session(parsed: Dict, session_date: date, session_start: Optional[str] = None) -> List[Dict]:
    """Subset of agenda items belonging to the recording's session (date + clock).

    A multi-day OJ has several sessions; a recording corresponds to one. Match by
    date, and when several sessions share a date, by the closest start clock.
    """
    items = parsed.get("items", [])
    sessions = parsed.get("sessions", [])
    iso = session_date.isoformat()
    same_day = [s for s in sessions if s.get("date") == iso]
    if not same_day:
        return [it for it in items if it.get("session_date") == iso] or items

    target_idx = None
    if session_start and len(same_day) > 1:
        def _mins(hhmm):
            try:
                h, m = hhmm.split(":"); return int(h) * 60 + int(m)
            except Exception:
                return 0
        want = _mins(session_start)
        best = min(same_day, key=lambda s: abs(_mins(s.get("start", "00:00")) - want))
        target_idx = sessions.index(best)
    else:
        target_idx = sessions.index(same_day[0])

    return [it for it in items if it.get("session_index") == target_idx]
