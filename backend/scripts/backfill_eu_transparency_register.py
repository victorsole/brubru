"""
Backfill ``eu_transparency_register`` from the daily TR XML export.

Source: https://transparency-register.europa.eu/odplastorganisationxml_en
~17,247 active interest representatives. Refreshed daily.

The XML is ~110 MB. We stream-parse it via lxml.iterparse to keep
memory bounded, then UPSERT each ``<interestRepresentative>`` into the
table. Multi-valued fields (interests, levelsOfInterest) are flattened
to TEXT[]. Free-text fields (goals, EULegislativeProposals,
communicationActivities, complementaryInformation, structure.*) are
composed into a single body_html / body_text per row.

Run:
    python3.12 backend/scripts/backfill_eu_transparency_register.py            # dry-run, 5 rows
    python3.12 backend/scripts/backfill_eu_transparency_register.py --apply
    python3.12 backend/scripts/backfill_eu_transparency_register.py --apply --source /tmp/tr.xml  # use cached download
"""

from __future__ import annotations

import argparse
import io
import re
import sys
import urllib.request as ureq
try:
    from lxml import etree as ET  # tolerant parser; handles invalid char refs
    _USE_LXML = True
except ImportError:  # pragma: no cover
    import xml.etree.ElementTree as ET  # type: ignore
    _USE_LXML = False
from datetime import datetime
from html import escape as html_escape
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _specialised_helpers import ChunkedDb  # noqa: E402

SOURCE_URL = "https://transparency-register.europa.eu/odplastorganisationxml_en"
PUBLIC_URL_TPL = "https://transparency-register.europa.eu/search-detail_en?id={code}"
NS = "http://intragate.ec.europa.eu/transparencyregister/odp"
MIN_BODY_LEN = 200
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"


def fetch_xml(url: str = SOURCE_URL, dest: Path = Path("/tmp/tr.xml")) -> Path:
    if dest.exists() and dest.stat().st_size > 50_000_000:
        print(f"[INFO] Using cached {dest} ({dest.stat().st_size:,} bytes)", flush=True)
        return dest
    print(f"[INFO] Downloading {url}...", flush=True)
    req = ureq.Request(url, headers={"User-Agent": UA, "Accept": "application/xml"})
    with ureq.urlopen(req, timeout=300) as r, open(dest, "wb") as out:
        while True:
            chunk = r.read(1024 * 1024)
            if not chunk:
                break
            out.write(chunk)
    print(f"[INFO] Downloaded {dest.stat().st_size:,} bytes", flush=True)
    return dest


# ─────────────────────── XML helpers ─────────────────────────────────────


def text_of(parent, *path) -> Optional[str]:
    """Walk a / b / c (skipping namespace) returning the leaf text or None."""
    cur = parent
    for tag in path:
        if cur is None:
            return None
        # Try namespaced and bare
        found = None
        for child in cur:
            t = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if t == tag:
                found = child
                break
        cur = found
    if cur is None:
        return None
    txt = (cur.text or "").strip()
    return txt or None


def texts_of_all(parent, *path) -> list[str]:
    """Return a list of leaf texts at the given path. The last segment can
    repeat (e.g. interests/interest/name has multiple <interest> siblings)."""
    if not parent:
        return []
    cur_list = [parent]
    for tag in path[:-1]:
        next_list = []
        for c in cur_list:
            for child in c:
                t = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                if t == tag:
                    next_list.append(child)
        cur_list = next_list
    leaves = []
    last = path[-1]
    for c in cur_list:
        for child in c:
            t = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            if t == last:
                txt = (child.text or "").strip()
                if txt:
                    leaves.append(txt)
    return leaves


