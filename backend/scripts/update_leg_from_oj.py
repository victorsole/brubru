#!/usr/bin/env python3.12
"""Add each day's Official Journal L publications to docs/LEG_2026-10, then rebuild its table (CSV + Excel).

The LEG_2026-10 export (Publications Office, 11 Oct 2026) stops at the OJ of 9 Oct 2026. For every OJ day since,
this script reads the L publications from Cellar, with the query behind /api/v2/legislative/eur-lex/oj/daily (it
matched the EUR-Lex daily view item for item on the 8 days checked on 20 Oct 2026), and gives each new legal act the
folder the export would have given it:

  <dump>/<Cellar work id>/tree_non_inferred.rdf   Cellar, notice=non-inferred-tree: the export's own file
  <dump>/<Cellar work id>/fmx4/*.xml              the English Formex files, when the act has an English version
  <dump>/<Cellar work id>/brubru_source.json      what added the folder, from which OJ (the table's `source` column)

The export kept only the acts Cellar flagged in force on the day it was cut (every act since June 2026 in it is
in_force true), plus corrigenda; this script adds every sector-3 publication as the OJ publishes it, and the table's
in_force is the flag Cellar states when the folder is added (often none yet for a new act).

Kept, as in the export: sector 3 (legal acts and their corrigenda; a corrigendum with no English version gets the
metadata only, like the export's). Skipped and logged: every other sector (international agreements, acts of bodies
set up by agreements). A publication whose CELEX Cellar has not assigned yet stays pending and is read again at the
next run. Every decision goes to the ledger daily_updates.csv in --out. The last --recheck-days OJ days are listed
again at every run (Cellar can index a publication later in the day), and so is any older day still pending, so a
day the Mac was off is caught up at the next run.

Only the summary table is rebuilt (build_leg_table.py); the links and families tables are not. Writes no database:
eu_laws has its own daily sync on Railway. Run daily by launchd through backend/scripts/leg_oj_daily.sh.

    python3.12 backend/scripts/update_leg_from_oj.py            # dry run: what would be added
    python3.12 backend/scripts/update_leg_from_oj.py --apply    # add the folders, then rebuild the table
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import io
import json
import os
import pathlib
import shutil
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, timezone

BACKEND = pathlib.Path(__file__).resolve().parents[1]
_REPO_ROOT = BACKEND.parent

# The last OJ day in the 11 Oct 2026 export (max date_publication of its folders); the first day this script reads.
EXPORT_LAST_OJ_DAY = date(2026, 10, 9)
CELLAR_WORK = "https://publications.europa.eu/resource/cellar/"
RDF_ACCEPT = "application/rdf+xml;notice=non-inferred-tree"
FMX_ACCEPT = "application/zip;mtype=fmx4"
RDF_NS = "{http://www.w3.org/1999/02/22-rdf-syntax-ns#}"
CDM_NS = "{http://publications.europa.eu/ontology/cdm#}"
SOURCE_FILE = "brubru_source.json"  # build_leg_table.py reads it for the source column
LEDGER = "daily_updates.csv"
LEDGER_FIELDS = ["oj_date", "oj_id", "celex", "work_id", "language", "status", "reason", "run_at"]
FINAL = {"added", "already", "skipped"}  # "pending" and "error" are read again at the next run
MAX_ZIP_BYTES = 500_000_000


class Fail(Exception):
    """A publication that could not be added this run (logged as error, read again next run)."""


# ---- Cellar (replaced by fakes in the tests)

def _run(coro):
    return asyncio.run(coro)


def publication_days(since: date, until: date) -> list[date]:
    """The days the OJ published anything in [since, until], oldest first."""
    sys.path.insert(0, str(BACKEND))
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient

    async def go():
        async with CellarSPARQLClient() as client:
            return await client.oj_publication_dates(since, until)
    return sorted(_run(go()))


def list_day(day: date) -> list[dict]:
    """One dict per OJ L publication of `day` (work, celex, oj_id, lang3, fmts, title): /oj/daily's own grouping."""
    sys.path.insert(0, str(BACKEND))
    from services.api_clients.cellar_sparql_client import CellarSPARQLClient, group_oj_acts

    async def go():
        async with CellarSPARQLClient() as client:
            return group_oj_acts(await client.oj_acts_published_on(day, "L"), "L")
    return _run(go())


