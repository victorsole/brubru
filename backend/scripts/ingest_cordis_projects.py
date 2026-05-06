"""
Real ingestion of CORDIS funded projects (Horizon Europe + H2020 + FP7)
into ft_funded_projects.

Source: https://cordis.europa.eu/data/cordis-{HORIZON,h2020,fp7}projects-csv.zip
The CORDIS portal is a SPA but the Publications Office publishes monthly
bulk dumps as zipped CSVs. Each zip contains:
  project.csv       (10-20k+ rows, the master table)
  organization.csv  (coordinator + partner orgs)
  euroSciVoc.csv    (EuroSciVoc taxonomy assignments)
  topics.csv        (call topic linkage)
  legalBasis.csv    (regulation references)
  webLink.csv       (additional URLs)

We ingest project.csv as the canonical source and populate JSONB columns
(organisations, topics, euroscivoc, legal_basis_details, web_links) per
project so /api/v1/discover/eurio/* endpoints can serve consortium /
deliverables / funding queries from a single SELECT.

UPSERT on project_id. Run:
    python3.12 backend/scripts/ingest_cordis_projects.py [--limit 5000] [--apply]
                                                         [--programme horizon|h2020|fp7|all]
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
import sys
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras


ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"

DUMPS = {
    "horizon": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "h2020":   "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
    "fp7":     "https://cordis.europa.eu/data/cordis-fp7projects-csv.zip",
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


def _csv_groupby(z: zipfile.ZipFile, member: str, key_col: str) -> Dict[str, List[Dict[str, Any]]]:
    """Read a CSV inside the zip and group rows by `key_col`."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    if member not in z.namelist():
        return out
    with z.open(member) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
        for row in reader:
            pid = (row.get(key_col) or "").strip()
            if not pid:
                continue
            out.setdefault(pid, []).append(row)
    return out


def _to_bool(s: Any) -> Optional[bool]:
    if s is None:
        return None
    s = str(s).strip().lower()
    if s in ("true", "yes", "1", "y"): return True
    if s in ("false", "no", "0", "n", ""): return False
    return None


def load_full_org_map(z: zipfile.ZipFile) -> Dict[str, List[Dict[str, Any]]]:
    """Build a per-project list of ALL organisations (not only the coordinator)."""
    out: Dict[str, List[Dict[str, Any]]] = {}
    if "organization.csv" not in z.namelist():
        return out
    with z.open("organization.csv") as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
        for row in reader:
            pid = (row.get("projectID") or row.get("projectId") or "").strip()
            if not pid:
                continue
            out.setdefault(pid, []).append({
                "name": (row.get("name") or "").strip() or None,
                "short_name": (row.get("shortName") or "").strip() or None,
                "country": (row.get("country") or "").strip() or None,
                "city": (row.get("city") or "").strip() or None,
                "is_sme": _to_bool(row.get("SME")),
                "activity_type": (row.get("activityType") or "").strip() or None,
                "role": (row.get("role") or "").strip() or None,
                "ec_contribution": parse_float(row.get("ecContribution") or ""),
                "total_cost": parse_float(row.get("totalCost") or ""),
                "url": (row.get("organizationURL") or "").strip() or None,
                "vat": (row.get("vatNumber") or "").strip() or None,
                "nuts_code": (row.get("nutsCode") or "").strip() or None,
            })
    return out


def _trunc(v: Optional[str], n: int) -> Optional[str]:
    """Truncate to fit a varchar(n) column. CORDIS CSVs occasionally have
    misaligned columns from unescaped embedded quotes — without this, a
    single bad row poisons a whole 200-row batch."""
    if v is None:
        return None
    s = str(v).strip()
    return s[:n] if len(s) > n else (s or None)


def normalise(
    row: dict,
    coord: dict,
    programme: str,
    *,
    organisations: List[Dict[str, Any]],
    topics: List[Dict[str, Any]],
    euroscivoc: List[Dict[str, Any]],
    legal_basis_details: List[Dict[str, Any]],
    web_links: List[Dict[str, Any]],
) -> dict:
    pid = (row.get("id") or "").strip()
    return {
        "project_id": _trunc(pid, 120),
        "project_acronym": _trunc(row.get("acronym"), 120),
        "title": (row.get("title") or "").strip() or None,  # title is TEXT, no limit
        "objective": (row.get("objective") or "").strip() or None,
        "keywords": (row.get("keywords") or "").strip() or None,
        "topic_code": (row.get("topics") or "").strip() or None,  # widened to TEXT
        "grant_doi": _trunc(row.get("grantDoi"), 120),
        "framework_programme": _trunc((row.get("frameworkProgramme") or programme).upper(), 120),
        "type_of_action": (row.get("fundingScheme") or "").strip() or None,  # widened to TEXT
        "coordinator_name": coord.get("name") or None,
        "coordinator_country": (coord.get("country") or "")[:2] or None,
        "start_date": parse_date(row.get("startDate") or ""),
        "end_date": parse_date(row.get("endDate") or ""),
        "total_cost": parse_float(row.get("totalCost") or ""),
        "eu_contribution": parse_float(row.get("ecMaxContribution") or ""),
        "cost_currency": "EUR",
        "status": _trunc((row.get("status") or "").lower() or "unknown", 40),
        "source_url": f"https://cordis.europa.eu/project/id/{pid}",
        "published_at": parse_date(row.get("ecSignatureDate") or ""),
        "organisations": organisations,
        "topics": topics,
        "euroscivoc": euroscivoc,
        "legal_basis_details": legal_basis_details,
        "web_links": web_links,
    }


