#!/usr/bin/env python3.12
"""Complete register documents that arrived as a bare reference: CELEX, date, text, title.

Why (13 Oct 2026). The 100 newest documents on /commission-register-documents served no text, and 82
of them no date and no link. A document arrives from the EUR-Lex feeds as a reference and a title. Its
CELEX, date and text were added by scripts run by hand, last on 2 October, so every later row stayed
as it arrived: 110 of the 111 that came after 5 October had no text.

This runs the same steps on a schedule, each on what the step before it stored:
  1. CELEX  the one the row's own reference, title or link states, once Cellar confirms it
  2. date   Cellar's work_date_document for that CELEX
  3. text   the act's text from eu_laws where it is held, otherwise from Cellar
  4. title  Cellar's English title, where the row holds a placeholder ("SWD document 52026SC0702")

The parsers and fetchers are the ones those scripts use, imported, so there is one of each. Only an
empty cell is written (a placeholder title counts as empty) and nothing is derived.

Left alone, and counted: a row whose title is a corrigendum's CELEX ("CELEX:32011L0089R(02)"). It is
filed under the act it corrects, so that act's date and text are not its own.

Usage (from backend/):
    python3.12 scripts/complete_commission_documents.py                    # dry run, writes nothing
    python3.12 scripts/complete_commission_documents.py --apply            # what the cron runs
    python3.12 scripts/complete_commission_documents.py --apply --days 0   # every row, not the last 30 days

Exit code: 0 done ("[SYNC_STATUS] degraded: ..." when documents older than three days are still
incomplete); 1 when there was work and Cellar answered none of it (a wall is not an absence).
"""
from __future__ import annotations

import argparse
import datetime as dt
import importlib.util
import json
import pathlib
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, BACKEND / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


_celex = _load("backfill_register_celex_from_title")    # _candidate, _exists
_date = _load("backfill_dates_from_cellar_by_celex")    # _dates
_laws = _load("fetch_eu_law_bodies")                    # _fetch, _database_url

DAYS = 30        # rows first seen in this window are worked on
GRACE_DAYS = 3   # Cellar can hold a document two days after its date (COM(2026) 546, 9 Oct 2026)
BATCH = 60
MIN_TITLE = 20   # Cellar's short form is "SWD/2026/119 final", and one title came back empty

# A corrigendum arrives titled with its own CELEX but filed under the act it corrects.
CORRIGENDUM = r"^CELEX:\S*R\(\d+\)"
PLACEHOLDER = r"^(SWD|JOIN|COM) document "

_SCOPE = f"first_seen >= :since AND title !~ '{CORRIGENDUM}'"

NO_CELEX = text(f"""
    SELECT id, reference, title, portal_url FROM commission_documents
     WHERE coalesce(celex, '') = '' AND {_SCOPE}
     ORDER BY first_seen DESC""")
TAKEN = text("SELECT celex FROM commission_documents WHERE coalesce(celex, '') <> ''")
SET_CELEX = text("""
    UPDATE commission_documents SET celex = :v, last_updated = now()
     WHERE id = :rid AND coalesce(celex, '') = ''""")

NO_DATE = text(f"""
    SELECT id, celex FROM commission_documents
     WHERE publication_date IS NULL AND coalesce(celex, '') <> '' AND {_SCOPE}""")
SET_DATE = text("""
    UPDATE commission_documents SET publication_date = :v, last_updated = now()
     WHERE id = :rid AND publication_date IS NULL""")

FROM_LAWS = text(f"""
    UPDATE commission_documents d
       SET text_body = l.body_txt,
           body_html = COALESCE(NULLIF(d.body_html, ''), l.body_html),
           last_updated = now()
      FROM eu_laws l
     WHERE l.celex = d.celex AND coalesce(d.text_body, '') = '' AND coalesce(l.body_txt, '') <> ''
       AND d.first_seen >= :since AND d.title !~ '{CORRIGENDUM}'""")
LAWS_HAVE = text(f"""
    SELECT count(*) FROM commission_documents d JOIN eu_laws l ON l.celex = d.celex
     WHERE coalesce(d.text_body, '') = '' AND coalesce(l.body_txt, '') <> ''
       AND d.first_seen >= :since AND d.title !~ '{CORRIGENDUM}'""")
NO_TEXT = text(f"""
    SELECT id, celex FROM commission_documents d
     WHERE coalesce(text_body, '') = '' AND coalesce(celex, '') <> '' AND {_SCOPE}
       AND NOT EXISTS (SELECT 1 FROM eu_laws l WHERE l.celex = d.celex AND coalesce(l.body_txt, '') <> '')
     ORDER BY first_seen DESC LIMIT :lim""")
