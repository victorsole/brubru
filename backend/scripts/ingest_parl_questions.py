"""
Ingest EP parliamentary questions from the EP Open Data API.

Why this was rewritten (25 Sep 2026)
------------------------------------
The previous version scraped the plenary questions HTML listing. That page now
sits behind a WAF (HTTP 202, 0 bytes), so it parsed nothing, printed "No
questions parsed", inserted nothing and exited 0: the `parl_questions` job
recorded SUCCESS every day while the newest stored question was dated 24 April
2026. EP Open Data listed 3,590 questions for 2026 against 1,370 held.

Source: https://data.europarl.europa.eu/api/v2/parliamentary-questions
  - the list (?year=YYYY, paged) gives every question id for a year;
  - the item (/parliamentary-questions/{id}) gives title, date, authors (EP
    person ids) and the answer's date when there is one.

Each run:
  1. lists this year's questions (and last year's in January), inserts every id
     we do not hold, newest first;
  2. refreshes the answer date of recent unanswered questions;
  3. stops starting new fetches after --max-seconds, so a run always records.

Exit status is the verdict: 1 when the list cannot be read (the source is down
or walled: never "success" with nothing), `[SYNC_STATUS] degraded` while ids
are left for the next run, 0 otherwise.

Usage:
    python3.12 scripts/ingest_parl_questions.py                  # scheduled form
    python3.12 scripts/ingest_parl_questions.py --dry-run
    python3.12 scripts/ingest_parl_questions.py --year 2026 --max-seconds 780
"""

import argparse
import datetime as dt
import sys
import time
from pathlib import Path

import httpx
import psycopg2

BACKEND = Path(__file__).resolve().parents[1]
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

API = "https://data.europarl.europa.eu/api/v2/parliamentary-questions"
DOCEO = "https://www.europarl.europa.eu/doceo/document/{id}_EN.html"
PAGE = 500

_TYPES = {
    "QUESTION_WRITTEN": "written",
    "QUESTION_WRITTEN_PRIORITY": "priority",
    "QUESTION_ORAL": "oral",
    "QUESTION_TIME": "question_time",
}


def reference(identifier: str) -> str:
    """'E-10-2026-001683' -> 'E-001683/2026' (the form already stored)."""
    letter, _term, year, num = identifier.split("-")
    return f"{letter}-{num}/{year}"


def _get_data(client: httpx.Client, url: str, params: dict, attempts: int = 4):
    """The response's `data` list, retried; None only for a genuine 404.

    A 200 can carry the failure in its BODY: EP Open Data answers "Pending
    acquire queue has reached its maximum size" with HTTP 200 and no `data`.
    That is transient load, so it is retried, never read as an empty answer.
    """
    last = ""
    for attempt in range(1, attempts + 1):
        r = client.get(url, params=params)
        if r.status_code == 404:
            return None
        if r.status_code == 204:
            return []          # past the end of a list: EP answers 204, not an empty page
        if r.status_code == 200:
            try:
                data = r.json().get("data")
            except ValueError:
                data = None
            if data is not None:
                return data
            last = f"200 without data: {r.text[:160]}"
        else:
            last = f"HTTP {r.status_code}"
        if attempt < attempts:
            wait = 2.0 * attempt
            if r.status_code == 429:
                # Throttled: honour Retry-After, else back off harder.
                try:
                    wait = max(wait, float(r.headers.get("Retry-After", "")))
                except ValueError:
                    wait = 10.0 * attempt
            time.sleep(min(wait, 60.0))
    raise RuntimeError(f"{url}: {last} after {attempts} attempts")


def list_ids(client: httpx.Client, year: int, deadline: float) -> list[str]:
    ids, offset = [], 0
    while True:
        if time.monotonic() > deadline:
            raise RuntimeError(f"listing {year} ran past the time budget at offset {offset}")
        page = _get_data(client, API, {"year": year, "format": "application/ld+json",
                                       "offset": offset, "limit": PAGE})
        if page is None:
            raise RuntimeError(f"list for {year} answered 404")
        ids += [d["identifier"] for d in page if d.get("identifier")]
        # The server returns FEWER items than asked for at will (300 of 500
        # on 25 Sep 2026), so a short page is not the end: only an empty one is.
        if not page:
            return list(dict.fromkeys(ids))
        offset += len(page)


