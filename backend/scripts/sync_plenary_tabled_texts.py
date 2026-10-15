#!/usr/bin/env python3.12
"""Every report and motion tabled in plenary, from EP Open Data (15 Oct 2026).

Why: /api/v2/parliament/plenary-tabled-texts held 46 texts since July 2024 and served
document_date null on all of them. ingest_texts_submitted.py read Parliament's
"texts submitted" page, which lists only the current session, and the table kept no date.
EP Open Data lists every plenary document per year (/api/v2/plenary-documents?year=Y:
2025 alone has 272 reports and 228 motions in its first 500) and describes each one:
its date, title, procedure, rapporteur and committee, and the PDF, which its distribution
serves without the browser check that walls Parliament's own document site.

Reports (A) and motions for resolutions (B) of the 10th term. A text already held with its
date and text is not read again; a write changes only values that differ, so the change
signal (trigger) moves only when something did. The PDF's text is the body.

    python3.12 scripts/sync_plenary_tabled_texts.py --year 2026 --limit 5    # dry run
    python3.12 scripts/sync_plenary_tabled_texts.py --since-year 2024 --apply
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

API = "https://data.europarl.europa.eu/api/v2/plenary-documents"
BASE = "https://data.europarl.europa.eu/"
HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                         "(KHTML, like Gecko) Chrome/141.0 Safari/537.36",
           "Accept": "application/ld+json"}
_ID = re.compile(r"^([AB])-(10)-(\d{4})-(\d{4})$")
_PROC = re.compile(r"\b(\d{4}/\d{4}\([A-Z]{3}\))")
_RAPPORTEUR = re.compile(r"Rapporteurs?:\s*(.+?)\s*$")

HELD = text("""SELECT ta_reference FROM plenary_tabled_texts
                WHERE document_date IS NOT NULL AND coalesce(length(full_text), 0) >= 500""")
UPSERT = text("""
    INSERT INTO plenary_tabled_texts
        (id, ta_reference, title, text_type, procedure_ref, parliamentary_term, full_text,
         document_date, committees, rapporteur_name, rapporteur_mep_id, source_url,
         full_text_url, pdf_url, scraped_at, first_seen, last_updated)
    VALUES (gen_random_uuid(), :ref, :title, 'other', :proc, 10, :txt, :day, :committees,
            :rapporteur, :mep, :html, :html, :pdf, now(), now(), now())
    ON CONFLICT (ta_reference) DO UPDATE SET
        title = EXCLUDED.title,
        procedure_ref = coalesce(EXCLUDED.procedure_ref, plenary_tabled_texts.procedure_ref),
        full_text = CASE WHEN length(coalesce(EXCLUDED.full_text, '')) >= 500
                         THEN EXCLUDED.full_text ELSE plenary_tabled_texts.full_text END,
        document_date = EXCLUDED.document_date,
        committees = CASE WHEN cardinality(EXCLUDED.committees) > 0
                          THEN EXCLUDED.committees ELSE plenary_tabled_texts.committees END,
        rapporteur_name = coalesce(EXCLUDED.rapporteur_name, plenary_tabled_texts.rapporteur_name),
        rapporteur_mep_id = coalesce(EXCLUDED.rapporteur_mep_id, plenary_tabled_texts.rapporteur_mep_id),
        source_url = EXCLUDED.source_url,
        full_text_url = EXCLUDED.full_text_url,
        pdf_url = EXCLUDED.pdf_url,
        scraped_at = now()
    RETURNING (xmax = 0) AS inserted""")


def _get(url: str, accept: str | None = None, attempts: int = 3) -> bytes:
    h = dict(HEADERS)
    if accept:
        h["Accept"] = accept
    for n in range(attempts):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=60) as r:
                return r.read()
        except (urllib.error.URLError, TimeoutError):
            if n == attempts - 1:
                raise
            time.sleep(4 * (n + 1))
    return b""


def list_year(year: int) -> list[str]:
    """Every A- and B- identifier of the 10th term EP Open Data lists for a year."""
    ids, offset = [], 0
    while True:
        d = json.loads(_get(f"{API}?year={year}&format=application%2Fld%2Bjson&offset={offset}&limit=500"))
        rows = d.get("data") or []
        ids += [r["identifier"] for r in rows if _ID.match(r.get("identifier", ""))]
        if len(rows) < 500:
            return ids
        offset += 500


def reference_of(identifier: str) -> str:
    """'A-10-2025-0136' -> 'A10/2025/0136', the form the table already uses."""
    kind, term, year, num = _ID.match(identifier).groups()
    return f"{kind}{term}/{year}/{num}"


def describe(record: dict) -> dict:
    """The row's values from one EP Open Data record (no file read)."""
    identifier = record["identifier"]
    alt = ""
    title = (record.get("title_dcterms") or {}).get("en")
    pdf = None
    for e in record.get("is_realized_by") or []:
        if not str(e.get("language", "")).endswith("/ENG"):
            continue
        alt = ((e.get("title_alternative") or {}).get("en")) or alt
        title = ((e.get("title") or {}).get("en")) or title
        for m in e.get("is_embodied_by") or []:
            if str(m.get("format", "")).endswith("/PDF") and m.get("is_exemplified_by"):
                pdf = BASE + m["is_exemplified_by"]
    proc = _PROC.search(alt or "")
    rap = _RAPPORTEUR.search(alt or "")
    mep, committees = None, []
    for p in record.get("workHadParticipation") or []:
        role = str(p.get("participation_role", ""))
        if role.endswith("/RAPPORTEUR") and not mep:
            m = re.search(r"(\d+)$", str(p.get("id", "")))
            mep = m.group(1) if m else None
        org = str(p.get("participation_in_name_of", ""))
        # A report's author is its committee; a motion's is a political group, not a committee.
        if role.endswith("/AUTHOR") and org.startswith("org/") and identifier.startswith("A-"):
            committees.append(org[4:])
    day = record.get("document_date")
    html = f"https://www.europarl.europa.eu/doceo/document/{identifier}_EN.html"
    return {"ref": reference_of(identifier), "title": " ".join((title or identifier).split())[:500],
            "proc": proc.group(1) if proc else None, "day": date.fromisoformat(day[:10]) if day else None,
            "committees": sorted(set(committees)), "rapporteur": rap.group(1)[:200] if rap else None,
            "mep": mep, "html": html, "pdf": pdf or f"https://www.europarl.europa.eu/doceo/document/{identifier}_EN.pdf"}


