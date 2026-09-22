#!/usr/bin/env python3.12
"""Repair carriage statuses that the OLD inference rule advanced too far.

WHY (22 September 2026)
----------------------
Until 15 September 2026 `infer_carriage_status` treated OEIL's "Decision by
Parliament, 1st reading" as proof that a procedure was COMPLETED. That is wrong:
under Rule 60 Parliament routinely votes its amendments and then refers the
matter straight back to committee for interinstitutional negotiation, without
adopting the legislative resolution. The file is mid-procedure, not finished.

The rule was corrected that day. The DATA was not, and could not be: statuses
move through `advance_status()`, which returns a new value only when it is
strictly FURTHER ALONG than the stored one. It is deliberately monotonic, so a
status that was wrongly advanced can never come back down on its own. Every
subsequent sync re-reads the file, infers the correct lower status, and
discards it.

The result reached users. On 22 September the Critical Medicines Act carriage
said COMPLETED while OEIL said "Awaiting Parliament's position in 1st reading"
and forecast the plenary vote for 23 November 2026. Both halves of the
pharmaceutical package said COMPLETED with a plenary forecast of 19 October
2026. The Legislative Train: state of play was telling people that live files
were over.

A monotonic rule needs a deliberate repair path. This is it.

WHAT IT DOES
------------
1. Selects carriages whose stored status claims the file is finished
   (COMPLETED / ADOPTED) while OEIL still forecasts a FUTURE event. A forecast
   dated after today is a direct contradiction of "finished".
2. Fetches each procedure file LIVE and reads OEIL's own Status field. The
   stored `oeil_key_events` could themselves be stale, and a repair driven by
   stale data would just write a different wrong answer. OEIL's Status line is
   the authority, so the script goes and asks it.
3. Recomputes the status from the live key events with the CURRENT production
   rule, and only writes when OEIL's Status agrees the file is unfinished.
4. Prints a table and writes nothing unless --apply is given.

A file whose OEIL Status does say "Procedure completed" is LEFT ALONE and
reported, because then the forecast is the stale half, not the status.

USAGE
    python3.12 backend/scripts/repair_carriage_status_from_oeil.py            # dry run
    python3.12 backend/scripts/repair_carriage_status_from_oeil.py --apply
    python3.12 backend/scripts/repair_carriage_status_from_oeil.py --ref 2023/0131(COD)
"""
from __future__ import annotations

import argparse
import datetime as dt
import os
import pathlib
import re
import sys
from typing import List, Optional, Tuple

_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

from dotenv import load_dotenv  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

from services.scrapers.oeil_procedure_parser import infer_carriage_status  # noqa: E402

OEIL_URL = "https://oeil.secure.europarl.europa.eu/oeil/en/procedure-file?reference={ref}"

# OEIL's own Status wording that means the procedure really is over. Anything
# else that starts "Awaiting" is by definition unfinished.
_FINISHED = ("procedure completed", "procedure rejected", "procedure lapsed",
             "procedure withdrawn", "act adopted")


def _status_line(page_text: str) -> Optional[str]:
    """OEIL's Status value, which sits on the line after a bare 'Status' label."""
    lines = [l.strip() for l in (page_text or "").split("\n")]
    for i, l in enumerate(lines):
        if l == "Status":
            for nxt in lines[i + 1:i + 4]:
                if nxt:
                    return nxt
    return None


def _event_types(page_text: str) -> List[str]:
    """The Event column of the Key events table, as OEIL words it.

    Each row reads `DD/MM/YYYY  Event text  [Reference]  [Summary]`, so the
    event is whatever follows the date on that line.
    """
    out: List[str] = []
    block = page_text
    k = block.find("Key events")
    if k >= 0:
        block = block[k:]
    end = block.find("Technical information")
    if end > 0:
        block = block[:end]
    for line in block.split("\n"):
        m = re.match(r"\s*\d{2}/\d{2}/\d{4}\s+(.+?)\s*$", line)
        if m:
            out.append(re.sub(r"\s{2,}.*$", "", m.group(1)).strip())
    return out


