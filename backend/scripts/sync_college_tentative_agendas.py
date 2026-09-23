"""Sync the College of Commissioners' TENTATIVE agendas, daily.

What this is for
----------------
The Secretariat-General publishes, every week or two, a document listing the
items expected on the agenda of forthcoming Commission meetings, four to eight
weeks ahead. It is the single best forward view of what the Commission is about
to adopt, and it MOVES: on 28 April 2026 a refresh shifted the Energy Package
from 19 May to 10 June and added a Fertilisers Action Plan to 13 May, and we
only noticed because Victor read it by hand.

Until now nothing fetched these. `sync_college_agendas.py` fetches PUBLISHED
order-of-the-day documents, which is a different thing: it tells you what a
meeting that already happened discussed. `/news` Part 1b described the tentative
agendas as MANDATORY DAILY, but only as prose, so it depended on someone
remembering. `commission_documents` held zero rows of this type.

Two corrections to what the skill said
--------------------------------------
1. The skill says the JSON API is WAF-walled and 503s, and prescribes a
   Playwright render plus a regex over the HTML. That is no longer true of
   `api/groupSearch`: a plain POST returns 200 and clean JSON. Measured
   22 September 2026. Keeping Playwright here would have put a browser in the
   daily cron for no reason.
2. The PDF endpoint answers with `Content-Type: application/json` while the
   bytes are a real `%PDF`. Trust the magic bytes, not the header.

What it does
------------
POST the same query the register UI sends, take the newest page (or every page
with --backfill), download any document we do not already hold, extract the
text, parse the agenda table, and UPSERT into `commission_documents` with
doc_type SEC. Then diff the newest agenda against the one we held before and
print what changed, because the change is the story, not the document.

Nothing here asserts a firm date. The document itself is headed "(tbc)" and
says the planning is indicative and that the President may change it at any
time, so every date is reported as provisional.

    python3.12 backend/scripts/sync_college_tentative_agendas.py
    python3.12 backend/scripts/sync_college_tentative_agendas.py --dry-run
    python3.12 backend/scripts/sync_college_tentative_agendas.py --backfill --pages 5
"""
from __future__ import annotations

import pathlib

# Repo root derived from this file's location, so a repo move cannot break it.
_REPO_ROOT = str(pathlib.Path(__file__).resolve().parents[2])

import argparse
import datetime as dt
import json
import os
import re
import sys
import urllib.request
from typing import Any

sys.path.insert(0, os.path.join(_REPO_ROOT, "backend"))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(os.path.join(_REPO_ROOT, ".env"))

BASE = "https://ec.europa.eu/transparency/documents-register"
SEARCH = f"{BASE}/api/groupSearch"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# Exactly the payload the register UI posts. Keep it byte-for-byte: the register
# is strict about the shape and silently returns everything if `types` is wrong.
QUERY: dict[str, Any] = {
    "categories": [],
    "types": ["TENTAT_AGENDA_COM_MEETING"],
    "departments": [],
    "language": "en",
    "keywordsSearchType": "AT_LEAST_ONE",
    "target": "TITLE_AND_CONTENT",
    "sortBy": "DOCUMENT_DATE_DESC",
    "isRegular": True,
    "page": 1,
}

DATE_RE = re.compile(r"^\s*(\d{1,2}/\d{1,2}/\d{4})\s*$")
# A responsible Member is printed in capitals. Accents are common (SÉJOURNÉ) so
# an A-Z range would silently drop them, the same defect that once lost
# KNOTEK Ondřej from the deep-dive parser. Test by CASE, not by range.
EVENT_RE = re.compile(r"^\s*\d{1,2}(-\d{1,2})?\s+\w+\s*$")
# The right-hand "Other relevant events" column. Its labels must be dropped as
# well as its date ranges, or a label glues itself onto the next agenda item.
EVENT_LABELS = {"EP Plenary", "European Council", "Euro Summit", "EPSCO",
                "Informal European Council", "EU-", "G7", "G20"}


