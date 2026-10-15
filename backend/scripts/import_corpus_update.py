"""
Delta Import for EU Law Corpus Updates

Compares a new corpus directory against the existing eu_laws database:
inserts new laws, re-parses changed laws, repoints unchanged laws at the new
directory, and checks laws missing from the corpus against Cellar before
marking any of them repealed.

Rules learned on the LEG_2026-10 update (13 Oct 2026):
- An existing row keeps its current main file when that file still exists in the
  folder; the *.doc.xml wrapper has no CELEX, so re-picking it wiped CELEX.
- Only rows from a LEG_* dump are touched; OJ_*, DPP_* and canon rows are other writers'.
- A CELEX already held by another row is never inserted again: the Cellar sync's OJ_* rows hold
  the same acts under different uuids (1,738 duplicates on 13 Oct 2026, removed by hand).
- Absence from the dump is NOT repeal (3 of 30 sampled absent laws were in force):
  only Cellar's in-force flag = 0 marks a row repealed.
- The CELEX comes from the folder's own metadata (tree_non_inferred.rdf), never from the text
  (14 Oct 2026): the parser found none in 224 files, so the act's held CELEX went unchecked and a
  nameless duplicate was inserted; 35 corrigenda took the CELEX their text names (the act they
  correct). Every LEG_2026-10 folder with text states exactly one. A new folder whose metadata
  states none is reported, not inserted; a row whose CELEX differs from its folder is reported, not
  re-keyed (text, EuroVoc and links are keyed on it: a person decides).

Usage (repo root; the models import `core.database`, so backend/ must be on the path):
    PYTHONPATH=.:backend python3.12 -m backend.scripts.import_corpus_update \
        --corpus-path docs/LEG_2026-10 [--dry-run] [--verbose] [--backup]
"""

import argparse
import csv
import hashlib
import json
import logging
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text