def _fetch(ref: str, fetcher) -> str:
    r = fetcher(OEIL_URL.format(ref=ref), expand_accordions=True, strip_chrome=True)
    return re.sub(r"[ \t]+", " ", r.text or "")


def candidates(conn, only_ref: Optional[str]) -> List[Tuple[str, str, str, str]]:
    """(ref, title, stored status, earliest future forecast)."""
    today = dt.date.today().isoformat()
    rows = conn.execute(text("""
        SELECT oeil_procedure_ref, title, current_status, oeil_forecasts
          FROM legislative_carriages
         WHERE oeil_procedure_ref IS NOT NULL
           AND current_status IN ('COMPLETED', 'ADOPTED')
           AND oeil_forecasts IS NOT NULL
    """))
    out = []
    for r in rows:
        if only_ref and r.oeil_procedure_ref != only_ref:
            continue
        fc = r.oeil_forecasts
        if not isinstance(fc, list):
            continue
        future = sorted(d for d in
                        (x.get("date") for x in fc if isinstance(x, dict))
                        if d and d > today)
        if future:
            out.append((r.oeil_procedure_ref, str(r.title or ""), r.current_status, future[0]))
    return sorted(out)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true", help="write the corrected statuses")
    ap.add_argument("--ref", help="only this procedure reference")
    a = ap.parse_args()

    load_dotenv(os.path.join(_BACKEND, ".env"))
    url = os.environ["DATABASE_URL"].replace("postgresql://", "postgresql+psycopg2://")
    engine = create_engine(url, pool_pre_ping=True)

    with engine.connect() as conn:
        cands = candidates(conn, a.ref)

    print("CARRIAGE STATUS REPAIR  (stored status says finished, OEIL forecasts a future event)")
    print("=" * 100)
    if not cands:
        print("[OK] no contradictions found.")
        return 0
    print(f"{len(cands)} candidate(s). Checking each against live OEIL.\n")

    from services.scrapers.waf_browser_fetcher import fetch_one

    fixes: List[Tuple[str, str, str, str]] = []
    left: List[Tuple[str, str, str]] = []
    for ref, title, stored, forecast in cands:
        try:
            page = _fetch(ref, fetch_one)
        except Exception as exc:                                  # noqa: BLE001
            print(f"[WARN] {ref}: fetch failed ({exc}); NOT repaired")
            continue
        oeil_status = _status_line(page) or "(no Status line found)"
        events = _event_types(page)
        inferred = (infer_carriage_status(events) or "").upper() or None
        finished = any(f in oeil_status.lower() for f in _FINISHED)

        print(f"  {ref:<18} stored={stored:<10} forecast={forecast}")
        print(f"      OEIL Status : {oeil_status}")
        print(f"      {len(events)} key events -> current rule infers: {inferred}")

        if finished:
            left.append((ref, stored, oeil_status))
            print("      -> OEIL agrees it is finished; the FORECAST is the stale half. Left alone.\n")
            continue
        if not inferred or inferred == stored:
            left.append((ref, stored, oeil_status))
            print("      -> no lower status proven by the events. Left alone.\n")
            continue
        fixes.append((ref, stored, inferred, oeil_status))
        print(f"      -> REPAIR {stored} -> {inferred}\n")

    print("=" * 100)
    print(f"{len(fixes)} to repair, {len(left)} left alone.")
    if not fixes:
        return 0
    if not a.apply:
        print("\nDry run. Re-run with --apply to write.")
        return 0

    with engine.begin() as conn:
        for ref, stored, new, _ in fixes:
            conn.execute(text("""
                UPDATE legislative_carriages
                   SET current_status = :new, last_updated = now()
                 WHERE oeil_procedure_ref = :ref
            """), {"new": new, "ref": ref})
            print(f"  [WROTE] {ref}: {stored} -> {new}")

    # Read back. A write that is not verified is not a fix.
    with engine.connect() as conn:
        print("\nverification:")
        for ref, stored, new, _ in fixes:
            got = conn.execute(text(
                "SELECT current_status FROM legislative_carriages WHERE oeil_procedure_ref = :r"),
                {"r": ref}).scalar()
            mark = "OK " if got == new else "FAIL"
            print(f"  [{mark}] {ref:<18} now {got}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
