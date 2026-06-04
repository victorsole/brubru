"""
Backfill real titles for committee_work_items rows left with a scraper-junk title.

The committee "Work in Progress" scraper often captured page chrome instead of a
real title, e.g.
  "***I Ordinary legislative procedure (COD) first reading AGRI ENVI"
  "Delegated acts (DEA) ENVI"
  "Procedure File: 2025/2880(RSP)"
Migration 094 fixed the 152 rows linked to a carriage; this script resolves the
rest from the OEIL *search* listing (which carries the real title in
`div.es_document-body > p`), reusing the repo Playwright WAF fetcher.

Dedupes by procedure_ref (one fetch per procedure, applied to every committee row
that shares it). Substantive procedures (COD/CNS/APP/INI/INL/NLE/BUD/...) are
resolved before technical scrutiny (DEA/RPS) so the user-visible cards improve first.

Usage:
    python3.12 -m backend.scripts.backfill_committee_titles_from_oeil --limit 3   # dry-run sample
    python3.12 -m backend.scripts.backfill_committee_titles_from_oeil --apply     # full run
"""

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # backend/ on path

from core.database import SessionLocal
from models.committee_work import CommitteeWorkItem
from services.scrapers.waf_browser_fetcher import WafBrowserFetcher

BODY_P_RE = re.compile(r'class="es_document-body"[^>]*>\s*<p[^>]*>(.*?)</p>', re.S)
JUNK_RES = [
    re.compile(r"^\s*\*+"),                                       # "***I ..."
    re.compile(r"ordinary legislative procedure|first reading|second reading", re.I),
    re.compile(r"\([A-Z]+\)\s+[A-Z]{3,4}\s*$"),                   # "(DEA) ENVI"
    re.compile(r"^\s*procedure file:", re.I),
]
TECHNICAL = {"DEA", "RPS", "IMM", "REG", "RSO", "GBD", "BUI", "ACI", "COS", "DCE"}


def is_junk(title: str) -> bool:
    t = (title or "").strip()
    return (not t) or any(r.search(t) for r in JUNK_RES)


def _search_url(ref: str) -> str:
    return f"https://oeil.europarl.europa.eu/oeil/en/search?fullText.term={quote(ref, safe='')}&fullText.mode=EXACT_WORD"


def parse_title_for_ref(html: str, ref: str) -> str | None:
    for fragment in html.split('<div class="es_document">')[1:]:
        if ref not in fragment:
            continue
        m = BODY_P_RE.search(fragment)
        if not m:
            continue
        title = re.sub(r"<[^>]+>", "", m.group(1))
        title = re.sub(r"\s+", " ", title).strip()
        if title and not is_junk(title) and len(title) >= 8:
            return title
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill committee_work_items titles from OEIL search.")
    parser.add_argument("--apply", action="store_true", help="Persist changes (default dry-run).")
    parser.add_argument("--limit", type=int, default=0, help="Only process N distinct refs (0 = all).")
    parser.add_argument("--delay", type=float, default=0.6, help="Seconds between fetches.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        rows = db.query(CommitteeWorkItem).all()
        junk_rows = [r for r in rows if is_junk(r.title)]

        # Group junk rows by procedure_ref; substantive types first.
        by_ref: dict[str, list] = {}
        for r in junk_rows:
            by_ref.setdefault(r.procedure_ref, []).append(r)
        refs = sorted(
            by_ref.keys(),
            key=lambda ref: (1 if (by_ref[ref][0].procedure_type in TECHNICAL) else 0, ref),
        )
        if args.limit:
            refs = refs[: args.limit]
        print(f"[INFO] {len(junk_rows)} junk rows across {len(by_ref)} refs; processing {len(refs)}.")

        recovered_refs = recovered_rows = 0
        failed: list[str] = []
        with WafBrowserFetcher() as f:
            for i, ref in enumerate(refs, 1):
                try:
                    res = f.fetch(_search_url(ref), expand_accordions=False)
                    title = parse_title_for_ref(res.html or "", ref)
                except Exception as exc:
                    title = None
                    print(f"  [{i}/{len(refs)}] {ref}: fetch error {type(exc).__name__}")
                if title:
                    n = len(by_ref[ref])
                    print(f"  [{i}/{len(refs)}] {ref} ({n} row/s) -> {title[:80]}")
                    if args.apply:
                        for r in by_ref[ref]:
                            r.title = title
                    recovered_refs += 1
                    recovered_rows += n
                else:
                    failed.append(ref)
                    print(f"  [{i}/{len(refs)}] {ref}: no title found")
                if args.apply and recovered_refs and recovered_refs % 15 == 0:
                    db.commit()
                time.sleep(args.delay)

        if args.apply:
            db.commit()
            print(f"[OK] Resolved {recovered_refs} refs / {recovered_rows} rows. {len(failed)} unresolved.")
        else:
            print(f"[DRY-RUN] Would resolve {recovered_refs} refs / {recovered_rows} rows. {len(failed)} unresolved. Re-run with --apply.")
        if failed:
            print("  unresolved:", ", ".join(failed[:15]), ("..." if len(failed) > 15 else ""))
    finally:
        db.close()


if __name__ == "__main__":
    main()
