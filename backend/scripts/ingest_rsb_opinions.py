"""
Ingest Regulatory Scrutiny Board opinions.

Source: commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/regulatory-scrutiny-board-opinions-evaluations-and-fitness-checks_en
Target: rsb_opinions table.

Strategy: scrape the listing page for opinion entries (each entry has title,
date, target initiative, verdict, link to PDF).
"""

import datetime as dt
import hashlib
import re
import uuid
from pathlib import Path

import httpx
import psycopg2
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]

URLS = [
    # Year-by-year pages (Commission lists by year)
    "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/regulatory-scrutiny-board-opinions-evaluations-and-fitness-checks/regulatory-scrutiny-board-opinions-impact-assessments-2025_en",
    "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/regulatory-scrutiny-board-opinions-evaluations-and-fitness-checks/regulatory-scrutiny-board-opinions-impact-assessments-2024_en",
    "https://commission.europa.eu/law/law-making-process/regulatory-scrutiny-board/regulatory-scrutiny-board-opinions-evaluations-and-fitness-checks_en",
]


def derive_verdict(text: str) -> str:
    t = text.lower()
    if "positive with reservations" in t:
        return "positive_with_reservations"
    if "negative" in t and "opinion" in t:
        return "negative"
    if "positive" in t:
        return "positive"
    return "unknown"


def parse_date(text: str):
    text = text.strip()
    for fmt in ("%d %B %Y", "%d.%m.%Y", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    # Try to extract from "Opinion of the Regulatory Scrutiny Board, dated DD Month YYYY"
    m = re.search(r"(\d{1,2})\s+(January|February|March|April|May|June|July|August|September|October|November|December)\s+(\d{4})", text)
    if m:
        try:
            return dt.datetime.strptime(m.group(0), "%d %B %Y").date()
        except ValueError:
            pass
    return None


def main():
    db_url = open(ROOT / ".env").read().split("DATABASE_URL=")[1].split("\n")[0].strip().strip('"')
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    }

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        for url in URLS:
            try:
                r = client.get(url)
                r.raise_for_status()
            except Exception as e:
                print(f"[ERR] {url}: {e}")
                continue

            soup = BeautifulSoup(r.text, "html.parser")
            # Strategy: every block with a PDF link is an opinion candidate.
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if not href.endswith(".pdf"):
                    continue
                if "/rsb_" not in href.lower() and "scrutiny-board" not in href.lower() and "ia_" not in href.lower():
                    # Heuristic — RSB PDFs typically include 'rsb' or 'ia_' in the path
                    if "regulatory-scrutiny-board" not in href.lower():
                        continue
                title = a.get_text(strip=True)
                if not title or len(title) < 10:
                    # Walk up to enclosing block for the title
                    parent = a.find_parent(["li", "div", "p", "article"])
                    if parent:
                        title = parent.get_text(" ", strip=True)[:300]
                if not title:
                    continue

                # Extract date from surrounding text
                surrounding = a.find_parent(["li", "div", "p", "article"])
                surrounding_text = surrounding.get_text(" ", strip=True) if surrounding else title
                opinion_date = parse_date(surrounding_text) or dt.date(2024, 1, 1)
                verdict = derive_verdict(surrounding_text)

                # Build a stable reference from the PDF URL hash + date
                ref = f"RSB-{opinion_date.isoformat()}-{hashlib.md5(href.encode()).hexdigest()[:8]}"

                full_url = href if href.startswith("http") else f"https://commission.europa.eu{href}"

                try:
                    cur.execute("""
                        INSERT INTO rsb_opinions (
                            id, opinion_reference, title, opinion_type,
                            verdict, opinion_date, pdf_url, source_url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (opinion_reference) DO NOTHING
                    """, (
                        str(uuid.uuid4()), ref, title[:5000], "impact_assessment",
                        verdict, opinion_date, full_url, url,
                    ))
                    if cur.rowcount > 0:
                        inserted += 1
                    else:
                        skipped += 1
                except Exception as e:
                    skipped += 1
                    conn.rollback()
                    continue
            conn.commit()
            print(f"[OK] {url}: running total inserted={inserted}")

    cur.execute("SELECT COUNT(*) FROM rsb_opinions")
    total = cur.fetchone()[0]
    print(f"\n=== DONE === inserted={inserted} skipped={skipped} total={total}")


if __name__ == "__main__":
    main()
