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
                                                         [--programme horizon|h2020|fp7|all] [--force]

Weekly tier since 23 Oct 2026 (api/cron.py, --programme all), followed by the status rule
(services/funding/project_status.py). Until then nothing ran it: the last read was 6 May. CORDIS
refreshes a dump about monthly (Horizon Europe and H2020 on 8 Oct 2026; FP7 last on 2 Jan 2025),
so a dump whose Last-Modified is not newer than the one we last read IN FULL is skipped (kept in
job_cursors as cordis_dump_<programme>, saved only when a whole dump was read and written, so a
run cut short reads it again); --force reads it anyway. A dump read that yields no project exits 1; projects that could not be
written are reported as degraded.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import email.utils
import io
import json
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg2
import psycopg2.extras

# The real environment first, then a local .env: this script's own reader looked at the repo-root
# .env only, which Railway does not have (the same bug ingest_funding_sedia.get_env documents).
from ingest_funding_sedia import get_env

USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0; +https://brubru.beresol.eu)"

DUMPS = {
    "horizon": "https://cordis.europa.eu/data/cordis-HORIZONprojects-csv.zip",
    "h2020":   "https://cordis.europa.eu/data/cordis-h2020projects-csv.zip",
    "fp7":     "https://cordis.europa.eu/data/cordis-fp7projects-csv.zip",
}


def dump_modified(url: str) -> Optional[dt.datetime]:
    """The dump's Last-Modified, as naive UTC (the column type), or None if the server gives none."""
    req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        stamp = r.headers.get("Last-Modified")
    if not stamp:
        return None
    return email.utils.parsedate_to_datetime(stamp).astimezone(dt.timezone.utc).replace(tzinfo=None)


def last_read(conn, programme: str) -> Optional[dt.datetime]:
    """The Last-Modified of the dump last read in full. Not max(scraped_at): a run killed halfway
    stamps part of the rows, which would make a half-read dump look read."""
    with conn.cursor() as cur:
        cur.execute("SELECT cursor_value FROM job_cursors WHERE job_key = %s", (f"cordis_dump_{programme}",))
        row = cur.fetchone()
    conn.commit()
    return dt.datetime.fromisoformat(row[0]) if row else None


