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
Only NULL procedure_refs and `other` types are written, with one exception.

The exception: a stored procedure both authorities contradict (12 October 2026)
----------------------------------------------------------------------------
Four adopted texts were filed under a procedure they only CITE: another job
filled an empty procedure with the first reference inside the stored text, and
this one never looked at a row that already had one. Their resolutions were
served as adopted with no link to the text and no text. That guess is gone, and
each run now compares every stored procedure with OEIL, which lists a procedure's
adopted texts on its page (`oeil_procedures.text_refs`). Where OEIL lists the
text on other procedures only, EP Open Data is asked; the text is refiled only
where the two agree, and what was copied from the wrong procedure's file is
cleared for `enrich_ep_texts_and_resolutions.py` to refill. Where they do not
agree nothing is written and the run is recorded as degraded, naming the texts.

OEIL can only contradict a text whose procedure page Brubru holds, and it holds
procedures from 2024 on. `--recheck` covers the rest by hand (about 10 seconds a
text): every text no held OEIL page lists is asked of EP Open Data again, and
where the answer differs from what is stored, the text's OWN page settles it (its
"Procedure :" box). Run on 12 October 2026: 85 such texts, 2 misfiled, same cause.

Usage (from backend/):
    python3.12 scripts/backfill_texts_adopted_procedures.py              # dry run
    python3.12 scripts/backfill_texts_adopted_procedures.py --apply --limit 60
    python3.12 scripts/backfill_texts_adopted_procedures.py --recheck          # dry run, by hand
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


# A stored procedure OEIL contradicts: it lists the text on other procedures' pages and
# never on the stored one's. A text OEIL lists on two pages (one vote closing two files)
# is not contradicted while the stored procedure is one of them.
CONTRADICTED = text(r"""
    WITH links AS (
        SELECT regexp_replace(t, '^T(\d+)-(\d{4})/(\d{4})$', 'P\1_TA(\3)\2') AS ta, o.procedure_ref
        FROM oeil_procedures o, unnest(o.text_refs) AS t
        WHERE t ~ '^T\d+-\d{4}/\d{4}$'
    )
    SELECT ta.id, ta.ta_reference, ta.procedure_ref AS stored, ta.text_type::text AS text_type,
           array_agg(DISTINCT l.procedure_ref) AS oeil_refs
    FROM texts_adopted ta JOIN links l ON l.ta = ta.ta_reference
    WHERE ta.procedure_ref IS NOT NULL
    GROUP BY ta.id, ta.ta_reference, ta.procedure_ref, ta.text_type
    HAVING NOT bool_or(l.procedure_ref = ta.procedure_ref)
    ORDER BY ta.ta_reference
""")
# The texts OEIL cannot speak for: no OEIL page Brubru holds lists them (--recheck).
UNCONFIRMED = text(r"""
    WITH links AS (
        SELECT regexp_replace(t, '^T(\d+)-(\d{4})/(\d{4})$', 'P\1_TA(\3)\2') AS ta
        FROM oeil_procedures o, unnest(o.text_refs) AS t
        WHERE t ~ '^T\d+-\d{4}/\d{4}$'
    )
    SELECT ta.id, ta.ta_reference, ta.procedure_ref AS stored, ta.text_type::text AS text_type,
           ta.full_text_url
    FROM texts_adopted ta
    WHERE ta.procedure_ref IS NOT NULL AND ta.ta_reference ~ '^P\d+_TA\('
      AND NOT EXISTS (SELECT 1 FROM links l WHERE l.ta = ta.ta_reference)
    ORDER BY ta.ta_reference
""")
# The carriage link, rapporteur and committees were copied from the WRONG procedure's file
# by enrich_ep_texts_and_resolutions.py, which only fills empty ones: cleared here, it
# refills them from the right file later in the same tier.
REFILE = text(
    "UPDATE texts_adopted SET procedure_ref = :p, "
    "text_type = COALESCE(CAST(:t AS adopted_text_type), text_type), "
    "legislative_carriage_id = NULL, rapporteur_name = NULL, rapporteur_mep_id = NULL, "
    "committees = '{}', last_updated = now() "
    "WHERE id = :id AND procedure_ref = :old")


def settle(stored: str, second: list[str], open_data: str | None) -> str | None:
    """The procedure a misfiled text is refiled under, or None to leave it alone.

    Only where two authorities agree: EP Open Data names a procedure AND a second one
    names the same (`second`: the procedures on whose OEIL page the text is listed, or
    the one the text's own page states). One source alone corrects nothing."""
    if open_data and open_data != stored and open_data in (second or []):
        return open_data
    return None


def own_page_procedure(ta_reference: str, url: str | None) -> str | None:
    """The procedure the adopted text's own doceo page states, or None."""
    import asyncio

    from services.scrapers.texts_adopted_scraper import TextsAdoptedScraper
    detail = asyncio.run(TextsAdoptedScraper().scrape_text_detail(
        ta_reference, url if url and "-TOC_" not in url else None))
    return detail.procedure_ref if detail else None


