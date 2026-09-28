"""Discover new Council register documents by reference, from data.consilium (not walled).

Why (28 Sep 2026): the Council register SEARCH and LISTING pages on
www.consilium.europa.eu answer Railway's address with a browser challenge (HTTP 403),
so `council_documents` failed 5 of 5 runs and nothing new reached Council Watch. The
same documents are served by reference over plain HTTP at data.consilium.europa.eu,
reachable from the Railway container (measured: 200 with a real %PDF). Council
references are sequential within a year and series, so new documents can be found
by asking for the numbers after the highest one held:

  CM  meeting notices and provisional agendas of Council working parties (dense)
  ST  standard documents, incl. Council meeting agendas (gaps: restricted ones 404)
  WK  working documents (sparse)

Each series stops after a run of consecutive misses (a 404 is "not published", not
an error). Documents are written with the register ingest's own upsert, so rows are
identical whichever route found them. For meeting notices the meeting date is kept
in extra_metadata.meeting_date, so Council Watch can say when the group meets.

Verdict: exit 1 when data.consilium answers nothing at all; `[SYNC_STATUS] degraded`
when the time budget ran out before a series reached its end; 0 otherwise.

    python3.12 scripts/discover_council_documents.py --apply                # scheduled form
    python3.12 scripts/discover_council_documents.py --series CM --max 20   # dry run
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from scripts.ingest_council_documents import SOURCE_REGISTER, _engine, _persist  # noqa: E402
from services.scrapers.council_register import CouncilDoc, fetch_document_text  # noqa: E402

# Consecutive misses after which a series is taken to have reached its end.
MISS_LIMIT = {"CM": 30, "ST": 250, "WK": 150}
_UA = {"User-Agent": "Mozilla/5.0 (compatible; BrubruIngest/1.0)"}
_DATE_RE = re.compile(r"Brussels,\s+(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_MEETING_RE = re.compile(r"Date\s*:\s*(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})")
_SUBJECT_RE = re.compile(r"Subject\s*:\s*(.+?)(?=\s+(?:Date|Time|Venue|Format)\s*:|\n\s*\n|$)", re.S)
# Council and Coreper agendas carry no "Subject:" line: the body is named in the heading.
# "COUNCIL OF THE EUROPEAN UNION1 (Economic and Financial Affairs)" (footnote digit
# included), "PERMANENT REPRESENTATIVES COMMITTEE (Part 2)".
_AGENDA_RE = re.compile(
    r"PROVISIONAL AGENDA\s+(?:(COUNCIL OF THE EUROPEAN UNION)\d?\s*\(((?:[^()]|\([^()]*\))*)\)"
    r"|(PERMANENT REPRESENTATIVES COMMITTEE)\s*\((Part \d)\))")
_AGENDA_WHEN_RE = re.compile(r"(\d{1,2})\s+([A-Z][a-z]+)\s+(\d{4})\s*\(\d{1,2}[:.]\d{2}\)")


def _d(m) -> date | None:
    if not m:
        return None
    try:
        return datetime.strptime(f"{m.group(1)} {m.group(2)} {m.group(3)}", "%d %B %Y").date()
    except ValueError:
        return None


def parse(ref: str, body: str) -> dict:
    """Title, document date and (for meeting notices) meeting date, from the text itself."""
    head = " ".join(body[:5000].split())
    title = None
    m = _SUBJECT_RE.search(head)
    if m:
        title = m.group(1).strip()
    meeting = _d(_MEETING_RE.search(head))
    a = _AGENDA_RE.search(head)
    if a:
        when = _AGENDA_WHEN_RE.search(head, a.end())
        meeting = meeting or _d(when)
        if not title:
            body_name = (f"Council ({' '.join(a.group(2).split())})" if a.group(1)
                         else f"Coreper ({a.group(4)})")
            title = f"Provisional agenda: {body_name}" + (
                f", {meeting.day} {meeting:%B %Y}" if meeting else "")
    return {"title": (title or ref)[:400], "published": _d(_DATE_RE.search(head)),
            "meeting_date": meeting}


def held_max(conn, series: str, year: int) -> int:
    v = conn.execute(text("""
        SELECT max(split_part(external_id, '-', 2)::int) FROM institutional_publications
        WHERE source_slug = :s AND external_id ~ :rx"""),
        {"s": SOURCE_REGISTER, "rx": f"^{series}-[0-9]+-{year}-"}).scalar()
    return int(v or 0)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--series", action="append", choices=list(MISS_LIMIT), default=[])
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--max", type=int, default=400, help="documents to fetch per series and run")
    ap.add_argument("--max-seconds", type=int, default=420)
    ap.add_argument("--pace", type=float, default=0.3)
    args = ap.parse_args()

    series_list = args.series or ["CM", "ST", "WK"]
    deadline = time.monotonic() + args.max_seconds
    asked = found = written = 0
    unfinished = []
    engine = _engine()
    client = httpx.Client(timeout=40, headers=_UA, follow_redirects=True)
    try:
        for series in series_list:
            with engine.connect() as conn:
                n = held_max(conn, series, args.year)
            misses = got = 0
            print(f"[discover] {series}-{args.year}: highest held {n}")
            while misses < MISS_LIMIT[series] and got < args.max:
                if time.monotonic() > deadline:
                    unfinished.append(series)
                    break
                n += 1
                ref = f"{series}-{n}-{args.year}-INIT"
                url = f"https://data.consilium.europa.eu/doc/document/{ref}/en/pdf"
                asked += 1
                try:
                    r = client.get(url)
                except Exception as exc:  # noqa: BLE001
                    print(f"  {ref}: {type(exc).__name__}")
                    misses += 1
                    continue
                time.sleep(args.pace)
                if r.status_code != 200 or r.content[:4] != b"%PDF":
                    misses += 1
                    continue
                misses = 0
                got += 1
                found += 1
                doc = CouncilDoc(external_id=ref, title=ref, url=url, published=None,
                                 subject_matters=[], category="document")
                body = fetch_document_text(doc) or ""
                meta = parse(ref, body)
                doc.title, doc.published = meta["title"], meta["published"]
                print(f"  {ref}: {doc.published} {doc.title[:80]}")
                if args.apply:
                    with engine.begin() as conn:
                        _persist(conn, doc, SOURCE_REGISTER, body or None)
                        if meta["meeting_date"]:
                            conn.execute(text(
                                "UPDATE institutional_publications SET extra_metadata = "
                                "coalesce(extra_metadata, '{}'::jsonb) || CAST(:m AS jsonb) "
                                "WHERE source_slug = :s AND external_id = :e"),
                                {"m": json.dumps({"meeting_date": meta["meeting_date"].isoformat()}),
                                 "s": SOURCE_REGISTER, "e": ref})
                    written += 1
    finally:
        client.close()

    print(f"[discover] asked {asked}, found {found}, written {written}"
          f"{'' if args.apply else ' (dry run: nothing written)'}")
    if asked and not found:
        print("[INFO] no new documents in any series")
    if unfinished:
        print(f"[SYNC_STATUS] degraded: time budget ran out before the end of {', '.join(unfinished)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
