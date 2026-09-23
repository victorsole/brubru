#!/usr/bin/env python3.12
"""Give each adopted text its procedure reference, from the EP's own Open Data API.

Why (23 September 2026)
-----------------------
495 of the 750 texts adopted this term had no `procedure_ref`, and 507 were typed
`other`. The listing parser takes the reference from a regex on the item's
description, and the stored full text starts AFTER the heading where the
reference sits, so the enrichment step (`enrich_ep_texts_and_resolutions.py`)
had nothing to match either. The September 2026 plenary is the clearest case:
47 texts, 44 without a procedure.

It does not stay inside `texts_adopted`. `backfill_ep_resolutions_corpus.py`
builds `ep_resolutions` from resolution-typed texts WITH a procedure, so a text
without one never becomes a resolution: the corpus reported success every day
and had not grown since 27 August, and its newest resolution was 9 July.

How
---
The EP Open Data API links an adopted text to the document it adopts, and that
document to its procedure, whose record carries the full label:

    adopted-texts/TA-10-2026-0276  -> adopts  eli/dl/doc/A-10-2026-0201
    plenary-documents/A-10-2026-0201 -> eli/dl/proc/2025-0419
    procedures/2025-0419           -> label "2025/0419(COD)"

The type is then derived from the procedure kind, conservatively: COD, CNS, APP
and NLE produce a legislative resolution, INI, RSP and INL a resolution, IMM
(immunity) a decision. Anything else keeps `other`, which means UNCLASSIFIED.
Only NULL procedure_refs and `other` types are written; nothing already set is
overwritten.

Usage (from backend/):
    python3.12 scripts/backfill_texts_adopted_procedures.py              # dry run
    python3.12 scripts/backfill_texts_adopted_procedures.py --apply --limit 60
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

from sqlalchemy import create_engine, text  # noqa: E402

API = "https://data.europarl.europa.eu/api/v2"
_TA = re.compile(r"^P(\d+)_TA\((\d{4})\)(\d{4})$")
_PROC = re.compile(r"eli/dl/proc/(\d{4}-\d{4})")
_LABEL = re.compile(r"^\d{4}/\d{4}\(([A-Z]+)\)$")
TYPE_BY_KIND = {
    "COD": "legislative_resolution", "CNS": "legislative_resolution",
    "APP": "legislative_resolution", "NLE": "legislative_resolution",
    "INI": "resolution", "RSP": "resolution", "INL": "resolution",
    "IMM": "decision",
}


def _get(path: str, attempts: int = 4) -> dict | None:
    """GET a JSON-LD resource. The API refuses bursts ('Pending acquire queue has
    reached its maximum size'), so back off and retry rather than read an error
    body as data."""
    url = f"{API}/{path}{'&' if '?' in path else '?'}format=application%2Fld%2Bjson"
    for i in range(attempts):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "Brubru/1.0"}), timeout=90) as r:
                body = json.load(r)
            if isinstance(body, dict) and "error" in body and "data" not in body:
                raise RuntimeError(str(body["error"])[:120])
            return body
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
        except Exception:  # noqa: BLE001 -- retried below, reported by the caller
            pass
        time.sleep(3 * (i + 1))
    raise RuntimeError(f"EP API unreachable for {path}")


def resolve(ta_reference: str) -> tuple[str | None, str]:
    """(procedure label or None, reason)."""
    m = _TA.match(ta_reference or "")
    if not m:
        return None, "not a TA reference"
    term, year, num = m.groups()
    doc = _get(f"adopted-texts/TA-{term}-{year}-{num}")
    if not doc or not doc.get("data"):
        return None, "adopted text not in the EP API"
    adopts = doc["data"][0].get("adopts") or []
    if not adopts:
        return None, "adopts nothing"
    for target in adopts:
        tid = str(target).rsplit("/", 1)[-1]
        pd = _get(f"plenary-documents/{tid}")
        if not pd:
            continue
        procs = sorted(set(_PROC.findall(json.dumps(pd))))
        if len(procs) != 1:
            if procs:
                return None, f"{tid} names {len(procs)} procedures"
            continue
        p = _get(f"procedures/{procs[0]}")
        label = ((p or {}).get("data") or [{}])[0].get("label")
        if label and _LABEL.match(label):
            return label, f"via {tid}"
        return None, f"procedure {procs[0]} has no usable label"
    return None, "no adopted document names a procedure"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="texts per run (0 = all)")
    ap.add_argument("--pace", type=float, default=0.5, help="seconds between texts")
    ap.add_argument("--budget", type=int, default=0,
                    help="stop starting new texts after this many seconds (0 = none); the warm "
                         "tier passes one because a plenary document takes ~25s to fetch")
    a = ap.parse_args()

    url = os.environ["DATABASE_URL"]
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as c:
        rows = c.execute(text(
            "SELECT id, ta_reference, text_type::text AS text_type FROM texts_adopted "
            "WHERE procedure_ref IS NULL AND ta_reference LIKE 'P%\\_TA(%' "
            "ORDER BY adoption_date DESC NULLS LAST" + (f" LIMIT {int(a.limit)}" if a.limit else ""))).all()
    print(f"[INFO] {len(rows)} adopted text(s) without a procedure")

    # Write each text as it resolves (23 Sep 2026). The first version collected
    # everything and wrote at the end, so a timeout lost the whole run: at ~25s a
    # text, 60 texts outlast the warm tier's 1500s limit and nothing would land.
    started = time.monotonic()
    found, failed, reasons, written = [], 0, {}, 0
    for i, r in enumerate(rows, 1):
        if a.budget and time.monotonic() - started > a.budget:
            print(f"[INFO] budget spent; {len(rows) - i + 1} text(s) left for the next run", flush=True)
            break
        try:
            label, why = resolve(r.ta_reference)
        except RuntimeError as e:
            failed += 1
            print(f"  [ERROR] {r.ta_reference}: {e}")
            continue
        if label:
            kind = _LABEL.match(label).group(1)
            new_type = TYPE_BY_KIND.get(kind) if r.text_type == "other" else None
            found.append((r.id, r.ta_reference, label, new_type))
            if a.apply:
                with engine.begin() as c:
                    written += c.execute(text(
                        "UPDATE texts_adopted SET procedure_ref = :p, "
                        "text_type = COALESCE(CAST(:t AS adopted_text_type), text_type), last_updated = now() "
                        "WHERE id = :id AND procedure_ref IS NULL"),
                        {"p": label, "t": new_type, "id": r.id}).rowcount
            print(f"  [{i}/{len(rows)}] {r.ta_reference} -> {label}"
                  + (f" ({new_type})" if new_type else ""), flush=True)
        else:
            key = re.sub(r"[A-Z]+-\d+-\d{4}-\d{4}", "DOC", why)
            reasons[key] = reasons.get(key, 0) + 1
        time.sleep(a.pace)

    print(f"\n[INFO] resolved {len(found)}, unresolved {i - len(found) - failed if rows else 0}, "
          f"API errors {failed}")
    for why, n in sorted(reasons.items(), key=lambda x: -x[1])[:6]:
        print(f"       {n:4d}  {why}")
    if not a.apply:
        print("[DRY-RUN] nothing written")
        return 1 if failed and not found else 0

    with engine.connect() as c:
        still = c.execute(text("SELECT count(*) FROM texts_adopted WHERE procedure_ref IS NULL "
                               "AND ta_reference LIKE 'P%\\_TA(%'")).scalar()
    print(f"[APPLIED] wrote {written} procedure reference(s); {still} still without one")
    # An API outage that resolved nothing is a failure, not a quiet day.
    return 1 if failed and not written else 0


if __name__ == "__main__":
    sys.exit(main())
