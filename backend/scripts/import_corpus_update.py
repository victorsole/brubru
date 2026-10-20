"""
Delta Import for EU Law Corpus Updates

Compares a new corpus directory against the existing eu_laws database:
inserts new laws, re-parses changed laws, repoints unchanged laws at the new
directory, and checks laws missing from the corpus against Cellar before
marking any of them repealed.

Rules learned on the LEG_2026-10 update (13 Oct 2026):
- The main file is chosen by what it contains (15 Oct 2026): only a file whose root element is
  the act (ACT, CORR, GENERAL, AGR) qualifies, never an ANNEX page, the DOC cover page or the
  PUBLICATION contents; with several, the one whose title matches the folder's metadata title.
  Keeping a row's earlier file on every import had left 7,352 rows on an annex page and 2,849
  filled from the cover page. A corrigendum takes the republished act when its folder holds one
  (Victor, 15 Oct 2026). A folder with no act file is reported, not read. Title (without
  EUR-Lex's number prefix) and date from the metadata; type from the CELEX letter; the keys the
  old file put in extra_metadata, and caches computed from it, go; other writers' keys stay.
- Only rows from a LEG_* dump are touched; OJ_*, DPP_* and canon rows are other writers'.
- A CELEX already held by another row is never inserted again: the Cellar sync's OJ_* rows hold
  the same acts under different uuids (1,738 duplicates on 13 Oct 2026, removed by hand).
- Absence from the dump is NOT repeal (3 of 30 sampled absent laws were in force):
  only Cellar's in-force flag = 0 marks a row repealed.
- The CELEX comes from the folder's own metadata (tree_non_inferred.rdf), never from the text
  (14 Oct 2026): the parser found none in 224 files, so the act's held CELEX went unchecked and a
  nameless duplicate was inserted; 35 corrigenda took the CELEX their text names (the act they
  correct). Every LEG_2026-10 folder with text states exactly one. Every existing row is checked
  against its folder, changed or not. A new folder whose metadata states none is reported, not
  inserted; a row whose CELEX differs from its folder is reported, not re-keyed (text, EuroVoc and
  links are keyed on it: a person decides); each such row goes to celex_report_<version>.csv.
  Migration 300 makes eu_laws.celex unique; the held map keeps a batch from failing on it.

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
from backend.scripts.leg_export_metadata import COLS as _META_COLS, export_metadata, merged
from backend.scripts.leg_folder import (  # noqa: F401 (re-exported for the repair scripts)
    RDF_CELEX,
    CELEX_SHAPE,
    MAIN_ROOTS,
    WRAPPERS,
    FMX_ROOT,
    RDF_NS,
    CDM_NS,
    TITLE_STOP,
    MATCH_MIN,
    TYPE_OF_LETTER,
    WRONG_FILE_TYPES,
    FILE_KEYS,
    DERIVED_FROM_FILE,
    NUMBER_PREFIX,
    file_root,
    strip_number_prefix,
    usable_title,
    numbered_title,
    title_date,
    act_date,
    rdf_meta,
    title_match,
    main_file,
    number_in_title,
    act_confirmed,
    type_label,
    folder_celex,
    celex_for,
    is_legal_act,
)
from backend.scripts.import_leg_archive import (
    determine_policy_area,
    is_primary_legislation,
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
METADATA_COLS = tuple(c for c in _META_COLS if c not in ("alias", "acronym"))  # aliases.csv is the only source of those
PROGRESS_INTERVAL = 1000
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
SPARQL_CONTROL_CELEX = "32016R0679"  # in force; a batch that does not return it as 1 is rejected
SPARQL_BATCH = 40
RDF_IN_FORCE = re.compile(r"in-force[^>]*>\s*(true|false)\s*<", re.I)


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


def rdf_in_force(corpus_path: Path, uuid: str) -> Optional[bool]:
    """In-force flag from the dump's own metadata (MTD); None when the RDF has no flag."""
    rdf = corpus_path / uuid / "tree_non_inferred.rdf"
    if not rdf.exists():
        return None
    found = RDF_IN_FORCE.findall(rdf.read_text(errors="ignore"))
    return None if not found else found[0].lower() == "true"


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
    # oj_reference is left to fill_eu_laws_oj_reference.py (daily): the Formex file gives no publication date (17 Oct 2026);
    # legal_basis to fill_eu_laws_legal_basis.py (daily): one form, read from Cellar (20 Oct 2026)
    return {
        "doc_type": parsed.doc_type,
        "title": parsed.title,
        "date": parsed.date,
        "policy_area": determine_policy_area(parsed),
        "is_primary_legislation": is_primary_legislation(parsed),
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
        "skipped_not_legal_act": 0,
        "duplicates_without_celex": 0,
        "metadata_without_celex": 0,
        "celex_filled": 0,
        "celex_conflicts": 0,
        "celex_text_disagrees": 0,
        "without_celex_after": 0,
        "repealed": 0,
        "absent_in_force": 0,
        "absent_unverified": 0,
        "no_act_file": 0,
        "not_confirmed": 0,
        "errors": 0,
    }

    try:
        if backup and not dry_run:
            write_backup_csv(db, corpus_version)
        elif backup:
            logger.info("[INFO] DRY RUN: would write the pre-update CSV backup")

        # Find all main XML files in new corpus
        logger.info(f"[INFO] Scanning corpus: {corpus_path}")
        # every folder with Formex text; main_file picks the act's file, at any depth (8 folders keep it in
        # fmx4/NNNN/NN/DOC_n/, which the old top-level glob never read: 30,238 found of 30,246)
        xml_files = [d.name for d in sorted(corpus_path.iterdir()) if (d / "fmx4").is_dir()]
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
        celex_fill = []  # existing rows an earlier import left without CELEX, whose act no other row holds
        celex_report = []  # (uuid, outcome, row or text CELEX, folder CELEX, holder uuid): every row a person should see
        start_time = time.time()
        pending_count = 0

        def check_existing(uuid, cx, row_celex):
            """Every existing LEG row is checked against its folder's CELEX, changed or not; returns the outcome."""
            celex, outcome = celex_for(uuid, cx, row_celex, held)
            if outcome == "fill":
                held[celex] = uuid
                celex_fill.append({"u": uuid, "c": celex})
            elif outcome == "conflict":
                stats["celex_conflicts"] += 1
                celex_report.append((uuid, outcome, row_celex, cx, ""))
            elif outcome == "held":
                stats["duplicates_without_celex"] += 1
                celex_report.append((uuid, outcome, "", cx, held[cx]))
            elif outcome == "none":
                stats["metadata_without_celex"] += 1
                celex_report.append((uuid, outcome, row_celex or "", "", ""))
            return outcome

        for i, uuid in enumerate(xml_files):
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
                cx = folder_celex(corpus_path, uuid)
                if row is None and cx and not is_legal_act(cx):
                    stats["skipped_not_legal_act"] += 1
                    if verbose:
                        logger.info(f"[SKIP] {uuid}: {cx} is not a legal act (CELEX sector {cx[0]})")
                    continue
                # the act's own file, by content: a row that points at an annex or cover page gets a new hash and is re-read
                meta = {}
                picked, _ = main_file(corpus_path, uuid, cx or (row.celex if row else None),
                                      lambda: meta.setdefault("m", rdf_meta(corpus_path, uuid))["title"], formex_parser,
                                      current=(PROJECT_ROOT / row.xml_path) if row is not None else None)
                if picked is None:
                    # no act file (only annexes, a cover page or scans): never read a row from one
                    stats["no_act_file"] += 1
                    celex_report.append((uuid, "no_act_file", row.celex if row is not None else "", cx or "", ""))
                    logger.warning(f"[WARN] Not read, the folder holds no act file: {uuid}")
                    continue
                xml_path = picked
                xml_rel = stored_path(xml_path)
                content_hash = compute_file_hash(xml_path)

                if row is not None and row.content_hash == content_hash:
                    stats["unchanged"] += 1
                    if row.xml_path != xml_rel or row.corpus_version != corpus_version:
                        refresh.append({"u": uuid, "p": xml_rel, "v": corpus_version})
                    check_existing(uuid, cx, row.celex)
                    continue

                parsed = formex_parser.parse_file(xml_path)
                if not parsed.title:
                    stats["errors"] += 1
                    logger.warning(f"[WARN] No title after parse: {uuid}")
                    continue
                fields = parsed_fields(parsed, xml_rel, content_hash, corpus_version)
                m = meta.setdefault("m", rdf_meta(corpus_path, uuid))  # title and date from the metadata, like the CELEX
                why_not = act_confirmed(cx or (row.celex if row is not None else None), parsed, usable_title(m["title"]))
                if why_not:  # the same gate as repair_eu_laws_wrong_file: never write a file that may not be the act
                    stats["not_confirmed"] += 1
                    celex_report.append((uuid, "file_not_confirmed: " + why_not, row.celex if row is not None else "", cx or "", ""))
                    if verbose:
                        logger.info(f"[WARN] {uuid}: {xml_rel} not written ({why_not})")
                    continue
                fields["title"] = numbered_title(usable_title(m["title"]) or fields["title"], xml_path)
                # the date the title gives the act, else the metadata's (Cellar errs: 32026R0144 held 2025-01-14)
                fields["date"] = act_date(cx or (row.celex if row is not None else None), fields["title"],
                                          m["date"] or fields["date"])
                fields.update(export_metadata(corpus_path, uuid, cx or (row.celex if row is not None else None)))

                if parsed.celex and cx and parsed.celex != cx:
                    # usually the act the text amends or implements: the metadata is the folder's own
                    stats["celex_text_disagrees"] += 1
                    celex_report.append((uuid, "text_names_another", parsed.celex, cx, ""))

                if row is not None:
                    if check_existing(uuid, cx, row.celex) == "held":
                        continue  # a nameless duplicate of an act another row holds: not re-parsed
                    # Changed: the CELEX column is never written here (no regress to NULL, no re-key)
                    if not dry_run:
                        law = db.query(EULaw).filter(EULaw.uuid == uuid).first()
                        if law:
                            for k, v in fields.items():
                                if k == "extra_metadata":  # a new file: its keys and what was cached from the old one go
                                    keep = {a: b for a, b in (law.extra_metadata or {}).items()
                                            if a not in FILE_KEYS + DERIVED_FROM_FILE}
                                    v = {**keep, **v}
                                elif k in METADATA_COLS:
                                    v = merged(k, getattr(law, k), v)  # never blank, merge procedures, in_force kept
                                setattr(law, k, v)
                            law.doc_type_normalized = type_label(law.celex, law.doc_type_normalized)
                            law.corpus_status = law.corpus_status or "active"
                            pending_count += 1
                    stats["updated"] += 1
                    if verbose:
                        logger.info(f"[UPDATE] {uuid} ({row.celex or 'no CELEX'})")
                else:
                    celex, outcome = celex_for(uuid, cx, None, held)
                    if outcome == "held":
                        # Another row (usually an OJ_* row from the Cellar sync) already holds this act
                        stats["skipped_celex_held"] += 1
                        if verbose:
                            logger.info(f"[SKIP] {uuid}: {cx} is held by {held[cx]}")
                        continue
                    if outcome == "none":
                        stats["skipped_no_celex"] += 1
                        celex_report.append((uuid, "new_without_celex", "", "", ""))
                        logger.warning(f"[WARN] Not imported, the folder's metadata states no single CELEX: {uuid}")
                        continue
                    held[celex] = uuid
                    # New law: the dump's own in-force flag decides the status
                    status = "repealed" if rdf_in_force(corpus_path, uuid) is False else "active"
                    if not dry_run:
                        db.add(EULaw(
                            uuid=uuid, celex=celex, corpus_status=status,
                            doc_type_normalized=type_label(celex, None), **fields,
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
        # Rows left without CELEX take their folder's; counted as persisted. The NOT EXISTS skips a CELEX another
        # writer (the daily Cellar sync) stored during the run, which the unique index (migration 300) would refuse.
        if dry_run:
            stats["celex_filled"] = len(celex_fill)
        else:
            for f in celex_fill:
                stats["celex_filled"] += db.execute(
                    text("UPDATE eu_laws SET celex = :c WHERE uuid = :u AND coalesce(celex, '') = '' "
                         "AND NOT EXISTS (SELECT 1 FROM eu_laws o WHERE o.celex = :c)"), f,
                ).rowcount
            db.commit()
        stats["without_celex_after"] = db.execute(
            text("SELECT count(*) FROM eu_laws WHERE corpus_version = :v AND coalesce(celex, '') = ''"),
            {"v": corpus_version},
        ).scalar()
        if celex_report:
            cr_path = PROJECT_ROOT / "backend" / "data" / "backups" / f"celex_report_{corpus_version}{'_dry_run' if dry_run else ''}.csv"
            cr_path.parent.mkdir(parents=True, exist_ok=True)
            with open(cr_path, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["uuid", "outcome", "row_or_text_celex", "folder_celex", "held_by_uuid"])
                w.writerows(celex_report)
            logger.info(f"[INFO] CELEX report ({len(celex_report)} rows for a person): {cr_path}")

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
    logger.info(f"[WARN] Not read, the folder holds no act file (annexes, cover page or scans only): {stats['no_act_file']}")
    logger.info(f"[WARN] Not written, the file is not confirmed as the act in English (listed for a person): {stats['not_confirmed']}")
    logger.info(f"[INFO] New folders skipped, their CELEX is held by another row: {stats['skipped_celex_held']}")
    logger.info(f"[WARN] New folders not imported, their metadata states no single CELEX: {stats['skipped_no_celex']}")
    logger.info(f"[INFO] New folders not imported, not a legal act (CELEX sector other than 3): {stats['skipped_not_legal_act']}")
    logger.info(f"[INFO] Rows without CELEX that took their folder's: {stats['celex_filled']}" + (" (would)" if args.dry_run else ""))
    logger.info(f"[WARN] Rows without CELEX whose act another row holds (duplicates, for a person): {stats['duplicates_without_celex']}")
    logger.info(f"[WARN] Rows whose folder's metadata states no single CELEX: {stats['metadata_without_celex']}")
    logger.info(f"[WARN] Rows whose CELEX differs from their folder's (kept, for a person): {stats['celex_conflicts']}")
    logger.info(f"[INFO] Texts naming another CELEX than their metadata (metadata kept): {stats['celex_text_disagrees']}")
    logger.info(f"[INFO] {corpus_version} rows without CELEX now: {stats['without_celex_after']}")
    logger.info(f"[REPEAL] Absent and not in force at Cellar, marked repealed: {stats['repealed']}")
    logger.info(f"[INFO] Absent but still in force at Cellar (left active): {stats['absent_in_force']}")
    logger.info(f"[INFO] Absent and unverified (left untouched): {stats['absent_unverified']}")
    logger.info(f"[ERROR] Errors: {stats['errors']}")
    logger.info("=" * 60)
    if stats["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
