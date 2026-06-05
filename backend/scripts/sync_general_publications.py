"""Backfill EU general publications (eu_general_publications) from Cellar SPARQL."""
from __future__ import annotations
import argparse, logging, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from sqlalchemy.dialects.postgresql import insert as pg_insert
from core.database import engine
from models.general_publication import EuGeneralPublication
from services.scrapers import general_publications_ingest as gp
logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("sync_general_publications")

def _bulk(table, rows, conflict_col, batch=500):
    if not rows: return 0
    cols=[c.name for c in table.columns if c.name not in ("id","first_seen","fetched_at")]
    done=0
    for i in range(0,len(rows),batch):
        chunk=[{k:r.get(k) for k in cols} for r in rows[i:i+batch]]
        stmt=pg_insert(table).values(chunk)
        stmt=stmt.on_conflict_do_update(index_elements=[conflict_col], set_={c:getattr(stmt.excluded,c) for c in cols if c!=conflict_col})
        with engine.begin() as conn: conn.execute(stmt)
        done+=len(chunk)
    return done

def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--limit-total",type=int,default=6000); ap.add_argument("--dry-run",action="store_true")
    a=ap.parse_args()
    rows=gp.fetch(limit_total=a.limit_total)
    nb=sum(1 for r in rows if not (r["body_txt"] or "").strip())
    log.info("[gen-pub] fetched %d publications; missing-body=%d", len(rows), nb)
    if a.dry_run:
        for r in rows[:4]: log.info("    %s | %s", r["publication_date"], r["title"][:60])
        return
    n=_bulk(EuGeneralPublication.__table__, rows, "publication_id")
    log.info("[gen-pub] DONE: %d publications upserted", n)

if __name__=="__main__": main()