def _get(url: str, accept: str, language: str | None = None) -> bytes | None:
    """The body, None on 404; retried on anything else, then raised."""
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
    headers = {"Accept": accept}
    if language:
        headers["Accept-Language"] = language
    last = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return None
            last = f"HTTP {e.code}"
        except Exception as e:  # noqa: BLE001
            last = type(e).__name__
        time.sleep(5 * (attempt + 1))
    raise Fail(f"{url}: {last}")


def fetch_rdf(work_id: str) -> bytes | None:
    return _get(CELLAR_WORK + work_id, RDF_ACCEPT)


def fetch_formex(work_id: str) -> bytes | None:
    return _get(CELLAR_WORK + work_id, FMX_ACCEPT, "eng")


# ---- folders

def rdf_celexes(raw: bytes) -> set[str]:
    root = ET.fromstring(raw)
    return {e.text.strip() for e in root.iter(CDM_NS + "resource_legal_id_celex") if e.text and e.text.strip()}


def unpack_formex(blob: bytes, dest: pathlib.Path) -> list[str]:
    """Write the zip's XML files flat into dest, as the export holds them (its fmx4 folders carry no image: a figure's
    .tif or .jpg is left out); refuse the zip if any name is a path or hidden."""
    if len(blob) > MAX_ZIP_BYTES:
        raise Fail(f"Formex zip of {len(blob):,} bytes")
    names = []
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        members = [m for m in z.infolist() if not m.is_dir()]
        if sum(m.file_size for m in members) > MAX_ZIP_BYTES:
            raise Fail("Formex zip expands beyond the size limit")
        for m in members:
            name = m.filename
            if "/" in name or "\\" in name or name.startswith("."):
                raise Fail(f"unexpected file in the Formex zip: {name!r}")
            if not name.endswith(".xml"):
                continue  # an image of a figure: the export keeps the text files only
            (dest / name).write_bytes(z.read(m))
            names.append(name)
    wrappers = (".doc.xml", ".toc.xml", ".doc.fmx.xml", ".toc.fmx.xml")
    if not any(not n.endswith(wrappers) for n in names):
        raise Fail("the Formex zip holds no act file, only wrappers")
    return sorted(names)


def add_folder(dump: pathlib.Path, act: dict, day: date, now: str) -> str:
    """Build the act's folder beside the dump, then move it in whole; returns the reason recorded."""
    work_id = act["work"].rsplit("/", 1)[-1]
    tmp_root = dump.parent / ".leg_oj_tmp"
    tmp = tmp_root / work_id
    shutil.rmtree(tmp, ignore_errors=True)
    (tmp / "fmx4").mkdir(parents=True)
    try:
        raw = fetch_rdf(work_id)
        if raw is None:
            raise Fail("Cellar has no metadata notice for the work (404)")
        got = rdf_celexes(raw)
        if got != {act["celex"]}:
            raise Fail(f"the metadata states CELEX {sorted(got)}, the OJ listing {act['celex']}")
        (tmp / "tree_non_inferred.rdf").write_bytes(raw)
        files, why = [], ""
        if act.get("lang3") != "ENG":
            why = "metadata only: no English version"
        elif "fmx4" not in (act.get("fmts") or {}):
            why = "metadata only: no English Formex at Cellar"
        else:
            blob = fetch_formex(work_id)
            if blob is None:
                raise Fail("the listing has an English Formex version, Cellar answered 404 for it")
            files = unpack_formex(blob, tmp / "fmx4")
        if not files:
            (tmp / "fmx4").rmdir()  # as the export holds an act without an English text: metadata only
        (tmp / SOURCE_FILE).write_text(json.dumps({
            "source": "OJ daily", "oj_date": day.isoformat(), "oj_id": act["oj_id"], "celex": act["celex"],
            "work_id": work_id, "language": act.get("language"), "added_at": now,
            "added_by": "backend/scripts/update_leg_from_oj.py"}, indent=1), encoding="utf-8")
        os.rename(tmp, dump / work_id)  # same filesystem: the folder appears whole or not at all
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return f"{len(files)} Formex file(s)" if files else why


