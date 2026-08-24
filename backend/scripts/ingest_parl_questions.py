"""
Ingest EP parliamentary questions.

Source: europarl.europa.eu Open Data REST API for parliamentary questions.
Target: parliamentary_questions table.

Fast path: use the EP "All Activities" feed which exposes questions in JSON.
Fallback: scrape the plenary questions HTML listing pages.
"""

import datetime as dt
import re
import uuid
from pathlib import Path

import httpx
import psycopg2
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]


def parse_date(text: str):
    if not text:
        return None
    text = text.strip()
    for fmt in ("%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d %B %Y", "%d.%m.%Y"):
        try:
            return dt.datetime.strptime(text[:11].strip(), fmt).date()
        except ValueError:
            continue
    m = re.search(r"(\d{1,2}) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\w* (\d{4})", text)
    if m:
        try:
            return dt.datetime.strptime(m.group(0)[:20], "%d %b %Y").date()
        except ValueError:
            pass
    return None


def main():
    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    db_url = get_database_url()
    conn = psycopg2.connect(db_url)
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }

    # Strategy A: scrape recent plenary questions search pages.
    # The EP plenary questions page is at /plenary/en/parliamentary-questions.html
    # We hit the date-filtered search to get a ~recent-questions sample.
    base_listing = (
        "https://www.europarl.europa.eu/plenary/en/parliamentary-questions.html"
        "?action=Submit&searchType=question&clean=false"
    )

    with httpx.Client(headers=headers, timeout=30.0, follow_redirects=True) as client:
        try:
            r = client.get(base_listing)
            r.raise_for_status()
        except Exception as e:
            print(f"[ERR] listing: {e}")
            r = None

        candidates = []
        if r is not None:
            soup = BeautifulSoup(r.text, "html.parser")
            # The questions listing has rows like "E-001234/2026 — Subject — date — author"
            for li in soup.find_all(["li", "tr", "div"]):
                text = li.get_text(" ", strip=True)
                m = re.search(r"\b([EPHO])-(\d{6})/(\d{4})\b", text)
                if not m:
                    continue
                qref = m.group(0)
                # Skip duplicates within the same scrape
                if any(c["question_reference"] == qref for c in candidates):
                    continue
                qtype = {"E": "written", "O": "oral", "P": "priority", "H": "question_time"}.get(m.group(1), "written")
                term_year = int(m.group(3))
                term = 10 if term_year >= 2024 else 9
                # Look for a link
                link = li.find("a", href=True)
                src_url = link["href"] if link else base_listing
                if src_url.startswith("/"):
                    src_url = f"https://www.europarl.europa.eu{src_url}"
                # Subject is usually the link text
                subj = (link.get_text(" ", strip=True) if link else "")[:2000] or text[:300]
                d = parse_date(text)
                candidates.append({
                    "question_reference": qref,
                    "question_type": qtype,
                    "parliamentary_term": term,
                    "subject": subj,
                    "submitted_date": d,
                    "source_url": src_url,
                })

        # NO synthetic fallback. Fabricated questions would poison chat retrieval +
        # the MEUB Parliamentary Questions tab (libe-seed contamination rule). If the
        # scrape returns nothing, ingest nothing — use the EP Open Data path instead.
        if not candidates:
            print("[INFO] No questions parsed. Ingesting nothing (no synthetic seeds).")

        for c in candidates:
            try:
                cur.execute("""
                    INSERT INTO parliamentary_questions (
                        id, question_reference, question_type, parliamentary_term,
                        subject, submitted_date, source_url
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (question_reference) DO NOTHING
                """, (
                    str(uuid.uuid4()), c["question_reference"], c["question_type"],
                    c["parliamentary_term"], c["subject"][:5000], c["submitted_date"],
                    c["source_url"],
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

    cur.execute("SELECT COUNT(*) FROM parliamentary_questions")
    total = cur.fetchone()[0]
    print(f"\n=== DONE === inserted={inserted} skipped={skipped} total={total}")


if __name__ == "__main__":
    main()
