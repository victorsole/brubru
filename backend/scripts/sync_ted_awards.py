"""
Fill ted_award_notices + ted_award_winners (migration 315): TED contract awards whose buyer is an
EU institution, body or agency, read from each notice's eForms XML (services/scrapers/ted_awards.py).

TED's search API lists the candidates (result notices since --since whose buyer is labelled
eu-ins-bod-ag or has an EU-body address); each new one's XML is downloaded once and read: the
buyer is checked again on its own web and e-mail address, the winners are the organisations of the
tenders a contract was concluded with. A notice already held is not downloaded again (an award
notice is never edited: a change comes as a new notice, which keeps the notice uuid with a higher
version; the older one is then marked superseded_by the newer).

Runs daily in the daily tier (api/cron.py) over the last 14 days; the first fill reads from
1 Jan 2024 (TED has published eForms only since 25 Oct 2023). The tier records this job's run.

Run: python3.12 scripts/sync_ted_awards.py [--apply] [--since YYYY-MM-DD] [--until YYYY-MM-DD]
     [--limit N] [--refresh]
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from ingest_funding_sedia import get_env  # noqa: E402
from services.scrapers.ted_awards import compose_body, fetch_xml, host, parse_award, search_awards  # noqa: E402

NOTICE_COLUMNS = (
    "notice_uuid", "notice_version", "procedure_uuid", "changed_notice", "notice_subtype", "publication_date",
    "dispatch_date", "title", "description", "contract_nature", "procedure_type", "cpv_main", "cpv_codes",
    "body_code", "contracting_authority", "buyer_country", "buyer_legal_type", "buyers", "awarded_value",
    "awarded_value_currency", "lots", "lot_count", "winner_count", "public_url", "body_txt", "body_html",
)
WINNER_COLUMNS = (
    "lot_id", "lot_title", "rank", "name", "country", "city", "company_id", "vat_key", "size",
    "is_group_lead", "group_size", "tender_value", "tender_value_currency", "contract_id",
    "contract_reference", "contract_title", "contract_date", "award_date",
)
_JSON = {"buyers", "lots"}
UPSERT_NOTICE = (
    f"INSERT INTO ted_award_notices (publication_number, {', '.join(NOTICE_COLUMNS)}) "
    f"VALUES (%s, {', '.join('%s' for _ in NOTICE_COLUMNS)}) ON CONFLICT (publication_number) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in NOTICE_COLUMNS) + ", scraped_at = now()"
)
UPSERT_WINNERS = (
    f"INSERT INTO ted_award_winners (publication_number, tender_id, org_ref, {', '.join(WINNER_COLUMNS)}) VALUES %s "
    "ON CONFLICT (publication_number, tender_id, org_ref) DO UPDATE SET "
    + ", ".join(f"{c} = EXCLUDED.{c}" for c in WINNER_COLUMNS) + ", scraped_at = now()"
)
# The current version of each notice; the others point at it.
SUPERSEDE = """
WITH latest AS (
    SELECT DISTINCT ON (notice_uuid) notice_uuid, publication_number
      FROM ted_award_notices WHERE notice_uuid IS NOT NULL
     ORDER BY notice_uuid, notice_version DESC NULLS LAST, publication_date DESC NULLS LAST, publication_number DESC
)
UPDATE ted_award_notices n
   SET superseded_by = nullif(l.publication_number, n.publication_number)
  FROM latest l
 WHERE n.notice_uuid = l.notice_uuid
   AND n.superseded_by IS DISTINCT FROM nullif(l.publication_number, n.publication_number)
"""
FIRST_DAY = date(2024, 1, 1)
DAILY_WINDOW = 14


# A body's other domain, seen on TED (F4E's industry portal and e-mail; its site is fusionforenergy.europa.eu).
HOST_ALIASES = {"f4e.europa.eu": "f4e"}


def body_codes(cur) -> dict:
    """economy_bodies.code by the host of its website: the buyer's own web address names the body."""
    cur.execute("SELECT code, website FROM economy_bodies WHERE website IS NOT NULL")
    by_host = dict(HOST_ALIASES)
    for code, website in cur.fetchall():
        h = host(website)
        # The Commission's own site; its services' pages (ec.europa.eu/...) are matched below.
        if h and "/" not in website.split("://", 1)[-1].rstrip("/"):
            by_host.setdefault(h, code)
    return by_host


def _code_of_host(h: str, by_host: dict):
    """The host or the nearest parent a body owns (the-secretary-general.europarl.europa.eu)."""
    labels = h.split(".")
    for i in range(max(len(labels) - 2, 0) + 1):
        if ".".join(labels[i:]) in by_host:
            return by_host[".".join(labels[i:])]
    if h in ("ec.europa.eu", "commission.europa.eu") or h.endswith(".ec.europa.eu"):
        return "commission"
    return None


def body_code_of(notice: dict, by_host: dict):
    """The lead buyer's body (the contracting authority's): its web address names it, else its e-mail
    domain (DG COMM's web address is an e-procurement platform). A joint procurement's other buyers
    never do: F4E led one with EFCA and EU-OSHA, and it was tagged EFCA (27 Oct 2026)."""
    lead = notice["buyers"][0]
    for value in (lead.get("website"), lead.get("email")):
        h = host(value)
        code = _code_of_host(h, by_host) if h else None
        if code:
            return code
    return None