# ---- ledger

def read_ledger(path: pathlib.Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as fh:
        return list(csv.DictReader(fh))


def append_ledger(path: pathlib.Path, rows: list[dict]) -> None:
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=LEDGER_FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)


def latest_status(ledger: list[dict]) -> dict:
    """(oj_date, oj_id) -> the last row recorded for it."""
    out = {}
    for r in ledger:
        out[(r["oj_date"], r["oj_id"])] = r
    return out


def days_to_read(ledger: list[dict], since: date, today: date, recheck_days: int, max_days: int) -> list[date]:
    """Every OJ day from `since` with nothing recorded or something not final, any earlier day still open in the
    ledger (a one-off backfill's leftovers), and the last recheck_days OJ days."""
    days = publication_days(since, today)
    st = latest_status(ledger)
    seen = {d for d, _ in st}
    open_days = {d for (d, _), r in st.items() if r["status"] not in FINAL}
    want = [d for d in days if d.isoformat() not in seen or d.isoformat() in open_days]
    want += [date.fromisoformat(d) for d in open_days if date.fromisoformat(d) < since]
    want += days[-recheck_days:] if recheck_days else []
    return sorted(set(want))[:max_days]


def dump_celexes(out: pathlib.Path, ledger: list[dict]) -> set[str]:
    """CELEX numbers the dump already holds: the last table build plus what this script added since."""
    held = set()
    table = out / "leg_2026-10_table.csv"
    if table.exists():
        with table.open(newline="", encoding="utf-8-sig") as fh:
            held = {r["CELEX"] for r in csv.DictReader(fh)}
    return held | {r["celex"] for r in ledger if r["status"] == "added"}


# ---- table rebuild

TABLE_FILES = ("leg_2026-10_table.csv", "leg_2026-10_eurovoc.csv", "leg_2026-10_table.xlsx", "qa.json")


def rebuild(dump: pathlib.Path, out: pathlib.Path) -> None:
    """build_leg_table.py over the whole dump; the previous outputs are kept in out/previous and put back on failure."""
    prev = out / "previous"
    prev.mkdir(exist_ok=True)
    for f in TABLE_FILES:
        if (out / f).exists():
            shutil.copy2(out / f, prev / f)
    r = subprocess.run([sys.executable, str(BACKEND / "scripts" / "build_leg_table.py"), "--dump", str(dump), "--out", str(out)],
                       capture_output=True, text=True)
    if r.returncode != 0:
        for f in TABLE_FILES:
            if (prev / f).exists():
                shutil.copy2(prev / f, out / f)
        raise Fail(f"build_leg_table.py failed, previous table restored: {r.stderr.strip()[-600:]}")
    recalc = os.environ.get("LEG_RECALC_SCRIPT")  # the xlsx skill's LibreOffice recalc, so the formulas carry values
    if recalc and pathlib.Path(recalc).exists():
        rc = subprocess.run([sys.executable, recalc, str(out / "leg_2026-10_table.xlsx"), "600"], capture_output=True, text=True)
        print(f"[INFO] recalc: {rc.stdout.strip()[-300:] or rc.stderr.strip()[-300:]}")


# ---- run