def _get(path: str, attempts: int = 4) -> dict | None:
    """GET a JSON-LD resource. The API refuses bursts ('Pending acquire queue has
    reached its maximum size'), so back off and retry rather than read an error
    body as data."""
    url = f"{API}/{path}{'&' if '?' in path else '?'}format=application%2Fld%2Bjson"
    for i in range(attempts):
        try:
            with urllib.request.urlopen(
                    urllib.request.Request(url, headers={"User-Agent": "Brubru/1.0"}), timeout=90) as r:
                # 204 No Content is the API's answer for a document it has not published
                # (yet): TA-10-2026-0335 on its adoption day, 8 Oct 2026. Same meaning as
                # 404. Parsing the empty body raised, was retried 4 times, and the caller
                # read a fast, explicit "none" as the API being unreachable.
                if r.status == 204:
                    return None
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
    # Second route (24 Sep 2026): the text's OWN record. Urgent-procedure votes
    # (Rule 170: the EUDR delays, the wolf, CO2 cars, the CSRD/CSDDD stop-the-
    # clock) adopt the Commission proposal directly, so there is no A-document
    # to follow and the route above finds nothing: 23 of the term's texts
    # stayed without a procedure. The record itself names it, in
    # inverse_created_a_realization_of ("eli/dl/proc/2025-0044") and in its
    # decision event ("2025-0044-DEC-DCPL-..."). Only an unambiguous single
    # procedure is used.
    own = sorted(set(_PROC.findall(json.dumps(doc["data"][0]))))
    if len(own) == 1:
        p = _get(f"procedures/{own[0]}")
        label = ((p or {}).get("data") or [{}])[0].get("label")
        if label and _LABEL.match(label):
            return label, "via the text's own procedure link"
        return None, f"procedure {own[0]} has no usable label"
    if len(own) > 1:
        return None, f"text names {len(own)} procedures"
    return None, "adopts nothing" if not adopts else "no adopted document names a procedure"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=0, help="texts per run (0 = all)")
    ap.add_argument("--pace", type=float, default=0.5, help="seconds between texts")
    ap.add_argument("--recheck", action="store_true",
                    help="by hand: also re-verify every text no held OEIL page lists, against EP Open "
                         "Data and the text's own page (about 10s a text)")
    ap.add_argument("--only", action="append", default=[], metavar="TA_REFERENCE",
                    help="with --recheck: only these texts (repeatable)")
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

    started = time.monotonic()
    found, failed, reasons, written = [], 0, {}, 0

    # First, the stored procedures OEIL contradicts. Normally none.
    with engine.connect() as c:
        wrong = c.execute(CONTRADICTED).all()
    refiled, unsettled = 0, []
    if wrong:
        print(f"[INFO] {len(wrong)} adopted text(s) filed under a procedure OEIL does not list them under")
    unconfirmed = []
    if a.recheck:
        with engine.connect() as c:
            unconfirmed = [r for r in c.execute(UNCONFIRMED).all()
                           if not a.only or r.ta_reference in a.only]
        print(f"[INFO] --recheck: {len(unconfirmed)} adopted text(s) no held OEIL page lists", flush=True)
    for r in list(wrong) + list(unconfirmed):
        by_oeil = hasattr(r, "oeil_refs")
        if a.budget and time.monotonic() - started > a.budget:
            if by_oeil:
                unsettled.append(f"{r.ta_reference} (not reached)")
            continue
        try:
            label, why = resolve(r.ta_reference)
        except RuntimeError as e:
            print(f"  [ERROR] {r.ta_reference}: {e}")
            unsettled.append(f"{r.ta_reference} (EP Open Data unreachable)")
            continue
        if by_oeil:
            second, named = list(r.oeil_refs), "OEIL"
        elif not label or label == r.stored:
            continue                       # EP Open Data confirms it, or has no answer
        else:
            page = own_page_procedure(r.ta_reference, r.full_text_url)
            second, named = ([page] if page else []), "the text's own page"
        new = settle(r.stored, second, label)
        if not new:
            unsettled.append(f"{r.ta_reference} (stored {r.stored}; {named} {', '.join(second) or 'none'}; "
                             f"EP Open Data {label or why})")
            continue
        new_type = TYPE_BY_KIND.get(_LABEL.match(new).group(1)) if r.text_type == "other" else None
        if a.apply:
            with engine.begin() as c:
                refiled += c.execute(REFILE, {"p": new, "t": new_type, "id": r.id,
                                              "old": r.stored}).rowcount
        print(f"  [{'REFILED' if a.apply else 'WOULD REFILE'}] {r.ta_reference}: {r.stored} -> {new} "
              f"({named} and EP Open Data agree)"
              + (f" ({new_type})" if new_type else ""), flush=True)
        time.sleep(a.pace)
    for u in unsettled:
        print(f"  [UNSETTLED] {u}")

    # Write each text as it resolves (23 Sep 2026). The first version collected
    # everything and wrote at the end, so a timeout lost the whole run: at ~25s a
    # text, 60 texts outlast the warm tier's 1500s limit and nothing would land.
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
    if unsettled:
        # Exit 0 with a degraded mark: the job did its work, and a text two authorities
        # disagree on needs a person, not a red build every hour.
        print(f"[SYNC_STATUS] degraded: {len(unsettled)} adopted text(s) whose stored procedure a "
              f"second source contradicts, not settled: {'; '.join(unsettled)[:700]}")
    if not a.apply:
        print("[DRY-RUN] nothing written")
        return 1 if failed and not found else 0

    with engine.connect() as c:
        still = c.execute(text("SELECT count(*) FROM texts_adopted WHERE procedure_ref IS NULL "
                               "AND ta_reference LIKE 'P%\\_TA(%'")).scalar()
    print(f"[APPLIED] wrote {written} procedure reference(s), refiled {refiled}; "
          f"{still} still without one")
    # An API outage that resolved nothing is a failure, not a quiet day.
    return 1 if failed and not written else 0


if __name__ == "__main__":
    sys.exit(main())
