#!/usr/bin/env python3.12
"""Complete register documents that arrived as a bare reference: CELEX, date, text, title.

Why (13 Oct 2026). The 100 newest documents on /commission-register-documents served no text, and 82
of them no date and no link. A document arrives from the EUR-Lex feeds as a reference and a title. Its
CELEX, date and text were added by scripts run by hand, last on 2 October, so every later row stayed
as it arrived: 110 of the 111 that came after 5 October had no text.

This runs those steps on a schedule, each on what the step before it stored:
  1. CELEX  the one the row's own title, link or reference states, once Cellar holds it
  2. date   Cellar's work_date_document for that CELEX
  3. text   the act's text from eu_laws where it is held, otherwise from Cellar
  4. title  Cellar's title, where the row holds a placeholder ("SWD document 52026SC0702")

Only an empty cell is written (a placeholder title counts as empty) and nothing is derived. The CELEX
is read whole: a suffix is part of it. 52026SC0050 is an opinion of the Regulatory Scrutiny Board and
52026SC0050(01) the staff working document SWD(2026) 50; a CELEX rebuilt from "SWD(2026) 50" gave that
document the opinion's text.

A corrigendum (32011L0089R(02)) is its own document, with its own date, and exists only in the
languages it corrects: 274 of the 293 held on 13 Oct 2026 have no English version, 236 exist in one
language. Its title and text are stored in English where there is one, otherwise in the first of
French, Spanish, Italian, Dutch, German, then any; `languages` lists that language first. The page
is stored only if it names the act it corrects or carries the title Cellar gives the document.

Left alone, and counted: a row still filed under the act its corrigendum corrects (title
"CELEX:32011L0089R(02)", reference 32011L0089). refile_register_documents.py refiles those.

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
import urllib.error
import urllib.parse
import urllib.request

BACKEND = pathlib.Path(__file__).resolve().parents[1]
for p in (str(BACKEND.parent), str(BACKEND)):
    if p not in sys.path:
        sys.path.insert(0, p)

import certifi  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402

_spec = importlib.util.spec_from_file_location("fetch_eu_law_bodies", BACKEND / "scripts" / "fetch_eu_law_bodies.py")
_laws = importlib.util.module_from_spec(_spec)  # _fetch, _cellar_url, _strip, _clean_html, _database_url
sys.modules["fetch_eu_law_bodies"] = _laws
_spec.loader.exec_module(_laws)

SPARQL = "https://publications.europa.eu/webapi/rdf/sparql"
DAYS = 30        # rows first seen in this window are worked on
GRACE_DAYS = 3   # Cellar can hold a document two days after its date (COM(2026) 546, 9 Oct 2026)
BATCH = 40
MIN_TITLE = 20   # Cellar's short form is "SWD/2026/119 final", and one title came back empty
MIN_CORRIGENDUM = 150  # a corrigendum is a few lines: the 600-character floor for acts would refuse it

# A CELEX, whole. "(01)" marks a second document under one number, "R(02)" a corrigendum or a
# later version (SWD(2024) 29 final/3 is 52024SC0029R(02)).
CELEX = r"[1-9][0-9]{4}[A-Z]{1,2}[0-9]{4,5}(?:\([0-9]{2}\))?(?:R\([0-9]{2}\))?"
_IS_CELEX = re.compile(rf"^{CELEX}$")
_IN_TITLE = re.compile(rf"^(?:(?:SWD|JOIN|COM|SEC) document |CELEX:)({CELEX})(?![0-9A-Za-z(])")
_IN_LINK = re.compile(rf"[?&]uri=CELEX:({CELEX})$")
_PARTS = re.compile(r"^([1-9])([0-9]{4})([A-Z]{1,2})([0-9]{4,5})")

PLACEHOLDER = r"^((SWD|JOIN|COM|SEC) document |CELEX:)"
# Still filed under the act its corrigendum corrects: that act's date and text are not its own.
MISFILED = r"({a}title ~ '^CELEX:\S*R\([0-9]+\)' AND {a}reference !~ 'R\([0-9]{{2}}\)$')"
LANGUAGES = {"BUL": "BG", "CES": "CS", "DAN": "DA", "DEU": "DE", "ELL": "EL", "ENG": "EN", "EST": "ET",
             "FIN": "FI", "FRA": "FR", "GLE": "GA", "HRV": "HR", "HUN": "HU", "ITA": "IT", "LAV": "LV",
             "LIT": "LT", "MLT": "MT", "NLD": "NL", "POL": "PL", "POR": "PT", "RON": "RO", "SLK": "SK",
             "SLV": "SL", "SPA": "ES", "SWE": "SV"}
PREFERRED = ("ENG", "FRA", "SPA", "ITA", "NLD", "DEU")


def _scope(alias: str = "") -> str:
    return f"{alias}first_seen >= :since AND NOT {MISFILED.format(a=alias)}"


NO_CELEX = text(f"""
    SELECT id, reference, title, portal_url FROM commission_documents
     WHERE coalesce(celex, '') = '' AND {_scope()}
     ORDER BY first_seen DESC""")
TAKEN = text("SELECT celex FROM commission_documents WHERE coalesce(celex, '') <> ''")
SET_CELEX = text("""
    UPDATE commission_documents SET celex = :v, last_updated = now()
     WHERE id = :rid AND coalesce(celex, '') = ''""")

NO_DATE = text(f"""
    SELECT id, celex FROM commission_documents
     WHERE publication_date IS NULL AND coalesce(celex, '') <> '' AND {_scope()}""")
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
       AND {_scope('d.')}""")