from backend.core.database import SessionLocal
from backend.models.eu_law import EULaw
from backend.services.parsers.formex_parser import FormexParser
from backend.scripts.import_leg_archive import (
    determine_policy_area,
    is_primary_legislation,
    find_main_xml_files,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Silence SQLAlchemy logging
logging.getLogger('sqlalchemy.engine').setLevel(logging.WARNING)

BATCH_SIZE = 500
PROGRESS_INTERVAL = 1000
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
SPARQL_CONTROL_CELEX = "32016R0679"  # in force; a batch that does not return it as 1 is rejected
SPARQL_BATCH = 40
RDF_IN_FORCE = re.compile(r"in-force[^>]*>\s*(true|false)\s*<", re.I)
RDF_CELEX = re.compile(r"<[\w.-]+:resource_legal_id_celex\b[^>]*>\s*([^<\s]+)\s*<")


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def detect_corpus_version(corpus_path: Path) -> str:
    """Auto-detect corpus version from directory name (e.g., LEG_2026-06)."""
    name = corpus_path.name
    if name.startswith("LEG_"):
        return name
    return f"LEG_{name}"


def stored_path(xml_path: Path) -> str:
    """Path as stored in eu_laws.xml_path: relative to the repo root, like the existing rows."""
    try:
        return str(xml_path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(xml_path)


def choose_main(default_path: Path, old_xml_path: Optional[str]) -> Path:
    """Keep the row's current main file when it still exists in the folder."""
    if old_xml_path:
        old = default_path.parent / Path(old_xml_path).name
        if old.exists():
            return old
    return default_path


def rdf_in_force(corpus_path: Path, uuid: str) -> Optional[bool]:
    """In-force flag from the dump's own metadata (MTD); None when the RDF has no flag."""
    rdf = corpus_path / uuid / "tree_non_inferred.rdf"
    if not rdf.exists():
        return None
    found = RDF_IN_FORCE.findall(rdf.read_text(errors="ignore"))
    return None if not found else found[0].lower() == "true"


def folder_celex(corpus_path: Path, uuid: str) -> Optional[str]:
    """The folder's own CELEX from the dump's metadata; None unless it states exactly one."""
    rdf = corpus_path / uuid / "tree_non_inferred.rdf"
    if not rdf.exists():
        return None
    found = set(RDF_CELEX.findall(rdf.read_text(errors="ignore")))
    return found.pop() if len(found) == 1 else None


def celex_for(uuid: str, cx: Optional[str], row_celex: Optional[str], held: dict) -> tuple:
    """(CELEX the row gets, outcome) given its folder's CELEX cx and the {celex: uuid} map of rows holding one.

    keep: the row already carries cx | fill: a new row, or a row without CELEX, takes cx |
    held: another row holds cx, so this folder duplicates an act already in the table: not written |
    conflict: the row carries another CELEX than its folder states: kept, for a person |
    none: the metadata states no single CELEX.
    """
    if not cx:
        return row_celex, "none"
    if held.get(cx, uuid) != uuid:
        return row_celex, "held"
    if row_celex == cx:
        return cx, "keep"
    if not row_celex:
        return cx, "fill"
    return row_celex, "conflict"


def cellar_in_force(celexes: list) -> dict:
    """Cellar in-force flag per CELEX: {celex: '0' | '1' | None (unverified)}.

    A batch is rejected (all None) unless the control CELEX comes back as 1:
    an empty or failed answer must never read as 'not in force'.
    """
    out = {}
    for i in range(0, len(celexes), SPARQL_BATCH):
        batch = celexes[i:i + SPARQL_BATCH]
        values = " ".join(
            f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>'
            for c in batch + [SPARQL_CONTROL_CELEX]
        )
        query = (
            "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
            f"SELECT ?celex ?inforce WHERE {{ VALUES ?celex {{ {values} }} "
            "?w cdm:resource_legal_id_celex ?celex . "
            "OPTIONAL { ?w cdm:resource_legal_in-force ?inforce } }"
        )
        flags = {}
        try:
            req = urllib.request.Request(
                SPARQL_URL + "?" + urllib.parse.urlencode(
                    {"query": query, "format": "application/sparql-results+json"}),
                headers={"Accept": "application/sparql-results+json"},
            )
            rows = json.load(urllib.request.urlopen(req, timeout=120))["results"]["bindings"]
            for b in rows:
                flags.setdefault(b["celex"]["value"], set()).add(b.get("inforce", {}).get("value"))
        except Exception as e:
            logger.error(f"[ERROR] Cellar SPARQL batch {i // SPARQL_BATCH} failed: {type(e).__name__}: {e}")
            flags = {}
        if flags.get(SPARQL_CONTROL_CELEX) != {"1"}:
            logger.error(f"[ERROR] Cellar batch {i // SPARQL_BATCH} rejected (control CELEX not returned as in force)")
            out.update({c: None for c in batch})
            continue
        for c in batch:
            v = flags.get(c)
            out[c] = next(iter(v)) if v and len(v) == 1 and None not in v else None
    return out


def write_backup_csv(db, corpus_version: str) -> Path:
    """Pre-update copy of every LEG_* row's mutable columns, as a local CSV.

    Not a backup TABLE: a new public.* table is readable through the Supabase Data API
    until RLS and grants are set, and this copy never needs to be served.
    """
    out_dir = PROJECT_ROOT / "backend" / "data" / "backups"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"eu_laws_pre_{corpus_version}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    rows = db.execute(text(
        "SELECT uuid, celex, title, xml_path, content_hash, corpus_version, corpus_status "
        "FROM eu_laws WHERE corpus_version LIKE 'LEG\\_%' ORDER BY uuid"
    )).fetchall()
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["uuid", "celex", "title", "xml_path", "content_hash", "corpus_version", "corpus_status"])
        w.writerows(rows)
    logger.info(f"[OK] Backup written: {path} ({len(rows)} rows)")
    return path


def parsed_fields(parsed, xml_rel: str, content_hash: str, corpus_version: str) -> dict:
    return {
        "doc_type": parsed.doc_type,
        "title": parsed.title,
        "date": parsed.date,
        "oj_reference": parsed.oj_reference,
        "policy_area": determine_policy_area(parsed),
        "is_primary_legislation": is_primary_legislation(parsed),
        "legal_basis": parsed.legal_basis if parsed.legal_basis else None,
        "citations": parsed.citations if parsed.citations else None,
        "xml_path": xml_rel,
        "content_hash": content_hash,
        "corpus_version": corpus_version,
        "extra_metadata": {
            "short_title": parsed.short_title,
            "language": parsed.language,
            "page_count": parsed.page_count,
            "eea_relevance": parsed.eea_relevance,
            "article_count": len(parsed.articles),
            "recital_count": len(parsed.recitals),
            "annex_count": len(parsed.annexes),
        },
    }


