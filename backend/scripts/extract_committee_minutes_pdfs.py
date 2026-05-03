"""
Backfill extracted PDF content for EP committee minutes.

Iterates rows in `committee_minutes` where pdf_url IS NOT NULL AND has_full_text = FALSE,
downloads the PDF, parses agenda items + attendees + decisions, and writes back.

Run:
    python3.12 backend/scripts/extract_committee_minutes_pdfs.py            # dry-run, 3 rows
    python3.12 backend/scripts/extract_committee_minutes_pdfs.py --apply    # write to DB
    python3.12 backend/scripts/extract_committee_minutes_pdfs.py --apply --limit 200
    python3.12 backend/scripts/extract_committee_minutes_pdfs.py --apply --committee ECON
    python3.12 backend/scripts/extract_committee_minutes_pdfs.py --pdf-url <url>   # one-shot test

The structure of EP committee minutes is consistent across committees:
  page 1+ : header, then numbered agenda items (1. ... 2. ... etc.), each may include
            an OEIL procedure ref like 2024/0089(COD), an internal committee dossier
            ref ECON_OJ(2026)0209_1, and an optional "Speakers:" line.
  later   : "RECORD OF ATTENDANCE" multilingual header, then Bureau / Members /
            Substitutes / Council / Commission / Other / Pol-group secretariats /
            DG / etc. blocks with comma-separated names.
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import psycopg2
import psycopg2.extras
from pypdf import PdfReader


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0)"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_pdf(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


# Markers that signal "end of agenda body, start of attendance list" — multilingual.
ATTENDANCE_MARKERS = (
    "RECORD OF ATTENDANCE",
    "ПРИСЪСТВЕН ЛИСТ",
    "LISTA DE ASISTENCIA",
    "LISTE DE PRÉSENCE",
    "PRESENTIELIJST",
)

# Section headers inside the attendance list — first English token of each block.
SECTION_HEADER_HINTS = {
    "BUREAU": ("Бюро/Mesa/", "Bureau"),
    "MEMBERS": ("Членове/Diputados/", "Members"),
    "SUBSTITUTES": ("Заместници/Suplentes/", "Substitutes"),
    "INVITATION": ("По покана", "invitation of the Chair"),
    "COUNCIL": ("Съвет/Consejo/", "Council"),
    "COMMISSION": ("Комисия/Comisión/", "Commission"),
    "OTHER_BODIES": ("Други институции", "Other institutions"),
    "POL_GROUP_SEC": ("Секретариат на политическите", "Secretariats of political groups"),
    "PRESIDENT_OFFICE": ("Кабинет на председателя", "President's Office"),
    "SG_OFFICE": ("Кабинет на генералния", "Secretary-General's Office"),
    "DG": ("Генерална дирекция", "Directorate-General"),
}

PROCEDURE_REF_RE = re.compile(r"\b(\d{4}/\d{4}\(\w+\))")
INTERNAL_REF_RE = re.compile(r"\b([A-Z]{3,5}_(?:OJ|PV|AD|AM|PR)\(\d{4}\)[\w\-]+)")
# Matches numbered agenda items like "1. Adoption of agenda" tolerating
# pdf-extraction artifacts where a page-footer language code ("EN") is glued
# to the next item — e.g. "EN4. Any other business".
AGENDA_ITEM_RE = re.compile(r"(?:^|EN)\s*(\d{1,2})\.\s+([^\n]+)", re.MULTILINE)
DECISION_PATTERNS = (
    re.compile(r"\bThe (?:agenda|report|opinion|amendments?|motion|draft\s+\w+) was (adopted|rejected|approved|withdrawn|noted)\b", re.IGNORECASE),
    re.compile(r"\b(?:adopted|rejected|approved) (?:by|with) (\d+) (?:votes? )?(?:in favour|against|to)", re.IGNORECASE),
    re.compile(r"\bDecision:\s*(.+?)(?:\.|$)", re.IGNORECASE),
)
VOTE_TALLY_RE = re.compile(
    r"(\d{1,3})\s*(?:in favour|for|pour|à favor|für)\s*[,;]?\s*"
    r"(\d{1,3})\s*(?:against|contre|en contra|gegen)\s*[,;]?\s*"
    r"(\d{1,3})\s*(?:abstentions?|abstenciones|enthaltungen)",
    re.IGNORECASE,
)


def extract_text(pdf_bytes: bytes) -> Tuple[str, int]:
    """Return (full_text, page_count). NUL-byte safe."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    pages = []
    for p in reader.pages:
        try:
            t = p.extract_text() or ""
        except Exception:
            t = ""
        pages.append(t)
    full = "\n".join(pages).replace("\x00", "")
    return full, len(reader.pages)


