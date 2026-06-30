"""
Step 1a of the PyEuroVoc long-context retraining corpus.

Pull the GOLD EuroVoc descriptors for every CELEX in eu_laws from Cellar
(predicate cdm:work_is_about_concept_eurovoc), so we have a (CELEX -> official
EuroVoc subject set) table. This is the supervision signal for the retraining;
the DB's own `subject_matter` column is garbage and is NOT used.

Design notes (each one an audited finding from the pilot, 30 Jun 2026):
  - The CELEX literal MUST be typed ^^xsd:string or Virtuoso returns 0 matches.
  - Batched with VALUES (~100 CELEX/query) so the full ~28k is a few minutes,
    not 28k round-trips.
  - Resumable: already-pulled CELEX are skipped on a re-run (append-only JSONL).
  - Per-batch retry with backoff; a failing batch is split and retried so one
    bad CELEX cannot lose a whole batch.
  - EuroVoc "new concept" ids (c_xxxx, not in the 7,029 release) are recorded
    separately, never silently dropped.

Read-only against publications.europa.eu. No GPU, no LLM.

Run:  python3.12 scripts/build_eurovoc_corpus.py            # full
      python3.12 scripts/build_eurovoc_corpus.py --limit 500 --batch 100
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import logging
logging.disable(logging.WARNING)
from core.database import SessionLocal  # noqa: E402
from sqlalchemy import text  # noqa: E402

ENDPOINT = "http://publications.europa.eu/webapi/rdf/sparql"
XSD = "^^<http://www.w3.org/2001/XMLSchema#string>"
_EV_RE = re.compile(r"eurovoc\.europa\.eu/(\w+)")
OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eurovoc_corpus"
GOLD_PATH = OUT_DIR / "gold_labels.jsonl"
DESC_PATH = Path(__file__).resolve().parent.parent / "data" / "eu_vocabularies" / "eurovoc_descriptors.json"


def _descriptors():
    """id -> {label, mt} for the 7,029-descriptor release."""
    return {d["id"]: {"label": d["label"], "mt": d.get("mt")}
            for d in json.loads(DESC_PATH.read_text())}


def _query(celexes: list[str], timeout: int = 180) -> dict[str, list[str]]:
    vals = " ".join(f'"{c}"{XSD}' for c in celexes)
    q = (f"PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>\n"
         f"SELECT ?celex ?ev WHERE {{ VALUES ?celex {{ {vals} }} "
         f"?work cdm:resource_legal_id_celex ?celex . "
         f"?work cdm:work_is_about_concept_eurovoc ?ev . }}")
    r = requests.get(ENDPOINT, params={"query": q, "format": "application/sparql-results+json"},
                     headers={"Accept": "application/sparql-results+json"}, timeout=timeout)
    r.raise_for_status()
    out: dict[str, list[str]] = {}
    for b in r.json()["results"]["bindings"]:
        m = _EV_RE.search(b["ev"]["value"])
        if m:
            out.setdefault(b["celex"]["value"], []).append(m.group(1))
    return out


def _batch_with_retry(celexes: list[str], *, tries: int = 3) -> dict[str, list[str]]:
    """Query a batch; on failure back off, then split-and-retry so one bad CELEX
    cannot sink the whole batch."""
    for attempt in range(tries):
        try:
            return _query(celexes)
        except Exception as e:
            if attempt < tries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            if len(celexes) > 1:  # split and retry the halves
                mid = len(celexes) // 2
                left = _batch_with_retry(celexes[:mid], tries=tries)
                right = _batch_with_retry(celexes[mid:], tries=tries)
                return {**left, **right}
            print(f"  [skip] CELEX {celexes} failed: {type(e).__name__}", flush=True)
            return {}
    return {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=None, help="cap number of CELEX (testing)")
    ap.add_argument("--batch", type=int, default=100)
    ap.add_argument("--pause", type=float, default=0.3, help="seconds between batches (politeness)")
    args = ap.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    descriptors = _descriptors()

    db = SessionLocal()
    rows = db.execute(text(
        "SELECT DISTINCT celex FROM eu_laws WHERE celex IS NOT NULL AND celex <> '' ORDER BY celex")).fetchall()
    db.close()
    all_celex = [r[0] for r in rows]
    if args.limit:
        all_celex = all_celex[: args.limit]

    # resume: skip CELEX already written
    done: set[str] = set()
    if GOLD_PATH.exists():
        for line in GOLD_PATH.read_text().splitlines():
            try:
                done.add(json.loads(line)["celex"])
            except Exception:
                pass
    todo = [c for c in all_celex if c not in done]
    print(f"[corpus] {len(all_celex)} distinct CELEX | {len(done)} already pulled | {len(todo)} to do "
          f"| {len(descriptors)} descriptors loaded", flush=True)

    t0 = time.time()
    written = covered = total_tags = c_tags = unmapped = 0
    with GOLD_PATH.open("a", encoding="utf-8") as f:
        for i in range(0, len(todo), args.batch):
            chunk = todo[i: i + args.batch]
            gold = _batch_with_retry(chunk)
            for celex in chunk:
                ids = sorted(set(gold.get(celex, [])))
                numeric = [x for x in ids if not x.startswith("c_")]
                new_concepts = [x for x in ids if x.startswith("c_")]
                labels = [descriptors[x]["label"] for x in numeric if x in descriptors]
                mts = sorted({descriptors[x]["mt"] for x in numeric if x in descriptors and descriptors[x]["mt"]})
                domains = sorted({m[:2] for m in mts})
                rec = {"celex": celex, "ids": numeric, "labels": labels, "mts": mts,
                       "domains": domains, "new_concepts": new_concepts}
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                written += 1
                if numeric:
                    covered += 1
                total_tags += len(numeric)
                c_tags += len(new_concepts)
                unmapped += sum(1 for x in numeric if x not in descriptors)
            f.flush()
            if (i // args.batch) % 20 == 0:
                el = time.time() - t0
                print(f"  {written}/{len(todo)} written | covered={covered} | {el:.0f}s "
                      f"| ~{(len(todo)-written)/max(1,written)*el/60:.0f} min left", flush=True)
            time.sleep(args.pause)

    el = time.time() - t0
    print(f"\n[done] wrote {written} records in {el/60:.1f} min")
    print(f"  covered (>=1 numeric descriptor): {covered}/{written} = {100*covered//max(1,written)}%")
    print(f"  total numeric tags: {total_tags} | avg/covered: {total_tags/max(1,covered):.2f}")
    print(f"  c_ new-concept tags: {c_tags} | numeric ids not in our file: {unmapped}")
    print(f"  -> {GOLD_PATH}")


if __name__ == "__main__":
    main()
