"""
Ingest Commission Transparency Initiative meetings register into
transparency_meetings.

The /api/v1/meetings endpoint surfaces these — they're meetings between
Commission officials (Commissioners, cabinet members, DG/EA directors)
and external interest representatives, with the lobbyist's Transparency
Register ID. Distinct from the public commissioner agenda (#6) which is
the daily schedule.

Source (HTML pages, no JSON API):
  https://ec.europa.eu/transparency-initiative/meetings/listcommissioners?collegeid=0
  https://ec.europa.eu/transparency-initiative/meetings/listdg
  https://ec.europa.eu/transparency-initiative/meetings/listea
  https://ec.europa.eu/transparency-initiative/meetings/meeting/{type}?id={uuid}&page={N}
    type ∈ {commissioner, cabinet, dg, ea}

Each meeting page renders a table with: Commission Representative(s),
Date (DD/MM/YYYY), Location, Interest representative(s), Subject matter,
Minutes link.

Run:
    python3.12 backend/scripts/ingest_transparency_meetings.py            # dry-run, 5 hosts
    python3.12 backend/scripts/ingest_transparency_meetings.py --apply
    python3.12 backend/scripts/ingest_transparency_meetings.py --apply --type dg --limit 50
"""

from __future__ import annotations

import argparse
import re
import sys
import time
import urllib.request
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import psycopg2
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/126.0.0.0"
BASE = "https://ec.europa.eu/transparency-initiative/meetings"