def save_read(conn, programme: str, modified: dt.datetime, built: int, written: int) -> None:
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO job_cursors (job_key, cursor_value, note, updated_at)
            VALUES (%s, %s, %s, now())
            ON CONFLICT (job_key) DO UPDATE SET cursor_value = EXCLUDED.cursor_value,
                note = EXCLUDED.note, updated_at = now()
        """, (f"cordis_dump_{programme}", modified.isoformat(),
              f"dump read in full: {built} projects, {written} written"))
    conn.commit()


def download(url: str, dest: Path) -> None:
    # Always a fresh copy: a cached zip was reused for as long as /tmp lived, so a scheduled run
    # could re-read an old dump without saying so.
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
                    "pic": (row.get("organisationID") or "").strip() or None,
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
                # organisationID is the organisation's PIC: the portal's own contact-form link on the
                # same row is contact-form/project/<organisationID>/<projectID> (26 Oct 2026). It
                # was not kept, so partners could only be told apart by name.
                "pic": (row.get("organisationID") or "").strip() or None,
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
        "coordinator_pic": coord.get("pic") or None,
        "start_date": parse_date(row.get("startDate") or ""),
        "end_date": parse_date(row.get("endDate") or ""),
        "total_cost": parse_float(row.get("totalCost") or ""),
        "eu_contribution": parse_float(row.get("ecMaxContribution") or ""),
        "cost_currency": "EUR",
        # The source's word, or None: "unknown" here was ours, not CORDIS's (11 FP7 rows, 26 Oct 2026).
        "source_status": _trunc((row.get("status") or "").strip().lower(), 40) or None,
        "source_url": f"https://cordis.europa.eu/project/id/{pid}",
        "published_at": parse_date(row.get("ecSignatureDate") or ""),
        "organisations": organisations,
        "topics": topics,
        "euroscivoc": euroscivoc,
        "legal_basis_details": legal_basis_details,
        "web_links": web_links,
    }


_UPSERT_SQL = """
    INSERT INTO ft_funded_projects
        (project_id, project_acronym, title, objective, keywords, topic_code, grant_doi,
         framework_programme, type_of_action,
         coordinator_name, coordinator_country, start_date, end_date, total_cost,
         eu_contribution, cost_currency, status, source_status, source_url, published_at, coordinator_pic,
         organisations, topics, euroscivoc, legal_basis_details, web_links,
         scraped_at, last_updated)
    VALUES (%(project_id)s, %(project_acronym)s, %(title)s, %(objective)s, %(keywords)s,
            %(topic_code)s, %(grant_doi)s,
            %(framework_programme)s, %(type_of_action)s, %(coordinator_name)s,
            %(coordinator_country)s, %(start_date)s, %(end_date)s, %(total_cost)s,
            %(eu_contribution)s, %(cost_currency)s, 'unknown', %(source_status)s, %(source_url)s,
            %(published_at)s, %(coordinator_pic)s,
            %(organisations)s, %(topics)s, %(euroscivoc)s,
            %(legal_basis_details)s, %(web_links)s,
            NOW(), NOW())
    ON CONFLICT (project_id) DO UPDATE SET
        title = EXCLUDED.title,
        objective = EXCLUDED.objective,
        keywords = EXCLUDED.keywords,
        topic_code = EXCLUDED.topic_code,
        grant_doi = EXCLUDED.grant_doi,
        -- The source word only: the served status is set by services/funding/project_status.py
        -- from it and the dates (23 Oct 2026); writing it here flipped the field every run.
        source_status = EXCLUDED.source_status,
        start_date = COALESCE(EXCLUDED.start_date, ft_funded_projects.start_date),
        end_date = COALESCE(EXCLUDED.end_date, ft_funded_projects.end_date),
        coordinator_name = EXCLUDED.coordinator_name,
        coordinator_country = EXCLUDED.coordinator_country,
        coordinator_pic = COALESCE(EXCLUDED.coordinator_pic, ft_funded_projects.coordinator_pic),
        total_cost = EXCLUDED.total_cost,
        eu_contribution = EXCLUDED.eu_contribution,
        organisations = EXCLUDED.organisations,
        topics = EXCLUDED.topics,
        euroscivoc = EXCLUDED.euroscivoc,
        legal_basis_details = EXCLUDED.legal_basis_details,
        web_links = EXCLUDED.web_links,
        scraped_at = NOW(),
        last_updated = NOW()
