"""Tag every requirement with who it binds, and backfill deadlines already in its text.

Two deterministic enrichments, no model calls.

1. ADDRESSEE
   EU legal texts mix obligations on companies with obligations on Member
   States, the Commission, producer responsibility organisations and online
   platform providers. The corpus did not record which, so:
     * the gap analyser reported that a company had a compliance gap on
       "Member States shall bring into force the laws necessary to comply with
       this Directive" -- 5 of 6 not_applicable cases in the gold set were
       wrong this way;
     * and Member-State duties are 85.5% 'critical', ABOVE the corpus average,
       so the severity signal actively points the wrong way.
   The addressee is taken from the grammatical subject the requirement opens
   with. Anything that does not open with another actor stays
   'economic_operator', which is both the default and the overwhelming
   majority, so a mis-parse degrades to today's behaviour rather than
   inventing an exemption.

2. DEADLINE
   Only 61 of 2,691 requirements carried a date in the `deadline` column, yet
   hundreds state one in their text. Deadlines are the most actionable field
   in a compliance report and the action-plan timeline was empty by
   construction. Extracted only where the date is CUED as an obligation date
   ("by", "from", "no later than", "not later than", "before", "with effect
   from"). Dates that merely identify a version of a text -- "the combined
   nomenclature as in force on 28 June 2024" -- are deliberately not matched:
   a wrong deadline is worse than a missing one.

Usage:
  python3.12 -m scripts.enrich_requirement_metadata --dry-run
  python3.12 -m scripts.enrich_requirement_metadata --apply
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import date
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from dotenv import load_dotenv

load_dotenv(project_root / ".env")

import psycopg2
import psycopg2.extras

MONTHS = {m: i + 1 for i, m in enumerate(
    ["January", "February", "March", "April", "May", "June", "July",
     "August", "September", "October", "November", "December"])}

# Ordered: first match wins, so the most specific actor is checked first.
#
# The second pass (10 Aug 2026) widened these after an audit found 140
# requirements still tagged 'economic_operator' while plainly binding someone
# else. The first pass only recognised one phrasing per actor, and EU drafting
# uses several: "Each Member State shall", "The Member States shall", a named
# agency as bare subject ("EBA shall establish..."), or the definite article
# alone ("The Office shall be tasked with..."). Every one of those was being
# put to a company as a compliance obligation, which is how a FinTech startup
# got measured against "ECB shall calculate the baseline amount of a sanction".
#
# Checked against the corpus before widening: there is no requirement opening
# "The Board", so `the (agency|office)` cannot capture a company's own board or
# office. "The authority responsible for..." is a national body either way.
ADDRESSEE_PATTERNS = [
    ("member_state",       r"^\s*(each |the )?member states?\b"),
    # "Commission" without the article must be followed by an auxiliary before
    # it counts as the institution. Two traps in the corpus otherwise:
    # "Commission Regulation (EC) No 1275/2008 ... should no longer apply",
    # which is a citation, and "Commission independent annual audits at own
    # expense ...", where commission is a VERB and the duty is the company's.
    # Mis-tagging that second one would excuse a real audit obligation.
    ("commission",         r"^\s*the commission\b"),
    ("commission",         r"^\s*commission (services|shall|must|should|may|is|are|has|have|will)\b"),
    ("pro",                r"^\s*producer responsibility organisations?\b"),
    ("online_platform",    r"^\s*providers of online platforms\b"),
    ("fulfilment_service", r"^\s*fulfilment service providers\b"),
    # Named EU agencies as a bare subject. Kept as an explicit list rather than
    # a catch-all acronym rule so a company acronym can never be swept up.
    ("eu_agency",          r"^\s*(esma|eba|eiopa|ecb|ema|efsa|echa|easa|acer|enisa|eu-osha|"
                           r"eurojust|europol|frontex|cedefop|eea|efca|emsa|era|eu-lisa)\b"),
    ("eu_agency",          r"^\s*the (agency|office|centre)\b"),
    ("national_authority", r"^\s*(the )?((competent|supervisory|regulatory) (national )?authorit(y|ies)|"
                           r"national competent authorit(y|ies)|authority responsible)\b"),
    ("notified_body",      r"^\s*(the )?notified bod(y|ies)\b"),
]

# A date only counts as a deadline when something marks it as one.
DEADLINE_RE = re.compile(
    r"\b(?:by|from|as from|with effect from|before|no later than|not later than|"
    r"at the latest by)\s+(\d{1,2})\s+("
    + "|".join(MONTHS) + r")\s+(\d{4})\b",
    re.IGNORECASE,
)
# Explicitly NOT a deadline: version markers and adoption dates.
EXCLUDE_RE = re.compile(
    r"\b(as in force on|in the version in force on|adopted on|of the european parliament and of the council of)\b",
    re.IGNORECASE,
)


def classify_addressee(text: str) -> str:
    t = (text or "").lstrip()
    for name, pattern in ADDRESSEE_PATTERNS:
        if re.match(pattern, t, re.IGNORECASE):
            return name
    return "economic_operator"


def extract_deadline(text: str):
    """Return the EARLIEST cued date in the text, or None.

    Earliest, because a requirement that mentions several dates is binding from
    the first of them; taking the latest would flatter the reader.
    """
    if not text:
        return None
    found = []
    for m in DEADLINE_RE.finditer(text):
        window = text[max(0, m.start() - 60):m.start()]
        if EXCLUDE_RE.search(window):
            continue
        day, month, year = int(m.group(1)), MONTHS[m.group(2).capitalize()], int(m.group(3))
        try:
            found.append(date(year, month, day))
        except ValueError:
            continue
    return min(found) if found else None


def connect():
    url = os.environ.get("DATABASE_URL") or ""
    return psycopg2.connect(url.replace(":5432/", ":6543/"), connect_timeout=25)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--samples", type=int, default=6)
    args = ap.parse_args()
    apply = args.apply and not args.dry_run

    conn = connect()
    cur = conn.cursor(cursor_factory=psycopg2.extras.DictCursor)
    cur.execute("""SELECT id, requirement_text, deadline, criticality, extra_metadata
                     FROM law_requirements ORDER BY id""")
    rows = cur.fetchall()

    addressee_updates, deadline_updates = [], []
    tally = Counter()
    samples = {"deadline": [], "addressee": []}

    for r in rows:
        addressee = classify_addressee(r["requirement_text"])
        tally[addressee] += 1
        meta = r["extra_metadata"] or {}
        if meta.get("addressee") != addressee:
            addressee_updates.append((r["id"], addressee))
            if addressee != "economic_operator" and len(samples["addressee"]) < args.samples:
                samples["addressee"].append((r["id"], addressee, r["requirement_text"][:88]))

        if r["deadline"] is None:
            d = extract_deadline(r["requirement_text"])
            if d:
                deadline_updates.append((r["id"], d))
                if len(samples["deadline"]) < args.samples:
                    m = DEADLINE_RE.search(r["requirement_text"])
                    samples["deadline"].append((r["id"], d.isoformat(),
                                                (m.group(0) if m else "")[:60]))

    print(f"{len(rows)} requirements scanned\n")
    print("ADDRESSEE distribution")
    for k, v in tally.most_common():
        print(f"  {k:<20} {v:>5}  ({100*v/len(rows):4.1f}%)")
    print(f"  -> {len(addressee_updates)} rows to tag")
    print("\n  samples of non-company obligations:")
    for rid, a, txt in samples["addressee"]:
        print(f"    {rid} [{a}] {txt}...")

    print(f"\nDEADLINE backfill")
    have = sum(1 for r in rows if r["deadline"] is not None)
    print(f"  currently set : {have} / {len(rows)}  ({100*have/len(rows):.1f}%)")
    print(f"  extractable   : {len(deadline_updates)}")
    print(f"  after backfill: {have + len(deadline_updates)} "
          f"({100*(have+len(deadline_updates))/len(rows):.1f}%)")
    print("\n  samples (id, extracted date, matched phrase):")
    for rid, d, phrase in samples["deadline"]:
        print(f"    {rid}  {d}  \"{phrase}\"")

    if not apply:
        conn.rollback(); cur.close(); conn.close()
        print("\n[DRY-RUN] nothing written. Re-run with --apply")
        return 0

    for rid, addressee in addressee_updates:
        cur.execute("""UPDATE law_requirements
                          SET extra_metadata = COALESCE(extra_metadata, '{}'::jsonb)
                                               || jsonb_build_object('addressee', %s)
                        WHERE id = %s""", (addressee, rid))
    for rid, d in deadline_updates:
        cur.execute("""UPDATE law_requirements
                          SET deadline = %s,
                              extra_metadata = COALESCE(extra_metadata, '{}'::jsonb)
                                               || jsonb_build_object('deadline_source', 'extracted_from_text')
                        WHERE id = %s""", (d, rid))
    conn.commit()

    cur.execute("""SELECT extra_metadata->>'addressee' AS a, count(*),
                          count(*) FILTER (WHERE deadline IS NOT NULL) AS with_deadline
                     FROM law_requirements GROUP BY 1 ORDER BY 2 DESC""")
    print(f"\n[OK] tagged {len(addressee_updates)}, backfilled {len(deadline_updates)} deadlines")
    for a, n, wd in cur.fetchall():
        print(f"  {str(a):<20} {n:>5} rows, {wd:>4} with a deadline")
    cur.close(); conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
