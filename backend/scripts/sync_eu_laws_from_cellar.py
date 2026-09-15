#!/usr/bin/env python3.12
"""
Recurring ingest of new OJ L legislation from Cellar into eu_laws.

Why this exists
---------------
Found 15 September 2026: eu_laws had no recurring ingest. Its rows came from
the November 2025 Publications Office bulk export (LEG_2025-11) plus hand
one-shots, so 1,856 OJ L regulations, directives and decisions published since
then were missing, including the Digital Omnibus on AI. The daily
sync_eurlex_via_sparql.py finds new acts but writes them to
legislative_carriages, never to eu_laws.

What it does
------------
1. Asks Cellar SPARQL for sector-3 acts of type R, L or D in the OJ L series
   whose OJ publication date falls in the window, one calendar month per query
   and paged with OFFSET, so nothing is truncated by a LIMIT.
2. Keeps only standard CELEX shapes (3YYYY[RLD]NNNN). Corrigenda and other
   variants are out of scope.
3. Skips CELEX already in eu_laws (checked against the full candidate list,
   not a sample).
4. Skips acts that have no English title yet (Publications Office metadata
   lags up to two working days). They are NOT written with a placeholder:
   the rolling window picks them up on a later run.
5. Inserts a metadata row with xml_path = cellar://..., the same convention as
   the one-shot ingests. Full text is fetched on demand from Cellar.
6. Records a sync_runs row (source_key eu_laws_cellar) and exits non-zero on
   failure, so a broken run is visible rather than silent.

Idempotent: a re-run inserts nothing it has already inserted.

Usage (from backend/):
    python3.12 scripts/sync_eu_laws_from_cellar.py                 # dry-run, last 14 days
    python3.12 scripts/sync_eu_laws_from_cellar.py --apply
    python3.12 scripts/sync_eu_laws_from_cellar.py --since 2025-11-01 --apply   # backfill
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
import time
import uuid as _uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Optional

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(ROOT / ".env")
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.sync.freshness import record_run  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("eu-laws-cellar")

SPARQL_URL = "https://publications.europa.eu/webapi/rdf/sparql"
SOURCE_KEY = "eu_laws_cellar"
PAGE = 500
CELEX_RE = re.compile(r"^3(\d{4})([RLD])(\d{4})$")
TYPE_LABEL = {"R": "Regulation", "L": "Directive", "D": "Decision"}
# "Commission Implementing Regulation (EU) 2026/123 of ..." -> "Commission Implementing Regulation"
# "Council Decision (CFSP) 2026/45 of ..."                -> "Council Decision (CFSP)"
_DOC_TYPE_RE = re.compile(r"^(.*?)\s+(?:\((?:EU|Euratom|EU, Euratom)\)\s+)?(?:No\s+)?\d{4}/\d+")


def _sparql(query: str, retries: int = 3) -> List[Dict[str, str]]:
    last: Optional[Exception] = None
    for attempt in range(retries):
        try:
            r = httpx.post(
                SPARQL_URL,
                data={"query": query, "format": "application/sparql-results+json"},
                timeout=120,
            )
            r.raise_for_status()
            return [
                {k: v["value"] for k, v in b.items()}
                for b in r.json()["results"]["bindings"]
            ]
        except Exception as e:  # noqa: BLE001
            last = e
            log.warning(f"SPARQL attempt {attempt + 1} failed: {type(e).__name__}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"Cellar SPARQL failed after {retries} attempts: {last}")


def _month_windows(since: date, until: date):
    start = since
    while start <= until:
        nxt = (start.replace(day=1) + timedelta(days=32)).replace(day=1)
        end = min(until, nxt - timedelta(days=1))
        yield start, end
        start = end + timedelta(days=1)


def discover(since: date, until: date) -> List[Dict[str, str]]:
    """Every OJ L act of type R/L/D published in [since, until], deduplicated by CELEX."""
    out: Dict[str, Dict[str, str]] = {}
    for w_from, w_to in _month_windows(since, until):
        offset = 0
        while True:
            q = f"""
            PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
            SELECT ?work ?celex ?pub ?docdate ?title ?eli ?eif ?eea ?inforce ?dg WHERE {{
              ?work cdm:official-journal-act_part_of_collection_document
                    <http://publications.europa.eu/resource/authority/document-collection/OJ-L> .
              ?work cdm:official-journal-act_date_publication ?pub .
              FILTER(STR(?pub) >= "{w_from.isoformat()}" && STR(?pub) <= "{w_to.isoformat()}")
              ?work cdm:resource_legal_id_celex ?celex .
              FILTER(REGEX(STR(?celex), "^3[0-9]{{4}}[RLD][0-9]{{4}}$"))
              OPTIONAL {{ ?work cdm:work_date_document ?docdate . }}
              OPTIONAL {{ ?work cdm:resource_legal_eli ?eli . }}
              OPTIONAL {{ ?work cdm:resource_legal_date_entry-into-force ?eif . }}
              OPTIONAL {{ ?work cdm:resource_legal_eea ?eea . }}
              OPTIONAL {{ ?work cdm:resource_legal_in-force ?inforce . }}
              OPTIONAL {{ ?work cdm:resource_legal_responsibility_of_agent ?dg . }}
              OPTIONAL {{
                ?expr cdm:expression_belongs_to_work ?work ;
                      cdm:expression_uses_language
                      <http://publications.europa.eu/resource/authority/language/ENG> ;
                      cdm:expression_title ?title .
              }}
            }}
            ORDER BY ?celex
            LIMIT {PAGE} OFFSET {offset}
            """
            rows = _sparql(q)
            for r in rows:
                c = r.get("celex", "")
                prev = out.get(c)
                # multiple OPTIONAL matches multiply rows; keep the one with a title
                if prev is None or (not prev.get("title") and r.get("title")):
                    out[c] = r
            log.info(f"  {w_from}..{w_to} offset {offset}: {len(rows)} rows")
            if len(rows) < PAGE:
                break
            offset += PAGE
    return list(out.values())


def relations(works: List[str]) -> Dict[str, Dict[str, List[str]]]:
    """amends / based_on CELEX lists per work, in batches."""
    rel: Dict[str, Dict[str, List[str]]] = {}
    for i in range(0, len(works), 60):
        batch = works[i:i + 60]
        values = " ".join(f"<{w}>" for w in batch)
        q = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
        SELECT ?work ?kind ?celex WHERE {{
          VALUES ?work {{ {values} }}
          {{ ?work cdm:resource_legal_amends_resource_legal ?t . BIND("amends" AS ?kind) }}
          UNION
          {{ ?work cdm:resource_legal_based_on_resource_legal ?t . BIND("based_on" AS ?kind) }}
          ?t cdm:resource_legal_id_celex ?celex .
        }}
        """
        for r in _sparql(q):
            d = rel.setdefault(r["work"], {"amends": [], "based_on": []})
            if r["celex"] not in d[r["kind"]]:
                d[r["kind"]].append(r["celex"])
    return rel


