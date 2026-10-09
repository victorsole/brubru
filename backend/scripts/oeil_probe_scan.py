#!/usr/bin/env python3.12
"""OEIL probe scan: find OEIL procedure files by URL, then reconcile them.

Why this exists
---------------
Brubru's OEIL feeds only see what OEIL's "latest" lists and Brubru's own carriages point at.
On 9 Oct 2026 a probe of every 2026 reference number found 518 procedure pages, and 17 of
them were not in `legislative_carriages` (one contiguous block of resolutions, 2560-2576).
Nothing in the system had said anything was missing. This asks OEIL directly: for the numbers
Brubru does not hold, does OEIL have a procedure?

Two modes
---------
  audit   Cron-sync source (`is_audit`). Budgeted: probes the numbers just above what Brubru
          holds in each number series (where new procedures appear) plus a window over the
          numbers it does not hold, which rotates daily so the whole gap list is covered over
          a few runs. Reads `legislative_carriages` and `ep_resolutions` READ ONLY. Writes nothing to the database.
          Exit 1 = OEIL serves procedures Brubru lacks (recorded as `degraded`, and the names
          are the tail of stderr, so they reach `sync_runs.error`). A gap counts only for a TYPE
          that some Brubru procedure table holds; a type no table holds (an institutional motion
          of censure, say) is listed apart on stdout and never degrades the run.
  full    CI / on demand. Probes the whole year, then checks the result against the EP Open
          Data /procedures list (union of four paging runs, because one run drops rows) and
          probes every listed label the scan missed. No database, no secrets. Writes a CSV,
          a JSON summary and a Markdown summary into --out.

Exit codes (both modes)
    0  clean
    1  gaps: audit = OEIL serves refs Brubru lacks; full = the scan missed a procedure that
       the exact-label probe then found (the series/type assumptions have drifted)
    2  a wall, an unexplained answer, an outage, or NOTHING was probed. A check that probed
       nothing must not pass.

Nothing here writes procedures. Ingesting what the audit finds is the carriage sync's job.
Rules: sequential, honest BrubruBot UA, paced, backoff, stop on any anomaly, no LLM.

Usage:
    python3.12 scripts/oeil_probe_scan.py --mode audit
    python3.12 scripts/oeil_probe_scan.py --mode audit --numbers 2555-2580   # targeted check
    python3.12 scripts/oeil_probe_scan.py --mode full --year 2026 --out /tmp/oeil_probe
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.scrapers.oeil_probe import (  # noqa: E402
    DEFAULT_BANDS,
    PROCEDURE_URL,
    Band,
    OeilProber,
    ProbeBlocked,
    audit_targets,
    band_of,
    cod_instrument,
    derive_bands,
    fetch_epod_union,
    normalise_label,
    numbers_by_band,
    parse_ref,
    reconcile,
    split_gaps_by_held_type,
)

CSV_COLUMNS = ["year", "type", "cod_instrument", "title", "url", "procedure_number", "procedure_ref", "type_label",
               "subject", "status", "key_events", "motion_refs", "text_refs", "found_by", "fetched_on"]
GAP_LIST_LIMIT = 40          # names printed to stderr (the tail becomes sync_runs.error)


def info(msg: str) -> None:
    print(f"[INFO] {msg}", flush=True)


def err(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def parse_numbers(spec: str) -> List[int]:
    out: List[int] = []
    for part in spec.split(","):
        if "-" in part:
            a, b = part.split("-")
            out.extend(range(int(a), int(b) + 1))
        elif part.strip():
            out.append(int(part))
    return out


# --------------------------------------------------------------------------- database (audit, read only)


def load_brubru_refs(year: int) -> Tuple[Set[str], Set[str], Set[str]]:
    """(held, emeeting_only_extra, tracked_refs_any_year).

    held = refs of `year` in `legislative_carriages` or `ep_resolutions`. `tracked_refs_any_year` = every
    ref those two PROCEDURE tables hold, any year: it feeds the type bands and tells which TYPES some
    table holds (committee agendas are not a procedure table and are left out of it).
    One read-only transaction.
    """
    from dotenv import load_dotenv
    from sqlalchemy import create_engine, text

    load_dotenv(BACKEND_DIR / ".env")
    load_dotenv(BACKEND_DIR.parent / ".env")
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise SystemExit("[ERROR] DATABASE_URL not set")
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    pat = r"^[0-9]{4}/[0-9]{4}\([A-Z]{3}\)$"
    engine = create_engine(url, pool_pre_ping=True)
    with engine.connect() as conn:
        conn.execute(text("SET TRANSACTION READ ONLY"))
        allrefs = {r[0] for r in conn.execute(
            text("select distinct oeil_procedure_ref from legislative_carriages where oeil_procedure_ref ~ :p"),
            {"p": pat})}
        # ep_resolutions holds resolutions with an adopted text (361 refs, 9 Oct 2026): the first
        # comparison missed this table and called six held resolutions a gap.
        allrefs |= {r[0] for r in conn.execute(
            text("select distinct procedure_ref from ep_resolutions where procedure_ref ~ :p"), {"p": pat})}
        em = {r[0] for r in conn.execute(
            text("select distinct procedure_ref from ep_emeeting_documents where procedure_ref ~ :p"), {"p": pat})}
    held = {r for r in allrefs if r.startswith(f"{year}/")}
    em_year = {r for r in em if r.startswith(f"{year}/")} - held
    return held, em_year, allrefs


# --------------------------------------------------------------------------- audit


def run_audit(args) -> int:
    year = args.year
    held, em_only, all_refs = load_brubru_refs(year)
    bands = derive_bands(all_refs)
    known = numbers_by_band(held, year, bands)
    info(f"audit {year}: Brubru holds {len(held)} procedure refs in carriages or resolutions ({len(em_only)} more only in committee agendas)")
    for b in bands:
        info(f"  band {b.name} {b.lo}-{b.hi} types {','.join(b.types)}: holds {len(known[b.name])}, "
             f"highest {max(known[b.name]) if known[b.name] else '-'}")

    if args.numbers:
        targets: List[Tuple[int, Tuple[str, ...]]] = []
        for n in parse_numbers(args.numbers):
            b = band_of(n, bands)
            targets.append((n, b.types if b else tuple(t for bb in bands for t in bb.types)))
    else:
        # The warm tier runs about four times a day: advance the window per six-hour slot, not per day,
        # or the same numbers would be probed four times and the others never.
        now = datetime.now(timezone.utc)
        day = args.day_ordinal if args.day_ordinal is not None else now.date().toordinal() * 4 + now.hour // 6
        targets = audit_targets(known, bands, request_budget=args.max_requests, day_ordinal=day)
    if not targets:
        err("[ERROR] audit planned no probes: refusing to report a clean run")
        return 2

    prober = OeilProber(pace=args.pace)
    deadline = time.monotonic() + args.max_seconds
    hits: Dict[str, dict] = {}
    probed = 0
    try:
        for number, types in targets:
            if time.monotonic() > deadline:
                info("time budget reached; stopping early (remaining numbers are covered by the next runs)")
                break
            res = prober.sweep(year, number, types)
            probed += 1
            if res:
                hits[res.ref] = res.record
    except ProbeBlocked as exc:
        err(f"[ERROR] OEIL probe stopped: {exc}")
        _write_audit_json(args, year, held, hits, probed, len(targets), prober.requests, blocked=str(exc))
        return 2

    if probed == 0:
        err("[ERROR] audit probed no numbers: refusing to report a clean run")
        return 2
    rec = reconcile(hits, held)
    gaps, untracked = split_gaps_by_held_type(rec["on_oeil_not_held"], all_refs)
    info(f"probed {probed} numbers ({prober.requests} requests): {len(hits)} procedures on OEIL, "
         f"{len(rec['held_and_on_oeil'])} already held, {len(gaps)} NOT held")
    if untracked:
        # Not counted: no Brubru table is meant to hold this type, so it can never be "ingested" and
        # counting it would keep the audit degraded for ever.
        info(f"{len(untracked)} procedure(s) of a type no Brubru table holds (not counted as gaps): "
             + "; ".join(f"{r} {(hits[r].get('title') or '')[:50]}" for r in untracked[:10]))
    _write_audit_json(args, year, held, hits, probed, len(targets), prober.requests, gaps=gaps, untracked=untracked)
    if gaps:
        shown = gaps[:GAP_LIST_LIMIT]
        err(f"[GAP] OEIL serves {len(gaps)} {year} procedure(s) that neither legislative_carriages nor ep_resolutions holds:")
        for ref in shown:
            title = (hits[ref].get("title") or "")[:70]
            err(f"[GAP]   {ref} {title}")
        if len(gaps) > len(shown):
            err(f"[GAP]   ... and {len(gaps) - len(shown)} more")
        err(f"[GAP] summary: {len(gaps)} gap(s) over {probed} numbers probed")
        return 1
    print(f"[OK] {probed} numbers probed, no gap", flush=True)
    return 0


def _write_audit_json(args, year, held, hits, probed, planned, requests, gaps=None, blocked=None, untracked=None) -> None:
    if not args.out:
        return
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / f"oeil_probe_audit_{year}.json").write_text(json.dumps({
        "year": year, "run_at": datetime.now(timezone.utc).isoformat(), "held_carriage_refs": len(held),
        "numbers_planned": planned, "numbers_probed": probed, "requests": requests, "hits": len(hits),
        "on_oeil_not_held": gaps or [], "blocked": blocked,
        "gap_records": [_feed_record(r, hits[r]) for r in (gaps or [])],
        "no_table_holds_this_type": [_feed_record(r, hits[r]) for r in (untracked or [])],
    }, indent=1, ensure_ascii=False))


# --------------------------------------------------------------------------- full


def _scan_band(prober: OeilProber, year: int, band: Band, hits: Dict[str, dict], *, open_ended: bool,
               tail_gap: int, deadline: float, only: Optional[Set[int]]) -> bool:
    """Scan every number of a band. An open-ended band stops after `tail_gap` empty numbers past its
    last hit. Returns False when the time budget ended the scan early."""
    last_hit = band.lo - 1
    for n in range(band.lo, band.hi + 1):
        if only is not None and n not in only:
            continue
        if time.monotonic() > deadline:
            return False
        if open_ended and n > last_hit + tail_gap:
            break
        res = prober.sweep(year, n, band.types)
        if res:
            hits[res.ref] = res.record
            last_hit = n
    return True


def run_full(args) -> int:
    year = args.year
    bands = DEFAULT_BANDS
    prober = OeilProber(pace=args.pace)
    deadline = time.monotonic() + args.max_seconds
    only = set(parse_numbers(args.numbers)) if args.numbers else None
    hits: Dict[str, dict] = {}
    complete = True
    t0 = time.monotonic()
    try:
        for i, band in enumerate(bands):
            info(f"scanning band {band.name} {band.lo}-{band.hi} types {','.join(band.types)}")
            ok = _scan_band(prober, year, band, hits, open_ended=(i == len(bands) - 1), tail_gap=args.tail_gap,
                            deadline=deadline, only=only)
            complete = complete and ok
            info(f"  {len(hits)} procedures so far, {prober.requests} requests, {time.monotonic() - t0:.0f}s")
        missed: List[str] = []
        listed_not_served: List[str] = []
        epod_total = epod_distinct = None
        if not args.no_epod and only is None:
            info("reading the EP Open Data list (union of four paging runs)")
            labels, epod_total = fetch_epod_union(year)
            epod_distinct = len(labels)
            api_only = sorted({normalise_label(l) for l in labels} - set(hits))
            info(f"list has {len(labels)} labels ({epod_total} reported); {len(api_only)} not found by the scan: probing them by exact label")
            for lab in api_only:
                p = parse_ref(lab)
                if not p or p[0] != year:
                    continue
                res = prober.probe(lab)
                if res.kind == "hit":
                    missed.append(lab)
                    hits[lab] = {**res.record, "_found_by": "list_then_fetched"}
                else:
                    listed_not_served.append(lab)
    except ProbeBlocked as exc:
        err(f"[ERROR] OEIL probe stopped: {exc}")
        return 2

    rows = _rows(year, hits)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / f"oeil_{year}_procedures.csv", "w", newline="", encoding="utf-8-sig") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    (out / f"oeil_{year}_procedures.json").write_text(json.dumps(
        [_feed_record(ref, rec) for ref, rec in sorted(hits.items())], indent=1, ensure_ascii=False))
    types: Dict[str, int] = {}
    for r in rows:
        types[r["type"]] = types.get(r["type"], 0) + 1
    summary = {
        "year": year, "run_at": datetime.now(timezone.utc).isoformat(), "requests": prober.requests,
        "seconds": round(time.monotonic() - t0), "procedures_found": len(rows), "by_type": dict(sorted(types.items(), key=lambda kv: -kv[1])),
        "scan_complete": complete, "epod_reported_total": epod_total, "epod_distinct_labels": epod_distinct,
        "missed_by_scan_found_by_exact_label": missed, "listed_but_not_served_by_oeil": listed_not_served,
    }
    (out / f"oeil_{year}_probe_summary.json").write_text(json.dumps(summary, indent=1))
    (out / "summary.md").write_text(_markdown(summary))
    info(f"found {len(rows)} procedures with {prober.requests} requests in {summary['seconds']}s; files in {out}")
    if not rows:
        err("[ERROR] the scan found no procedure at all: refusing to report a clean run")
        return 2
    if epod_total and epod_distinct is not None and epod_distinct != epod_total:
        info(f"warning: the EP list union has {epod_distinct} of {epod_total} reported labels (list incomplete)")
    if missed:
        err(f"[GAP] the exact-label probe found {len(missed)} procedure(s) the scan missed: {', '.join(missed[:GAP_LIST_LIMIT])}")
        return 1
    if epod_distinct is None:
        print(f"[OK] {len(rows)} procedures (EP Open Data cross-check not run)", flush=True)
    else:
        print(f"[OK] {len(rows)} procedures; every label of the EP list is either found or not served by OEIL", flush=True)
    return 0


def _rows(year: int, hits: Dict[str, dict]) -> List[dict]:
    today = date.today().isoformat()
    rows = []
    for ref, rec in hits.items():
        y, n, t = parse_ref(ref)  # type: ignore[misc]
        rows.append({
            "year": y, "type": t, "cod_instrument": cod_instrument(rec.get("instrument")) if t == "COD" else "",
            "title": rec.get("title") or "", "url": PROCEDURE_URL + ref, "procedure_number": n, "procedure_ref": ref,
            "type_label": rec.get("type_label") or "", "subject": rec.get("subject") or "", "status": rec.get("status") or "",
            "key_events": " | ".join(e["event"] for e in rec.get("key_events", [])),
            "motion_refs": " | ".join(rec.get("motion_refs", [])), "text_refs": " | ".join(rec.get("text_refs", [])),
            "found_by": rec.get("_found_by", "url_probe"), "fetched_on": today,
        })
    return sorted(rows, key=lambda r: (r["procedure_number"], r["type"]))


def _feed_record(ref: str, rec: dict) -> dict:
    """What a consumer of the feed needs per procedure. `state` is always 'served' here: a 404 is never
    written as absent, it is simply not a record (a page may still be being initiated)."""
    y, n, t = parse_ref(ref)  # type: ignore[misc]
    return {"procedure_ref": ref, "year": y, "number": n, "type": t, "title": rec.get("title"),
            "status": rec.get("status"), "state": "served", "instrument": rec.get("instrument"),
            "subject": rec.get("subject"), "key_events": rec.get("key_events", []),
            "motion_refs": rec.get("motion_refs", []), "text_refs": rec.get("text_refs", []),
            "url": PROCEDURE_URL + ref, "fetched_on": date.today().isoformat()}


def _markdown(s: dict) -> str:
    lines = [f"## OEIL probe {s['year']}", "",
             f"- Procedures found: **{s['procedures_found']}** ({s['requests']} requests, {s['seconds']} s)",
             f"- Scan complete within its time budget: {s['scan_complete']}",
             (f"- EP Open Data list: {s['epod_distinct_labels']} distinct of {s['epod_reported_total']} reported"
              if s["epod_distinct_labels"] is not None else "- EP Open Data cross-check: NOT RUN"),
             f"- Missed by the scan, found by exact label: {len(s['missed_by_scan_found_by_exact_label'])}",
             f"- Listed by EP Open Data but not served by OEIL (404): {len(s['listed_but_not_served_by_oeil'])}", "",
             "| Type | Procedures |", "| --- | ---: |"]
    lines += [f"| {t} | {n} |" for t, n in s["by_type"].items()]
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- cli


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--mode", choices=["audit", "full"], required=True)
    ap.add_argument("--year", type=int, default=datetime.now(timezone.utc).year)
    ap.add_argument("--out", default=None, help="output directory (full mode: required in practice; default ./oeil_probe_out)")
    ap.add_argument("--pace", type=float, default=0.35, help="seconds between requests")
    ap.add_argument("--max-seconds", type=int, default=None, help="wall-clock budget (audit default 600, full default 14400)")
    ap.add_argument("--max-requests", type=int, default=1500, help="audit: request budget for planning")
    ap.add_argument("--numbers", default=None, help="restrict to numbers, e.g. 2555-2580 or 1-40,2000")
    ap.add_argument("--day-ordinal", type=int, default=None, help="audit: rotate the window as if it were this day")
    ap.add_argument("--tail-gap", type=int, default=100, help="full: stop the open-ended last band after this many empty numbers")
    ap.add_argument("--no-epod", action="store_true", help="full: skip the EP Open Data cross-check")
    args = ap.parse_args(argv)
    if args.max_seconds is None:
        args.max_seconds = 600 if args.mode == "audit" else 14400
    if args.mode == "full" and not args.out:
        args.out = "oeil_probe_out"
    try:
        return run_audit(args) if args.mode == "audit" else run_full(args)
    except ProbeBlocked as exc:
        err(f"[ERROR] {exc}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
