"""
Real ingestion of CORDIS funded projects (Horizon Europe + H2020) into
ft_funded_projects.

Source: https://cordis.europa.eu/data/cordis-{HORIZON,h2020}projects-csv.zip
The CORDIS portal is a SPA but the Publications Office publishes monthly
bulk dumps as zipped CSVs. Each zip contains:
  project.csv       (20k+ rows, the master table)
  organization.csv  (coordinator + partner orgs)
  euroSciVoc.csv    (EuroSciVoc taxonomy assignments)
  topics.csv        (call topic linkage)
  legalBasis.csv    (regulation references)

We ingest project.csv as the canonical source, then enrich with the first
coordinator org from organization.csv.

UPSERT on project_id. Run:
    python3.12 backend/scripts/ingest_cordis_projects.py [--limit 5000] [--apply]
                                                         [--horizon | --h2020 | --both]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Dict, Optional

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"

DUMPS = {
    "horizon": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "h2020": "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
}


def get_env(key: str) -> str:
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return ""


def download(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        print(f"  [cache] {dest}")
        return
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as r, dest.open("wb") as f:
        while True:
            chunk = r.read(64 * 1024)
            if not chunk:
                break
            f.write(chunk)


def parse_date(s: str) -> Optional[dt.date]:
    if not s:
        return None
    for fmt in ("%Y-%m-%d", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y"):
        try:
            return dt.datetime.strptime(s.strip()[:19], fmt).date()
        except ValueError:
            continue
    return None


def parse_float(s: str) -> Optional[float]:
    if not s or s in ("NA", "null"):
        return None
    try:
        return float(s.replace(",", ".").replace(" ", ""))
    except ValueError:
        return None


def load_coordinator_map(z: zipfile.ZipFile) -> Dict[str, dict]:
    """Read organization.csv and pick the COORDINATOR (or first) org per project."""
    out: Dict[str, dict] = {}
    if "organization.csv" not in z.namelist():
        return out
    with z.open("organization.csv") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
        for row in reader:
            pid = (row.get("projectID") or row.get("projectId") or "").strip()
            if not pid:
                continue
            role = (row.get("role") or "").strip().upper()
            existing = out.get(pid)
            # Prefer COORDINATOR rows; otherwise keep first seen
            if not existing or (role == "COORDINATOR" and existing.get("role") != "COORDINATOR"):
                out[pid] = {
                    "name": (row.get("name") or "").strip(),
                    "country": (row.get("country") or "").strip(),
                    "role": role,
                }
    return out


def normalise(row: dict, coord: dict, programme: str) -> dict:
    pid = (row.get("id") or "").strip()
    return {
        "project_id": pid,
        "project_acronym": (row.get("acronym") or "").strip() or None,
        "title": (row.get("title") or "").strip() or None,
        "objective": (row.get("objective") or "").strip() or None,
        "framework_programme": (row.get("frameworkProgramme") or programme).strip(),
        "type_of_action": (row.get("fundingScheme") or "").strip() or None,
        "coordinator_name": coord.get("name") or None,
        "coordinator_country": coord.get("country") or None,
        "start_date": parse_date(row.get("startDate") or ""),
        "end_date": parse_date(row.get("endDate") or ""),
        "total_cost": parse_float(row.get("totalCost") or ""),
        "eu_contribution": parse_float(row.get("ecMaxContribution") or ""),
        "cost_currency": "EUR",
        "status": (row.get("status") or "").strip().lower() or "unknown",
        "source_url": f"https://cordis.europa.eu/project/id/{pid}",
        "published_at": parse_date(row.get("ecSignatureDate") or ""),
    }


def upsert(cur, row: dict) -> None:
    cur.execute(
        """
        INSERT INTO ft_funded_projects
            (project_id, project_acronym, title, objective, framework_programme, type_of_action,
             coordinator_name, coordinator_country, start_date, end_date, total_cost,
             eu_contribution, cost_currency, status, source_url, published_at,
             scraped_at, last_updated)
        VALUES (%(project_id)s, %(project_acronym)s, %(title)s, %(objective)s,
                %(framework_programme)s, %(type_of_action)s, %(coordinator_name)s,
                %(coordinator_country)s, %(start_date)s, %(end_date)s, %(total_cost)s,
                %(eu_contribution)s, %(cost_currency)s, %(status)s, %(source_url)s,
                %(published_at)s, NOW(), NOW())
        ON CONFLICT (project_id) DO UPDATE SET
            title = EXCLUDED.title,
            status = EXCLUDED.status,
            coordinator_name = EXCLUDED.coordinator_name,
            coordinator_country = EXCLUDED.coordinator_country,
            total_cost = EXCLUDED.total_cost,
            eu_contribution = EXCLUDED.eu_contribution,
            last_updated = NOW()
        """,
        row,
    )


def ingest_dump(programme: str, conn, args) -> int:
    cache = Path("/tmp") / f"cordis-{programme}.zip"
    print(f"\n[INFO] downloading {DUMPS[programme]} -> {cache}")
    download(DUMPS[programme], cache)
    print(f"[INFO] {cache.stat().st_size / 1024 / 1024:.1f} MB")
    inserted = 0
    with zipfile.ZipFile(cache) as z:
        coord_map = load_coordinator_map(z)
        print(f"[INFO] coordinator map: {len(coord_map)} projects")
        with z.open("project.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
            cur = conn.cursor()
            for i, row in enumerate(reader):
                if args.limit and inserted >= args.limit:
                    break
                pid = (row.get("id") or "").strip()
                if not pid:
                    continue
                rec = normalise(row, coord_map.get(pid, {}), programme.upper())
                if not rec["title"]:
                    continue
                if args.apply:
                    try:
                        upsert(cur, rec)
                        inserted += 1
                    except Exception as exc:  # noqa: BLE001
                        print(f"  [DB ERR] {pid}: {exc}")
                        conn.rollback()
                else:
                    inserted += 1
                if inserted and inserted % 1000 == 0:
                    if args.apply:
                        conn.commit()
                    print(f"  ... {inserted} written")
            if args.apply:
                conn.commit()
    print(f"[DONE] {programme}: inserted={inserted}")
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = unbounded")
    ap.add_argument("--programme", choices=["horizon", "h2020", "both"], default="horizon")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    conn = psycopg2.connect(db_url)

    total = 0
    if args.programme in ("horizon", "both"):
        total += ingest_dump("horizon", conn, args)
    if args.programme in ("h2020", "both"):
        total += ingest_dump("h2020", conn, args)

    print(f"\n[GRAND TOTAL] inserted={total} apply={args.apply}")


if __name__ == "__main__":
    main()