LAWS_HAVE = text(f"""
    SELECT count(*) FROM commission_documents d JOIN eu_laws l ON l.celex = d.celex
     WHERE coalesce(d.text_body, '') = '' AND coalesce(l.body_txt, '') <> '' AND {_scope('d.')}""")
NO_TEXT = text(f"""
    SELECT id, celex FROM commission_documents d
     WHERE coalesce(text_body, '') = '' AND coalesce(celex, '') <> '' AND {_scope()}
       AND NOT EXISTS (SELECT 1 FROM eu_laws l WHERE l.celex = d.celex AND coalesce(l.body_txt, '') <> '')
     ORDER BY first_seen DESC LIMIT :lim""")
SET_TEXT = text("""
    UPDATE commission_documents
       SET text_body = :txt, body_html = COALESCE(NULLIF(body_html, ''), :html), last_updated = now()
     WHERE id = :rid AND coalesce(text_body, '') = ''""")

NO_TITLE = text(f"""
    SELECT id, celex, title FROM commission_documents
     WHERE title ~ '{PLACEHOLDER}' AND coalesce(celex, '') <> '' AND {_scope()}""")
SET_TITLE = text(f"""
    UPDATE commission_documents SET title = :v, last_updated = now()
     WHERE id = :rid AND title ~ '{PLACEHOLDER}'""")

# The feed reader writes {{EN}} on every row; a corrigendum exists in the languages it corrects.
NO_LANGUAGES = text(f"""
    SELECT id, celex, languages FROM commission_documents
     WHERE celex ~ 'R\\([0-9]{{2}}\\)$' AND coalesce(languages::text, '{{}}') IN ('{{}}', '{{EN}}')
       AND {_scope()}""")
SET_LANGUAGES = text("""
    UPDATE commission_documents SET languages = :v, last_updated = now()
     WHERE id = :rid AND coalesce(languages::text, '{}') IN ('{}', '{EN}')""")

STILL = text(f"""
    SELECT reference FROM commission_documents
     WHERE (publication_date IS NULL OR coalesce(text_body, '') = '')
       AND first_seen < :settled AND {_scope()}
     ORDER BY first_seen DESC""")
MISFILED_ROWS = text(f"SELECT count(*) FROM commission_documents WHERE first_seen >= :since AND {MISFILED.format(a='')}")

_FACTS = (
    "PREFIX cdm: <http://publications.europa.eu/ontology/cdm#> "
    "SELECT ?c ?d ?lang ?t WHERE {{ VALUES ?c {{ {vals} }} ?w cdm:resource_legal_id_celex ?c . "
    "OPTIONAL {{ ?w cdm:work_date_document ?d }} "
    "OPTIONAL {{ ?e cdm:expression_belongs_to_work ?w ; cdm:expression_uses_language ?lang . "
    "OPTIONAL {{ ?e cdm:expression_title ?t }} }} }}")


# --------------------------------------------------------------------------
# Pure functions (tested without a network or a database)
# --------------------------------------------------------------------------

