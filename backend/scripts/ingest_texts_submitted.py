"""
Ingest "texts submitted" (committee reports tabled for plenary, not yet adopted)
into texts_adopted with adoption_date=NULL — the v1 /texts-submitted endpoint
filters precisely on that condition.

Source: https://www.europarl.europa.eu/plenary/en/texts-submitted.html

The page lists A-NN-YYYY-XXXX references with HTML/PDF/DOCX links. Each row
becomes a texts_adopted entry with:
  ta_reference   = "A10/{NNNN}/{YYYY}" (provisional reference until adoption)
  title          = derived from page (committee+procedure)
  procedure_ref  = parsed from page if available
  source_url     = doceo HTML
  full_text_url  = doceo HTML
  pdf_url        = doceo PDF
  adoption_date  = NULL  (THIS is what makes it appear in /texts-submitted)
"""

from __future__ import annotations

import argparse
import re
import sys
import urllib.request
from pathlib import Path

import psycopg2
import psycopg2.extras
from bs4 import BeautifulSoup


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
SOURCE_URL = "https://www.europarl.europa.eu/plenary/en/texts-submitted.html"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0)"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_html() -> str:
    req = urllib.request.Request(SOURCE_URL, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


# Match the canonical doceo URL form `A-{term}-{year}-{num}_EN.{ext}`.
# Anchored on `/A-` + `_EN.` so we DON'T accidentally pick up EP's internal
# `report-details.html?reference=A10-NNNN-YYYY` anchors — those use the
# inverted num-then-year order and would silently flip the year/num bindings.
A_REF = re.compile(r"/A-(\d{1,2})-(\d{4})-(\d{4})_EN\.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    print(f"[INFO] fetching {SOURCE_URL}")
    html = fetch_html()
    soup = BeautifulSoup(html, "html.parser")

    # Pull all doceo A-{term}-{year}-{num}_EN.{html,pdf,docx} links and infer
    # titles from surrounding text.
    rows = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = A_REF.search(href)
        if not m:
            continue
        term, year, num = m.group(1), m.group(2), m.group(3)
        ta_ref = f"A{term}/{year}/{num}"
        if ta_ref in seen:
            continue
        seen.add(ta_ref)
        # Title from the <a> text or the parent <li>/<tr> text
        title = a.get_text(" ", strip=True)
        if not title or title.lower() in ("html", "pdf", "docx"):
            parent = a.find_parent(["li", "tr", "td", "div"])
            if parent:
                title = parent.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title or f"Committee report tabled — {ta_ref}").strip()[:500]
        rows.append({
            "ta_reference": ta_ref,
            "title": title,
            "parliamentary_term": int(term),
            "source_url": f"https://www.europarl.europa.eu/doceo/document/A-{term}-{year}-{num}_EN.html",
            "full_text_url": f"https://www.europarl.europa.eu/doceo/document/A-{term}-{year}-{num}_EN.html",
            "pdf_url": f"https://www.europarl.europa.eu/doceo/document/A-{term}-{year}-{num}_EN.pdf",
        })

    print(f"[INFO] {len(rows)} unique A-references parsed")

    if not args.apply:
        for r in rows[:5]:
            print(f"  {r['ta_reference']}: {r['title'][:60]}")
        print("[NOTE] Dry-run — pass --apply to write to DB.")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        try:
            cur.execute("""
                INSERT INTO texts_adopted
                    (ta_reference, title, parliamentary_term, source_url, full_text_url, pdf_url,
                     adoption_date, scraped_at, last_updated)
                VALUES (%(ta_reference)s, %(title)s, %(parliamentary_term)s, %(source_url)s,
                        %(full_text_url)s, %(pdf_url)s, NULL, NOW(), NOW())
                ON CONFLICT (ta_reference) DO UPDATE SET
                    title = EXCLUDED.title,
                    source_url = EXCLUDED.source_url,
                    full_text_url = EXCLUDED.full_text_url,
                    pdf_url = EXCLUDED.pdf_url,
                    last_updated = NOW()
            """, r)
            inserted += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  [DB ERR] {r['ta_reference']}: {exc}")
            conn.rollback()
    conn.commit()
    print(f"[DONE] upserted {inserted} rows")


if __name__ == "__main__":
    main()
