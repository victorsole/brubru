"""
Fill eu_laws.celex (and its year/type/number parts) from the dump's own metadata (MTD).

Each text folder of a Publications Office dump holds tree_non_inferred.rdf with exactly one
own-work CELEX literal (LEG_2026-10: 30,246 of 30,246 folders with text). The XML parser only finds
a CELEX in about 59% of main files, so the rest were NULL.

Rules:
- Only rows with celex IS NULL are written; an existing CELEX is never overwritten.
- Existing CELEX values are compared with the metadata and disagreements are reported.
- A folder whose RDF does not hold exactly one CELEX is skipped (stays NULL).
- A CELEX already held by another row is reported, not silently duplicated.

Usage (repo root):
    PYTHONPATH=.:backend python3.12 -m backend.scripts.fill_celex_from_mtd \
        --corpus-path docs/LEG_2026-10 [--dry-run]
"""

import argparse
import csv
import logging
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from psycopg2.extras import execute_values
from sqlalchemy import text

from backend.core.database import SessionLocal
from backend.scripts.backfill_eu_laws import parse_celex

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
CELEX_LITERAL = re.compile(r"resource_legal_id_celex[^>]*>\s*([^<\s][^<]*?)\s*<")
PAGE = 1000

UPDATE_SQL = """
UPDATE eu_laws AS e
SET celex = v.celex, celex_year = v.y::int, celex_type = v.t::char(1), celex_number = v.n::int
FROM (VALUES %s) AS v(uuid, celex, y, t, n)
WHERE e.uuid = v.uuid AND e.celex IS NULL
"""


def mtd_celex(corpus_path: Path) -> dict:
    """{uuid: celex} for every text folder; folders without exactly one CELEX are left out."""
    out, odd = {}, 0
    for d in corpus_path.iterdir():
        if not (d / "fmx4").is_dir():
            continue
        rdf = d / "tree_non_inferred.rdf"
        found = set(CELEX_LITERAL.findall(rdf.read_text(errors="ignore"))) if rdf.exists() else set()
        if len(found) == 1:
            out[d.name] = next(iter(found))
        else:
            odd += 1
    logger.info(f"[INFO] MTD CELEX read for {len(out)} folders ({odd} folders without exactly one CELEX)")
    return out


def main():
    ap = argparse.ArgumentParser(description="Fill NULL eu_laws.celex from the corpus metadata")
    ap.add_argument("--corpus-path", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    corpus = Path(args.corpus_path)
    if not corpus.is_absolute():
        corpus = PROJECT_ROOT / corpus
    celex_of = mtd_celex(corpus)
    if not celex_of:
        logger.error("[ERROR] No CELEX read from the corpus metadata. Check the path.")
        sys.exit(1)

    db = SessionLocal()
    try:
        rows = db.execute(text("SELECT uuid, celex FROM eu_laws WHERE uuid = ANY(:u)"), {"u": list(celex_of)}).fetchall()
        held = Counter(r[0] for r in db.execute(text("SELECT celex FROM eu_laws WHERE celex IS NOT NULL")).fetchall())
        stats = Counter()
        todo, mismatches, dupes = [], [], []
        for uuid, current in rows:
            new = celex_of[uuid]
            if current:
                if current == new:
                    stats["already_correct"] += 1
                else:
                    stats["disagrees"] += 1
                    mismatches.append((uuid, current, new))
                continue
            if held.get(new):
                stats["celex_held_by_another_row"] += 1
                dupes.append((uuid, new))
                continue
            p = parse_celex(new)
            todo.append((uuid, new, p["celex_year"] if p else None, p["celex_type"] if p else None,
                         p["celex_number"] if p else None))
            stats["to_fill"] += 1
            if not p:
                stats["to_fill_unparsed_parts"] += 1
        stats["folders_without_row"] = len(celex_of) - len(rows)
        logger.info(f"[INFO] {dict(stats)}")

        out_dir = PROJECT_ROOT / "backend" / "data" / "backups"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        for name, data, header in (("celex_filled", todo, ["uuid", "celex", "y", "t", "n"]),
                                   ("celex_disagrees", mismatches, ["uuid", "db_celex", "mtd_celex"]),
                                   ("celex_held_elsewhere", dupes, ["uuid", "mtd_celex"])):
            if data:
                path = out_dir / f"{name}_{corpus.name}_{stamp}.csv"
                with open(path, "w", newline="") as f:
                    w = csv.writer(f); w.writerow(header); w.writerows(data)
                logger.info(f"[INFO] {len(data)} rows listed in {path.name}")

        if args.dry_run:
            logger.info("[INFO] DRY RUN: no database changes")
            return
        written = 0
        raw = db.connection().connection
        with raw.cursor() as cur:
            for i in range(0, len(todo), PAGE):
                execute_values(cur, UPDATE_SQL, todo[i:i + PAGE], page_size=PAGE)
                written += cur.rowcount
                raw.commit()
        logger.info(f"[OK] CELEX written on {written} rows (expected {len(todo)})")
        if written != len(todo):
            logger.error("[ERROR] Written count differs from expected")
            sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    main()