def process_corpus(
    corpus_path: Path,
    corpus_version: str,
    dry_run: bool = False,
    verbose: bool = False,
    backup: bool = False,
):
    """Main delta import logic."""
    db = SessionLocal()
    formex_parser = FormexParser()

    stats = {
        "new": 0,
        "updated": 0,
        "unchanged": 0,
        "refreshed": 0,
        "skipped_other_source": 0,
        "skipped_celex_held": 0,
        "skipped_no_celex": 0,
        "celex_filled": 0,
        "celex_conflicts": 0,
        "celex_text_disagrees": 0,
        "no_celex_left": 0,
        "repealed": 0,
        "absent_in_force": 0,
        "absent_unverified": 0,
        "errors": 0,
    }

    try:
        if backup and not dry_run:
            write_backup_csv(db, corpus_version)
        elif backup:
            logger.info("[INFO] DRY RUN: would write the pre-update CSV backup")

        # Find all main XML files in new corpus
        logger.info(f"[INFO] Scanning corpus: {corpus_path}")
        xml_files = find_main_xml_files(corpus_path)
        total_files = len(xml_files)
        logger.info(f"[INFO] Found {total_files} documents in new corpus")

        if total_files == 0:
            logger.error("[ERROR] No documents found in corpus. Check the path.")
            stats["errors"] += 1
            return stats

        # Load existing rows in bulk for fast lookup
        logger.info("[INFO] Loading existing laws from database...")
        existing = {
            r.uuid: r for r in db.query(
                EULaw.uuid, EULaw.celex, EULaw.content_hash, EULaw.xml_path,
                EULaw.corpus_version, EULaw.corpus_status,
            ).all()
        }
        logger.info(f"[INFO] Loaded {len(existing)} existing laws from database")

        held = {
            c: u for c, u in db.query(EULaw.celex, EULaw.uuid).filter(EULaw.celex.isnot(None)).all()
        }
        new_corpus_uuids = set()

        def flush():
            """Commit pending ORM rows; a failed batch is rolled back and counted, never swallowed."""
            nonlocal pending_count
            if dry_run or pending_count == 0:
                return
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                stats["errors"] += pending_count
                logger.error(f"[ERROR] batch of {pending_count} rolled back: {type(e).__name__}: {str(e)[:200]}")
            pending_count = 0

        refresh = []  # unchanged rows that only need the new path / version
        celex_fill = []  # unchanged rows an earlier import left without CELEX
        start_time = time.time()
        pending_count = 0

        for i, (uuid, default_path) in enumerate(xml_files):
            new_corpus_uuids.add(uuid)

            if (i + 1) % PROGRESS_INTERVAL == 0:
                elapsed = time.time() - start_time
                rate = (i + 1) / elapsed if elapsed > 0 else 0
                eta = (total_files - (i + 1)) / rate if rate > 0 else 0
                logger.info(
                    f"[INFO] Progress: {i + 1}/{total_files} "
                    f"({rate:.1f}/s, ETA: {eta / 60:.1f} min) -- "
                    f"new={stats['new']}, updated={stats['updated']}, "
                    f"unchanged={stats['unchanged']}, errors={stats['errors']}"
                )

            row = existing.get(uuid)
            if row is not None and not (row.corpus_version or "").startswith("LEG_"):
                # OJ_*, DPP_*, canon rows belong to other writers
                stats["skipped_other_source"] += 1
                if verbose:
                    logger.info(f"[SKIP] {uuid} belongs to {row.corpus_version}")
                continue

            try:
                xml_path = choose_main(default_path, row.xml_path if row else None)
                xml_rel = stored_path(xml_path)
                content_hash = compute_file_hash(xml_path)

                if row is not None and row.content_hash == content_hash:
                    stats["unchanged"] += 1
                    if row.xml_path != xml_rel or row.corpus_version != corpus_version:
                        refresh.append({"u": uuid, "p": xml_rel, "v": corpus_version})
                    if not row.celex:
                        celex, outcome = celex_for(uuid, folder_celex(corpus_path, uuid), None, held)
                        if outcome == "fill":
                            held[celex] = uuid
                            celex_fill.append({"u": uuid, "c": celex})
                            stats["celex_filled"] += 1
                        else:
                            stats["no_celex_left"] += 1
                            if verbose:
                                logger.info(f"[WARN] {uuid} stays without CELEX ({outcome})")
                    continue

                parsed = formex_parser.parse_file(xml_path)
                if not parsed.title:
                    stats["errors"] += 1
                    logger.warning(f"[WARN] No title after parse: {uuid}")
                    continue

                cx = folder_celex(corpus_path, uuid)
                if parsed.celex and cx and parsed.celex != cx:
                    stats["celex_text_disagrees"] += 1
                    if verbose:
                        logger.info(f"[WARN] {uuid}: the text names {parsed.celex}, the metadata {cx}: metadata kept")
                celex, outcome = celex_for(uuid, cx, row.celex if row else None, held)
                if outcome == "held":
                    # Another row (usually an OJ_* row from the Cellar sync) already holds this act
                    stats["skipped_celex_held"] += 1
                    if verbose:
                        logger.info(f"[SKIP] {uuid}: {cx} is held by {held[cx]}")
                    continue
                if outcome == "none" and row is None:
                    stats["skipped_no_celex"] += 1
                    logger.warning(f"[WARN] Not imported, the folder's metadata states no single CELEX: {uuid}")
                    continue
                if outcome == "conflict":
                    stats["celex_conflicts"] += 1
                    logger.warning(f"[WARN] {uuid} keeps {row.celex}; its folder states {cx}: left for a person")
                if outcome == "fill" and row is not None:
                    stats["celex_filled"] += 1
                if celex:
                    held[celex] = uuid

                if row is not None:
                    # Changed: never regress CELEX to NULL, never re-key
                    if not dry_run:
                        law = db.query(EULaw).filter(EULaw.uuid == uuid).first()
                        if law:
                            for k, v in parsed_fields(parsed, xml_rel, content_hash, corpus_version).items():
                                setattr(law, k, v)
                            law.celex = celex
                            law.corpus_status = law.corpus_status or "active"
                            pending_count += 1
                    stats["updated"] += 1
                    if verbose:
                        logger.info(f"[UPDATE] {uuid} ({celex or 'no CELEX'})")
                else:
                    # New law: the dump's own in-force flag decides the status
                    status = "repealed" if rdf_in_force(corpus_path, uuid) is False else "active"
                    if not dry_run:
                        db.add(EULaw(
                            uuid=uuid, celex=celex, corpus_status=status,
                            **parsed_fields(parsed, xml_rel, content_hash, corpus_version),
                        ))
                        pending_count += 1
                    stats["new"] += 1
                    if verbose:
                        logger.info(f"[NEW] {uuid} ({celex}) {status}")

                if pending_count >= BATCH_SIZE:
                    flush()

            except Exception as e:
                stats["errors"] += 1
                logger.error(f"[ERROR] {uuid}: {type(e).__name__}: {e}")
                if not dry_run:
                    db.rollback()
                    stats["errors"] += pending_count  # rows rolled back with the failed one
                    pending_count = 0

        flush()

        # Repoint unchanged rows (path + version only; updated_at is not touched)
        stats["refreshed"] = len(refresh)
        logger.info(f"[INFO] {len(refresh)} unchanged laws to repoint at {corpus_version}")
        if not dry_run:
            for j in range(0, len(refresh), BATCH_SIZE):
                db.execute(
                    text("UPDATE eu_laws SET xml_path = :p, corpus_version = :v WHERE uuid = :u"),
                    refresh[j:j + BATCH_SIZE],
                )
                db.commit()
            for j in range(0, len(celex_fill), BATCH_SIZE):
                db.execute(
                    text("UPDATE eu_laws SET celex = :c WHERE uuid = :u AND coalesce(celex, '') = ''"),
                    celex_fill[j:j + BATCH_SIZE],
                )
                db.commit()

        # Laws in a LEG_* dump but not in this one: verify at Cellar, never infer from absence
        absent = [
            u for u, r in existing.items()
            if (r.corpus_version or "").startswith("LEG_")
            and u not in new_corpus_uuids and r.corpus_status != "repealed"
        ]
        logger.info(f"[INFO] {len(absent)} laws are not in the new corpus; checking Cellar in-force flags")
        celex_of = {u: existing[u].celex for u in absent if existing[u].celex}
        flags = cellar_in_force(sorted(set(celex_of.values())))
        to_repeal = []
        report = []
        for u in absent:
            flag = flags.get(celex_of.get(u))
            if flag == "0":
                to_repeal.append(u)
            elif flag == "1":
                stats["absent_in_force"] += 1
            else:
                stats["absent_unverified"] += 1
            report.append((u, celex_of.get(u, ""), {"0": "not_in_force", "1": "in_force"}.get(flag, "unverified")))
        stats["repealed"] = len(to_repeal)
        if not dry_run:
            for j in range(0, len(to_repeal), BATCH_SIZE):
                db.query(EULaw).filter(EULaw.uuid.in_(to_repeal[j:j + BATCH_SIZE])).update(
                    {"corpus_status": "repealed"}, synchronize_session=False)
                db.commit()
        if report:
            # a dry run must not overwrite the real run's report
            rep_path = PROJECT_ROOT / "backend" / "data" / "backups" / f"absent_from_{corpus_version}{'_dry_run' if dry_run else ''}.csv"
            rep_path.parent.mkdir(parents=True, exist_ok=True)
            with open(rep_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["uuid", "celex", "cellar_status"])
                w.writerows(report)
            logger.info(f"[INFO] Absent-law report: {rep_path}")

    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(
        description="Delta import for EU law corpus updates"
    )
    parser.add_argument(
        "--corpus-path", type=str, required=True,
        help="Path to new corpus directory (e.g., docs/LEG_2026-10)"
    )
    parser.add_argument(
        "--corpus-version", type=str, default=None,
        help="Corpus version label (default: auto-detect from directory name)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Show what would happen without making DB changes"
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Show each file as it is processed"
    )
    parser.add_argument(
        "--backup", action="store_true",
        help="Write a pre-update CSV of every LEG_* row to backend/data/backups/"
    )

    args = parser.parse_args()

    corpus_path = Path(args.corpus_path)
    if not corpus_path.is_absolute():
        corpus_path = PROJECT_ROOT / args.corpus_path

    if not corpus_path.exists():
        logger.error(f"[ERROR] Corpus path not found: {corpus_path}")
        sys.exit(1)

    corpus_version = args.corpus_version or detect_corpus_version(corpus_path)

    logger.info("=" * 60)
    logger.info("[INFO] EU Law Corpus Delta Import")
    logger.info(f"[INFO] Corpus path: {corpus_path}")
    logger.info(f"[INFO] Corpus version: {corpus_version}")
    if args.dry_run:
        logger.info("[INFO] DRY RUN -- no database changes will be made")
    if args.backup:
        logger.info("[INFO] Pre-update CSV backup requested")
    logger.info("=" * 60)

    start_time = time.time()
    stats = process_corpus(
        corpus_path=corpus_path,
        corpus_version=corpus_version,
        dry_run=args.dry_run,
        verbose=args.verbose,
        backup=args.backup,
    )
    elapsed = time.time() - start_time

    logger.info("=" * 60)
    logger.info("[INFO] DELTA IMPORT " + ("DRY RUN " if args.dry_run else "") + ("FAILED" if stats["errors"] else "COMPLETE"))
    logger.info(f"[INFO] Time: {elapsed:.1f}s ({elapsed / 60:.1f} min)")
    logger.info(f"[NEW] New laws inserted: {stats['new']}")
    logger.info(f"[UPDATE] Laws re-parsed and updated: {stats['updated']}")
    logger.info(f"[INFO] Unchanged: {stats['unchanged']} (repointed at {corpus_version}: {stats['refreshed']})")
    logger.info(f"[INFO] Skipped, owned by another source: {stats['skipped_other_source']}")
    logger.info(f"[INFO] Skipped, CELEX already held by another row: {stats['skipped_celex_held']}")
    logger.info(f"[INFO] CELEX taken from the folder's metadata by a row that had none: {stats['celex_filled']}")
    logger.info(f"[WARN] Not imported, the folder's metadata states no single CELEX: {stats['skipped_no_celex']}")
    logger.info(f"[WARN] Rows still without CELEX (their act is held by another row): {stats['no_celex_left']}")
    logger.info(f"[WARN] Rows whose CELEX differs from their folder's (kept, for a person): {stats['celex_conflicts']}")
    logger.info(f"[INFO] Texts naming another CELEX than their metadata (metadata kept): {stats['celex_text_disagrees']}")
    logger.info(f"[REPEAL] Absent and not in force at Cellar, marked repealed: {stats['repealed']}")
    logger.info(f"[INFO] Absent but still in force at Cellar (left active): {stats['absent_in_force']}")
    logger.info(f"[INFO] Absent and unverified (left untouched): {stats['absent_unverified']}")
    logger.info(f"[ERROR] Errors: {stats['errors']}")
    logger.info("=" * 60)
    if stats["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