SET_TEXT = text("""
    UPDATE commission_documents
       SET text_body = :txt, body_html = COALESCE(NULLIF(body_html, ''), :html), last_updated = now()
     WHERE id = :rid AND coalesce(text_body, '') = ''""")

NO_TITLE = text(f"""
    SELECT id, celex, title FROM commission_documents
     WHERE title ~ '{PLACEHOLDER}' AND coalesce(celex, '') <> '' AND first_seen >= :since""")
SET_TITLE = text(f"""
    UPDATE commission_documents SET title = :v, last_updated = now()
     WHERE id = :rid AND title ~ '{PLACEHOLDER}'""")

STILL = text(f"""
    SELECT reference,
           publication_date IS NULL AS no_date,
           coalesce(text_body, '') = '' AS no_text
      FROM commission_documents
     WHERE (publication_date IS NULL OR coalesce(text_body, '') = '')
       AND first_seen < :settled AND {_SCOPE}
     ORDER BY first_seen DESC""")
CORRIGENDA = text(f"""
    SELECT count(*) FROM commission_documents
     WHERE title ~ '{CORRIGENDUM}' AND first_seen >= :since
       AND (publication_date IS NULL OR coalesce(text_body, '') = '')""")

_TITLES = (
    "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
    "SELECT ?c ?t WHERE {{ VALUES ?c {{ {vals} }} ?w cdm:resource_legal_id_celex ?c . "
    "?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language "
    "<http://publications.europa.eu/resource/authority/language/ENG> ; cdm:expression_title ?t . }}")


# --------------------------------------------------------------------------
# Pure functions (tested without a network or a database)
# --------------------------------------------------------------------------

def one_title(titles: set[str] | None) -> str | None:
    """Cellar's English title, or nothing: an empty or short string is not a title, and two
    different titles for one CELEX are not settled here."""
    real = {" ".join(t.split()) for t in (titles or ()) if len(" ".join(t.split())) >= MIN_TITLE}
    return next(iter(real))[:1000] if len(real) == 1 else None


def one_date(dates: set[str] | None) -> dt.date | None:
    return dt.date.fromisoformat(next(iter(dates))) if dates and len(dates) == 1 else None


def answered(got) -> bool:
    """Did Cellar answer about this text? A 404 and a too-short page are answers; a refusal, a
    timeout or a broken PDF is not, and must never read as 'no text exists'."""
    return not isinstance(got, str) or got.startswith(("http_404", "too_short", "http_300_nodocs"))


def verdict(work: int, reached: int, still: list[str]) -> tuple[int, str | None]:
    """(exit code, degraded line). `work` is what needed Cellar, `reached` what Cellar answered."""
    if work and not reached:
        return 1, None
    if still:
        shown = ", ".join(still[:8]) + (f" and {len(still) - 8} more" if len(still) > 8 else "")
        return 0, (f"{len(still)} register documents older than {GRACE_DAYS} days still lack a date "
                   f"or a text: {shown}")
    return 0, None


# --------------------------------------------------------------------------
# I/O
# --------------------------------------------------------------------------

