"""
Populate `ft_participants` from the participant JSON already stored on
`ft_funded_projects.coordinator_name`.

Migration 075 created this table and seeded nothing, so the Tenderator's
"organisations like yours that have won similar calls" panel has had no data
since May 2026. The intended source is the F&T Participant Register, which is
WAF-blocked, and that is where the work stalled.

It turns out we already hold the data. About 26% of ft_funded_projects rows
(28,125 of 109,636) carry the raw F&T Portal participant JSON in
coordinator_name rather than a plain name -- the same rows the Tenderator has
to defend against with `_clean_coordinator` so cards do not render JSON. That
payload contains what the register would have given us:

    [{"role":"coordinator","pic":910827867,
      "legalName":"INSTITUTO NACIONAL DE ESTADISTICA",
      "postalAddress":{...},"country":"ES", ...}]

So this is a re-read of data we own, not a scrape.

DELIBERATE LIMIT: rows whose coordinator_name is a plain string are SKIPPED.
`ft_participants.pic` is NOT NULL, and a participant register keyed on a
synthetic identifier in a column named `pic` would be a fabrication -- the
number would look like a Participant Identification Code and match nothing.
An organisation we cannot key correctly is better absent than wrong.

Run:
    python3.12 backend/scripts/derive_ft_participants.py            # dry run
    python3.12 backend/scripts/derive_ft_participants.py --apply
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, Iterable, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from core.database import SessionLocal  # noqa: E402
from services.tenders.country_codes import normalise_country  # noqa: E402

PORTAL_ORG = (
    "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/"
    "how-to-participate/participant-register/search"
)


# The stored payload is TRUNCATED. Whatever wrote these rows capped the value
# at 300 characters, mid-string, so json.loads raises "Unterminated string" on
# every one of the 28,125 and a parse-based reader recovers nothing.
#
# What survives is the head of the first participant, which is the part we
# want: "pic" and "legalName" are emitted before the postal address that gets
# cut off. So read those two with a regex and take everything else from columns
# that are not truncated (coordinator_country). Anything past the cut is gone
# and is left null rather than guessed.
_PIC = re.compile(r'"pic"\s*:\s*"?(\d{6,12})"?')
_LEGAL_NAME = re.compile(r'"legalName"\s*:\s*"((?:[^"\\]|\\.)*)"')
_SHORT_NAME = re.compile(r'"shortName"\s*:\s*"((?:[^"\\]|\\.)*)"')
# The country sits inside postalAddress.countryCode.abbreviation, which is
# usually PAST the 300-character cut -- coordinator_country is null on all
# 28,125 of these rows, so there is no second source. Read it when it survived,
# leave it null when it did not. A participant register with an honest gap
# beats one where every organisation is confidently in the wrong country.
_COUNTRY_ABBR = re.compile(r'"abbreviation"\s*:\s*"([A-Za-z]{2,3})"')


def _unescape(value: str | None) -> str | None:
    """Decode JSON string escapes in a regex-captured fragment.

    The capture is raw source, so a name arrives as MINISTERE DE L\\u0027INTERIEUR.
    Re-wrapping it in quotes and letting json decode it turns that back into the
    apostrophe it always was.
    """
    if value is None:
        return None
    try:
        return json.loads(f'"{value}"')
    except (ValueError, TypeError):
        return value


def participants_in(raw: Optional[str]) -> Iterable[Dict[str, Any]]:
    """Yield the participant recoverable from a coordinator_name payload.

    A plain name yields nothing: there is no PIC to key it on. A truncated
    payload yields at most the first (coordinator) participant, which is the
    only one whose fields survived the cut.
    """
    if not raw:
        return
    text_value = raw.strip()
    if not (text_value.startswith("[{") or text_value.startswith("{")):
        return

    # Try a real parse first: some payloads may be short enough to be intact,
    # and a full parse gives more fields than the regex fallback.
    try:
        payload = json.loads(text_value)
        entries = payload if isinstance(payload, list) else [payload]
        found = False
        for entry in entries:
            if isinstance(entry, dict) and entry.get("pic") and entry.get("legalName"):
                found = True
                yield entry
        if found:
            return
    except (ValueError, TypeError):
        pass

    pic_match = _PIC.search(text_value)
    name_match = _LEGAL_NAME.search(text_value)
    if not (pic_match and name_match):
        return
    short = _SHORT_NAME.search(text_value)
    country_match = _COUNTRY_ABBR.search(text_value)
    yield {
        "pic": pic_match.group(1),
        "legalName": _unescape(name_match.group(1)),
        "shortName": _unescape(short.group(1)) if short else None,
        "country": country_match.group(1) if country_match else None,
        "_truncated": True,
    }


def country_of(entry: Dict[str, Any]) -> Optional[str]:
    """Best available country for a participant, validated."""
    for candidate in (
        entry.get("country"),
        (entry.get("postalAddress") or {}).get("country")
        if isinstance(entry.get("postalAddress"), dict) else None,
    ):
        resolved = normalise_country(candidate)
        if resolved:
            return resolved
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="write to ft_participants")
    ap.add_argument("--limit", type=int, default=None, help="cap source rows (debugging)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        sql = (
            "SELECT coordinator_name, coordinator_country FROM ft_funded_projects "
            "WHERE is_test = FALSE AND (coordinator_name LIKE '[{%' OR coordinator_name LIKE '{%')"
        )
        if args.limit:
            sql += f" LIMIT {int(args.limit)}"
        rows = db.execute(text(sql)).fetchall()
        print(f"[source] {len(rows)} project rows carry participant JSON")

        # pic -> merged record. project_count is how many funded projects this
        # organisation appears on, which is the number the drawer wants.
        by_pic: Dict[str, Dict[str, Any]] = {}
        counts: Dict[str, int] = defaultdict(int)

        for row in rows:
            for entry in participants_in(row.coordinator_name):
                pic = str(entry["pic"]).strip()
                if not pic:
                    continue
                counts[pic] += 1
                record = by_pic.setdefault(pic, {
                    "pic": pic,
                    "legal_name": (entry.get("legalName") or "").strip(),
                    "short_name": (entry.get("shortName") or None),
                    "country": None,
                    "org_type": entry.get("organisationType") or entry.get("orgType"),
                    "vat": entry.get("vatNumber") or entry.get("vat"),
                    "address": None,
                    "website": entry.get("website") or None,
                    "source_url": PORTAL_ORG,
                })
                if not record["country"]:
                    record["country"] = country_of(entry) or normalise_country(row.coordinator_country)
                if not record["address"]:
                    postal = entry.get("postalAddress")
                    if isinstance(postal, dict):
                        street, city = postal.get("street"), postal.get("city")
                        record["address"] = ", ".join(p for p in (street, city) if p) or None

        for pic, record in by_pic.items():
            record["project_count"] = counts[pic]

        print(f"[derived] {len(by_pic)} distinct organisations with a real PIC")
        top = sorted(by_pic.values(), key=lambda r: -r["project_count"])[:5]
        for record in top:
            print(f"  {record['project_count']:>5} projects  {record['country'] or '--'}  {record['legal_name'][:60]}")

        if not args.apply:
            print("\n[dry run] nothing written. Re-run with --apply.")
            return 0

        written = 0
        for record in by_pic.values():
            db.execute(text(
                """
                INSERT INTO ft_participants
                    (pic, legal_name, short_name, country, org_type, vat, address,
                     website, project_count, source_url, is_test, last_updated, created_at)
                VALUES (:pic, :legal_name, :short_name, :country, :org_type, :vat,
                        :address, :website, :project_count, :source_url, FALSE, now(), now())
                ON CONFLICT (pic) DO UPDATE SET
                    legal_name = EXCLUDED.legal_name,
                    short_name = COALESCE(EXCLUDED.short_name, ft_participants.short_name),
                    country = COALESCE(EXCLUDED.country, ft_participants.country),
                    org_type = COALESCE(EXCLUDED.org_type, ft_participants.org_type),
                    vat = COALESCE(EXCLUDED.vat, ft_participants.vat),
                    address = COALESCE(EXCLUDED.address, ft_participants.address),
                    website = COALESCE(EXCLUDED.website, ft_participants.website),
                    project_count = EXCLUDED.project_count,
                    last_updated = now()
                """
            ), record)
            written += 1
        db.commit()
        print(f"\n[applied] {written} organisations upserted into ft_participants")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