def fetch_item(client: httpx.Client, identifier: str) -> dict | None:
    data = _get_data(client, f"{API}/{identifier}",
                     {"format": "application/ld+json", "language": "en"})
    return data[0] if data else None


def to_row(item: dict, names: dict) -> dict:
    identifier = item["identifier"]
    titles = item.get("title_dcterms") or {}
    title = (titles.get("en") or next(iter(titles.values()), "") or "").strip()
    wtype = (item.get("work_type") or "").rsplit("/", 1)[-1]
    person_ids = [c.split("/", 1)[1] for c in item.get("creator") or []
                  if isinstance(c, str) and c.startswith("person/")]
    answers = item.get("inverse_answers_to") or []
    answered = min((a.get("document_date") for a in answers if a.get("document_date")),
                   default=None)
    term = (item.get("parliamentary_term") or "org/ep-10").rsplit("-", 1)[-1]
    return {
        "question_reference": reference(identifier),
        "question_type": _TYPES.get(wtype, "written"),
        "parliamentary_term": int(term) if term.isdigit() else 10,
        "subject": title[:5000] or identifier,
        "submitted_date": item.get("document_date"),
        "answered_date": answered,
        "asking_mep_ids": person_ids,
        "asking_mep_names": [names[p] for p in person_ids if p in names],
        "source_url": DOCEO.format(id=identifier),
        "answer_url": DOCEO.format(id=f"{identifier}-ASW") if answers else None,
    }


_UPSERT = """
INSERT INTO parliamentary_questions (
    question_reference, question_type, parliamentary_term, subject,
    submitted_date, answered_date, asking_mep_ids, asking_mep_names,
    source_url, answer_url
) VALUES (
    %(question_reference)s, %(question_type)s, %(parliamentary_term)s, %(subject)s,
    %(submitted_date)s, %(answered_date)s, %(asking_mep_ids)s, %(asking_mep_names)s,
    %(source_url)s, %(answer_url)s
)
ON CONFLICT (question_reference) DO UPDATE SET
    answered_date = COALESCE(EXCLUDED.answered_date, parliamentary_questions.answered_date),
    answer_url = COALESCE(EXCLUDED.answer_url, parliamentary_questions.answer_url),
    submitted_date = COALESCE(parliamentary_questions.submitted_date, EXCLUDED.submitted_date),
    last_updated = NOW()
"""