def _titles(celexes: list[str], ctx) -> dict[str, set[str]]:
    vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes)
    req = urllib.request.Request(
        _date.SPARQL + "?" + urllib.parse.urlencode({"query": _TITLES.format(vals=vals)}),
        headers={"Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=90, context=ctx) as r:
        data = json.load(r)
    out: dict[str, set[str]] = {}
    for b in data["results"]["bindings"]:
        out.setdefault(b["c"]["value"], set()).add(b["t"]["value"])
    return out


def _batched(fn, celexes: list[str], ctx) -> tuple[dict[str, set[str]], int]:
    """(answers, CELEX asked in a batch Cellar answered)."""
    found: dict[str, set[str]] = {}
    reached = 0
    for i in range(0, len(celexes), BATCH):
        part = celexes[i:i + BATCH]
        try:
            found.update(fn(part, ctx))
            reached += len(part)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] Cellar did not answer for {len(part)} documents: {type(e).__name__}: {e}")
        time.sleep(0.3)
    return found, reached


def complete(engine, ctx, since: dt.datetime, apply: bool, limit: int) -> tuple[int, int, dict]:
    """Run the four steps. Returns (work that needed Cellar, work Cellar answered, counts)."""
    n = {"celex": 0, "date": 0, "text_from_laws": 0, "text_from_cellar": 0, "title": 0}
    work = reached = 0
    scope = {"since": since}

    def store(stmt, params) -> int:
        if not apply:
            return 1
        with engine.begin() as c:
            return c.execute(stmt, params).rowcount

    # 1. CELEX
    with engine.connect() as c:
        rows = list(c.execute(NO_CELEX, scope))
        taken = {r[0] for r in c.execute(TAKEN)}
    stated = unconfirmed = 0
    for r in rows:
        # A staff working document arrives as "SWD(2026) 702": its CELEX is in the link it came with.
        cand = _celex._candidate(r.reference, r.title) or _celex._candidate("", r.portal_url or "")
        if not cand or cand in taken:
            continue
        stated += 1
        if stated > limit:  # the rest wait for the next run: a backlog must not outlast the cron's timeout
            continue
        work += 1
        st = _celex._exists(cand, ctx)
        if st.isdigit():
            reached += 1
        if st in ("200", "300", "303"):
            n["celex"] += store(SET_CELEX, {"rid": r.id, "v": cand})
            taken.add(cand)
        else:
            unconfirmed += 1
        time.sleep(0.2)
    print(f"[INFO] CELEX : {len(rows)} rows without one | {stated} state one | stored {n['celex']} "
          f"| not confirmed by Cellar {unconfirmed}")

    # 2. date
    with engine.connect() as c:
        rows = list(c.execute(NO_DATE, scope))
    found, got = _batched(_date._dates, sorted({r.celex for r in rows}), ctx)
    work += len(rows)
    reached += len(rows) if got else 0
    for r in rows:
        d = one_date(found.get(r.celex))
        if d:
            n["date"] += store(SET_DATE, {"rid": r.id, "v": d})
    print(f"[INFO] date  : {len(rows)} rows without one | stored {n['date']}")

    # 3. text
    with engine.connect() as c:
        held = c.execute(LAWS_HAVE, scope).scalar_one()
    if apply and held:
        with engine.begin() as c:
            n["text_from_laws"] = c.execute(FROM_LAWS, scope).rowcount
    else:
        n["text_from_laws"] = held
    with engine.connect() as c:
        rows = list(c.execute(NO_TEXT, {**scope, "lim": limit}))
    why: dict[str, int] = {}
    for r in rows:
        work += 1
        got = _laws._fetch(r.celex, ctx)
        reached += answered(got)
        if isinstance(got, str):
            key = "too_short" if got.startswith("too_short") else got
            why[key] = why.get(key, 0) + 1
        else:
            html, txt = got
            n["text_from_cellar"] += store(SET_TEXT, {"rid": r.id, "txt": txt, "html": html})
        time.sleep(0.3)
    print(f"[INFO] text  : copied from eu_laws {n['text_from_laws']} | asked Cellar for {len(rows)} "
          f"| stored {n['text_from_cellar']} | not stored {why or 0}")

    # 4. title
    with engine.connect() as c:
        rows = list(c.execute(NO_TITLE, scope))
    found, got = _batched(_titles, sorted({r.celex for r in rows}), ctx)
    work += len(rows)
    reached += len(rows) if got else 0
    for r in rows:
        t = one_title(found.get(r.celex))
        if t:
            n["title"] += store(SET_TITLE, {"rid": r.id, "v": t})
    print(f"[INFO] title : {len(rows)} placeholders | stored {n['title']}")
    return work, reached, n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="write (default: dry run)")
    ap.add_argument("--days", type=int, default=DAYS, help="rows first seen in the last N days; 0 = every row")
    ap.add_argument("--limit", type=int, default=120,
                    help="most CELEX checked and most texts fetched at Cellar in one run")
    args = ap.parse_args()

    now = dt.datetime.now(dt.timezone.utc)
    since = now - dt.timedelta(days=args.days) if args.days else dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    engine = create_engine(
        _laws._database_url(), pool_pre_ping=True, pool_recycle=300,
        connect_args={"keepalives": 1, "keepalives_idle": 20, "keepalives_interval": 10,
                      "keepalives_count": 3, "connect_timeout": 20})
    ctx = ssl.create_default_context(cafile=certifi.where())

    work, reached, n = complete(engine, ctx, since, args.apply, args.limit)

    with engine.connect() as c:
        still = [r.reference for r in c.execute(
            STILL, {"since": since, "settled": now - dt.timedelta(days=GRACE_DAYS)})]
        corrigenda = c.execute(CORRIGENDA, {"since": since}).scalar_one()
    if corrigenda:
        print(f"[INFO] {corrigenda} corrigenda left as they arrived: filed under the act they correct")
    if not args.apply:
        print(f"[INFO] dry run, nothing written (each step sees only what is already stored): {n}")
        return 0
    code, degraded = verdict(work, reached, still)
    if code:
        print(f"[ERROR] {work} documents needed Cellar and it answered for none")
        return code
    if degraded:
        print(f"[SYNC_STATUS] degraded: {degraded}")
    print(f"[OK] stored {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