"""


def _params_for(rec: dict) -> dict:
    p = dict(rec)
    for k in ("organisations", "topics", "euroscivoc", "legal_basis_details", "web_links"):
        p[k] = psycopg2.extras.Json(p.get(k) or [])
    return p


def ingest_dump(programme: str, conn, args) -> Optional[tuple]:
    """(projects built, projects written), or None when the dump is unchanged since our last read."""
    modified, read = dump_modified(DUMPS[programme]), last_read(conn, programme)
    if not args.force and modified and read and modified <= read:
        print(f"\n[OK] {programme}: dump unchanged since {modified:%d %b %Y} "
              f"(last read {read:%d %b %Y}); skipped", flush=True)
        return None
    cache = Path(tempfile.gettempdir()) / f"cordis-{programme}.zip"
    print(f"\n[INFO] downloading {DUMPS[programme]} (modified {modified}) -> {cache}", flush=True)
    download(DUMPS[programme], cache)
    print(f"[INFO] {cache.stat().st_size / 1024 / 1024:.1f} MB", flush=True)
    try:
        built, written = _read_dump(programme, cache, conn, args)
    finally:
        cache.unlink(missing_ok=True)
    if args.apply and modified and built:
        save_read(conn, programme, modified, built, written)
    return built, written


BATCH_SIZE = 200


def _write(conn, chunk: List[dict]) -> int:
    """One SQL round-trip per batch (execute_batch); a failed batch falls back to row by row."""
    cur = conn.cursor()
    try:
        psycopg2.extras.execute_batch(cur, _UPSERT_SQL, [_params_for(r) for r in chunk],
                                      page_size=BATCH_SIZE)
        conn.commit()
        return len(chunk)
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"  [BATCH ERR] {exc} — falling back to per-row", flush=True)
    written = 0
    for r in chunk:
        try:
            cur.execute(_UPSERT_SQL, _params_for(r))
            conn.commit()
            written += 1
        except Exception as exc2:  # noqa: BLE001
            conn.rollback()
            print(f"    [SKIP] {r.get('project_id')}: {exc2}", flush=True)
    return written


def _read_dump(programme: str, cache: Path, conn, args) -> tuple:
    """Streams project.csv: each batch is written as it is built and each project's lookups are
    dropped once used, so the whole dump is never held twice (H2020 peaked at 0.8 GB that way)."""
    built = inserted = 0
    chunk: List[dict] = []
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
        with z.open("project.csv") as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8-sig"), delimiter=";")
            for row in reader:
                pid = (row.get("id") or "").strip()
                if not pid:
                    continue
                topics = [
                    {"topic": (t.get("topic") or "").strip() or None,
                     "title": (t.get("title") or "").strip() or None}
                    for t in topics_map.pop(pid, [])
                ]
                eurosci = [
                    {"code": (e.get("euroSciVocCode") or "").strip() or None,
                     "path": (e.get("euroSciVocPath") or "").strip() or None,
                     "title": (e.get("euroSciVocTitle") or "").strip() or None}
                    for e in eurosci_map.pop(pid, [])
                ]
                legal = [
                    {"code": (lb.get("legalBasis") or "").strip() or None,
                     "title": (lb.get("title") or "").strip() or None,
                     "unique_programme_part": _to_bool(lb.get("uniqueProgrammePart"))}
                    for lb in legal_map.pop(pid, [])
                ]
                weblinks = [
                    {"url": (w.get("physUrl") or "").strip() or None,
                     "type": (w.get("type") or "").strip() or None,
                     "title": (w.get("title") or "").strip() or None}
                    for w in weblink_map.pop(pid, [])
                ]
                rec = normalise(
                    row, coord_map.pop(pid, {}), programme.upper(),
                    organisations=full_orgs_map.pop(pid, []),
                    topics=topics,
                    euroscivoc=eurosci,
                    legal_basis_details=legal,
                    web_links=weblinks,
                )
                if not rec["title"]:
                    continue
                if args.limit and built >= args.limit:
                    break
                built += 1
                if not args.apply:
                    continue
                chunk.append(rec)
                if len(chunk) == BATCH_SIZE:
                    inserted += _write(conn, chunk)
                    chunk = []
                    if built % 2000 == 0:
                        print(f"  ... {built:,} written so far: {inserted:,}", flush=True)
        if chunk:
            inserted += _write(conn, chunk)
    print(f"[INFO] built {built:,} project records", flush=True)
    print(f"[DONE] {programme}: inserted={inserted}", flush=True)
    return built, inserted


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="0 = unbounded")
    ap.add_argument("--programme", choices=["horizon", "h2020", "fp7", "all"], default="horizon")
    ap.add_argument("--force", action="store_true", help="Read a dump even if unchanged since our last read.")
    args = ap.parse_args(argv)

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)
    conn = psycopg2.connect(db_url)

    outcome = {p: ingest_dump(p, conn, args) for p in ("horizon", "h2020", "fp7")
               if args.programme in (p, "all")}
    conn.close()
    read = {p: o for p, o in outcome.items() if o is not None}
    print(f"\n[GRAND TOTAL] built={sum(b for b, _ in read.values())} "
          f"inserted={sum(w for _, w in read.values())} skipped={sorted(set(outcome) - set(read))} "
          f"apply={args.apply}")
    empty = [p for p, (built, _) in read.items() if built == 0]
    if empty:
        print(f"[ERROR] dump read but no project built: {empty} (format change or a truncated file)")
        return 1
    short = {p: built - written for p, (built, written) in read.items() if args.apply and written < built}
    if short:
        print(f"[SYNC_STATUS] degraded: projects not written {short} (see the [SKIP] lines)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