def _flush(db_url: str, rows: list[dict]) -> None:
    """Write and clear `rows` on a fresh connection (one retry)."""
    if not rows:
        return
    for attempt in (1, 2):
        try:
            conn = psycopg2.connect(db_url)
            try:
                with conn, conn.cursor() as cur:
                    for row in rows:
                        cur.execute(_UPSERT, row)
            finally:
                conn.close()
            rows.clear()
            return
        except psycopg2.OperationalError:
            if attempt == 2:
                raise
            time.sleep(3)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, action="append",
                    help="Year to list (repeatable). Default: this year, plus last year in January.")
    ap.add_argument("--max-seconds", type=int, default=780,
                    help="Stop starting new fetches after this long (scheduled timeout is 900).")
    ap.add_argument("--refresh-days", type=int, default=120,
                    help="Re-check the answer of unanswered questions submitted in this window.")
    ap.add_argument("--pace", type=float, default=0.35,
                    help="Seconds between item fetches (EP Open Data throttles with 429).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    today = dt.date.today()
    years = args.year or ([today.year - 1, today.year] if today.month == 1 else [today.year])
    started = time.monotonic()

    from scripts._db_url import get_database_url   # env first; .env is a dev fallback
    conn = psycopg2.connect(get_database_url())
    cur = conn.cursor()
    cur.execute("SELECT question_reference FROM parliamentary_questions")
    held = {r[0] for r in cur.fetchall()}
    cur.execute("SELECT htv_id::text, full_name FROM ep_members WHERE htv_id IS NOT NULL")
    names = dict(cur.fetchall())
    cur.execute(
        "SELECT question_reference FROM parliamentary_questions "
        "WHERE answered_date IS NULL AND submitted_date >= %s "
        "ORDER BY submitted_date", (today - dt.timedelta(days=args.refresh_days),))
    stale = [r[0] for r in cur.fetchall()]
    # No connection is held across network work (25 Sep 2026: the server
    # dropped one mid-run while EP Open Data was slow). Writes go out in
    # batches, each on a fresh connection.
    conn.close()
    db_url = get_database_url()

    headers = {"User-Agent": "Brubru/1.0 (EU policy intelligence; +https://brubru.beresol.eu)",
               "Accept": "application/ld+json"}
    inserted = refreshed = missing_upstream = errors = 0
    with httpx.Client(headers=headers, timeout=60.0, follow_redirects=True) as client:
        listed = []
        for year in years:
            try:
                listed += list_ids(client, year, started + args.max_seconds)
            except Exception as exc:  # noqa: BLE001
                print(f"[ERROR] cannot list {year} questions: {type(exc).__name__}: {exc}")
                return 1
        if not listed:
            print(f"[ERROR] EP Open Data listed 0 questions for {years}: source down or changed")
            return 1
        # A list shorter than what we already hold for those years is a broken
        # read, not a quiet day: never let it pass as "0 new".
        held_years = sum(1 for r in held if r.rsplit("/", 1)[-1] in {str(y) for y in years})
        if len(listed) < held_years:
            print(f"[ERROR] listed {len(listed)} questions for {years} but {held_years} "
                  f"are already stored: the listing is incomplete")
            return 1

        # Newest first across all question types: E-10-2026-001683 -> (2026, 1683).
        new = sorted((i for i in listed if reference(i) not in held),
                     key=lambda i: (i.split("-")[2], int(i.split("-")[3])), reverse=True)
        by_ref = {reference(i): i for i in listed}
        refresh = [by_ref[r] for r in stale if r in by_ref]
        print(f"[INFO] listed {len(listed)} for {years}; held {len(held)}; "
              f"new {len(new)}; unanswered to re-check {len(refresh)}")

        queue = [(i, True) for i in new] + [(i, False) for i in refresh]
        done = 0
        pending: list[dict] = []
        for identifier, is_new in queue:
            if time.monotonic() - started > args.max_seconds:
                break
            done += 1
            if done > 1:
                time.sleep(args.pace)
            try:
                item = fetch_item(client, identifier)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                print(f"[WARN] {identifier}: {type(exc).__name__}: {exc}")
                continue
            if item is None:
                missing_upstream += 1
                continue
            row = to_row(item, names)
            if not is_new and not row["answered_date"]:
                continue
            if args.dry_run:
                print(f"  {'NEW' if is_new else 'ANS'} {row['question_reference']} "
                      f"{row['submitted_date']} {row['subject'][:60]}")
            else:
                pending.append(row)
                if len(pending) >= 50:
                    _flush(db_url, pending)
            inserted += is_new
            refreshed += (not is_new)
        if not args.dry_run:
            _flush(db_url, pending)

    left = len(queue) - done
    print(f"\n=== DONE === inserted={inserted} answers_refreshed={refreshed} "
          f"missing_upstream={missing_upstream} errors={errors} left_for_next_run={left} "
          f"({time.monotonic() - started:.0f}s)")
    if errors and errors > done // 2:
        print(f"[ERROR] {errors} of {done} item fetches failed")
        return 1
    if left or errors:
        print(f"[SYNC_STATUS] degraded: {left} question(s) left for the next run, "
              f"{errors} fetch error(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