def upsert(cur, row: dict) -> None:
    # Wrap JSONB-bound fields in psycopg2.extras.Json so they serialise correctly.
    params = dict(row)
    for k in ("organisations", "topics", "euroscivoc", "legal_basis_details", "web_links"):
        params[k] = psycopg2.extras.Json(params.get(k) or [])
    cur.execute(
        """
        INSERT INTO ft_funded_projects
            (project_id, project_acronym, title, objective, keywords, topic_code, grant_doi,
             framework_programme, type_of_action,
             coordinator_name, coordinator_country, start_date, end_date, total_cost,
             eu_contribution, cost_currency, status, source_url, published_at,
             organisations, topics, euroscivoc, legal_basis_details, web_links,
             scraped_at, last_updated)
        VALUES (%(project_id)s, %(project_acronym)s, %(title)s, %(objective)s, %(keywords)s,
                %(topic_code)s, %(grant_doi)s,
                %(framework_programme)s, %(type_of_action)s, %(coordinator_name)s,
                %(coordinator_country)s, %(start_date)s, %(end_date)s, %(total_cost)s,
                %(eu_contribution)s, %(cost_currency)s, %(status)s, %(source_url)s,
                %(published_at)s,
                %(organisations)s, %(topics)s, %(euroscivoc)s,
                %(legal_basis_details)s, %(web_links)s,
                NOW(), NOW())
        ON CONFLICT (project_id) DO UPDATE SET
            title = EXCLUDED.title,
            objective = EXCLUDED.objective,
            keywords = EXCLUDED.keywords,
            topic_code = EXCLUDED.topic_code,
            grant_doi = EXCLUDED.grant_doi,
            status = EXCLUDED.status,
            coordinator_name = EXCLUDED.coordinator_name,
            coordinator_country = EXCLUDED.coordinator_country,
            total_cost = EXCLUDED.total_cost,
            eu_contribution = EXCLUDED.eu_contribution,
            organisations = EXCLUDED.organisations,
            topics = EXCLUDED.topics,
            euroscivoc = EXCLUDED.euroscivoc,
            legal_basis_details = EXCLUDED.legal_basis_details,
            web_links = EXCLUDED.web_links,
            last_updated = NOW()
        """,
        params,
    )


_UPSERT_SQL = """
    INSERT INTO ft_funded_projects
        (project_id, project_acronym, title, objective, keywords, topic_code, grant_doi,
         framework_programme, type_of_action,
         coordinator_name, coordinator_country, start_date, end_date, total_cost,
         eu_contribution, cost_currency, status, source_url, published_at,
         organisations, topics, euroscivoc, legal_basis_details, web_links,
         scraped_at, last_updated)
    VALUES (%(project_id)s, %(project_acronym)s, %(title)s, %(objective)s, %(keywords)s,
            %(topic_code)s, %(grant_doi)s,
            %(framework_programme)s, %(type_of_action)s, %(coordinator_name)s,
            %(coordinator_country)s, %(start_date)s, %(end_date)s, %(total_cost)s,
            %(eu_contribution)s, %(cost_currency)s, %(status)s, %(source_url)s,
            %(published_at)s,
            %(organisations)s, %(topics)s, %(euroscivoc)s,
            %(legal_basis_details)s, %(web_links)s,
            NOW(), NOW())
    ON CONFLICT (project_id) DO UPDATE SET
        title = EXCLUDED.title,
        objective = EXCLUDED.objective,
        keywords = EXCLUDED.keywords,
        topic_code = EXCLUDED.topic_code,
        grant_doi = EXCLUDED.grant_doi,
        status = EXCLUDED.status,
        coordinator_name = EXCLUDED.coordinator_name,
        coordinator_country = EXCLUDED.coordinator_country,
        total_cost = EXCLUDED.total_cost,
        eu_contribution = EXCLUDED.eu_contribution,
        organisations = EXCLUDED.organisations,
        topics = EXCLUDED.topics,
        euroscivoc = EXCLUDED.euroscivoc,
        legal_basis_details = EXCLUDED.legal_basis_details,
        web_links = EXCLUDED.web_links,
        last_updated = NOW()
"""