def parse_iso(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    s = s.strip()
    if not s:
        return None
    try:
        # Strip 'Z' / millisecond / offset; psycopg2 handles ISO timestamp strings
        return s
    except Exception:
        return None


def parse_date(s: Optional[str]) -> Optional[str]:
    if not s:
        return None
    m = re.match(r"^(\d{4}-\d{2}-\d{2})", s)
    return m.group(1) if m else None


def to_int(s: Optional[str]) -> Optional[int]:
    if not s:
        return None
    try:
        return int(float(s))
    except (TypeError, ValueError):
        return None


def to_num(s: Optional[str]) -> Optional[float]:
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None


# ─────────────────────── Row builder ─────────────────────────────────────


_HTML_FIELDS_ORDER = [
    ("Goals", "goals"),
    ("EU legislative proposals", "eu_legislative_proposals"),
    ("Communication activities", "communication_activities"),
    ("Intergroup activities", "intergroup_activities"),
    ("Information about members", "info_members"),
    ("Member of", "is_member_of"),
    ("Organisation members", "organisation_members"),
    ("Interest represented", "interest_represented"),
    ("Complementary information", "complementary_info"),
]


def compose_body(record: dict) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Build body_html / body_text / body_source from the free-text fields."""
    sections_html = []
    sections_text = []
    for label, key in _HTML_FIELDS_ORDER:
        val = (record.get(key) or "").strip()
        if not val:
            continue
        sections_html.append(
            f"<section><h2>{html_escape(label)}</h2><p>{html_escape(val).replace(chr(10), '<br/>')}</p></section>"
        )
        sections_text.append(f"{label}\n\n{val}")
    if not sections_html:
        return None, None, None
    return (
        f"<article>{''.join(sections_html)}</article>",
        "\n\n".join(sections_text),
        "tr_composed",
    )


def build_record(rep: ET.Element) -> dict:
    """Convert an <interestRepresentative> element to a dict matching the
    eu_transparency_register column set."""
    code = text_of(rep, "identificationCode")

    # Phones (head office + EU office)
    head_phone_indic = text_of(rep, "headOffice", "phone", "indicPhone")
    head_phone_num = text_of(rep, "headOffice", "phone", "phoneNumber")
    head_phone = (f"+{head_phone_indic} {head_phone_num}".strip()
                  if head_phone_indic or head_phone_num else None)
    eu_phone_indic = text_of(rep, "EUOffice", "phone", "indicPhone")
    eu_phone_num = text_of(rep, "EUOffice", "phone", "phoneNumber")
    eu_phone = (f"+{eu_phone_indic} {eu_phone_num}".strip()
                if eu_phone_indic or eu_phone_num else None)

    # Multi-valued fields
    levels = texts_of_all(rep, "levelsOfInterest", "levelOfInterest", "levelOfInterest")
    interests = texts_of_all(rep, "interests", "interest", "name")

    # Financial — closed year
    fin_start = parse_date(text_of(rep, "financialData", "closedYear", "startDate"))
    fin_end = parse_date(text_of(rep, "financialData", "closedYear", "endDate"))
    costs_min = to_num(text_of(rep, "financialData", "closedYear", "costs", "range", "min"))
    costs_max = to_num(text_of(rep, "financialData", "closedYear", "costs", "range", "max"))
    grants_total = to_num(text_of(rep, "financialData", "closedYear", "grants", "total"))
    intermediaries_costs = to_num(text_of(rep, "financialData", "closedYear", "intermediaries", "totalCosts"))

    new_org_str = text_of(rep, "financialData", "newOrganisation")
    new_org = (new_org_str.lower() == "true") if new_org_str else None

    record = {
        "identification_code": code,
        "registration_date": parse_iso(text_of(rep, "registrationDate")),
        "last_update_date": parse_iso(text_of(rep, "lastUpdateDate")),

        "original_name": text_of(rep, "name", "originalName"),
        "acronym": text_of(rep, "acronym"),
        "entity_form": text_of(rep, "entityForm"),
        "website_url": text_of(rep, "webSiteURL"),
        "registration_category": text_of(rep, "registrationCategory"),

        "head_office_address": text_of(rep, "headOffice", "address"),
        "head_office_post_code": text_of(rep, "headOffice", "postCode"),
        "head_office_city": text_of(rep, "headOffice", "city"),
        "head_office_country": text_of(rep, "headOffice", "country"),
        "head_office_phone": head_phone,

        "eu_office_address": text_of(rep, "EUOffice", "address"),
        "eu_office_post_code": text_of(rep, "EUOffice", "postCode"),
        "eu_office_city": text_of(rep, "EUOffice", "city"),
        "eu_office_country": text_of(rep, "EUOffice", "country"),
        "eu_office_phone": eu_phone,

        "goals": text_of(rep, "goals"),
        "eu_legislative_proposals": text_of(rep, "EULegislativeProposals"),
        "communication_activities": text_of(rep, "communicationActivities"),
        "intergroup_activities": text_of(rep, "interOrUnofficalGroupings"),
        "info_members": text_of(rep, "members", "infoMembers"),
        "is_member_of": text_of(rep, "structure", "isMemberOf"),
        "organisation_members": text_of(rep, "structure", "organisationMembers"),
        "interest_represented": text_of(rep, "interestRepresented"),
        "complementary_info": text_of(rep, "financialData", "complementaryInformation"),

        "members_100_percent": to_int(text_of(rep, "members", "members100Percent")),
        "members_50_percent": to_int(text_of(rep, "members", "members50Percent")),
        "members_total": to_num(text_of(rep, "members", "members")),
        "members_fte": to_num(text_of(rep, "members", "membersFTE")),
        "ep_accredited_number": to_int(text_of(rep, "EPAccreditedNumber")),

        "financial_year_start": fin_start,
        "financial_year_end": fin_end,
        "costs_min": costs_min,
        "costs_max": costs_max,
        "grants_total": grants_total,
        "intermediaries_costs": intermediaries_costs,
        "new_organisation": new_org,

        "levels_of_interest": levels,
        "interests": interests,

        "public_url": PUBLIC_URL_TPL.format(code=code) if code else None,
    }

    # Compose body
    body_html, body_text, body_source = compose_body(record)
    record["has_body"] = bool(body_text and len(body_text) >= MIN_BODY_LEN)
    record["body_html"] = body_html if record["has_body"] else None
    record["body_text"] = body_text if record["has_body"] else None
    record["body_source"] = body_source if record["has_body"] else None

    return record


# ─────────────────────── UPSERT ──────────────────────────────────────────


UPSERT_SQL = """
INSERT INTO eu_transparency_register (
    identification_code, registration_date, last_update_date,
    original_name, acronym, entity_form, website_url, registration_category,
    head_office_address, head_office_post_code, head_office_city, head_office_country, head_office_phone,
    eu_office_address, eu_office_post_code, eu_office_city, eu_office_country, eu_office_phone,
    goals, eu_legislative_proposals, communication_activities, intergroup_activities,
    info_members, is_member_of, organisation_members, interest_represented, complementary_info,
    members_100_percent, members_50_percent, members_total, members_fte, ep_accredited_number,
    financial_year_start, financial_year_end, costs_min, costs_max, grants_total,
    intermediaries_costs, new_organisation,
    levels_of_interest, interests,
    has_body, body_html, body_text, body_source,
    public_url, fetched_at, updated_at
) VALUES (
    %(identification_code)s, %(registration_date)s, %(last_update_date)s,
    %(original_name)s, %(acronym)s, %(entity_form)s, %(website_url)s, %(registration_category)s,
    %(head_office_address)s, %(head_office_post_code)s, %(head_office_city)s, %(head_office_country)s, %(head_office_phone)s,
    %(eu_office_address)s, %(eu_office_post_code)s, %(eu_office_city)s, %(eu_office_country)s, %(eu_office_phone)s,
    %(goals)s, %(eu_legislative_proposals)s, %(communication_activities)s, %(intergroup_activities)s,
    %(info_members)s, %(is_member_of)s, %(organisation_members)s, %(interest_represented)s, %(complementary_info)s,
    %(members_100_percent)s, %(members_50_percent)s, %(members_total)s, %(members_fte)s, %(ep_accredited_number)s,
    %(financial_year_start)s, %(financial_year_end)s, %(costs_min)s, %(costs_max)s, %(grants_total)s,
    %(intermediaries_costs)s, %(new_organisation)s,
    %(levels_of_interest)s, %(interests)s,
    %(has_body)s, %(body_html)s, %(body_text)s, %(body_source)s,
    %(public_url)s, NOW(), NOW()
)
ON CONFLICT (identification_code) DO UPDATE SET
    registration_date = EXCLUDED.registration_date,
    last_update_date = EXCLUDED.last_update_date,
    original_name = EXCLUDED.original_name,
    acronym = EXCLUDED.acronym,
    entity_form = EXCLUDED.entity_form,
    website_url = EXCLUDED.website_url,
    registration_category = EXCLUDED.registration_category,
    head_office_address = EXCLUDED.head_office_address,
    head_office_post_code = EXCLUDED.head_office_post_code,
    head_office_city = EXCLUDED.head_office_city,
    head_office_country = EXCLUDED.head_office_country,
    head_office_phone = EXCLUDED.head_office_phone,
    eu_office_address = EXCLUDED.eu_office_address,
    eu_office_post_code = EXCLUDED.eu_office_post_code,
    eu_office_city = EXCLUDED.eu_office_city,
    eu_office_country = EXCLUDED.eu_office_country,
    eu_office_phone = EXCLUDED.eu_office_phone,
    goals = EXCLUDED.goals,
    eu_legislative_proposals = EXCLUDED.eu_legislative_proposals,
    communication_activities = EXCLUDED.communication_activities,
    intergroup_activities = EXCLUDED.intergroup_activities,
    info_members = EXCLUDED.info_members,
    is_member_of = EXCLUDED.is_member_of,
    organisation_members = EXCLUDED.organisation_members,
    interest_represented = EXCLUDED.interest_represented,
    complementary_info = EXCLUDED.complementary_info,
    members_100_percent = EXCLUDED.members_100_percent,
    members_50_percent = EXCLUDED.members_50_percent,
    members_total = EXCLUDED.members_total,
    members_fte = EXCLUDED.members_fte,
    ep_accredited_number = EXCLUDED.ep_accredited_number,
    financial_year_start = EXCLUDED.financial_year_start,
    financial_year_end = EXCLUDED.financial_year_end,
    costs_min = EXCLUDED.costs_min,
    costs_max = EXCLUDED.costs_max,
    grants_total = EXCLUDED.grants_total,
    intermediaries_costs = EXCLUDED.intermediaries_costs,
    new_organisation = EXCLUDED.new_organisation,
    levels_of_interest = EXCLUDED.levels_of_interest,
    interests = EXCLUDED.interests,
    has_body = EXCLUDED.has_body,
    body_html = EXCLUDED.body_html,
    body_text = EXCLUDED.body_text,
    body_source = EXCLUDED.body_source,
    public_url = EXCLUDED.public_url,
    updated_at = NOW();
"""


# ─────────────────────── Main ────────────────────────────────────────────


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--source", type=str, default=None)
    args = ap.parse_args()

    if args.source:
        xml_path = Path(args.source)
    else:
        xml_path = fetch_xml()

    db = ChunkedDb()
    counts = {"upserted": 0, "errors": 0, "with_body": 0}

    print(f"[INFO] Streaming {xml_path}... (parser={'lxml' if _USE_LXML else 'stdlib'})", flush=True)
    if _USE_LXML:
        # lxml.iterparse takes recover/huge_tree directly as kwargs.
        context = ET.iterparse(str(xml_path), events=("end",),
                               recover=True, huge_tree=True)
    else:
        context = ET.iterparse(str(xml_path), events=("end",))
    i = 0
    for ev, el in context:
        tag = el.tag.split("}")[-1] if "}" in el.tag else el.tag
        if tag != "interestRepresentative":
            continue
        i += 1
        try:
            record = build_record(el)
        except Exception as exc:
            counts["errors"] += 1
            print(f"  [{i:5}] parse error: {exc!s}", flush=True)
            el.clear()
            continue

        if record["has_body"]:
            counts["with_body"] += 1

        if not args.apply:
            if i <= args.limit:
                print(f"  [{i:4}] {record['identification_code']:18} | "
                      f"name={(record.get('original_name') or '')[:50]:50} | "
                      f"country={record.get('head_office_country','—')} | "
                      f"interests={len(record.get('interests') or [])} | "
                      f"body={'+' if record['has_body'] else '—'}", flush=True)
            el.clear()
            if i >= args.limit:
                break
            continue

        try:
            db.execute(UPSERT_SQL, record)
            counts["upserted"] += 1
            if counts["upserted"] % 1000 == 0:
                db.commit()
                print(f"  [{i:5}] {record['identification_code']:18} | "
                      f"upserted={counts['upserted']:,} with_body={counts['with_body']:,}", flush=True)
        except Exception as exc:
            db.rollback()
            counts["errors"] += 1
            print(f"  [{i:5}] DB error: {exc!s}", flush=True)
        el.clear()

    if args.apply:
        db.commit()
    print()
    print(f"[DONE] {counts}{' (DRY)' if not args.apply else ''}")
    db.close()


if __name__ == "__main__":
    main()