def split_agenda_and_attendance(full_text: str) -> Tuple[str, str]:
    """Split text into (agenda_body, attendance_block)."""
    cut = -1
    for marker in ATTENDANCE_MARKERS:
        idx = full_text.find(marker)
        if idx > 0 and (cut == -1 or idx < cut):
            cut = idx
    if cut < 0:
        return full_text, ""
    return full_text[:cut], full_text[cut:]


def parse_agenda_items(agenda_body: str) -> List[Dict[str, Any]]:
    """Extract numbered agenda items with optional procedure_ref and outcome hints."""
    items: List[Dict[str, Any]] = []
    matches = list(AGENDA_ITEM_RE.finditer(agenda_body))
    for i, m in enumerate(matches):
        number = int(m.group(1))
        title = m.group(2).strip()
        # Body of the agenda item runs from end-of-match to start of next match.
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(agenda_body)
        body = agenda_body[body_start:body_end].strip()
        proc_match = PROCEDURE_REF_RE.search(body) or PROCEDURE_REF_RE.search(title)
        procedure_ref = proc_match.group(1) if proc_match else None
        internal_match = INTERNAL_REF_RE.search(body) or INTERNAL_REF_RE.search(title)
        internal_ref = internal_match.group(1) if internal_match else None
        outcome = None
        for pat in DECISION_PATTERNS:
            mm = pat.search(body)
            if mm:
                outcome = mm.group(0).strip()[:300]
                break
        items.append({
            "number": number,
            "title": title[:500],
            "procedure_ref": procedure_ref,
            "internal_ref": internal_ref,
            "outcome": outcome,
        })
    return items


def parse_attendees_count(attendance_block: str) -> Optional[int]:
    """
    Count distinct named attendees in Bureau + Members + Substitutes sections.

    Strategy: locate the "Members" multilingual header (Členове/Diputados/...),
    take the next non-header lines until the "Substitutes" header, split by
    commas and 'and', count tokens that look like person names (>= 2 capitalised words).
    Apply the same to Bureau and Substitutes. Sum the three.
    """
    if not attendance_block:
        return None

    def extract_names_between(start_token: str, end_token: Optional[str]) -> List[str]:
        # Find the multilingual header block by start_token, jump past the header
        # block (which spans many lines of slash-separated translations), then
        # collect names until end_token or a blank line.
        i = attendance_block.find(start_token)
        if i < 0:
            return []
        # Header blocks end at the first non-translation line (not containing '/')
        # OR at "(*)" terminator.
        rest = attendance_block[i:]
        # Skip lines that look like header (contain many '/' or all-caps with slashes)
        lines = rest.splitlines()
        names_lines: List[str] = []
        in_names = False
        for line in lines[1:]:  # skip the line that starts with start_token itself
            stripped = line.strip()
            if not stripped:
                if in_names:
                    break
                continue
            if end_token and end_token in stripped:
                break
            # Heuristic: header lines have many '/' or end with '(*)'
            if stripped.endswith("(*)") or stripped.count("/") >= 3:
                continue
            in_names = True
            names_lines.append(stripped)
        joined = " ".join(names_lines)
        # Names are comma-separated; some lines also contain numbers like "216 (7)"
        # for substitutes' agenda-item lookups — skip pure-number tokens.
        tokens = re.split(r",| and ", joined)
        names: List[str] = []
        for t in tokens:
            t = t.strip()
            if not t:
                continue
            # Skip tokens that are just numbers/bracketed counts
            if re.fullmatch(r"\d+(?:\s*\(\d+\))?", t):
                continue
            # Strip parenthetical (P ECON), (2nd VP ECON), etc.
            t = re.sub(r"\s*\([^)]*\)\s*", "", t).strip()
            if not t:
                continue
            # Must contain at least one letter and a space (a person name has
            # at least two parts), or be a single recognisable surname token.
            if re.search(r"[A-Za-zÀ-ÿ]", t):
                names.append(t)
        return names

    bureau_names = extract_names_between("Бюро/Mesa/", "Членове/")
    members_names = extract_names_between("Членове/Diputados/", "Заместници/")
    substitutes_names = extract_names_between("Заместници/Suplentes/", "По покана")

    total = len({n.lower() for n in bureau_names + members_names + substitutes_names})
    return total if total > 0 else None


def parse_decisions(full_text: str) -> List[Dict[str, Any]]:
    """Extract decision/vote lines from the full text."""
    decisions: List[Dict[str, Any]] = []
    seen: set = set()
    for pat in DECISION_PATTERNS:
        for m in pat.finditer(full_text):
            text = m.group(0).strip()
            if text.lower() in seen:
                continue
            seen.add(text.lower())
            decisions.append({"text": text[:500], "type": "decision"})
    for m in VOTE_TALLY_RE.finditer(full_text):
        decisions.append({
            "text": m.group(0).strip()[:500],
            "type": "vote",
            "for": int(m.group(1)),
            "against": int(m.group(2)),
            "abstain": int(m.group(3)),
        })
    return decisions