def stated_celex(reference: str | None, title: str | None, link: str | None) -> str | None:
    """The CELEX the row itself states, whole. Never one rebuilt from "SWD(2026) 50"."""
    for rx, s in ((_IN_TITLE, title), (_IN_LINK, link)):
        m = rx.search((s or "").strip())
        if m:
            return m.group(1)
    ref = (reference or "").strip()
    return ref if _IS_CELEX.match(ref) else None


def is_corrigendum(celex: str | None) -> bool:
    """A corrigendum, or a later version of a Commission document: an R(NN) suffix. It exists only in
    the languages it concerns (52025PC0435R(01) corrects the Latvian text of a proposal)."""
    return bool(celex) and bool(re.search(r"R\([0-9]{2}\)$", celex))


def pick_language(titles: dict[str, str] | None) -> str | None:
    """English where the document exists in English, else the first language we can read."""
    have = set(titles or ())
    return next((lang for lang in PREFERRED if lang in have), min(have) if have else None)


def language_codes(titles: dict[str, str] | None) -> list[str]:
    """Two-letter codes, the language of the stored title and text first."""
    first = pick_language(titles)
    rest = sorted(LANGUAGES[x] for x in (titles or ()) if x in LANGUAGES and x != first)
    return ([LANGUAGES[first]] if first in LANGUAGES else []) + rest


def one_title(titles: dict[str, str] | None) -> str | None:
    """Cellar's title in the document's language, or nothing: an empty or short string is not a title."""
    lang = pick_language(titles)
    t = " ".join(((titles or {}).get(lang) or "").split()) if lang else ""
    return t[:1000] if len(t) >= MIN_TITLE else None


def one_date(dates: set[str] | None) -> dt.date | None:
    return dt.date.fromisoformat(next(iter(dates))) if dates and len(dates) == 1 else None


def names_its_act(celex: str, txt: str) -> bool:
    """A corrigendum names the act it corrects: "2024/2841", "No 36/2012", "85/374/EEC"."""
    m = _PARTS.match(celex or "")
    if not m:
        return False
    year, num = m.group(2), str(int(m.group(4)))
    flat = re.sub(r"\s+", "", txt or "")
    return any(f"{a}/{b}" in flat for a, b in ((year, num), (num, year), (year[2:], num), (num, year[2:])))


def _words(s: str | None) -> str:
    return " ".join(re.sub(r"[\W_]+", " ", (s or "").casefold()).split())


def carries_title(title: str | None, txt: str) -> bool:
    """The page prints the title Cellar gives the document. For a document with no number to name:
    32011D0402(01)R(02) corrects Parliament's rules on smoking, published under a date, not a number."""
    key = _words(title)[:40]
    return len(key) >= MIN_TITLE and key in _words(txt)


def answered(got) -> bool:
    """Did Cellar answer about this text? A 404, a too-short page and a page about another act are
    answers; a refusal, a timeout or a broken PDF is not, and must never read as 'no text exists'."""
    return not isinstance(got, str) or got.startswith(
        ("http_404", "too_short", "http_300_nodocs", "names_another_act", "no_language"))


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

