"""
Ingest RSB opinions from commission.europa.eu /publications/ pages.

NO CURATED SEED. Crawls the RSB opinions index, extracts every
/publications/ link, then fetches each publication page to harvest:
  - title (from <meta property="og:title">)
  - rsb-opinion PDF (from /document/download/{uuid}?filename=rsb-...)
  - evaluation date (best-effort from filename year)

Stored row's source_url is the /publications/{slug}_en page (row-specific).
"""

import argparse
import datetime as dt
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def get_env(k):
    env = ROOT / ".env"
    if not env.exists():
        return ""
    for line in env.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


INDEX_URL = "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/regulatory-scrutiny-board-opinions-evaluations-and-fitness-checks_en"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruRSBScraper/1.0; +https://brubru.beresol.eu)"


def http_get(url, timeout=30):
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, b""
    except Exception:
        return 0, b""


def extract_publication_slugs(html):
    text = html.decode("utf-8", errors="replace")
    return sorted(set(re.findall(r'href="(/publications/[^"]+_en)"', text)))


def parse_publication_page(html, source_url):
    if not html:
        return None
    text = html.decode("utf-8", errors="replace")
    m_title = re.search(r'<meta\s+property="og:title"\s+content="([^"]+)"', text)
    title = (m_title.group(1).strip() if m_title else None)
    if not title:
        m_title = re.search(r'<title>([^<]+)</title>', text)
        title = m_title.group(1).strip() if m_title else None
    if not title:
        return None
    rsb_pdf_m = re.search(
        r'href="(/document/download/[a-f0-9-]+_en\?filename=[^"]*[Rr][Ss][Bb][^"]*\.pdf)"',
        text,
    )
    rsb_pdf = ("https://commission.europa.eu" + rsb_pdf_m.group(1)) if rsb_pdf_m else None
    decision_date = None
    m_year_in_pdf = re.search(r'/document/download/[^"]+(20\d{2})[^"]*\.pdf', text)
    if m_year_in_pdf:
        try:
            decision_date = dt.date(int(m_year_in_pdf.group(1)), 1, 1)
        except Exception:
            pass
    return {
        "title": title[:1000],
        "rsb_pdf_url": rsb_pdf,
        "decision_date": decision_date,
        "source_url": source_url,
    }


def derive_reference(slug):
    """Stable URL-derived reference. No synthesis."""
    slug_clean = slug.split("/")[-1].replace("_en", "")
    return f"RSB-{slug_clean[:60]}"


def upsert(cursor, row):
    cursor.execute(
        """
        INSERT INTO rsb_opinions (
            opinion_reference, title, target_initiative, target_dg,
            opinion_type, verdict, opinion_date, summary, full_text, pdf_url, source_url,
            policy_areas
        ) VALUES (
            %(opinion_reference)s, %(title)s, %(target_initiative)s, NULL,
            'impact_assessment', 'unknown', %(opinion_date)s, NULL, NULL, %(pdf_url)s, %(source_url)s,
            '{}'
        )
        ON CONFLICT (opinion_reference) DO UPDATE SET
            title = EXCLUDED.title,
            opinion_date = COALESCE(EXCLUDED.opinion_date, rsb_opinions.opinion_date),
            pdf_url = COALESCE(EXCLUDED.pdf_url, rsb_opinions.pdf_url),
            source_url = EXCLUDED.source_url,
            last_updated = NOW()
        """,
        row,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing"); sys.exit(1)

    print(f"[INFO] Index: {INDEX_URL}")
    status, body = http_get(INDEX_URL)
    if status != 200:
        print(f"[FATAL] Index returned {status}"); sys.exit(2)
    slugs = extract_publication_slugs(body)
    print(f"[INFO] Found {len(slugs)} /publications/ links")

    candidates = []
    for slug in slugs:
        url = "https://commission.europa.eu" + slug
        s, b = http_get(url)
        if s != 200:
            continue
        parsed = parse_publication_page(b, url)
        if not parsed:
            continue
        # rsb_opinions.opinion_date is NOT NULL — fallback to a sentinel
        # (1970-01-01) when the year can't be derived. Better than dropping
        # the row, and the API can filter sentinel dates if needed.
        candidates.append({
            "opinion_reference": derive_reference(slug),
            "title": parsed["title"],
            "target_initiative": parsed["title"][:120],
            "opinion_date": parsed["decision_date"] or dt.date(1970, 1, 1),
            "pdf_url": parsed["rsb_pdf_url"],
            "source_url": parsed["source_url"],
        })
        time.sleep(0.4)

    print(f"[INFO] Parsed {len(candidates)} pages")
    if not candidates:
        print("[WARN] No rows produced"); sys.exit(0)
    if args.dry_run:
        for c in candidates[:8]:
            print(f"  [{('PDF' if c['pdf_url'] else 'no-pdf'):6s}]  {c['title'][:60]}")
            print(f"     -> {c['source_url']}")
        return

    import psycopg2
    conn = psycopg2.connect(db_url)
    try:
        with conn:
            with conn.cursor() as cur:
                for row in candidates:
                    upsert(cur, row)
        print(f"[OK] UPSERTed {len(candidates)} rsb_opinions rows.")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