def _is_member(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 40:
        return False
    letters = [ch for ch in s if ch.isalpha()]
    return bool(letters) and all(ch.isupper() for ch in letters)


def post(page: int, size: int = 20) -> dict:
    body = dict(QUERY, page=page)
    req = urllib.request.Request(
        f"{SEARCH}?size={size}&page={page}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json", "Accept": "application/json",
                 "User-Agent": UA},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def pdf_bytes(reference: str, ers_id: str) -> bytes | None:
    url = f"{BASE}/api/files/{reference}?ersIds={ers_id}"
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        raw = r.read()
    # The endpoint mislabels PDFs as application/json. Check the magic bytes.
    return raw if raw[:4] == b"%PDF" else None


def pdf_text(raw: bytes) -> str:
    import fitz  # PyMuPDF

    with fitz.open(stream=raw, filetype="pdf") as d:
        return "\n".join(p.get_text() for p in d)


def parse_items(text: str) -> list[dict]:
    """Pull (provisional meeting date, item, responsible Member) out of the table.

    The PDF is a three-column table flattened into one text stream, so the
    'Other relevant events' column lands inline with the agenda items. That
    column arrives as a date range ('5-8 October') followed by a label
    ('EP Plenary'). The first version of this parser dropped the range but kept
    the label, which then glued itself to the front of the next real item and
    produced 'EP Plenary 2026 annual overview report on simplification'. Both
    halves have to go.

    Sub-bullets (the '-' rows under 'European product package') carry no
    responsible Member, so they are attached to the item above them rather than
    discarded.
    """
    out: list[dict] = []
    current: str | None = None
    pending: list[str] = []
    sub_buf: list[str] = []
    in_subs = False

    def flush_sub() -> None:
        """Close the sub-bullet being accumulated and APPEND it.

        The first version assigned instead of appending, so each group kept only
        its last bullet: 'European product package' reported the Standardisation
        Regulation and silently lost the European Product Act.
        """
        nonlocal sub_buf
        txt = " ".join(sub_buf).strip()
        if txt and out:
            out[-1]["sub_items"].append(txt)
        sub_buf = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line or line == "(Str)":
            continue
        if line == "-":
            flush_sub()
            in_subs, pending = True, []
            continue
        m = DATE_RE.match(line)
        if m:
            flush_sub()
            current, pending, in_subs = m.group(1), [], False
            continue
        if current is None:
            continue
        if EVENT_RE.match(line) or line in EVENT_LABELS:
            pending = []            # the events column, both the range and its label
            continue
        if _is_member(line):
            flush_sub()
            title = " ".join(pending).strip()
            pending, in_subs = [], False
            if title:
                out.append({"meeting_date_provisional": current,
                            "item": title, "responsible": line, "sub_items": []})
            continue
        if in_subs and out:
            sub_buf.append(line)
        else:
            pending.append(line)
    flush_sub()
    return out


def rows_from_register(pages: int, size: int) -> list[dict]:
    seen: list[dict] = []
    for p in range(1, pages + 1):
        data = post(p, size)
        docs = data.get("documents") or []
        if p == 1:
            print(f"  register reports {data.get('totalResults')} tentative agendas "
                  f"in total; reading {pages} page(s) of {size}")
        if not docs:
            break
        for d in docs:
            ers = None
            for att in d.get("attachments") or []:
                lv = (att.get("linguisticVersions") or {})
                pick = lv.get("en") or (list(lv.values())[0] if lv else None)
                if pick and pick.get("ersId"):
                    ers = pick["ersId"]
                    title = pick.get("title")
                    break
            else:
                title = None
            seen.append({
                "reference": d.get("reference"),
                "date": (d.get("date") or "")[:10],
                "dg": d.get("responsibleDepartment"),
                "portal_url": d.get("url"),
                "ers_id": ers,
                "title": title,
            })
    return seen


SOURCE_KEY = "college_tentative_agendas"


def _run(a, outcome: dict) -> int:
    """The sync itself. Fills `outcome` so main() can record what happened."""
    pages = 32 if a.backfill else a.pages

    print("COLLEGE TENTATIVE AGENDAS")
    print("=" * 74)
    found = rows_from_register(pages, 20)
    print(f"  documents listed: {len(found)}")
    if not found:
        outcome["error"] = "the register returned no documents (a fetch failure, not an empty register)"
        print("\n[FAIL] the register returned no documents. That is a fetch failure, "
              "not an empty register: this query had 628 results on 22 Sep 2026.")
        return 1

    import psycopg2

    url = os.environ["DATABASE_URL"].replace("postgresql+psycopg2://", "postgresql://")
    conn = psycopg2.connect(url)
    cur = conn.cursor()
    cur.execute("""SELECT reference, text_body FROM commission_documents
                    WHERE document_register_category = 'TENTAT_AGENDA_COM_MEETING'""")
    held = {r[0]: (r[1] or "") for r in cur.fetchall()}
    print(f"  already held    : {len(held)}")

    new, changed, unchanged, failed = [], [], 0, []
    for row in found:
        ref, ers = row["reference"], row["ers_id"]
        if not ref or not ers:
            failed.append((ref, "no attachment id"))
            continue
        if ref in held and held[ref]:
            unchanged += 1
            continue
        try:
            raw = pdf_bytes(ref, ers)
            if raw is None:
                failed.append((ref, "not a PDF"))
                continue
            text = pdf_text(raw)
        except Exception as e:                      # noqa: BLE001
            failed.append((ref, f"{type(e).__name__}: {e}"))
            continue
        items = parse_items(text)
        (changed if ref in held else new).append({**row, "text": text, "items": items})

    outcome.update(new=[r["reference"] for r in new], changed=len(changed),
                   unchanged=unchanged, failed=failed)
    print(f"  new             : {len(new)}")
    print(f"  re-fetched      : {len(changed)}")
    print(f"  unchanged       : {unchanged}")
    if failed:
        print(f"  FAILED          : {len(failed)}")
        for ref, why in failed[:6]:
            print(f"     {ref}: {why}")

    if not a.dry_run:
        for rec in new + changed:
            cur.execute("""
                INSERT INTO commission_documents
                      (reference, title, doc_type, publication_date, dg_responsible,
                       portal_url, pdf_url, source_url, text_body,
                       document_register_category, scraped_at, first_seen, last_updated)
                VALUES (%s, %s, 'SEC', %s, %s, %s, %s, %s, %s,
                        'TENTAT_AGENDA_COM_MEETING', now(), now(), now())
                ON CONFLICT (reference) DO UPDATE SET
                    text_body = EXCLUDED.text_body,
                    title = EXCLUDED.title,
                    pdf_url = EXCLUDED.pdf_url,
                    scraped_at = now(),
                    last_updated = now()
            """, (rec["reference"], (rec["title"] or "")[:480], rec["date"] or None,
                  rec["dg"], rec["portal_url"],
                  f"{BASE}/api/files/{rec['reference']}?ersIds={rec['ers_id']}",
                  rec["portal_url"], rec["text"]))
        conn.commit()
        print(f"\n[OK] wrote {len(new) + len(changed)} document(s)")
    else:
        print("\n[DRY RUN] nothing written")

    # The change is the story. Print the newest agenda in full, and if we already
    # held a previous one, say what moved.
    newest = sorted(found, key=lambda r: r["date"] or "", reverse=True)[0]
    rec = next((r for r in new + changed if r["reference"] == newest["reference"]), None)
    if rec is None:
        cur.execute("""SELECT text_body FROM commission_documents WHERE reference = %s""",
                    (newest["reference"],))
        got = cur.fetchone()
        rec = {"reference": newest["reference"], "date": newest["date"],
               "items": parse_items(got[0]) if got and got[0] else []}

    print("\n" + "=" * 74)
    print(f"NEWEST TENTATIVE AGENDA: {rec['reference']}, issued {rec['date']}")
    print("Every date below is marked (tbc) in the source and the planning is")
    print("indicative. Do not assert adoption on any of them.")
    print("=" * 74)
    by_date: dict[str, list[dict]] = {}
    for it in rec["items"]:
        by_date.setdefault(it["meeting_date_provisional"], []).append(it)
    for d, items in by_date.items():
        print(f"\n  {d} (tbc)")
        for it in items:
            print(f"     {it['item'][:84]}")
            print(f"        -> {it['responsible']}")
            for sub in it.get("sub_items") or []:
                print(f"        . {sub[:78]}")
    if not rec["items"]:
        outcome["warn"] = f"no items parsed from {newest['reference']}; the PDF layout may have changed"
        print("\n  [WARN] no items parsed. The PDF layout may have changed; "
              "read the text_body directly before trusting this as empty.")

    prev = sorted((r for r in found if r["date"] < (newest["date"] or "")),
                  key=lambda r: r["date"] or "", reverse=True)
    if prev:
        cur.execute("SELECT text_body FROM commission_documents WHERE reference = %s",
                    (prev[0]["reference"],))
        g = cur.fetchone()
        if g and g[0]:
            old = {(i["meeting_date_provisional"], i["item"]) for i in parse_items(g[0])}
            cur_set = {(i["meeting_date_provisional"], i["item"]) for i in rec["items"]}
            added = sorted(cur_set - old)
            gone = sorted(old - cur_set)

            # A string-exact diff is too noisy to act on. When the Commission
            # corrected its own typo "Northern Neighbourghood" the first run
            # reported one dropped item and one added item, and a genuine
            # rename ("European Product Act" becoming "European product
            # package") looked identical to it. Pair them up first, so the
            # report separates four cases a reader treats differently.
            import difflib

            def close(a: str, b: str) -> float:
                return difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio()

            moved, reworded = [], []
            for da, ta in list(added):
                for dg_, tg in list(gone):
                    if ta == tg and da != dg_:
                        moved.append((tg, dg_, da))
                        added.remove((da, ta)); gone.remove((dg_, tg)); break
                    if da == dg_ and close(ta, tg) > 0.75:
                        reworded.append((da, tg, ta))
                        added.remove((da, ta)); gone.remove((dg_, tg)); break

            print(f"\n  CHANGES vs {prev[0]['reference']} ({prev[0]['date']}):")
            print(f"    MOVED to a different meeting : {len(moved)}")
            for t, a_, b_ in moved:
                print(f"       ~ {t[:58]}  {a_} -> {b_}")
            print(f"    REWORDED, same meeting       : {len(reworded)}")
            for d, a_, b_ in reworded:
                print(f"       ~ {d}  {a_[:40]}")
                print(f"              now: {b_[:56]}")
            print(f"    NEWLY ADDED                  : {len(added)}")
            for d, t in added[:10]:
                print(f"       + {d}  {t[:66]}")
            print(f"    GONE (adopted, or dropped)   : {len(gone)}")
            for d, t in gone[:10]:
                print(f"       - {d}  {t[:66]}")
            if not (added or gone or moved or reworded):
                print("       (no change in the item list)")

    conn.close()
    return 0


def _record(outcome: dict, rc: int, started: dt.datetime) -> None:
    """One sync_runs row per run (23 Sep 2026).

    The job ran from the hot-6h tier through a bare subprocess, which records
    nothing, so there was no way to tell a quiet register from a job that never
    ran. Counts are PERSISTED rows: the new references are re-read after the
    commit. Three states: failed (no data, or an exception), degraded (it ran,
    but some documents could not be fetched or the newest one did not parse),
    success.
    """
    from core.database import SessionLocal
    from services.sync.freshness import record_run
    from sqlalchemy import text

    db = SessionLocal()
    try:
        persisted = 0
        if outcome.get("new"):
            persisted = db.execute(
                text("SELECT count(*) FROM commission_documents WHERE reference = ANY(:r) "
                     "AND document_register_category = 'TENTAT_AGENDA_COM_MEETING'"),
                {"r": outcome["new"]},
            ).scalar()
        problems = [f"{ref}: {why}" for ref, why in outcome.get("failed", [])]
        if outcome.get("warn"):
            problems.append(outcome["warn"])
        if rc != 0 or outcome.get("error"):
            status, error = "failed", outcome.get("error") or f"exit code {rc}"
        elif outcome.get("new") and persisted != len(outcome["new"]):
            status = "failed"
            error = f"persisted {persisted} of {len(outcome['new'])} new document(s)"
        elif problems:
            status, error = "degraded", "; ".join(problems)[:1000]
        else:
            status, error = "success", None
        record_run(db, source_key=SOURCE_KEY, tier="hot_6h", status=status,
                   items_added=persisted, error=error, started_at=started)
    finally:
        db.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--pages", type=int, default=1, help="pages of 20 to read (default 1)")
    ap.add_argument("--backfill", action="store_true", help="read 32 pages, the whole series")
    ap.add_argument("--dry-run", action="store_true", help="fetch and parse, write nothing")
    a = ap.parse_args()
    started = dt.datetime.now(dt.timezone.utc)
    outcome: dict = {}
    try:
        rc = _run(a, outcome)
    except Exception as e:  # noqa: BLE001 -- recorded, then re-raised
        outcome["error"] = f"{type(e).__name__}: {e}"
        if not a.dry_run:
            _record(outcome, 1, started)
        raise
    if not a.dry_run:
        _record(outcome, rc, started)
    return rc


if __name__ == "__main__":
    sys.exit(main())
