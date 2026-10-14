"""Discover Council register documents by reference, from data.consilium (not walled).

Why (28 Sep 2026): the Council register SEARCH and LISTING pages on
www.consilium.europa.eu answer Railway's address with a browser challenge (HTTP 403),
so `council_documents` failed 5 of 5 runs and nothing new reached Council Watch. The
same documents are served by reference over plain HTTP at data.consilium.europa.eu,
reachable from the Railway container (measured: 200 with a real %PDF). Council
references are sequential within a year and series:

  CM  meeting notices and provisional agendas of Council working parties (dense)
  ST  standard documents, incl. Council meeting agendas (gaps: restricted ones 404)
  WK  working documents (sparse)

Why it changed (14 Oct 2026): asking only for the numbers after the highest one held
found about half of what the Council publishes. Every number was probed that day:
CM 4301-4608, 217 served and 112 held; ST 13600-14436, 204 served and 80 held. A
document published after the job had passed its number was never asked for again, and
revisions, addenda and corrigenda (REV, ADD, COR) were never asked for at all. Since
15 July 2024 the register serves roughly 20,000 first versions; 556 were held.

Each run now does three things, per series:
  forward   the numbers after the highest held, until a run of misses (as before)
  gaps      the numbers in the recent window (about three weeks) that are not held,
            a third of them per run, so each is asked again once a day
  versions  for documents in that window, the next REV, ADD and COR not held
`--sweep` asks every unheld number in a range, with its versions: the backfill, run
by hand, resumable because a held document is never asked for again.

Each series stops after a run of consecutive misses (a 404 is "not published", not an
error). Documents are written with the register ingest's own upsert, so rows are
identical whichever route found them. For meeting notices the meeting date is kept in
extra_metadata.meeting_date, so Council Watch can say when the group meets.

Verdict: exit 1 when data.consilium answers nothing at all (a 404 is an answer, a
timeout or a 5xx is not); `[SYNC_STATUS] degraded` when the time budget ran out or
more than a fifth of the requests went unanswered; 0 otherwise.

    python3.12 scripts/discover_council_documents.py --apply                # scheduled form
    python3.12 scripts/discover_council_documents.py --series CM --max 20   # dry run
    python3.12 scripts/discover_council_documents.py --sweep --series ST --year 2025 \\
        --from-number 5000 --to-number 18500 --max-seconds 0 --apply       # backfill
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import httpx  # noqa: E402
from sqlalchemy import text  # noqa: E402

from scripts.ingest_council_documents import SOURCE_REGISTER, _engine, _persist  # noqa: E402
from services.scrapers.council_register import CouncilDoc, fetch_document_text  # noqa: E402

# Consecutive misses after which a series is taken to have reached its end. Lower than
# before 14 Oct 2026 (ST 250, WK 150): a number passed too early is now asked again by
# the gap pass, so forward no longer has to wait out every restricted document.
MISS_LIMIT = {"CM": 30, "ST": 100, "WK": 60}
# The recent window re-asked for late publications: about three weeks of numbers.
GAP_WINDOW = {"CM": 400, "ST": 800, "WK": 400}
# The window is split across the day's runs (about 07:00, 13:00 and 19:00 UTC).
SLOTS = 3
VERSION_KINDS = ("REV", "ADD", "COR")
# The whole text, not a 200,000-character slice of it: 31 documents were cut there.
MAX_TEXT = 2_000_000
_UA = {"User-Agent": "Mozilla/5.0 (compatible; BrubruIngest/1.0)"}
_MONTH = r"(January|February|March|April|May|June|July|August|September|October|November|December)"
# "Brussels, 23 September 2026" and the "Brussels , 19 July 2024" spacing of older PDFs.
_DATE_RE = re.compile(r"(?:Brussels|Luxembourg|Strasbourg)\s*,\s*(\d{1,2})\s+" + _MONTH + r"\s+(\d{4})")
_MEETING_RE = re.compile(r"Date\s*:\s*(\d{1,2})\s+" + _MONTH + r"\s+(\d{4})")
_SUBJECT_RE = re.compile(r"Subject\s*:\s*(.+?)(?=\s+(?:Date|Time|Venue|Format)\s*:|\n\s*\n|$)", re.S)
# Agendas, lists of 'A' items and summary records carry no "Subject:" line: the document
# names its kind and the body it serves in a heading. "COUNCIL OF THE EUROPEAN UNION1
# (Economic and Financial Affairs)" (footnote digit included), "PERMANENT REPRESENTATIVES
# COMMITTEE (Part 2)", "SPECIAL COMMITTEE ON AGRICULTURE".
_KINDS = {"PROVISIONAL AGENDA": "Provisional agenda",
          "PROVISIONAL LIST OF 'A' ITEMS": "Provisional list of 'A' items",
          "LIST OF ADOPTED 'A' ITEMS": "List of adopted 'A' items",
          "LIST OF 'A' ITEMS": "List of 'A' items",
          "SUMMARY RECORD": "Summary record"}
_HEADING_RE = re.compile(
    r"(PROVISIONAL AGENDA|PROVISIONAL LIST OF 'A' ITEMS|LIST OF ADOPTED 'A' ITEMS|LIST OF 'A' ITEMS"
    r"|SUMMARY RECORD)\s+"
    r"(?:(COUNCIL OF THE EUROPEAN UNION)\d?\s*\(((?:[^()]|\([^()]*\))*)\)"
    r"|(PERMANENT REPRESENTATIVES COMMITTEE)\s*\((Part \d)\)"
    r"|((?:[A-Z][A-Z'\-]+\b\s*){2,}))")
_HEADING_WHEN_RE = re.compile(r"(\d{1,2})((?:\s+and\s+\d{1,2})?)\s+" + _MONTH + r"\s+(\d{4})")
_SMALL = {"On", "Of", "The", "And", "For", "In", "To"}


def _ymd(day, month, year) -> date | None:
    try:
        return datetime.strptime(f"{day} {month} {year}", "%d %B %Y").date()
    except ValueError:
        return None


def _d(m) -> date | None:
    return _ymd(m.group(1), m.group(2), m.group(3)) if m else None


def _tidy(name: str) -> str:
    name = " ".join(name.split())
    return re.sub(r"\(\s+", "(", re.sub(r"\s+([,)])", r"\1", name))


def _body_name(m) -> str:
    if m.group(2):
        return f"Council ({_tidy(m.group(3))})"
    if m.group(4):
        return f"Coreper ({m.group(5)})"
    words = [w.capitalize() for w in m.group(6).split()]
    return " ".join(w.lower() if i and w in _SMALL else w for i, w in enumerate(words))


def parse(ref: str, body: str) -> dict:
    """Title, document date and (for meetings) meeting date, from the text itself."""
    head = " ".join(body[:5000].split())
    title = None
    m = _SUBJECT_RE.search(head)
    if m:
        title = m.group(1).strip()
    meeting = _d(_MEETING_RE.search(head))
    h = _HEADING_RE.search(head)
    if h:
        when = _HEADING_WHEN_RE.search(head, h.end(), h.end() + 300)
        if when and not meeting:
            meeting = _ymd(when.group(1), when.group(3), when.group(4))
        if not title:
            title = f"{_KINDS[h.group(1)]}: {_body_name(h)}" + (
                f", {when.group(1)}{when.group(2)} {when.group(3)} {when.group(4)}" if when else "")
    return {"title": (title or ref)[:400], "published": _d(_DATE_RE.search(head)),
            "meeting_date": meeting}


def held(conn, series: str, year: int) -> set[str]:
    """Every reference held for a series and year, versions included."""
    return set(conn.execute(text(
        "SELECT external_id FROM institutional_publications "
        "WHERE source_slug = :s AND external_id ~ :rx"),
        {"s": SOURCE_REGISTER, "rx": f"^{series}-[0-9]+-{year}-"}).scalars())


def init_numbers(refs: set[str]) -> set[int]:
    return {int(r.split("-")[1]) for r in refs if r.endswith("-INIT")}


def ref_of(series: str, n: int, year: int, kind: str = "INIT", i: int = 0) -> str:
    return f"{series}-{n}-{year}-INIT" if kind == "INIT" else f"{series}-{n}-{year}-{kind}-{i}"


def url_of(ref: str) -> str:
    return f"https://data.consilium.europa.eu/doc/document/{ref}/en/pdf"


def next_versions(refs: set[str], series: str, n: int, year: int) -> list[str]:
    """The next REV, ADD and COR of document n that is not held yet."""
    out = []
    for kind in VERSION_KINDS:
        i = 1
        while ref_of(series, n, year, kind, i) in refs:
            i += 1
        out.append(ref_of(series, n, year, kind, i))
    return out


def slot_now(now: datetime | None = None) -> int:
    """Which third of the gap window this run asks: each number once a day."""
    now = now or datetime.now(timezone.utc)
    return (now.hour // 8) % SLOTS


class Asker:
    """Asks data.consilium for one reference and keeps the counts the verdict needs."""

    def __init__(self, client, pace: float):
        self.client, self.pace = client, pace
        self.asked = self.answered = self.found = 0

    def exists(self, ref: str) -> bool:
        self.asked += 1
        try:
            r = self.client.get(url_of(ref), headers={"Range": "bytes=0-3"})
        except Exception as exc:  # noqa: BLE001
            print(f"  {ref}: {type(exc).__name__}")
            return False
        finally:
            time.sleep(self.pace)
        if r.status_code in (200, 206, 404, 410):
            self.answered += 1
        ok = r.status_code in (200, 206) and r.content[:4] == b"%PDF"
        self.found += ok
        return ok


def store(engine, ref: str, apply: bool) -> bool:
    doc = CouncilDoc(external_id=ref, title=ref, url=url_of(ref), published=None,
                     subject_matters=[], category="document")
    body = fetch_document_text(doc, max_chars=MAX_TEXT) or ""
    meta = parse(ref, body)
    doc.title, doc.published = meta["title"], meta["published"]
    print(f"  {ref}: {doc.published} {doc.title[:80]}")
    if not apply:
        return False
    with engine.begin() as conn:
        _persist(conn, doc, SOURCE_REGISTER, body or None)
        if meta["meeting_date"]:
            conn.execute(text(
                "UPDATE institutional_publications SET extra_metadata = "
                "coalesce(extra_metadata, '{}'::jsonb) || CAST(:m AS jsonb) "
                "WHERE source_slug = :s AND external_id = :e"),
                {"m": json.dumps({"meeting_date": meta["meeting_date"].isoformat()}),
                 "s": SOURCE_REGISTER, "e": ref})
    return True


def chase_versions(asker, engine, refs, series, n, year, apply, deadline) -> int:
    """Ask the next REV, ADD and COR of a document; follow each one found to the next."""
    written = 0
    queue = next_versions(refs, series, n, year)
    while queue and time.monotonic() < deadline:
        ref = queue.pop(0)
        if not asker.exists(ref):
            continue
        written += store(engine, ref, apply)
        refs.add(ref)
        kind, i = ref.split("-")[3], int(ref.split("-")[4])
        queue.append(ref_of(series, n, year, kind, i + 1))
    return written


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--series", action="append", choices=list(MISS_LIMIT), default=[])
    ap.add_argument("--year", type=int, default=date.today().year)
    ap.add_argument("--max", type=int, default=400, help="new documents per series and run (forward)")
    ap.add_argument("--max-seconds", type=int, default=420, help="time budget; 0 = none")
    ap.add_argument("--pace", type=float, default=0.15)
    ap.add_argument("--slot", type=int, choices=range(SLOTS), help="gap third to ask (default: by the hour)")
    ap.add_argument("--no-gaps", action="store_true", help="forward only, as before 14 Oct 2026")
    ap.add_argument("--sweep", action="store_true", help="ask every unheld number in a range (backfill)")
    ap.add_argument("--from-number", type=int, default=1)
    ap.add_argument("--to-number", type=int)
    args = ap.parse_args(argv)

    series_list = args.series or ["CM", "ST", "WK"]
    deadline = time.monotonic() + (args.max_seconds or 10 ** 9)
    slot = args.slot if args.slot is not None else slot_now()
    written = 0
    unfinished = []
    engine = _engine()
    client = httpx.Client(timeout=40, headers=_UA, follow_redirects=True)
    asker = Asker(client, args.pace)
    try:
        for series in series_list:
            with engine.connect() as conn:
                refs = held(conn, series, args.year)
            have = init_numbers(refs)
            top = max(have, default=0)

            if args.sweep:
                hi = args.to_number or top
                todo = [n for n in range(args.from_number, hi + 1) if n not in have]
                print(f"[sweep] {series}-{args.year}: {len(todo)} unheld numbers in {args.from_number}-{hi}")
                for n in todo:
                    if time.monotonic() > deadline:
                        unfinished.append(series)
                        break
                    if asker.exists(ref_of(series, n, args.year)):
                        written += store(engine, ref_of(series, n, args.year), args.apply)
                        refs.add(ref_of(series, n, args.year))
                        written += chase_versions(asker, engine, refs, series, n, args.year, args.apply, deadline)
                continue

            # forward: the numbers after the highest held
            n, misses, got = top, 0, 0
            print(f"[forward] {series}-{args.year}: highest held {top}")
            while misses < MISS_LIMIT[series] and got < args.max:
                if time.monotonic() > deadline:
                    unfinished.append(series)
                    break
                n += 1
                ref = ref_of(series, n, args.year)
                if not asker.exists(ref):
                    misses += 1
                    continue
                misses, got = 0, got + 1
                written += store(engine, ref, args.apply)
                refs.add(ref)
                have.add(n)
            if args.no_gaps or series in unfinished:
                continue

            # gaps and versions: this run's third of the recent window
            window = [k for k in range(max(1, top - GAP_WINDOW[series] + 1), top + 1) if k % SLOTS == slot]
            gaps = [k for k in window if k not in have]
            print(f"[gaps] {series}-{args.year}: slot {slot}, {len(gaps)} unheld of {len(window)} numbers")
            for k in gaps:
                if time.monotonic() > deadline:
                    unfinished.append(series)
                    break
                if asker.exists(ref_of(series, k, args.year)):
                    written += store(engine, ref_of(series, k, args.year), args.apply)
                    refs.add(ref_of(series, k, args.year))
                    have.add(k)
            for k in [k for k in window if k in have]:
                if time.monotonic() > deadline:
                    if series not in unfinished:
                        unfinished.append(series)
                    break
                written += chase_versions(asker, engine, refs, series, k, args.year, args.apply, deadline)
    finally:
        client.close()

    print(f"[discover] asked {asker.asked}, answered {asker.answered}, found {asker.found}, "
          f"written {written}{'' if args.apply else ' (dry run: nothing written)'}")
    if asker.asked and not asker.answered:
        print("[ERROR] data.consilium answered none of the requests")
        return 1
    reasons = []
    if unfinished:
        reasons.append(f"time budget ran out in {', '.join(unfinished)}")
    if asker.asked and asker.answered < 0.8 * asker.asked:
        reasons.append(f"{asker.asked - asker.answered} of {asker.asked} requests unanswered")
    if reasons:
        print(f"[SYNC_STATUS] degraded: {'; '.join(reasons)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