def _facts(celexes: list[str], ctx) -> dict[str, dict]:
    """What Cellar holds for each CELEX: {"dates": {...}, "titles": {"ENG": "...", ...}}. A CELEX
    missing from the answer is one Cellar does not hold."""
    vals = " ".join(f'"{c}"^^<http://www.w3.org/2001/XMLSchema#string>' for c in celexes)
    req = urllib.request.Request(
        SPARQL, data=urllib.parse.urlencode({"query": _FACTS.format(vals=vals)}).encode(),
        headers={"Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(req, timeout=120, context=ctx) as r:
        data = json.load(r)
    out: dict[str, dict] = {}
    for b in data["results"]["bindings"]:
        x = out.setdefault(b["c"]["value"], {"dates": set(), "titles": {}})
        if "d" in b:
            x["dates"].add(b["d"]["value"][:10])
        if "lang" in b:
            x["titles"][b["lang"]["value"].rsplit("/", 1)[-1]] = b.get("t", {}).get("value") or ""
    return out


def facts_for(celexes: list[str], ctx) -> tuple[dict[str, dict], int]:
    """(facts, CELEX asked in a batch Cellar answered)."""
    found: dict[str, dict] = {}
    reached = 0
    for i in range(0, len(celexes), BATCH):
        part = celexes[i:i + BATCH]
        try:
            found.update(_facts(part, ctx))
            reached += len(part)
        except Exception as e:  # noqa: BLE001
            print(f"[ERROR] Cellar did not answer for {len(part)} documents: {type(e).__name__}: {e}")
        time.sleep(0.3)
    return found, reached


def _fetch_in(celex: str, lang: str, ctx, title: str | None = None) -> tuple[str, str] | str:
    """A corrigendum's page in one language, or a marker saying why not."""
    try:
        req = urllib.request.Request(_laws._cellar_url(celex), headers={
            "Accept": "application/xhtml+xml, text/html", "Accept-Language": lang.lower()})
        with urllib.request.urlopen(req, timeout=45, context=ctx) as r:
            raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        return f"http_{e.code}"
    except Exception as e:  # noqa: BLE001
        return type(e).__name__
    txt = _laws._strip(raw)
    if len(txt) < MIN_CORRIGENDUM:
        return f"too_short_{len(txt)}"
    if not (names_its_act(celex, txt) or carries_title(title, txt)):
        return "names_another_act"
    return _laws._clean_html(raw, txt), txt


def text_for(celex: str, titles: dict[str, str] | None, ctx) -> tuple[str, str] | str:
    if not is_corrigendum(celex):
        return _laws._fetch(celex, ctx)
    lang = pick_language(titles)
    if lang is None:
        return "no_language"
    got = _fetch_in(celex, lang, ctx, (titles or {}).get(lang))
    if isinstance(got, str) and lang == "ENG":
        whole = _laws._fetch(celex, ctx)  # a later version of a proposal is a PDF, like the proposal
        return got if isinstance(whole, str) else whole
    return got


def complete(engine, ctx, since: dt.datetime, apply: bool, limit: int) -> tuple[int, int, dict]:
    """Run the steps. Returns (work that needed Cellar, work Cellar answered, counts)."""
    n = {"celex": 0, "date": 0, "text_from_laws": 0, "text_from_cellar": 0, "title": 0, "languages": 0}
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
    stating = [(r, cand) for r in rows for cand in [stated_celex(r.reference, r.title, r.portal_url)]
               if cand and cand not in taken][:limit]  # the rest wait for the next run
    found, got = facts_for(sorted({cand for _, cand in stating}), ctx)
    work += len(stating)
    reached += len(stating) if got else 0
    for r, cand in stating:
        if cand in found and cand not in taken:
            n["celex"] += store(SET_CELEX, {"rid": r.id, "v": cand})
            taken.add(cand)
    print(f"[INFO] CELEX : {len(rows)} rows without one | {len(stating)} state one | stored {n['celex']} "
          f"| not held by Cellar {len(stating) - n['celex']}")

    # 2. date
    with engine.connect() as c:
        rows = list(c.execute(NO_DATE, scope))
    found, got = facts_for(sorted({r.celex for r in rows}), ctx)
    work += len(rows)
    reached += len(rows) if got else 0
    for r in rows:
        d = one_date((found.get(r.celex) or {}).get("dates"))
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
    found, _ = facts_for(sorted({r.celex for r in rows if is_corrigendum(r.celex)}), ctx)
    why: dict[str, int] = {}
    for r in rows:
        work += 1
        got = text_for(r.celex, (found.get(r.celex) or {}).get("titles"), ctx)
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

    # 4. title, and the languages of a corrigendum
    with engine.connect() as c:
        rows = list(c.execute(NO_TITLE, scope))
        langs = list(c.execute(NO_LANGUAGES, scope))
    found, got = facts_for(sorted({r.celex for r in rows} | {r.celex for r in langs}), ctx)
    work += len(rows) + len(langs)
    reached += (len(rows) + len(langs)) if got else 0
    for r in rows:
        t = one_title((found.get(r.celex) or {}).get("titles"))
        if t:
            n["title"] += store(SET_TITLE, {"rid": r.id, "v": t})
    for r in langs:
        codes = language_codes((found.get(r.celex) or {}).get("titles"))
        if codes and codes != list(r.languages or []):
            n["languages"] += store(SET_LANGUAGES, {"rid": r.id, "v": codes})
    print(f"[INFO] title : {len(rows)} placeholders | stored {n['title']} "
          f"| languages of corrigenda stored {n['languages']}")
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
        misfiled = c.execute(MISFILED_ROWS, {"since": since}).scalar_one()
    if misfiled:
        print(f"[INFO] {misfiled} corrigenda left as they arrived: filed under the act they correct")
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