def pdf_text(url: str) -> str | None:
    from pypdf import PdfReader
    try:
        raw = _get(url, accept="application/pdf")
        if raw[:4] != b"%PDF":
            return None
        txt = "\n".join((pg.extract_text() or "") for pg in PdfReader(io.BytesIO(raw)).pages)
    except Exception:  # noqa: BLE001
        return None
    txt = txt.replace("\x00", "").encode("utf-8", "ignore").decode("utf-8").strip()
    return txt or None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--since-year", type=int, default=date.today().year)
    ap.add_argument("--year", type=int, help="one year only")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="texts to read this run (0 = all)")
    ap.add_argument("--max-seconds", type=float, default=0)
    ap.add_argument("--pause", type=float, default=0.3)
    args = ap.parse_args(argv)
    years = [args.year] if args.year else list(range(max(args.since_year, 2024), date.today().year + 1))
    deadline = time.monotonic() + args.max_seconds if args.max_seconds else None

    engine = create_engine(os.environ["DATABASE_URL"], pool_pre_ping=True)
    with engine.connect() as c:
        held = {r[0] for r in c.execute(HELD)}
    todo = [i for y in years for i in list_year(y) if reference_of(i) not in held]
    if args.limit:
        todo = todo[:args.limit]
    print(f"[INFO] {years}: {len(todo)} tabled text(s) to read ({len(held)} held with date and text)")
    added = updated = no_text = failed = 0
    for n, identifier in enumerate(todo, 1):
        if deadline and time.monotonic() > deadline:
            print(f"[INFO] time budget reached; {len(todo) - n + 1} left for the next run")
            break
        try:
            rec = json.loads(_get(f"{API}/{identifier}?format=application%2Fld%2Bjson&language=en"))["data"][0]
        except Exception as exc:  # noqa: BLE001
            failed += 1
            print(f"  [{identifier}] record unreadable: {type(exc).__name__}")
            continue
        row = describe(rec)
        row["txt"] = pdf_text(row["pdf"])
        no_text += row["txt"] is None
        if not args.apply:
            if n <= 5:
                print(f"  {row['ref']} {row['day']} {row['proc']} {row['committees']} {row['rapporteur']} "
                      f"| {len(row['txt'] or '')} chars | {row['title'][:60]}")
            continue
        with engine.begin() as c:
            ins = c.execute(UPSERT, row).scalar()
        added += bool(ins)
        updated += not ins
        time.sleep(args.pause)
    print(f"[DONE] added {added}, updated {updated}; PDF without text {no_text}; records unreadable {failed}"
          + ("" if args.apply else " (DRY RUN)"))
    if todo and failed == len(todo):
        print("[ERROR] EP Open Data answered none of the records")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