def get_env(k: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


_UUID_RE = re.compile(r"id=([0-9a-f-]{36})")


def list_hosts(host_type: str) -> List[Dict[str, str]]:
    """Return a list of {'uuid': ..., 'name': ..., 'kind': ...}."""
    if host_type == "commissioner":
        url = f"{BASE}/listcommissioners?collegeid=0"
    elif host_type == "dg":
        url = f"{BASE}/listdg"
    elif host_type == "ea":
        url = f"{BASE}/listea"
    else:
        raise ValueError(host_type)

    soup = BeautifulSoup(fetch(url), "html.parser")
    hosts: List[Dict[str, str]] = []
    seen = set()
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "meeting/" not in href:
            continue
        m = _UUID_RE.search(href)
        if not m:
            continue
        u = m.group(1)
        if u in seen:
            continue
        seen.add(u)
        kind = ("commissioner" if "meeting/commissioner" in href
                else "cabinet" if "meeting/cabinet" in href
                else "dg" if "meeting/dg" in href
                else "ea" if "meeting/ea" in href
                else host_type)
        name = a.get_text(" ", strip=True) or "?"
        hosts.append({"uuid": u, "name": name[:200], "kind": kind})
    return hosts


def parse_date(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s, fmt)
        except ValueError:
            continue
    return None


def parse_meetings_page(host: Dict[str, str], page: int) -> List[Dict[str, object]]:
    url = f"{BASE}/meeting/{host['kind']}?id={host['uuid']}&page={page}"
    try:
        html = fetch(url)
    except Exception:
        return []
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table")
    if not table:
        return []
    rows = []
    for tr in table.find_all("tr")[1:]:
        cells = tr.find_all(["td", "th"])
        if len(cells) < 5:
            continue
        rep = cells[0].get_text("\n", strip=True)
        date_text = cells[1].get_text(" ", strip=True)
        location = cells[2].get_text(" ", strip=True)
        organisation = cells[3].get_text(" ", strip=True)
        subject = cells[4].get_text(" ", strip=True)

        meeting_date = parse_date(date_text)
        if not meeting_date:
            continue

        rep_lines = [l.strip() for l in rep.splitlines() if l.strip()]
        host_name = rep_lines[0] if rep_lines else host["name"]
        representatives = "; ".join(rep_lines[1:]) if len(rep_lines) > 1 else None

        rows.append({
            "id": str(uuid.uuid4()),
            "host_uuid": host["uuid"],
            "host_name": host_name[:200],
            "host_role": host["kind"].upper(),
            "host_dg": host["name"][:200] if host["kind"] == "dg" else None,
            "host_cabinet": host["name"][:200] if host["kind"] == "cabinet" else None,
            "meeting_date": meeting_date.date(),
            "location": location[:200] if location else None,
            "subject": (subject or organisation)[:1000],
            "organisation_met": organisation[:500] if organisation else "(unknown)",
            "transparency_register_id": None,
            "organisation_type": None,
            "representatives": representatives,
            "source_url": url,
            "policy_areas": [],
            "related_celex": [],
        })
    return rows


def fetch_all_meetings_for_host(host: Dict[str, str], max_pages: int = 50) -> List[Dict[str, object]]:
    all_rows: List[Dict[str, object]] = []
    for page in range(1, max_pages + 1):
        rows = parse_meetings_page(host, page)
        if not rows:
            break
        all_rows.extend(rows)
        time.sleep(0.15)
    return all_rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--type", choices=("commissioner", "dg", "ea", "all"), default="all")
    ap.add_argument("--limit", type=int, default=5,
                    help="Cap number of hosts processed (per type)")
    ap.add_argument("--max-pages", type=int, default=50)
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    types = ("commissioner", "dg", "ea") if args.type == "all" else (args.type,)
    all_hosts: List[Dict[str, str]] = []
    for t in types:
        hosts = list_hosts(t)
        print(f"[INFO] {t}: {len(hosts)} hosts found")
        if args.limit:
            hosts = hosts[: args.limit]
        all_hosts.extend(hosts)

    inserted = total_meetings = 0
    conn = psycopg2.connect(db_url) if args.apply else None
    cur = conn.cursor() if conn else None

    for host in all_hosts:
        meetings = fetch_all_meetings_for_host(host, max_pages=args.max_pages)
        total_meetings += len(meetings)
        print(f"  [{host['kind']:12s}] {host['name'][:60]:60s} → {len(meetings):4d} meetings")
        if not args.apply or not meetings:
            continue
        for m in meetings:
            attempt = 0
            while attempt < 3:
                try:
                    cur.execute(
                        """
                        INSERT INTO transparency_meetings
                          (id, host_uuid, host_name, host_role, host_dg, host_cabinet,
                           meeting_date, location, subject, organisation_met,
                           transparency_register_id, organisation_type, representatives,
                           source_url, policy_areas, related_celex,
                           scraped_at, first_seen, last_updated)
                        VALUES
                          (%(id)s, %(host_uuid)s, %(host_name)s, %(host_role)s, %(host_dg)s,
                           %(host_cabinet)s, %(meeting_date)s, %(location)s, %(subject)s,
                           %(organisation_met)s, %(transparency_register_id)s, %(organisation_type)s,
                           %(representatives)s, %(source_url)s, %(policy_areas)s, %(related_celex)s,
                           NOW(), NOW(), NOW())
                        ON CONFLICT DO NOTHING
                        """,
                        m,
                    )
                    inserted += 1
                    break
                except (psycopg2.OperationalError, psycopg2.InterfaceError) as exc:
                    print(f"    [RECONNECT] {exc}")
                    try:
                        conn.close()
                    except Exception:
                        pass
                    conn = psycopg2.connect(db_url)
                    cur = conn.cursor()
                    attempt += 1
                except Exception as exc:
                    print(f"    [ERR] {m['meeting_date']}: {exc}")
                    try:
                        conn.rollback()
                    except Exception:
                        pass
                    break
        try:
            conn.commit()
        except Exception:
            conn = psycopg2.connect(db_url)
            cur = conn.cursor()

    if conn:
        try:
            conn.close()
        except Exception:
            pass

    print(f"[DONE] hosts={len(all_hosts)} meetings_parsed={total_meetings} inserted={inserted}{' (applied)' if args.apply else ' (dry-run)'}")


if __name__ == "__main__":
    main()