def parse_minutes_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    full_text, page_count = extract_text(pdf_bytes)
    word_count = len(full_text.split())
    agenda_body, attendance_block = split_agenda_and_attendance(full_text)
    agenda_items = parse_agenda_items(agenda_body)
    attendees_count = parse_attendees_count(attendance_block)
    decisions = parse_decisions(full_text)

    quality = "low"
    if agenda_items and attendees_count and page_count >= 3:
        quality = "high"
    elif agenda_items or attendees_count:
        quality = "medium"

    return {
        "full_text": full_text,
        "word_count": word_count,
        "page_count": page_count,
        "agenda_items": agenda_items,
        "attendees_count": attendees_count,
        "decisions": decisions,
        "votes": [d for d in decisions if d.get("type") == "vote"],
        "extraction_quality": quality,
    }


def fetch_rows(cur, limit: int, committee: Optional[str]) -> List[Dict[str, Any]]:
    sql = """
        SELECT id::text AS id, committee_code, meeting_date, pdf_url, doc_url
        FROM committee_minutes
        WHERE pdf_url IS NOT NULL
          AND (has_full_text IS NULL OR has_full_text = FALSE)
    """
    params: List[Any] = []
    if committee:
        sql += " AND committee_code = %s"
        params.append(committee.upper())
    sql += " ORDER BY meeting_date DESC LIMIT %s"
    params.append(limit)
    cur.execute(sql, params)
    cols = [d[0] for d in cur.description]
    return [dict(zip(cols, row)) for row in cur.fetchall()]


def upsert_extraction(conn, row_id: str, parsed: Dict[str, Any]) -> None:
    cur = conn.cursor()
    cur.execute(
        """
        UPDATE committee_minutes
           SET full_text = %s,
               word_count = %s,
               page_count = %s,
               has_full_text = TRUE,
               extraction_quality = %s,
               agenda_items = %s::jsonb,
               votes = %s::jsonb,
               decisions = %s::jsonb,
               attendees_count = %s,
               last_updated = NOW()
         WHERE id = %s
        """,
        (
            parsed["full_text"],
            parsed["word_count"],
            parsed["page_count"],
            parsed["extraction_quality"],
            psycopg2.extras.Json(parsed["agenda_items"]),
            psycopg2.extras.Json(parsed["votes"]),
            psycopg2.extras.Json(parsed["decisions"]),
            parsed["attendees_count"],
            row_id,
        ),
    )
    cur.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="Write extraction back to DB")
    ap.add_argument("--limit", type=int, default=3, help="Max rows to process (default 3 for dry-run)")
    ap.add_argument("--committee", default=None, help="Filter by committee code (e.g. ECON)")
    ap.add_argument("--pdf-url", default=None, help="One-shot: parse a single PDF URL and print result")
    args = ap.parse_args()

    if args.pdf_url:
        print(f"[INFO] one-shot parse: {args.pdf_url}")
        parsed = parse_minutes_pdf(fetch_pdf(args.pdf_url))
        print(f"  pages: {parsed['page_count']}")
        print(f"  words: {parsed['word_count']}")
        print(f"  agenda_items: {len(parsed['agenda_items'])}")
        for it in parsed['agenda_items'][:6]:
            print(f"    {it['number']:>2}. {it['title'][:80]}  proc={it['procedure_ref']}  outcome={(it.get('outcome') or '')[:60]}")
        print(f"  attendees_count: {parsed['attendees_count']}")
        print(f"  decisions: {len(parsed['decisions'])}")
        for d in parsed['decisions'][:5]:
            print(f"    [{d['type']}] {d['text'][:120]}")
        print(f"  quality: {parsed['extraction_quality']}")
        return

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    rows = fetch_rows(cur, args.limit, args.committee)
    cur.close()
    print(f"[INFO] {len(rows)} rows to process (apply={args.apply})")

    ok = 0
    failed = 0
    for r in rows:
        url = r["pdf_url"] or r["doc_url"]
        if not url:
            continue
        try:
            pdf_bytes = fetch_pdf(url)
            parsed = parse_minutes_pdf(pdf_bytes)
            print(
                f"  [{r['committee_code']}] {r['meeting_date']} "
                f"pages={parsed['page_count']} agenda={len(parsed['agenda_items'])} "
                f"attendees={parsed['attendees_count']} decisions={len(parsed['decisions'])} "
                f"quality={parsed['extraction_quality']}"
            )
            if args.apply:
                upsert_extraction(conn, r["id"], parsed)
                conn.commit()
            ok += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [ERR] {r['committee_code']} {r['meeting_date']}: {exc}")
            failed += 1
            if args.apply:
                conn.rollback()

    conn.close()
    print(f"[DONE] ok={ok} failed={failed}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