def doc_type_from_title(title: str, type_letter: str) -> str:
    m = _DOC_TYPE_RE.match(title or "")
    if m and 0 < len(m.group(1)) <= 120:
        return m.group(1).strip()
    return TYPE_LABEL[type_letter]


def oj_reference(celex: str, pub: str) -> str:
    m = CELEX_RE.match(celex)
    y, n = m.group(1), int(m.group(3))
    d = date.fromisoformat(pub[:10])
    return f"OJ L, {y}/{n}, {d.day}.{d.month}.{d.year}"


_MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august",
     "september", "october", "november", "december"], 1)}
_TITLE_DATE_RE = re.compile(r"\bof\s+(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})")


def document_date(docdate: Optional[str], pub: str, title: str) -> Optional[str]:
    """Adoption date, guarded against Cellar data errors.

    An act cannot be adopted after it is published. Cellar held
    work_date_document 2029-09-10 for 32026R2053, whose title says
    10 September 2026. When the recorded date is later than the OJ publication
    date, take the date written in the title; failing that, the publication date.
    """
    pub = (pub or "")[:10]
    d = (docdate or "")[:10]
    if d and (not pub or d <= pub):
        return d
    m = _TITLE_DATE_RE.search((title or "").replace("\xa0", " "))
    if m and m.group(2).lower() in _MONTHS:
        try:
            return date(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1))).isoformat()
        except ValueError:
            pass
    return pub or None