def run(dump: pathlib.Path, out: pathlib.Path, apply: bool, today: date, recheck_days: int = 7, max_days: int = 31,
        since: date = EXPORT_LAST_OJ_DAY) -> int:
    ledger_path = out / LEDGER
    ledger = read_ledger(ledger_path)
    held = dump_celexes(out, ledger)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, errors, added = [], 0, 0
    try:
        days = days_to_read(ledger, since, today, recheck_days, max_days)
    except Exception as e:  # noqa: BLE001
        print(f"[ERROR] could not read the OJ days from Cellar: {type(e).__name__}: {e}")
        return 1
    print(f"[INFO] OJ days to read: {[d.isoformat() for d in days]}")
    for day in days:
        try:
            acts = list_day(day)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] {day}: could not list the OJ L publications: {type(e).__name__}: {e}")
            errors += 1
            continue
        if not acts:
            # an OJ day with no L publication listed is not proof of none: nothing is recorded, the day is read again
            print(f"[WARN] {day}: Cellar listed no L publication")
            continue
        for act in acts:
            work_id = act["work"].rsplit("/", 1)[-1]
            celex = act.get("celex")
            row = {"oj_date": day.isoformat(), "oj_id": act["oj_id"], "celex": celex or "", "work_id": work_id,
                   "language": act.get("language") or "", "run_at": now}
            if (dump / work_id).is_dir():
                row.update(status="already", reason="the folder is in the dump")
            elif not celex:
                row.update(status="pending", reason="Cellar has not assigned the CELEX yet")
            elif not celex.startswith("3"):
                row.update(status="skipped", reason=f"sector {celex[0]}: the export holds legal acts (sector 3) only")
            elif celex in held:
                row.update(status="already", reason="the CELEX is in the dump under another folder")
            elif not apply:
                row.update(status="would add", reason="dry run")
            else:
                try:
                    row.update(status="added", reason=add_folder(dump, act, day, now))
                    held.add(celex)
                    added += 1
                except Exception as e:  # noqa: BLE001
                    row.update(status="error", reason=f"{type(e).__name__}: {e}"[:400])
                    errors += 1
            rows.append(row)
            print(f"   {day} {act['oj_id']:<14} {celex or '-':<18} {row['status']:<9} {row['reason']}")
    if apply:
        # a publication is recorded until it reaches a final status, then never again (a recheck of an added act
        # reads "already"); a dry run records nothing
        prev = latest_status(ledger)
        fresh = [r for r in rows if prev.get((r["oj_date"], r["oj_id"]), {}).get("status") not in FINAL]
        append_ledger(ledger_path, fresh)
        if added:
            try:
                rebuild(dump, out)
                print(f"[OK] table rebuilt with {added} new folder(s)")
            except Fail as e:
                print(f"[ERROR] {e}")
                errors += 1
    by = {}
    for r in rows:
        by[r["status"]] = by.get(r["status"], 0) + 1
    print(f"[SUMMARY] {len(days)} OJ day(s), {len(rows)} publication(s): {by}; errors {errors}")
    return 1 if errors else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dump", default="docs/LEG_2026-10")
    ap.add_argument("--out", default="backend/data/leg_2026-10_table")
    ap.add_argument("--apply", action="store_true", help="add the folders and rebuild the table (default: dry run)")
    ap.add_argument("--recheck-days", type=int, default=7, help="OJ days listed again at every run")
    ap.add_argument("--max-days", type=int, default=31, help="most OJ days read in one run")
    ap.add_argument("--since", type=date.fromisoformat, default=EXPORT_LAST_OJ_DAY,
                    help="first OJ day to read (default: the export's last OJ day, 2026-10-09); an earlier date backfills")
    a = ap.parse_args()
    dump = pathlib.Path(a.dump) if pathlib.Path(a.dump).is_absolute() else _REPO_ROOT / a.dump
    out = pathlib.Path(a.out) if pathlib.Path(a.out).is_absolute() else _REPO_ROOT / a.out
    if not dump.is_dir() or not out.is_dir():
        print(f"[ERROR] dump {dump} or table folder {out} missing")
        return 1
    return run(dump, out, a.apply, date.today(), a.recheck_days, a.max_days, a.since)


if __name__ == "__main__":
    sys.exit(main())
