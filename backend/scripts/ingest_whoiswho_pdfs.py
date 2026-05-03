"""
Ingest the Publications Office EU Whoiswho PDFs into eu_officials.

Source: https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_{INST}_EN.pdf
Updated quarterly. The PDFs are the canonical authoritative directory of
EU officials — the JSON-LD scrape Brubru was using captured filter-bar
labels and address lines as if they were people.

Institutions covered (15 PDFs):
  EP, EURCOU, CONSIL, COM, CURIA, ECB, ECA, EEAS, EESC, COR,
  EIB, EIF, OMB, EDPS, AGEN_OTH

Run:
    python3.12 backend/scripts/ingest_whoiswho_pdfs.py                    # dry-run, all institutions
    python3.12 backend/scripts/ingest_whoiswho_pdfs.py --apply
    python3.12 backend/scripts/ingest_whoiswho_pdfs.py --apply --inst OMB
    python3.12 backend/scripts/ingest_whoiswho_pdfs.py --apply --replace  # wipe old rows first
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import time
import unicodedata
import urllib.request
import uuid
from pathlib import Path
from typing import Dict, Iterable, List, Optional

import psycopg2
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/126.0.0.0"

INSTITUTIONS: Dict[str, Dict[str, str]] = {
    "EP":       {"slug": "european-parliament",            "label": "European Parliament"},
    "EURCOU":   {"slug": "european-council",               "label": "European Council"},
    "CONSIL":   {"slug": "council-of-the-eu",              "label": "Council of the EU"},
    "COM":      {"slug": "european-commission",            "label": "European Commission"},
    "CURIA":    {"slug": "court-of-justice",               "label": "Court of Justice of the EU"},
    "ECB":      {"slug": "european-central-bank",          "label": "European Central Bank"},
    "ECA":      {"slug": "european-court-of-auditors",     "label": "European Court of Auditors"},
    "EEAS":     {"slug": "eeas",                           "label": "European External Action Service"},
    "EESC":     {"slug": "european-economic-and-social-committee", "label": "Economic and Social Committee"},
    "COR":      {"slug": "committee-of-the-regions",       "label": "Committee of the Regions"},
    "EIB":      {"slug": "european-investment-bank",       "label": "European Investment Bank"},
    "EIF":      {"slug": "european-investment-fund",       "label": "European Investment Fund"},
    "OMB":      {"slug": "european-ombudsman",             "label": "European Ombudsman"},
    "EDPS":     {"slug": "edps",                           "label": "European Data Protection Supervisor"},
    "AGEN_OTH": {"slug": "agencies-and-other-bodies",      "label": "EU Agencies and Other Bodies"},
}


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


# ───────────────────────── Parser ─────────────────────────────────────────

# Person row: optional title (Mr/Ms/...) + first name(s) + UPPERCASE surname.
# Names tolerate diacritics (À-ÿ), apostrophes, hyphens, dots (M. for short).
_TITLE = r"(?:Mr|Ms|Mrs|Dr|Mme|M\.|Mr\.|Ms\.)"
# Given name = capital-first AND must contain at least one lowercase letter
# (rejects "OF", "THE" etc that would otherwise sneak through). Allow short
# initials ("M.", "S."): one capital letter followed by a period.
_GIVEN_NAME = (
    r"(?:"
    r"[A-ZÀ-Þ]\.\s*"                                           # M. (initial)
    r"|[A-ZÀ-Þ][a-zà-ÿ][A-Za-zÀ-ÿ\.\-']*"                       # Capitalised
    r")"
)
# Family name = ALL UPPERCASE, ≥ 2 chars, may be multi-word (BARROS VALE) or
# hyphenated (HIRSCH-ZIEMBIŃSKA).
_FAMILY = r"[A-ZÀ-Þ][A-ZÀ-Þ\-'\.]{1,}(?:\s+[A-ZÀ-Þ][A-ZÀ-Þ\-'\.]{1,})*"

PERSON_RE = re.compile(
    rf"^\s*({_TITLE})?\s*"
    rf"({_GIVEN_NAME}(?:\s+{_GIVEN_NAME})*?)"
    rf"\s{{1,3}}"
    rf"({_FAMILY})\s*$"
)

# Reject common false positives — uppercase-looking phrases that aren't names.
_NOT_A_NAME = (
    "OF THE EUROPEAN", "EUROPEAN UNION", "EUROPEAN OMBUDSMAN",
    "EUROPEAN COMMISSION", "EUROPEAN PARLIAMENT", "EUROPEAN COUNCIL",
    "OFFICIAL DIRECTORY", "EU WHOISWHO", "DIRECTORATE-GENERAL",
    "SECRETARIAT-GENERAL", "DIRECTORATE FOR", "CABINET OF",
    "STRASBOURG CEDEX", "LUXEMBOURG", "BRUSSELS", "FRANKFURT",
)

EMAIL_RE = re.compile(r"\b([A-Za-z][\w\.\-]*@[\w\.\-]+\.[A-Za-z]{2,})\b")
PHONE_RE = re.compile(r"(?:^|\b)(?:Tel\.?|Phone)\s*[:\-]?\s*([+\d][\d\s\-\(\)\.]{6,})")
FAX_RE = re.compile(r"(?:^|\b)Fax\.?\s*[:\-]?\s*([+\d][\d\s\-\(\)\.]{6,})")
COUNTRY_LINE_RE = re.compile(r"^\s*([A-Z]{2,}(?:\s+[A-Z]{2,})*)\s*$")


# Lines that are NEVER person rows — header artifacts that pypdf extracts.
NON_PERSON_PATTERNS = (
    re.compile(r"^EUROPEAN UNION", re.IGNORECASE),
    re.compile(r"^EU WHOISWHO", re.IGNORECASE),
    re.compile(r"^OFFICIAL DIRECTORY", re.IGNORECASE),
    re.compile(r"^Reproduction is authorised"),
    re.compile(r"^©\s*European Union"),
    re.compile(r"^Tel\.|^Fax|^Phone"),
    re.compile(r"^Note to the reader"),
    re.compile(r"^The personal data"),
    re.compile(r"^Managed by the Publications"),
    re.compile(r"^Rue\s|^Avenue|^Boulevard|^Bvd|^Bd"),  # addresses
    re.compile(r"^\d{4,5}\s+(Bruxelles|Brussel|Strasbourg|Luxembourg|Frankfurt)"),
    re.compile(r"^\([Pp]ostal "),
    re.compile(r"^FOP engine"),
    re.compile(r"^FRANCE$|^BELGIUM$|^LUXEMBOURG$|^GERMANY$"),
)


def _is_person_line(line: str) -> Optional[re.Match]:
    line = line.strip()
    if not line or len(line) > 120:
        return None
    if any(p.match(line) for p in NON_PERSON_PATTERNS):
        return None
    upper = line.upper()
    if any(needle in upper for needle in _NOT_A_NAME):
        return None
    m = PERSON_RE.match(line)
    if not m:
        return None
    given, family = m.group(2).strip(), m.group(3).strip()
    # Sanity: the given-name half must contain at least one lowercase letter
    # (rejects all-caps phrases that the regex's permissive star quantifier
    # might still allow through).
    if not any(c.islower() for c in given):
        return None
    # Family-name half must not be a multi-word phrase longer than 4 tokens
    # (rejects "OF THE EUROPEAN UNION" style false positives).
    if len(family.split()) > 4:
        return None
    return m


def _slug(s: str, max_len: int = 60) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = s.encode("ascii", "ignore").decode("ascii").lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s[:max_len]


def parse_pdf(pdf_bytes: bytes, institution_slug: str) -> List[Dict[str, object]]:
    """Walk the PDF text top-to-bottom and emit one record per detected
    person row, capturing the role line that follows and any email / phone
    in the surrounding ~6 lines.
    """
    reader = PdfReader(io.BytesIO(pdf_bytes))
    text = "\n".join((p.extract_text() or "").replace("\x00", "") for p in reader.pages)
    lines = [ln.strip() for ln in text.splitlines()]
    rows: List[Dict[str, object]] = []
    seen_slugs = set()

    n = len(lines)
    for i, line in enumerate(lines):
        m = _is_person_line(line)
        if not m:
            continue
        title, given, family = m.group(1), m.group(2).strip(), m.group(3).strip()
        # Normalise the name: collapse internal whitespace.
        given = re.sub(r"\s+", " ", given)
        family = re.sub(r"\s+", " ", family)
        full_name = f"{given} {family}".strip()
        if len(full_name) < 4 or len(full_name) > 80:
            continue

        # Walk ahead up to 6 lines to find role + email + phone, stopping at
        # the next person row or section header.
        role: Optional[str] = None
        email: Optional[str] = None
        phone: Optional[str] = None
        for j in range(i + 1, min(i + 7, n)):
            nxt = lines[j].strip()
            if not nxt:
                continue
            if _is_person_line(nxt):
                break
            em = EMAIL_RE.search(nxt)
            if em and not email:
                email = em.group(1)[:200]
                continue
            pm = PHONE_RE.search(nxt)
            if pm and not phone:
                phone = re.sub(r"\s+", " ", pm.group(1)).strip()[:50]
                continue
            # Skip address lines / country-code stubs
            if re.match(r"^\d{4,5}\s+", nxt) or re.match(r"^Rue\b|^Avenue\b", nxt):
                continue
            if COUNTRY_LINE_RE.match(nxt) and len(nxt) <= 25:
                # Likely "FRANCE" / "BELGIUM" / ALL-CAPS country
                continue
            if not role and not nxt.startswith(("Tel", "Fax", "Phone", "Email", "http", "www.")):
                role = nxt[:300]

        slug_base = _slug(full_name)
        slug = f"{slug_base}-{institution_slug}"[:200]
        # De-dupe within a single PDF
        if slug in seen_slugs:
            continue
        seen_slugs.add(slug)

        rows.append({
            "id": str(uuid.uuid4()),
            "slug": slug,
            "name": full_name[:200],
            "title": title or None,
            "role": role,
            "institution_slug": institution_slug,
            "email": email,
            "phone": phone,
            "is_active": True,
        })

    return rows


# ───────────────────────── DB ─────────────────────────────────────────────

def fetch_pdf(inst: str) -> bytes:
    url = f"https://op.europa.eu/webpub/wiw/pdf/EUWhoiswho_{inst}_EN.pdf"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def upsert_rows(conn, rows: List[Dict[str, object]], institution_slug: str, replace: bool) -> int:
    cur = conn.cursor()
    if replace:
        cur.execute(
            "DELETE FROM eu_officials WHERE institution_slug = %s",
            (institution_slug,),
        )
        print(f"  wiped {cur.rowcount} old rows for {institution_slug}")

    inserted = 0
    for r in rows:
        try:
            cur.execute(
                """
                INSERT INTO eu_officials
                  (id, slug, name, title, role, institution_slug, email, phone,
                   is_active, scraped_at, first_seen, last_updated)
                VALUES
                  (%(id)s, %(slug)s, %(name)s, %(title)s, %(role)s, %(institution_slug)s,
                   %(email)s, %(phone)s, %(is_active)s, NOW(), NOW(), NOW())
                ON CONFLICT (slug) DO UPDATE SET
                  name = EXCLUDED.name,
                  title = EXCLUDED.title,
                  role = EXCLUDED.role,
                  email = EXCLUDED.email,
                  phone = EXCLUDED.phone,
                  is_active = EXCLUDED.is_active,
                  last_updated = NOW()
                """,
                r,
            )
            inserted += 1
        except Exception as exc:
            print(f"    [ERR] {r['slug']}: {exc}")
            conn.rollback()
        if inserted % 200 == 0 and inserted > 0:
            conn.commit()
    conn.commit()
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--replace", action="store_true",
                    help="Delete existing rows for each institution before re-ingesting (recommended)")
    ap.add_argument("--inst", choices=list(INSTITUTIONS.keys()) + ["all"], default="all")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    targets: Iterable[str] = INSTITUTIONS if args.inst == "all" else [args.inst]
    conn = psycopg2.connect(db_url) if args.apply else None

    grand_total = 0
    for inst in targets:
        meta = INSTITUTIONS[inst]
        print(f"\n[INFO] {inst} ({meta['label']}) — fetching…")
        try:
            pdf_bytes = fetch_pdf(inst)
        except Exception as exc:
            print(f"  [ERR] fetch failed: {exc}")
            continue
        print(f"  size: {len(pdf_bytes):,} bytes")
        rows = parse_pdf(pdf_bytes, meta["slug"])
        print(f"  parsed: {len(rows)} person rows")
        if rows:
            for r in rows[:3]:
                print(f"    {r['title'] or '':3s} {r['name']:35s} role={(r['role'] or '')[:40]}")
        if args.apply and rows:
            inserted = upsert_rows(conn, rows, meta["slug"], replace=args.replace)
            print(f"  upserted: {inserted}")
            grand_total += inserted

    # Final cleanup: with --replace, wipe any rows under institution slugs
    # that aren't covered by the 15 Whoiswho PDFs we ingested. The original
    # JSON-LD scrape had created per-agency slugs (frontex, eige, era, ...)
    # for officials that are now covered by the AGEN_OTH PDF under the
    # canonical 'agencies-and-other-bodies' slug. Without this cleanup, the
    # /officials endpoint would carry both the old junk rows and the new
    # clean rows side-by-side.
    if args.apply and args.replace and args.inst == "all" and conn is None:
        conn = psycopg2.connect(db_url)
    if args.apply and args.replace and args.inst == "all" and conn:
        canonical_slugs = tuple(meta["slug"] for meta in INSTITUTIONS.values())
        cur = conn.cursor()
        cur.execute(
            "DELETE FROM eu_officials WHERE institution_slug NOT IN %s",
            (canonical_slugs,),
        )
        print(f"  wiped {cur.rowcount} rows under non-canonical institution slugs")
        conn.commit()

    if conn:
        conn.close()
    print(f"\n[DONE] total upserted across institutions: {grand_total}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