def build_row(r: Dict[str, str], rel: Dict[str, List[str]], classify) -> Dict:
    celex = r["celex"]
    m = CELEX_RE.match(celex)
    year, letter, number = int(m.group(1)), m.group(2), int(m.group(3))
    title = r["title"].strip()
    doc_type = doc_type_from_title(title, letter)
    meta = {
        "eli": r.get("eli"),
        "oj_publication_date": r.get("pub", "")[:10],
        "entry_into_force": (r.get("eif") or "")[:10] or None,
        "eea_relevance": r.get("eea") in ("1", "true"),
        "in_force": r.get("inforce") in ("1", "true"),
        "responsible_dg": (r.get("dg") or "").rsplit("/", 1)[-1] or None,
        "amends": rel.get("amends", []),
        "based_on": rel.get("based_on", []),
        "cellar_work": r.get("work"),
        "ingested_by": "sync_eu_laws_from_cellar",
    }
    doc_date = document_date(r.get("docdate"), r.get("pub", ""), title)
    return {
        "uuid": str(_uuid.uuid4()),
        "celex": celex,
        "doc_type": doc_type,
        "doc_type_normalized": TYPE_LABEL[letter],
        "title": title,
        "date": doc_date,
        "oj": oj_reference(celex, r["pub"]),
        "area": classify(title, rel.get("amends", []) + rel.get("based_on", [])),
        "basis": [],
        "xml": f"cellar://publications.europa.eu/resource/celex/{celex}",
        "cv": f"OJ_{date.today():%Y-%m}",
        "year": year,
        "letter": letter,
        "number": number,
        "meta": json.dumps(meta),
    }


def make_classifier(db, rel: Dict[str, Dict[str, List[str]]], keywords: Dict[str, List]):
    """policy_area for a new act, same taxonomy as the existing eu_laws rows.

    1. Inherit the most common policy_area of the acts it amends or is based on
       (the citation-propagation strategy of final_classification.py). An
       implementing regulation belongs to the area of its basic act.
    2. Otherwise score the title against final_classification's keyword map,
       on WHOLE WORDS. Its own scorer uses substring counts, so "ets" fires
       inside "markets" and "euro" inside "European".
    3. Otherwise NULL. A wrong area is worse than none.
    """
    refs = sorted({c for d in rel.values() for k in ("amends", "based_on") for c in d[k] if c[:1] == "3"})
    area_of: Dict[str, str] = {}
    for i in range(0, len(refs), 1000):
        for c, a in db.execute(
            text("SELECT celex, policy_area FROM eu_laws WHERE celex = ANY(:c) AND policy_area IS NOT NULL"),
            {"c": refs[i:i + 1000]},
        ):
            area_of[c] = a
    patterns = {
        area: [(re.compile(r"\b" + re.escape(kw) + r"\b"), w) for kw, w in kws]
        for area, kws in keywords.items()
    }

    def classify(title: str, linked: List[str]) -> Optional[str]:
        votes: Dict[str, int] = {}
        for c in linked:
            if c in area_of:
                votes[area_of[c]] = votes.get(area_of[c], 0) + 1
        if votes:
            return max(sorted(votes), key=votes.get)
        t = (title or "").lower()
        scores = {}
        for area, pats in patterns.items():
            total = sum(w * min(len(p.findall(t)), 3) for p, w in pats)
            if total:
                scores[area] = total
        if scores and max(scores.values()) >= 2.0:
            return max(sorted(scores), key=scores.get)
        return None

    return classify