def store(conn, n: dict, by_host: dict) -> None:
    txt, page = compose_body(n)
    row = dict(n, body_code=body_code_of(n, by_host), lot_count=len(n["lots"]), winner_count=len(n["winners"]),
               body_txt=txt, body_html=page)
    values = [psycopg2.extras.Json(row[c]) if c in _JSON else row[c] for c in NOTICE_COLUMNS]
    winners = [(n["publication_number"], w["tender_id"], w["org_ref"], *(w[c] for c in WINNER_COLUMNS))
               for w in n["winners"] if w.get("org_ref")]
    with conn.cursor() as cur:
        cur.execute(UPSERT_NOTICE, [n["publication_number"], *values])
        if winners:
            psycopg2.extras.execute_values(cur, UPSERT_WINNERS, winners)
        # Winner rows a re-read no longer finds.
        cur.execute("DELETE FROM ted_award_winners WHERE publication_number = %s "
                    "AND tender_id || '/' || org_ref <> ALL(%s)",
                    (n["publication_number"], [f"{w[1]}/{w[2]}" for w in winners]))
    conn.commit()


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.strip().split("\n", 1)[0])
    ap.add_argument("--apply", action="store_true", help="Write (default: dry run; it still downloads, so pair it with --limit).")
    ap.add_argument("--since", type=date.fromisoformat, help=f"Published on or after (default: {DAILY_WINDOW} days ago, "
                    f"or {FIRST_DAY} when nothing is held).")
    ap.add_argument("--until", type=date.fromisoformat, default=None, help="Published on or before (default today).")
    ap.add_argument("--limit", type=int, default=None, help="Read at most N new notices (a sample).")
    ap.add_argument("--refresh", action="store_true", help="Download and read again the notices already held.")
    ap.add_argument("--sleep", type=float, default=0.5, help="Seconds between XML downloads.")
    args = ap.parse_args(argv)
    db = get_env("DATABASE_URL")
    if not db:
        print("[FATAL] DATABASE_URL missing")
        return 1
    conn = psycopg2.connect(db.replace("postgresql+psycopg2://", "postgresql://"))
    session = requests.Session()
    session.headers["User-Agent"] = "Brubru EU data (hello@beresol.eu)"
    counts = {"candidates": 0, "held": 0, "stored": 0, "not_eu": 0, "failed": 0, "winners": 0}
    failures = []
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ted_award_notices")
            empty = cur.fetchone()[0] == 0
            by_host = body_codes(cur)
        until = args.until or date.today()
        since = args.since or (FIRST_DAY if empty else until - timedelta(days=DAILY_WINDOW))
        candidates = list(dict.fromkeys(search_awards(session, since, until)))
        counts["candidates"] = len(candidates)
        with conn.cursor() as cur:
            cur.execute("SELECT publication_number FROM ted_award_notices WHERE publication_number = ANY(%s)", (candidates,))
            held = {r[0] for r in cur.fetchall()}
        todo = [p for p in candidates if args.refresh or p not in held]
        counts["held"] = len(candidates) - len(todo)
        if args.limit is not None:
            todo = todo[:args.limit]
        for i, pub in enumerate(todo, 1):
            try:
                notice = parse_award(fetch_xml(session, pub), pub)
                if notice is None:
                    counts["not_eu"] += 1
                elif args.apply:
                    store(conn, notice, by_host)
                    counts["stored"] += 1
                    counts["winners"] += len(notice["winners"])
                else:
                    counts["stored"] += 1
                    counts["winners"] += len(notice["winners"])
            except Exception as exc:  # noqa: BLE001 -- one notice never stops the run
                conn.rollback()
                counts["failed"] += 1
                failures.append(f"{pub}: {type(exc).__name__}: {exc}"[:160])
            if i % 200 == 0:
                print(f"[INFO] {i}/{len(todo)} read: {counts}", flush=True)
            time.sleep(args.sleep)
        if args.apply:
            with conn.cursor() as cur:
                cur.execute(SUPERSEDE)
                superseded = cur.rowcount
            conn.commit()
        else:
            superseded = 0
    finally:
        conn.close()
    verb = "stored" if args.apply else "readable (dry run)"
    print(f"[{'OK' if args.apply else 'DRY-RUN'}] {since} to {until}: {counts['candidates']} candidate notice(s), "
          f"{counts['held']} already held, {counts['stored']} {verb} with {counts['winners']} winner row(s), "
          f"{counts['not_eu']} without an EU-body buyer, {counts['failed']} failed; {superseded} superseded mark(s) changed")
    if failures:
        print(f"[SYNC_STATUS] degraded: {len(failures)} notice(s) failed: {'; '.join(failures[:5])}")
    if counts["candidates"] and not (counts["stored"] or counts["held"]):
        print("[ERROR] TED listed candidates but none was read")
        return 1
    if failures and len(failures) > max(5, counts["stored"] // 10):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