def _params_for(rec: dict) -> dict:
    p = dict(rec)
    for k in ("organisations", "topics", "euroscivoc", "legal_basis_details", "web_links"):
        p[k] = psycopg2.extras.Json(p.get(k) or [])
    return p


def ingest_dump(programme: str, conn, args) -> int:
    cache = Path("/tmp") / f"cordis-{programme}.zip"
    print(f"\n[INFO] downloading {DUMPS[programme]} -> {cache}", flush=True)
    download(DUMPS[programme], cache)
    print(f"[INFO] {cache.stat().st_size / 1024 / 1024:.1f} MB", flush=True)
    inserted = 0
    with zipfile.ZipFile(cache) as z:
        coord_map = load_coordinator_map(z)
        full_orgs_map = load_full_org_map(z)
        topics_map = _csv_groupby(z, "topics.csv", "projectID")
        eurosci_map = _csv_groupby(z, "euroSciVoc.csv", "projectID")
        legal_map = _csv_groupby(z, "legalBasis.csv", "projectID")
        weblink_map = _csv_groupby(z, "webLink.csv", "projectID")
        print(
            f"[INFO] aggregates loaded — orgs={len(full_orgs_map)} topics={len(topics_map)} "
            f"eurosci={len(eurosci_map)} legal={len(legal_map)} weblinks={len(weblink_map)}",
            flush=True,
        )

        # Build the full record list in memory first, then batch-upsert with
        # execute_batch (one SQL round-trip per BATCH_SIZE rows instead of one
        # per row — orders of magnitude faster on Supabase pooler).
        records: List[dict] = []
        with z.open("project.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
            for row in reader:
                pid = (row.get("id") or "").strip()
                if not pid:
                    continue
                topics = [
                    {"topic": (t.get("topic") or "").strip() or None,
                     "title": (t.get("title") or "").strip() or None}
                    for t in topics_map.get(pid, [])
                ]
                eurosci = [
                    {"code": (e.get("euroSciVocCode") or "").strip() or None,
                     "path": (e.get("euroSciVocPath") or "").strip() or None,
                     "title": (e.get("euroSciVocTitle") or "").strip() or None}
                    for e in eurosci_map.get(pid, [])
                ]
                legal = [
                    {"code": (lb.get("legalBasis") or "").strip() or None,
                     "title": (lb.get("title") or "").strip() or None,
                     "unique_programme_part": _to_bool(lb.get("uniqueProgrammePart"))}
                    for lb in legal_map.get(pid, [])
                ]
                weblinks = [
                    {"url": (w.get("physUrl") or "").strip() or None,
                     "type": (w.get("type") or "").strip() or None,
                     "title": (w.get("title") or "").strip() or None}
                    for w in weblink_map.get(pid, [])
                ]
                rec = normalise(
                    row, coord_map.get(pid, {}), programme.upper(),
                    organisations=full_orgs_map.get(pid, []),
                    topics=topics,
                    euroscivoc=eurosci,
                    legal_basis_details=legal,
                    web_links=weblinks,
                )
                if not rec["title"]:
                    continue
                if args.limit and len(records) >= args.limit:
                    break
                records.append(rec)

        print(f"[INFO] built {len(records):,} project records", flush=True)
        if not args.apply:
            return len(records)

        BATCH_SIZE = 200
        cur = conn.cursor()
        for i in range(0, len(records), BATCH_SIZE):
            chunk = records[i: i + BATCH_SIZE]
            try:
                psycopg2.extras.execute_batch(
                    cur,
                    _UPSERT_SQL,
                    [_params_for(r) for r in chunk],
                    page_size=BATCH_SIZE,
                )
                conn.commit()
                inserted += len(chunk)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                print(f"  [BATCH ERR @ {i}] {exc} — falling back to per-row", flush=True)
                for r in chunk:
                    try:
                        cur.execute(_UPSERT_SQL, _params_for(r))
                        conn.commit()
                        inserted += 1
                    except Exception as exc2:  # noqa: BLE001
                        conn.rollback()
                        print(f"    [SKIP] {r.get('project_id')}: {exc2}", flush=True)
            if (i + BATCH_SIZE) % 2000 == 0 or (i + BATCH_SIZE) >= len(records):
                print(f"  ... {min(i + BATCH_SIZE, len(records)):,}/{len(records):,}", flush=True)
    print(f"[DONE] {programme}: inserted={inserted}", flush=True)
    return inserted


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = unbounded")
    ap.add_argument("--programme", choices=["horizon", "h2020", "fp7", "all"], default="horizon")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    conn = psycopg2.connect(db_url)

    total = 0
    if args.programme in ("horizon", "all"):
        total += ingest_dump("horizon", conn, args)
    if args.programme in ("h2020", "all"):
        total += ingest_dump("h2020", conn, args)
    if args.programme in ("fp7", "all"):
        total += ingest_dump("fp7", conn, args)

    print(f"\n[GRAND TOTAL] inserted={total} apply={args.apply}")


if __name__ == "__main__":
    main()