INSERT_SQL = text(
    """
    INSERT INTO eu_laws
        (uuid, celex, doc_type, doc_type_normalized, title, date, oj_reference,
         policy_area, legal_basis, xml_path, is_primary_legislation,
         corpus_version, corpus_status, celex_year, celex_type, celex_number,
         extra_metadata)
    SELECT :uuid, :celex, :doc_type, :doc_type_normalized, :title, CAST(:date AS date), :oj,
           :area, :basis, :xml, true,
           :cv, 'active', :year, :letter, :number, CAST(:meta AS jsonb)
    WHERE NOT EXISTS (SELECT 1 FROM eu_laws WHERE celex = :celex)
    """
)


def main() -> int:
    ap = argparse.ArgumentParser(description="Ingest new OJ L acts from Cellar into eu_laws")
    ap.add_argument("--days", type=int, default=14, help="Rolling window when --since is not given")
    ap.add_argument("--since", type=str, help="YYYY-MM-DD, OJ publication date (backfill)")
    ap.add_argument("--until", type=str, help="YYYY-MM-DD, default today")
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    until = date.fromisoformat(args.until) if args.until else date.today()
    since = date.fromisoformat(args.since) if args.since else until - timedelta(days=args.days)
    started = datetime.now(timezone.utc)
    log.info(f"Window {since} .. {until} (OJ publication date), apply={args.apply}")

    db = SessionLocal()
    try:
        from scripts.eu_law_policy_keywords import AGGRESSIVE_KEYWORDS

        found = discover(since, until)
        log.info(f"Cellar: {len(found)} OJ L acts (R/L/D) in window")

        existing = set()
        celexes = [r["celex"] for r in found]
        for i in range(0, len(celexes), 1000):
            chunk = celexes[i:i + 1000]
            existing |= {
                c for (c,) in db.execute(
                    text("SELECT celex FROM eu_laws WHERE celex = ANY(:c)"), {"c": chunk}
                )
            }
        missing = [r for r in found if r["celex"] not in existing]
        no_title = [r["celex"] for r in missing if not (r.get("title") or "").strip()]
        todo = [r for r in missing if (r.get("title") or "").strip()]
        log.info(
            f"already in eu_laws: {len(existing)} | missing: {len(missing)} "
            f"| no English title yet (deferred): {len(no_title)} | to insert: {len(todo)}"
        )

        rel = relations([r["work"] for r in todo]) if todo else {}
        classify = make_classifier(db, rel, AGGRESSIVE_KEYWORDS)
        rows = [build_row(r, rel.get(r["work"], {}), classify) for r in todo]

        for row in rows[:15]:
            log.info(f"  {row['celex']} | {row['doc_type']} | {row['oj']} | {row['area']} | {row['title'][:70]}")
        if len(rows) > 15:
            log.info(f"  ... and {len(rows) - 15} more")

        if not args.apply:
            log.info("[DRY-RUN] nothing written. Re-run with --apply")
            return 0

        inserted = 0
        for i in range(0, len(rows), 200):
            for row in rows[i:i + 200]:
                inserted += db.execute(INSERT_SQL, row).rowcount
            db.commit()

        # Count what actually persisted, not what was attempted.
        persisted = db.execute(
            text("SELECT count(*) FROM eu_laws WHERE celex = ANY(:c)"),
            {"c": [r["celex"] for r in rows]},
        ).scalar() if rows else 0
        log.info(f"[OK] inserted {inserted}; {persisted}/{len(rows)} of this run's acts now present")
        if persisted != len(rows):
            raise RuntimeError(f"persisted {persisted} of {len(rows)} rows")

        record_run(
            db, source_key=SOURCE_KEY, tier="daily", status="success",
            items_added=inserted, started_at=started,
        )
        return 0
    except Exception as e:  # noqa: BLE001
        db.rollback()
        log.error(f"[ERROR] {type(e).__name__}: {e}")
        if args.apply:
            record_run(
                db, source_key=SOURCE_KEY, tier="daily", status="failed",
                error=f"{type(e).__name__}: {e}", started_at=started,
            )
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
