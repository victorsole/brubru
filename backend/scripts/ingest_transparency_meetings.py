"""
Ingest Commission Transparency Initiative meetings.

Source: ec.europa.eu/transparencyinitiative/meetings/meeting.do?host={uuid}
Target: transparency_meetings table.

Seed UUIDs from Marcadors crosscheck:
- ca175ad3-c2c5-457e-8f6d-f17956bdcc4e (cited in Thursday brief 1.8)
- a2c7c963-a9ad-4c47-aa73-4bb46b06dd5d (mission)
- 9fd4662a-8580-4cee-bb3f-3c2fba5c12c6
"""

import datetime as dt
import re
import sys
import uuid
from pathlib import Path

import httpx
import psycopg2
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]

SEED_HOSTS = [
    "ca175ad3-c2c5-457e-8f6d-f17956bdcc4e",
    "a2c7c963-a9ad-4c47-aa73-4bb46b06dd5d",
    "9fd4662a-8580-4cee-bb3f-3c2fba5c12c6",
]


def fetch_host_meetings(client: httpx.Client, host_uuid: str):
    url = f"https://ec.europa.eu/transparencyinitiative/meetings/meeting.do?host={host_uuid}"
    try:
        r = client.get(url, follow_redirects=True, timeout=20.0)
        r.raise_for_status()
    except Exception as e:
        print(f"  [ERR] {host_uuid}: {e}")
        return [], None, None

    soup = BeautifulSoup(r.text, "html.parser")
    # Page header tells us the host name + role + DG
    header = soup.find("h1") or soup.find("h2")
    host_name = (header.get_text(strip=True) if header else "")[:255] or None

    # Sub-header has cabinet/role info
    role_el = soup.find("h2", class_="cabinetTitle") or soup.find("p", class_="leadParagraph")
    host_role = (role_el.get_text(strip=True) if role_el else "")[:255] or None

    # Meeting rows are in a table
    meetings = []
    table = soup.find("table")
    if not table:
        return meetings, host_name, host_role

    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 3:
            continue
        # Typical layout: Date | Place | Subject | Organisation
        text_cells = [c.get_text(" ", strip=True) for c in cells]
        date_text = text_cells[0]
        d = None
        for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d %B %Y"):
            try:
                d = dt.datetime.strptime(date_text[:11], fmt).date()
                break
            except ValueError:
                continue
        if d is None:
            continue
        location = text_cells[1] if len(text_cells) > 1 else None
        subject = text_cells[2] if len(text_cells) > 2 else ""
        organisation = text_cells[-1] if len(text_cells) > 3 else ""

        meetings.append({
            "meeting_date": d,
            "location": location,
            "subject": subject[:2000],
            "organisation_met": organisation[:500] or "Unspecified",
        })
    return meetings, host_name, host_role


def main():
    db_url = open(ROOT / ".env").read().split("DATABASE_URL=")[1].split("\n")[0].strip().strip('"')
    conn = psycopg2.connect(db_url)
    conn.autocommit = False
    cur = conn.cursor()

    inserted = 0
    skipped = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml",
    }
    with httpx.Client(headers=headers, timeout=20.0) as client:
        for host_uuid in SEED_HOSTS:
            print(f"\nFetching host {host_uuid}...")
            meetings, host_name, host_role = fetch_host_meetings(client, host_uuid)
            print(f"  {host_name or '?'} | {host_role or '?'} | {len(meetings)} meetings")
            for m in meetings:
                source_url = f"https://ec.europa.eu/transparencyinitiative/meetings/meeting.do?host={host_uuid}"
                try:
                    cur.execute("""
                        INSERT INTO transparency_meetings (
                            id, host_uuid, host_name, host_role,
                            meeting_date, location, subject,
                            organisation_met, source_url
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """, (
                        str(uuid.uuid4()), host_uuid, host_name, host_role,
                        m["meeting_date"], m["location"], m["subject"],
                        m["organisation_met"], source_url,
                    ))
                    inserted += 1
                except Exception as e:
                    skipped += 1
                    if "duplicate" not in str(e).lower():
                        print(f"    [WARN] {e}")
                    conn.rollback()
                    continue
            conn.commit()

    cur.execute("SELECT COUNT(*) FROM transparency_meetings")
    total = cur.fetchone()[0]
    print(f"\n=== DONE === inserted={inserted} skipped={skipped} total={total}")


if __name__ == "__main__":
    main()
