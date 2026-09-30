"""
Ingest delegated + implementing acts from the Commission Register of
Delegated Acts (RegDel) Excel export.

Source URLs (no auth, no CSRF):
  https://webgate.ec.europa.eu/regdel/web/delegatedActs/excel?lang=en&filter=...
  https://webgate.ec.europa.eu/regdel/web/implementingActs/excel?lang=en&filter=...

Each row carries: Complete title, CCode (e.g. C(2026)876), Celex number,
Policy area, Leading Service Commission (DG), status, phase, planned
adoption date, basic legislative act (parent law title), empowerment
article.

This wipes the 7 fictitious seed rows that were sitting in secondary_acts
and replaces them with real data.

Run:
    python3.12 backend/scripts/ingest_regdel_acts.py            # dry-run, fetch only
    python3.12 backend/scripts/ingest_regdel_acts.py --apply
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type delegated
    python3.12 backend/scripts/ingest_regdel_acts.py --apply --type implementing
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

# xlrd, not pandas: the export is a legacy .xls and xlrd reads it in ~100 KB, where
# pandas (plus numpy) is ~50 MB in the container for one monthly job. The container had
# neither, so every scheduled run died with ModuleNotFoundError: No module named 'pandas'
# while the script worked on a laptop (28-29 Sep 2026).
import xlrd
import psycopg2

ROOT = Path(__file__).resolve().parents[2]
ENV = ROOT / ".env"
USER_AGENT = "Mozilla/5.0 (compatible; BrubruIngest/1.0) Chrome/151.0.0.0"

REGDEL_BASE = "https://webgate.ec.europa.eu/regdel/web"
EXPORT_FILTER = urllib.parse.quote('{"rowsPerPage":6,"firstRowOffset":0,"language":"en"}')


def get_env(k: str) -> str:
    """The value from the process environment, else from the repo-root .env.

    The environment comes FIRST because it is the only one that exists where this runs:
    the Railway container ships no .env, so a .env-only reader returns "" and the job
    dies on its first line. Three sibling jobs were fixed for this on 29 Sep 2026 and
    this one was missed, because its visible failure was a missing `pandas` and the
    DATABASE_URL fault was hidden behind it. Fixing the import revealed the second fault
    on the very next run. tests/test_scheduled_scripts_read_the_environment.py now
    asserts this for every scheduled script, so the class cannot come back one file at a
    time.
    """
    import os
    value = os.environ.get(k)
    if value:
        return value
    if not ENV.exists():
        return ""
    for line in ENV.read_text().splitlines():
        if line.startswith(f"{k}="):
            return line.split("=", 1)[1].strip()
    return ""


def fetch_excel(act_type: str) -> bytes:
    """Download the Excel export. act_type ∈ {'delegated', 'implementing'}."""
    path = "delegatedActs" if act_type == "delegated" else "implementingActs"
    url = f"{REGDEL_BASE}/{path}/excel?lang=en&filter={EXPORT_FILTER}"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


# Regex helpers for parsing the "Basic legislative act" free-text column
# into a CELEX number.
_BASIC_REGULATION_RE = re.compile(r"Regulation\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_REGULATION_LEGACY_RE = re.compile(r"Regulation\s*\(EU\)(?:\s*No)?\s*(\d{1,4})/(\d{4})", re.IGNORECASE)
_BASIC_DIRECTIVE_RE = re.compile(r"Directive\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)
_BASIC_DIRECTIVE_OLD_RE = re.compile(r"Directive\s*(\d{4})/(\d{1,3})/(?:EU|EC|EEC)", re.IGNORECASE)
_BASIC_DECISION_RE = re.compile(r"Decision\s*\(EU\)\s*(\d{4})/(\d{1,4})", re.IGNORECASE)


def derive_parent_celex(basic_text: Any) -> Optional[str]:
    """Extract a CELEX from the free-text 'Basic legislative act' column."""
    if not isinstance(basic_text, str) or not basic_text.strip():
        return None
    m = _BASIC_REGULATION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}R{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DIRECTIVE_OLD_RE.search(basic_text)
    if m and 1950 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}L{int(m.group(2)):04d}"
    m = _BASIC_DECISION_RE.search(basic_text)
    if m and 2000 <= int(m.group(1)) <= 2099:
        return f"3{m.group(1)}D{int(m.group(2)):04d}"
    m = _BASIC_REGULATION_LEGACY_RE.search(basic_text)
    if m and 1950 <= int(m.group(2)) <= 2099 and "Regulation (EU)" in basic_text:
        # legacy "(EU) No N/YYYY" form
        return f"3{m.group(2)}R{int(m.group(1)):04d}"
    return None


# Every status value the RegDel exports actually use, counted from the live sheets on
# 30 Sep 2026 (delegated: 10 distinct values, implementing: 5). The old map covered six
# keys and everything else fell through a `.get(..., "draft")` default, so 356 acts wore
# a status that was not theirs -- most seriously the 24 delegated acts Parliament or
# Council had OBJECTED to, which were served as 'draft'.
#
# 'Published' -> 'published', corrected 30 Sep 2026 (Victor's call). It had mapped to
# 'adopted', which collapsed the two stages RegDel actually distinguishes:
#
#   Planned -> Adopted -> Published
#
# 'Adopted' means the College has taken the decision; 'Published' means the act is in
# the Official Journal. The gap between them is the window in which the scrutiny clock
# runs and Parliament or Council can still object, and we hold 699 acts sitting in it
# right now (adopted, no CELEX yet, 569 of them with 2026 C-numbers). Mapping both to
# 'adopted' made that word mean nothing and left the enum's 'published' unused since
# migration 038. The correction moves 6,737 rows, so GovClipping is told before it lands.
_STATUS_MAP = {
    "Published": "published",
    "Adoption": "adopted",
    "Adopted": "adopted",
    "Adopted (urgency procedure)": "adopted",
    "Draft": "draft",
    "Empowerment": "draft",
    "Planned": "planned",
    "Objected": "objected",
    "Cancelled": "cancelled",
    "Withdrawn": "withdrawn",
    "On hold": "on_hold",
    "Notified": "notified",
    "Scrutiny finished": "scrutiny_finished",
}

# Statuses seen in an export that this map does not know. Collected rather than
# swallowed: the register can add a value at any time and the old default turned that
# into a silent 'draft'. Reported at the end of the run.
_UNMAPPED_STATUSES: dict[str, int] = {}


def _normalised_title(title: str) -> str:
    """A title stripped of its numbering preamble, for matching one act to itself.

    A planned act reads 'COMMISSION DELEGATED REGULATION (EU) .../... amending X' and the
    same act once published reads 'Commission Delegated Regulation (EU) 2024/3199 of 15
    October 2024 amending X'. Only the tail is stable, so the key is built from that.

    Measured on the live export (30 Sep 2026): 48/48 delegated and 272/274 implementing
    pipeline titles are distinct after this, and 7 collide with an act already held under
    a real C-number -- which is the point, those are skipped.
    """
    t = re.sub(r"\s+", " ", title).strip().lower()
    t = re.sub(r"^commission\s+(delegated|implementing)\s+"
               r"(regulation|decision|directive)\s*", "", t)
    t = re.sub(r"^\(eu\)\s*(no\s*)?[….\d/]*\s*", "", t)
    t = re.sub(r"^of\s+\d{1,2}\s+\w+\s+\d{4}\s*", "", t)
    t = re.sub(r"^(of\s+xxx|…/\.\.\.)\s*", "", t)
    return t.strip()


# Titles too thin to key on, and pipeline rows whose act we already hold under a real
# C-number. Collected and reported rather than silently dropped.
_WEAK_TITLES: List[str] = []
_SHADOWED: List[str] = []


def _blank(value) -> bool:
    """True for an empty cell, whichever reader produced it."""
    if value is None:
        return True
    if isinstance(value, float) and value != value:   # NaN
        return True
    return str(value).strip() == ""


def _read_xls(payload: bytes) -> List[Dict[str, Any]]:
    """Rows of the RegDel .xls export as dicts, keyed by the header row."""
    book = xlrd.open_workbook(file_contents=payload)
    sheet = book.sheet_by_index(0)
    if sheet.nrows == 0:
        return []
    headers = [str(sheet.cell_value(0, c)).strip() for c in range(sheet.ncols)]
    out: List[Dict[str, Any]] = []
    for r in range(1, sheet.nrows):
        out.append({headers[c]: sheet.cell_value(r, c) for c in range(sheet.ncols)})
    return out


def normalise_row(row: Dict[str, Any], act_type: str) -> Optional[Dict[str, Any]]:
    """Convert one Excel row into a secondary_acts record."""
    status_col = "Delegated act status" if act_type == "delegated" else "Implementing act status"
    title = row.get("Complete title")
    ccode = row.get("CCode")
    # xlrd gives '' for an empty cell; a float NaN can still arrive from older exports.
    if _blank(title):
        title = None
    if _blank(ccode):
        ccode = None
    title = title.strip() if isinstance(title, str) else None
    ccode = ccode.strip() if isinstance(ccode, str) else None
    if not title:
        return None
    if not ccode or ccode.lower() == "nan":
        # An act the Commission has ANNOUNCED but not adopted. Until 30 Sep 2026 this
        # returned None and 322 rows -- 207 Planned, 109 Cancelled, 6 On hold -- were
        # discarded, so the register's whole forward pipeline was invisible to us.
        #
        # There is no identifier to key on: a C-number is issued at adoption, the CELEX
        # at publication, and the register's JSON API is CSRF-protected so the Excel
        # export is the only open source. The key is therefore SYNTHETIC, and marked as
        # such so nothing downstream can read it as a Commission code.
        norm = _normalised_title(title)
        if len(norm) < 25:
            # 'Commission Implementing Regulation (*)' carries nothing to key on. A hash
            # of almost-nothing collides with the next almost-nothing.
            _WEAK_TITLES.append(title[:80])
            return None
        digest = hashlib.sha1(f"{act_type}|{norm}".encode("utf-8")).hexdigest()[:16]
        ccode = f"PLANNED:{digest}"
        is_pipeline = True
    else:
        is_pipeline = False

    celex = row.get("Celex number")
    celex = celex.strip() if isinstance(celex, str) else None
    if _blank(celex):
        celex = None

    policy = row.get("Policy area")
    policy_areas = []
    if isinstance(policy, str) and policy.strip():
        policy_areas = [p.strip() for p in policy.split(",") if p.strip()]

    dg = row.get("Leading Service Commission")
    dg = dg.strip() if isinstance(dg, str) and dg.strip() else None

    raw_status = row.get(status_col)
    # 'unknown', never 'draft'. A status we do not recognise is a gap in our mapping,
    # and calling it a draft asserts something about the act that we have not been told.
    # The enum carries 'unknown' precisely so an honest answer is available.
    if raw_status and str(raw_status).strip():
        key = str(raw_status).strip()
        status = _STATUS_MAP.get(key)
        if status is None:
            _UNMAPPED_STATUSES[key] = _UNMAPPED_STATUSES.get(key, 0) + 1
            status = "unknown"
    else:
        status = "unknown"

    parent_celex = derive_parent_celex(row.get("Basic legislative act"))

    # source_url is NOT NULL on the table. Prefer the EUR-Lex CELEX URL when
    # we have a CELEX. Otherwise fall back to the RegDel deep-link by CCode
    # (the public register is the authoritative source for draft / pending
    # acts that haven't yet received a CELEX).
    if celex:
        source_url = f"https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:{celex}"
    else:
        # RegDel uses the CCode without parens in its deep links.
        # Example: C(2026)876 → https://webgate.ec.europa.eu/regdel/#/{type}/{CCODE}
        slug_path = "delegatedActs" if act_type == "delegated" else "implementingActs"
        source_url = f"https://webgate.ec.europa.eu/regdel/#/{slug_path}?lang=en&search={urllib.parse.quote(str(ccode))}"

    planned_period = row.get("Planned adoption date")
    planned_period = planned_period.strip()[:16] if isinstance(planned_period, str) and planned_period.strip() else None

    return {
        "id": str(uuid.uuid4()),
        "act_type": act_type,
        "reference": str(ccode).strip(),
        "title": str(title).strip()[:1000],
        "parent_celex": parent_celex,
        "celex": celex,
        "status": status,
        "proposing_dg": dg,
        "source_url": source_url,
        "policy_areas": policy_areas,
        # The Commission's indicative timing ("Q3 2026"). A PERIOD, never a date: it
        # must not reach adoption_date, which means the day the College adopted the act.
        "planned_adoption_period": planned_period,
        "is_pipeline": is_pipeline,
        "norm_title": _normalised_title(title),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument(
        "--type",
        choices=("delegated", "implementing", "both"),
        default="both",
    )
    ap.add_argument("--limit", type=int, default=None, help="Truncate after N rows (debug)")
    args = ap.parse_args()

    db_url = get_env("DATABASE_URL")
    if not db_url:
        print("[FATAL] DATABASE_URL missing")
        sys.exit(1)

    targets = ("delegated", "implementing") if args.type == "both" else (args.type,)
    all_rows: List[Dict[str, Any]] = []

    for act_type in targets:
        print(f"[INFO] fetching RegDel {act_type} export...")
        bytes_ = fetch_excel(act_type)
        rows = _read_xls(bytes_)
        print(f"  {len(rows)} rows in Excel")
        for row in rows:
            rec = normalise_row(row, act_type)
            if rec:
                all_rows.append(rec)
        if args.limit:
            all_rows = all_rows[: args.limit]
            break

    # A pipeline row whose act we already hold under a real C-number is the SAME act
    # listed twice by the register, once as planned and once as published. 7 of the 322
    # were like that on 30 Sep 2026. The real act wins; keeping both would hand a
    # subscriber one act twice, under two different statuses.
    real_titles = {(r["act_type"], r["norm_title"]) for r in all_rows if not r["is_pipeline"]}
    kept = []
    for r in all_rows:
        if r["is_pipeline"] and (r["act_type"], r["norm_title"]) in real_titles:
            _SHADOWED.append(r["title"][:80])
            continue
        kept.append(r)
    all_rows = kept

    pipeline_n = sum(1 for r in all_rows if r["is_pipeline"])
    print(f"[INFO] {len(all_rows)} records normalised (apply={args.apply}); "
          f"{pipeline_n} announced-but-not-adopted")
    if _SHADOWED:
        print(f"[INFO] {len(_SHADOWED)} announced act(s) skipped: already held under a "
              f"real C-number")
    if _WEAK_TITLES:
        print(f"[INFO] {len(_WEAK_TITLES)} announced act(s) skipped: title too thin to "
              f"identify, e.g. {_WEAK_TITLES[0]!r}")

    if not args.apply:
        for r in all_rows[:5]:
            print(f"  {r['act_type']:13s} {r['reference']:14s} celex={(r['celex'] or '-'):12s} dg={(r['proposing_dg'] or '-'):8s} parent={(r['parent_celex'] or '-'):12s} status={r['status']:10s} policy={r['policy_areas'][:1]}")
        print("[NOTE] dry-run — pass --apply to write to DB")
        return

    conn = psycopg2.connect(db_url)
    cur = conn.cursor()
    # The hand-curated seed rows this script once wiped are long gone: the first run
    # removed them. The wipe itself was REMOVED on 30 Sep 2026 because it had started
    # destroying real acts.
    #
    # It matched on a hard-coded list of ten C-numbers, on the assumption that those
    # codes were invented. They were not invented for long: the Commission has since
    # issued C(2026)1234 and C(2026)2345 to real implementing regulations (amendments to
    # Annexes V and XIV), and the register now exports them. Every run therefore DELETED
    # those two acts and the loop below re-inserted them seconds later with a fresh
    # uuid4 -- so their `id`, the identifier GovClipping uses for incremental sync,
    # changed every single day while the row looked untouched.
    #
    # A cleanup keyed on values someone else allocates is a cleanup with an expiry date.
    # If fixture rows ever need removing again, match them on what makes them fixtures
    # (their fabricated titles), never on an identifier the source controls.

    # Two upsert paths, chosen by whether the act has a CELEX.
    #
    # CELEX is the identity. `reference` (the C(YYYY)NNNN code) is a LABEL the Commission
    # can re-issue for the same act, so conflicting on it lets a second row in for a CELEX
    # we already hold. That produced 783 duplicate pairs once, was cleaned up without
    # changing this line, and produced 80 more by 30 Sep 2026. Migration 258 adds the
    # partial unique index that backs the ON CONFLICT (celex) target.
    #
    # 731 acts have no CELEX yet (adopted but not published, or draft). For those the
    # C-number is the only stable handle we have, so they keep the reference path.
    #
    # Every updated column is wrapped in COALESCE(EXCLUDED.x, secondary_acts.x): a later
    # export with an empty cell must not blank a value we already hold. The old statement
    # assigned EXCLUDED.celex directly, so one empty cell would have erased a good CELEX.
    SET_CLAUSE = """
                  title        = COALESCE(EXCLUDED.title, secondary_acts.title),
                  parent_celex = COALESCE(EXCLUDED.parent_celex, secondary_acts.parent_celex),
                  status       = EXCLUDED.status,
                  proposing_dg = COALESCE(EXCLUDED.proposing_dg, secondary_acts.proposing_dg),
                  source_url   = COALESCE(EXCLUDED.source_url, secondary_acts.source_url),
                  policy_areas = COALESCE(EXCLUDED.policy_areas, secondary_acts.policy_areas),
                  planned_adoption_period = EXCLUDED.planned_adoption_period,
                  last_updated = NOW()
    """

    INSERT_HEAD = """
                INSERT INTO secondary_acts
                  (id, act_type, reference, title, parent_celex, celex, status,
                   proposing_dg, source_url, policy_areas, planned_adoption_period,
                   scraped_at, first_seen, last_updated)
                VALUES
                  (%(id)s, %(act_type)s, %(reference)s, %(title)s, %(parent_celex)s,
                   %(celex)s, %(status)s, %(proposing_dg)s, %(source_url)s, %(policy_areas)s,
                   %(planned_adoption_period)s, NOW(), NOW(), NOW())
    """

    # On the CELEX path `reference` is deliberately NOT overwritten. When RegDel hands us
    # a different C-number for an act we already hold, we cannot tell from the export
    # which one is right -- and in 3 of the 7 cases found on 30 Sep the number we already
    # had contradicted its own adoption year, so the incoming one was the better value.
    # Keeping both, one in `reference` and the other in merged_from, leaves the evidence
    # for a human instead of silently picking. The @> guard stops the same alternative
    # being appended on every daily run.
    SQL_BY_CELEX = INSERT_HEAD + """
                ON CONFLICT (celex) WHERE celex IS NOT NULL AND celex <> ''
                DO UPDATE SET
    """ + SET_CLAUSE + """,
                  merged_from = CASE
                    WHEN secondary_acts.reference IS DISTINCT FROM EXCLUDED.reference
                     AND NOT (COALESCE(secondary_acts.merged_from, '[]'::jsonb)
                              @> jsonb_build_array(jsonb_build_object(
                                   'reference', EXCLUDED.reference)))
                    THEN COALESCE(secondary_acts.merged_from, '[]'::jsonb)
                         || jsonb_build_array(jsonb_build_object(
                              'reference', EXCLUDED.reference,
                              'source', 'regdel_alternative_ccode',
                              'seen', NOW()::text))
                    ELSE secondary_acts.merged_from END
                RETURNING (xmax = 0) AS was_inserted
    """

    SQL_BY_REFERENCE = INSERT_HEAD + """
                ON CONFLICT (reference) DO UPDATE SET
    """ + SET_CLAUSE + """,
                  celex = COALESCE(EXCLUDED.celex, secondary_acts.celex)
                RETURNING (xmax = 0) AS was_inserted
    """

    # Same as above but the CELEX WE hold wins. Used only on the fallback path, where the
    # export's CELEX has already been shown to disagree with a row we corrected against
    # Cellar. COALESCE order is reversed on purpose: ours first, theirs only if we have none.
    SQL_BY_REFERENCE_KEEP_CELEX = INSERT_HEAD + """
                ON CONFLICT (reference) DO UPDATE SET
    """ + SET_CLAUSE + """,
                  celex = COALESCE(secondary_acts.celex, EXCLUDED.celex)
                RETURNING (xmax = 0) AS was_inserted
    """

    # Counted from what the database RETURNS, not from how many statements were sent.
    # The old loop incremented `inserted` once per attempt, so an update and an insert
    # were indistinguishable and the total was really "rows tried".
    inserted = updated = errors = celex_kept = 0
    for n, r in enumerate(all_rows, 1):
        # SAVEPOINT per row. conn.rollback() discards every uncommitted row in the
        # batch, not just the one that failed, so a single bad record used to throw
        # away up to 200 good ones silently. Same fix as ingest_transparency_meetings.
        try:
            cur.execute("SAVEPOINT one_row")
            try:
                cur.execute(SQL_BY_CELEX if r.get("celex") else SQL_BY_REFERENCE, r)
            except psycopg2.errors.UniqueViolation:
                # The CELEX path found no row to update and tried to INSERT, but this
                # act's C-number is already held by a row carrying a DIFFERENT CELEX.
                # That happens when we have corrected a CELEX the register still gets
                # wrong: C(2015)9013 is Regulation (EU) 2016/451, which RegDel exports
                # as 32015R0451 -- a CELEX that does not exist in Cellar at all.
                #
                # Fall back to matching on the C-number, and let the CELEX we already
                # hold win. Our value is the one checked against Cellar; re-applying the
                # export's would silently undo the correction on the next daily run.
                cur.execute("ROLLBACK TO SAVEPOINT one_row")
                cur.execute(SQL_BY_REFERENCE_KEEP_CELEX, r)
                celex_kept += 1
            row = cur.fetchone()
            if row and row[0]:
                inserted += 1
            else:
                updated += 1
            cur.execute("RELEASE SAVEPOINT one_row")
        except Exception as exc:
            cur.execute("ROLLBACK TO SAVEPOINT one_row")
            print(f"  [ERR] {r['reference']}: {exc}")
            errors += 1
        # Commit on rows PROCESSED, not on rows inserted: after the first full run
        # almost everything is an update, so an `inserted % 200` gate would hold the
        # whole run in one transaction.
        if n % 200 == 0:
            conn.commit()
    conn.commit()
    conn.close()

    print(f"[DONE] inserted={inserted} updated={updated} errors={errors} "
          f"of {len(all_rows)} record(s)")
    if celex_kept:
        print(f"[INFO] {celex_kept} act(s) kept the CELEX we hold over the one the "
              f"register exports (ours is the one verified against Cellar)")

    if _UNMAPPED_STATUSES:
        print("[WARN] status value(s) the register uses that we do not map; "
              "stored as 'unknown':")
        for k, v in sorted(_UNMAPPED_STATUSES.items(), key=lambda kv: -kv[1]):
            print(f"        {k!r}: {v} act(s)")
        print("        add them to _STATUS_MAP and to secondary_act_status_enum")

    # Three states, never two. A run that stored nothing is not a success: the RegDel
    # export can return an empty or restructured sheet, and a silent green would hide
    # it for weeks (feedback_a_green_signal_from_a_check_that_never_looked).
    if not all_rows:
        print("[FATAL] the RegDel export yielded no usable rows")
        return 1
    if errors and inserted + updated == 0:
        print(f"[FATAL] every row failed ({errors} error(s))")
        return 1
    if errors:
        print(f"[DEGRADED] {errors} row(s) rejected, {inserted + updated} stored")
        return 0
    return 0


if __name__ == "__main__":
    # sys.exit(main()), not main(): a script that returns 1 but exits 0 is
    # a failure the scheduler records as a success.
    sys.exit(main())
