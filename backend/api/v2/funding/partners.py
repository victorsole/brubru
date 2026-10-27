"""GET /api/v2/funding/partners — one row per organisation, found by what it was funded or paid for.

Phase 1 of the funding standard (proposal 23 Oct 2026, §3.3 B). On 20-21 Oct a partner search for
a DG CNECT tender found no consortium leads: Brubru held who received EU money and who sat in which
consortium, but only as projects and payments, never grouped by organisation, and `q` matched names.
Here `q` matches the SUBJECT of an organisation's activities (a funded project's title, objective and
keywords; an FTS payment's subject), and each organisation lists the activities that matched, each
with its own `self`, so the reader sees why it is there.

Activities: the CORDIS consortia of Horizon Europe, Horizon 2020 and FP7 projects (every member),
the coordinators of the other programmes' projects (their sources name no one else), and the
Financial Transparency System's beneficiaries (fts_commitments, migration 313; private persons left
out: organisations only), and the winners of TED contract awards whose buyer is an EU body
(ted_award_winners, migration 315: each member of a joint tender, as a contractor).

Identity, never a name alone across sources: the PIC where known (CORDIS organisationID, the F&T
coordinator's PIC); an FTS beneficiary or a TED winner takes the PIC of the CORDIS organisation with
the same VAT number (funding_org_identities, migration 314; a TED company id counts as a VAT number
only when shaped like its own country's); else its VAT number; else its name within its country. Countries are the EU style codes (EL, UK) everywhere (services/funding/countries.py).
"""
from __future__ import annotations

import html
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path as PathParam, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.orm import Session

from api.v1._deps import api_user_with_rate_limit
from api.v1._envelope import PaginatedResponse, build_envelope
from core.database import get_db
from models.user import User
from services.funding.countries import eu_code, vat_key
from services.funding.organisations import ORG_FORM
from services.funding.programme_codes import named_codes, topic_prefixes

router = APIRouter()
Day = date   # PartnerActivity has a field named `date`, which would shadow the type in its own annotation

PORTAL_ORG = "https://ec.europa.eu/info/funding-tenders/opportunities/portal/screen/how-to-participate/org-details/{pic}"
ROLES = ("coordinator", "participant", "beneficiary", "contractor", "offer", "request")
ACTIVITY_TYPES = ("HES", "REC", "PRC", "PUB", "OTH")
SOURCES = ("all", "projects", "payments", "awards", "announcements")
ORDERS = ("matches", "amount", "name")
MATCHES_ON_LIST = 10
MATCHES_ON_ITEM = 50

_PROJECT_TSV = ("to_tsvector('english', coalesce(p.title, '') || ' ' || coalesce(p.objective, '') || ' ' "
                "|| coalesce(p.keywords, ''))")
_EU_COUNTRY = "CASE upper({c}) WHEN 'GR' THEN 'EL' WHEN 'GB' THEN 'UK' ELSE upper({c}) END"
# FTS grants and contributions; every other type of contract is a procurement category.
# Measured on the 2024 and 2025 files: budget support, financial instruments, trust funds and shared
# management also go to beneficiaries, not to contractors.
_GRANT_LIKE = ("c.funding_type ~* '(grant|contribution|prize|subsid|membership|operational expenses of|"
               "budget support|financial instr|trust fund|shared management)'")
_NAME_SLUG = "regexp_replace(lower({n}), '[^[:alnum:]]+', '-', 'g')"
# The expression ted_award_notices' full-text index is built on (migration 315).
_AWARD_TSV = "to_tsvector('english', coalesce(n.title, '') || ' ' || coalesce(n.description, ''))"
# The expression ft_partner_search_announcements' full-text index is built on (migration 316).
_ANNOUNCEMENT_TSV = "to_tsvector('english', coalesce(s.topic_title, '') || ' ' || coalesce(s.summary, ''))"
_SME_TYPE = "Small or medium-size enterprise"
_O_NAME, _O_COUNTRY = "o->>'name'", "o->>'country'"
# TED never marks a winner as a person or an organisation, and names individual experts beside
# companies (351840-2025). A winner is a partner when its VAT number is a CORDIS or FTS organisation's,
# or its name carries a legal form or an organisation word: 9,918 of 11,711 winner rows (27 Oct 2026);
# the 1,793 left out are mostly organisations with plain names, and every individual checked.
# Victor's rule (27 Oct): no person profiles, as for the FTS's private persons.
AWARD_ORG_FORM = ORG_FORM            # services/funding/organisations.py, shared with Partner Search
AWARD_WINNER_IS_ORGANISATION = (
    "(w.vat_key IN (SELECT vat_key FROM funding_org_identities)"
    " OR w.vat_key IN (SELECT vat_key FROM fts_commitments"
    " WHERE vat_key IS NOT NULL AND beneficiary_type IS DISTINCT FROM 'Private Persons')"
    f" OR w.name ~* '{AWARD_ORG_FORM}')"
)


class PartnerActivity(BaseModel):
    kind: str = Field(..., description="project (a funded project) | payment (an FTS row: a grant, contribution or contract) | award (a TED contract award it won) | announcement (its F&T Portal Partner Search announcement).")
    id: str = Field(..., description="The project_id, the FTS row's id, the award notice's TED publication number, or the announcement's id.")
    title: Optional[str] = Field(None, description="The project's title, what the payment was for, the award notice's title (and lot), or the announcement's topic.")
    role: Optional[str] = Field(None, description="coordinator | participant | beneficiary | contractor | offer (an announcement offering expertise) | request (seeking it).")
    programme: Optional[str] = Field(None, description="The project's or payment's programme; an announcement's topic code.")
    date: Optional[Day] = Field(None, description="The project's start, the payment's project start, the award's contract signature (else its notice's publication), or the announcement's date.")
    department: Optional[str] = Field(None, description="Who paid or bought: the FTS row's department, the award's contracting authority.")
    eu_contribution: Optional[float] = Field(None, description="Its EU contribution in the project, EUR (CORDIS).")
    amount_eur: Optional[float] = Field(None, description="What the FTS row says it received, EUR.")
    tender_value_eur: Optional[float] = Field(None, description="An award: its tender's value when in euros, shared by a joint tender's members; "
                                            "for a framework agreement usually the framework's maximum, not money paid.")
    self: Optional[str] = Field(None, description="The activity on its own route.")


class PartnerItem(BaseModel):
    id: str = Field(..., description="The organisation's key here: pic:<PIC>, vat:<VAT number> or name:<country>:<name>.")
    name: Optional[str] = None
    short_name: Optional[str] = None
    pic: Optional[str] = Field(None, description="Participant Identification Code, when known.")
    vat: Optional[str] = Field(None, description="VAT number (letters and digits), when known.")
    country: Optional[str] = Field(None, description="EU style code (EL Greece, UK United Kingdom, else ISO 3166 alpha-2).")
    city: Optional[str] = None
    activity_type: Optional[str] = Field(None, description="HES higher education | REC research body | PRC private company | PUB public body | OTH other (CORDIS).")
    is_sme: Optional[bool] = Field(None, description="SME, as CORDIS states it.")
    projects: int = Field(0, description="Matching funded projects it takes part in.")
    coordinated: int = Field(0, description="Of those, the ones it coordinates.")
    payments: int = Field(0, description="Matching FTS rows (grants, contributions, contracts) it received.")
    contracts: int = Field(0, description="Of those, procurement contracts.")
    awards: int = Field(0, description="Matching TED contract awards from EU buyers it won (not in the amounts: a joint tender's value is shared).")
    announcements: int = Field(0, description="Matching F&T Portal Partner Search announcements it published (offering or seeking expertise for a topic).")
    eu_contribution: Optional[float] = Field(None, description="Its EU contribution over the matching projects, EUR (CORDIS).")
    amount_eur: Optional[float] = Field(None, description="What the matching FTS rows say it received, EUR.")
    matches: List[PartnerActivity] = Field(default_factory=list, description="The activities that matched, newest first (10 on the list, 50 on the item route).")
    public_url: Optional[str] = Field(None, description="Its F&T Portal profile (Partner search) when the PIC is known.")
    body_txt: Optional[str] = None
    body_html: Optional[str] = None
    document_date: Optional[date] = Field(None, description="Its most recent matching activity's start (not in the future).")
    creation_date: Optional[datetime] = Field(None, description="When Brubru first stored its earliest matching activity.")
    updated_date: Optional[datetime] = Field(None, description="When its most recently changed matching activity last changed.")


def _sql(*, q, name, role, programme, topic, dg, country, activity_type, is_sme, since, source,
         min_amount_eur, key, order, matches_cap):
    """The query and its parameters: activities -> one row per organisation key."""
    p_where, f_where, w_where, s_where, a_where, having, params = [], [], [], [], [], [], {}
    use_projects = source in ("all", "projects") and not dg
    use_payments = source in ("all", "payments") and activity_type is None and is_sme is None
    # An award has no programme, topic, activity type or SME flag of its own.
    use_awards = (source in ("all", "awards") and activity_type is None and is_sme is None
                  and not programme and not topic)
    # An announcement has no department and no CORDIS activity type; its SME flag is the portal's type.
    use_announcements = source in ("all", "announcements") and not dg and activity_type is None
    # An announcement always carries its PIC, so its partner is always pic:<PIC>: a vat: or name: key
    # can never include one (and the name lookup would read every announcement to find none).
    if key and not key.startswith("pic:"):
        use_announcements = False
    if q:
        p_where.append(f"{_PROJECT_TSV} @@ websearch_to_tsquery('english', :q)")
        f_where.append("to_tsvector('english', coalesce(c.subject, '')) @@ websearch_to_tsquery('english', :q)")
        w_where.append(f"{_AWARD_TSV} @@ websearch_to_tsquery('english', :q)")
        s_where.append(f"{_ANNOUNCEMENT_TSV} @@ websearch_to_tsquery('english', :q)")
        params["q"] = q
    if programme:
        named = named_codes(programme)
        p_where.append("(p.framework_programme ILIKE :prog_like" + (" OR p.framework_programme = ANY(CAST(:prog_named AS text[]))" if named else "") + ")")
        f_where.append("c.programme ILIKE :prog_like")
        params["prog_like"] = f"%{programme}%"
        if named:
            params["prog_named"] = named
            # A topic starts with its programme's code without the year: CEF2027 -> CEF-..., HORIZON -> HORIZON-...
            params["prog_topics"] = topic_prefixes(named)
            s_where.append("(s.topic_id ILIKE :prog_like OR s.topic_id ILIKE ANY(CAST(:prog_topics AS text[])))")
        else:
            s_where.append("s.topic_id ILIKE :prog_like")
    if topic:
        p_where.append("p.topic_code ILIKE :topic_prefix"); f_where.append("c.call_id ILIKE :topic_prefix")
        s_where.append("s.topic_id ILIKE :topic_prefix")
        params["topic_prefix"] = f"{topic.strip()}%"
    if dg:
        f_where.append("c.dg ILIKE :dg"); w_where.append("n.contracting_authority ILIKE :dg"); params["dg"] = f"%{dg}%"
    if since:
        p_where.append("p.start_date >= :since"); f_where.append("c.project_start >= :since")
        w_where.append("coalesce(w.contract_date, n.publication_date) >= :since"); params["since"] = since
        s_where.append("s.requested_date >= :since")
    if key:
        kind, _, val = key.partition(":")
        if kind == "pic":
            p_where.append("(p.organisations @> CAST(:key_contains AS jsonb) OR p.coordinator_pic = :key_val)")
            params["key_contains"] = f'[{{"pic": "{val}"}}]'
            f_where.append("c.vat_key IN (SELECT vat_key FROM funding_org_identities WHERE pic = :key_val)")
            w_where.append("w.vat_key IN (SELECT vat_key FROM funding_org_identities WHERE pic = :key_val)")
            s_where.append("s.pic = :key_val")
        elif kind == "vat":
            p_where.append("p.organisations @> CAST(:key_contains AS jsonb)")
            params["key_contains"] = f'[{{"vat": "{val}"}}]'
            f_where.append("c.vat_key = :key_val")
            w_where.append("w.vat_key = :key_val")
        else:
            cc, _, slug = val.partition(":")
            params["key_cc"], params["key_slug"] = cc.upper(), slug
            f_where.append(f"c.country_code = :key_cc AND {_NAME_SLUG.format(n='c.beneficiary')} = :key_slug")
            w_where.append(f"w.country = :key_cc AND {_NAME_SLUG.format(n='w.name')} = :key_slug")
            # Without this every consortium would be unpacked to find one name.
            p_where.append(
                f"(EXISTS (SELECT 1 FROM jsonb_array_elements(p.organisations) o WHERE "
                f"{_NAME_SLUG.format(n=_O_NAME)} = :key_slug AND {_EU_COUNTRY.format(c=_O_COUNTRY)} = :key_cc) "
                f"OR ({_NAME_SLUG.format(n='p.coordinator_name')} = :key_slug "
                f"AND {_EU_COUNTRY.format(c='p.coordinator_country')} = :key_cc))")
        params["key_val"] = val
        a_where.append("key = :key")
        params["key"] = key
    if name:
        a_where.append("(name ILIKE :name_like OR short_name ILIKE :name_like)"); params["name_like"] = f"%{name}%"
    if role:
        a_where.append("role = :role"); params["role"] = role
    if country:
        a_where.append("country = :cc"); params["cc"] = eu_code(country)
    if activity_type:
        a_where.append("activity_type = :at"); params["at"] = activity_type
    if is_sme is not None:
        a_where.append("is_sme = :sme"); params["sme"] = is_sme
    if min_amount_eur is not None:
        having.append("coalesce(sum(eu_contribution), 0) + coalesce(sum(amount_eur), 0) >= :min_amt")
        params["min_amt"] = min_amount_eur

    pw = "".join(f" AND {w}" for w in p_where)
    fw = "".join(f" AND {w}" for w in f_where)
    ww = "".join(f" AND {w}" for w in w_where)
    sw = "".join(f" AND {w}" for w in s_where)
    parts = []
    if use_projects:
        parts.append(f"""
        SELECT 'project' AS kind, pr.project_id AS ref, pr.title, pr.framework_programme AS programme, pr.start_date AS day,
               nullif(o->>'pic', '') AS pic, upper(regexp_replace(coalesce(o->>'vat', ''), '[^A-Za-z0-9]', '', 'g')) AS vat,
               o->>'name' AS name, nullif(o->>'short_name', '') AS short_name, {_EU_COUNTRY.format(c="o->>'country'")} AS country,
               nullif(o->>'city', '') AS city, nullif(o->>'activity_type', '') AS activity_type, (o->>'is_sme')::boolean AS is_sme,
               CASE WHEN o->>'role' = 'coordinator' THEN 'coordinator' ELSE 'participant' END AS role,
               (o->>'ec_contribution')::numeric AS eu_contribution, NULL::numeric AS amount_eur,
               NULL::text AS department, NULL::numeric AS tender_value_eur,
               pr.last_updated AS changed, pr.scraped_at AS created
          FROM proj pr, jsonb_array_elements(pr.organisations) o
        UNION ALL
        SELECT 'project', pr.project_id, pr.title, pr.framework_programme, pr.start_date,
               nullif(pr.coordinator_pic, ''), '', pr.coordinator_name, NULL, {_EU_COUNTRY.format(c='pr.coordinator_country')},
               NULL, NULL, NULL::boolean, 'coordinator', NULL::numeric, NULL::numeric, NULL::text, NULL::numeric,
               pr.last_updated, pr.scraped_at
          FROM proj pr
         WHERE jsonb_array_length(coalesce(pr.organisations, '[]'::jsonb)) = 0 AND pr.coordinator_name IS NOT NULL""")
    if use_payments:
        parts.append(f"""
        SELECT 'payment' AS kind, e.id::text AS ref, coalesce(c.subject, e.title) AS title, c.programme AS programme,
               c.project_start AS day, NULL::text AS pic, coalesce(c.vat_key, '') AS vat, c.beneficiary AS name,
               NULL::text AS short_name, c.country_code AS country, c.city AS city, NULL::text AS activity_type,
               NULL::boolean AS is_sme,
               CASE WHEN c.is_coordinator THEN 'coordinator' WHEN {_GRANT_LIKE} THEN 'beneficiary' ELSE 'contractor' END AS role,
               NULL::numeric AS eu_contribution, c.beneficiary_amount_eur AS amount_eur,
               c.dg AS department, NULL::numeric AS tender_value_eur,
               greatest(e.updated_at, c.last_updated) AS changed, e.creation_date AS created
          FROM fts_commitments c JOIN economy_items e ON e.id = c.economy_item_id
         WHERE c.beneficiary_type IS DISTINCT FROM 'Private Persons'{fw}""")
    if use_awards:
        parts.append(f"""
        SELECT 'award' AS kind, n.publication_number AS ref,
               CASE WHEN n.lot_count > 1 AND w.lot_title IS NOT NULL THEN n.title || ': ' || w.lot_title ELSE n.title END AS title,
               NULL::text AS programme, coalesce(w.contract_date, n.publication_date) AS day, NULL::text AS pic,
               coalesce(w.vat_key, '') AS vat, w.name AS name, NULL::text AS short_name, w.country AS country,
               w.city AS city, NULL::text AS activity_type, NULL::boolean AS is_sme, 'contractor' AS role,
               NULL::numeric AS eu_contribution, NULL::numeric AS amount_eur, n.contracting_authority AS department,
               CASE WHEN upper(w.tender_value_currency) = 'EUR' THEN w.tender_value END AS tender_value_eur,
               greatest(n.last_updated, w.last_updated) AS changed, n.first_seen AS created
          FROM ted_award_winners w JOIN ted_award_notices n ON n.publication_number = w.publication_number
         WHERE n.superseded_by IS NULL AND {AWARD_WINNER_IS_ORGANISATION}{ww}""")
    if use_announcements:
        parts.append(f"""
        SELECT 'announcement' AS kind, s.announcement_id AS ref, s.topic_title AS title, s.topic_id AS programme,
               s.requested_date AS day, s.pic AS pic, '' AS vat, s.organisation_name AS name, NULL::text AS short_name,
               s.country AS country, o.city AS city, NULL::text AS activity_type,
               (s.organisation_type = '{_SME_TYPE}') AS is_sme, s.expertise AS role,
               NULL::numeric AS eu_contribution, NULL::numeric AS amount_eur, NULL::text AS department,
               NULL::numeric AS tender_value_eur, s.last_updated AS changed, s.first_seen AS created
          FROM ft_partner_search_announcements s LEFT JOIN ft_partner_search_orgs o ON o.pic = s.pic
         WHERE true{sw}""")
    if not parts:
        return None, params
    order_sql = {
        "matches": "count(*) DESC, coalesce(sum(eu_contribution), 0) + coalesce(sum(amount_eur), 0) DESC, key",
        "amount": "coalesce(sum(eu_contribution), 0) + coalesce(sum(amount_eur), 0) DESC, key",
        "name": "mode() WITHIN GROUP (ORDER BY name), key",
    }[order]
    slug_n = _NAME_SLUG.format(n="a.name")
    sql = f"""
    WITH proj AS (
        SELECT p.project_id, p.title, p.framework_programme, p.start_date, p.organisations, p.coordinator_pic,
               p.coordinator_name, p.coordinator_country, p.last_updated, p.scraped_at
          FROM ft_funded_projects p WHERE p.is_test = false{pw}
    ), acts AS ({" UNION ALL ".join(parts)}
    ), keyed AS (
        SELECT a.*, coalesce(a.pic, m.pic) AS pic_resolved,
               CASE WHEN coalesce(a.pic, m.pic) IS NOT NULL THEN 'pic:' || coalesce(a.pic, m.pic)
                    WHEN a.vat <> '' THEN 'vat:' || a.vat
                    ELSE 'name:' || lower(coalesce(a.country, '')) || ':' || {slug_n} END AS key
          FROM acts a LEFT JOIN funding_org_identities m ON a.pic IS NULL AND a.vat <> '' AND m.vat_key = a.vat
         WHERE a.name IS NOT NULL
    )
    SELECT key, max(pic_resolved) AS pic, max(nullif(vat, '')) AS vat, mode() WITHIN GROUP (ORDER BY name) AS name,
           max(short_name) AS short_name, mode() WITHIN GROUP (ORDER BY country) AS country,
           mode() WITHIN GROUP (ORDER BY city) AS city, mode() WITHIN GROUP (ORDER BY activity_type) AS activity_type,
           bool_or(is_sme) AS is_sme,
           count(DISTINCT ref) FILTER (WHERE kind = 'project') AS projects,
           count(DISTINCT ref) FILTER (WHERE kind = 'project' AND role = 'coordinator') AS coordinated,
           count(*) FILTER (WHERE kind = 'payment') AS payments,
           count(*) FILTER (WHERE kind = 'payment' AND role = 'contractor') AS contracts,
           count(DISTINCT ref) FILTER (WHERE kind = 'award') AS awards,
           count(DISTINCT ref) FILTER (WHERE kind = 'announcement') AS announcements,
           sum(eu_contribution) AS eu_contribution, sum(amount_eur) AS amount_eur,
           max(day) FILTER (WHERE day <= CURRENT_DATE) AS last_day, min(created) AS created, max(changed) AS changed,
           (array_agg(jsonb_build_object('kind', kind, 'id', ref, 'title', title, 'role', role, 'programme', programme,
                                         'date', day, 'department', department, 'eu_contribution', eu_contribution,
                                         'amount_eur', amount_eur, 'tender_value_eur', tender_value_eur)
                      ORDER BY day DESC NULLS LAST))[1:{int(matches_cap)}] AS matches,
           count(*) OVER () AS total
      FROM keyed{"".join(f" WHERE {w}" if i == 0 else f" AND {w}" for i, w in enumerate(a_where))}
     GROUP BY key{" HAVING " + " AND ".join(having) if having else ""}
     ORDER BY {order_sql}
     LIMIT :limit OFFSET :offset"""
    return sql, params


def _item(r, base: str) -> PartnerItem:
    acts = []
    for m in r.matches or []:
        route = {"project": "/api/v2/funding/ft-funded-projects/", "payment": "/api/v2/funding/eu-funding-recipients/",
                 "award": "/api/v2/funding/tender-awards/",
                 "announcement": "/api/v2/funding/partner-announcements/"}[m["kind"]] + str(m["id"])
        acts.append(PartnerActivity(**m, self=base + route))
    lines = [r.name or "", f"Country: {r.country}" if r.country else "", f"PIC: {r.pic}" if r.pic else "",
             f"Matching projects: {r.projects} (coordinated: {r.coordinated})" if r.projects else "",
             f"Matching FTS payments: {r.payments} (contracts: {r.contracts})" if r.payments else "",
             f"Matching TED contract awards won: {r.awards}" if r.awards else "",
             f"Matching Partner Search announcements: {r.announcements}" if r.announcements else ""]
    lines += [f"- {a.date or ''} {a.role or ''}: {a.title or ''}".strip() for a in acts]
    lines = [l for l in lines if l]
    return PartnerItem(
        id=r.key, name=r.name, short_name=r.short_name, pic=r.pic, vat=r.vat, country=r.country, city=r.city,
        activity_type=r.activity_type, is_sme=r.is_sme, projects=r.projects, coordinated=r.coordinated,
        payments=r.payments, contracts=r.contracts, awards=r.awards, announcements=r.announcements,
        eu_contribution=float(r.eu_contribution) if r.eu_contribution is not None else None,
        amount_eur=float(r.amount_eur) if r.amount_eur is not None else None,
        matches=acts, public_url=PORTAL_ORG.format(pic=r.pic) if r.pic else None,
        body_txt="\n".join(lines),
        body_html="<ul>" + "".join(f"<li>{html.escape(l)}</li>" for l in lines) + "</ul>",
        document_date=r.last_day, creation_date=r.created, updated_date=r.changed,
    )


_DESC = """**What it does**
One row per organisation that took part in EU-funded projects, received EU money, won an EU body's contract or is looking for partners, found by **what it was funded, paid or contracted for**, not by its name. `q` searches the subjects of its activities: funded projects' titles, objectives and keywords (CORDIS consortia of Horizon Europe, Horizon 2020 and FP7, every member; the other programmes' coordinators), the subjects of the payments the EU Financial Transparency System lists (grants, contributions, procurement contracts) and the titles and descriptions of the TED contract awards of EU institutions, bodies and agencies since 2024 (`/api/v2/funding/tender-awards`: every winner, joint tenders' members included), and the F&T Portal's Partner Search announcements of organisations (`/api/v2/funding/partner-announcements`: the topic and the text an organisation published to offer or seek expertise; 329,855 announcements from 16,084 organisations on 27 Oct 2026; of the 9,996 whose profile carries the Partner Search flag, 5,196 had no EU project as the portal counts them). Each organisation carries its counts and totals over the matching activities and **the activities themselves, each with its own `self`**, so you can see why it matched.

**When to use it**
Finding consortium partners and competitors: "who coordinates projects on soil health", "which companies did DG CNECT pay or contract for studies on artificial intelligence", "which Spanish research bodies work on hydrogen storage", "who is looking for partners on this Horizon topic". For one organisation's whole record, follow its `self`.

**Input**
- `q` — the subject (full text: every word in any form; `"quoted phrase"`, `OR`, `-word`). `q` or `name` is required.
- `name` — part of the organisation's name.
- `role` — coordinator | participant (project roles) | beneficiary | contractor (FTS: a grant or contribution received, or a procurement contract; every TED award winner is a contractor) | offer | request (a Partner Search announcement offering or seeking expertise).
- `programme` — part of the programme's name or code (`Horizon Europe`, `LIFE`, `DIGITAL`); `topic` — a topic code or its start (`HORIZON-CL5-2026`; on payments, the FTS call ID; on announcements, their topic). Either leaves the awards out (an award has neither).
- `dg` — the paying or buying department (`CNECT`): the FTS payment's department, the award's contracting authority; projects and announcements are then left out.
- `country` — ISO-2 (EL and GR, UK and GB are the same country).
- `activity_type` (HES higher education | REC research | PRC private company | PUB public body | OTH) — as CORDIS states it, projects only; `is_sme` — as CORDIS states it, and on announcements the portal's "Small or medium-size enterprise" type.
- `since` — activities starting on or after (YYYY-MM-DD; an award's contract signature, an announcement's date); `min_amount_eur` — the organisation's EU contribution plus payments over the matches, at least (awards are not in the amounts: a joint tender's value is shared by its members).
- `source` — all (default) | projects | payments | awards | announcements. `order` — matches (default) | amount | name. `page`, `limit` (max 50).

**Try it**
```
GET /api/v2/funding/partners?q=soil%20health&role=coordinator
GET /api/v2/funding/partners?q=artificial%20intelligence%20study&dg=CNECT&role=contractor
GET /api/v2/funding/partners?q=hydrogen%20storage&country=ES&activity_type=REC
GET /api/v2/funding/partners?q=legal%20translation&source=awards
GET /api/v2/funding/partners?q=hydrogen&topic=HORIZON-CL5&source=announcements&role=request
```

**You get back**
A paginated envelope of organisations: `id` (pic:<PIC>, vat:<VAT number> or name:<country>:<name>), `name`, `short_name`, `pic`, `vat`, `country`, `city`, `activity_type`, `is_sme`, the counts `projects`, `coordinated`, `payments`, `contracts`, `awards`, `announcements`, the totals `eu_contribution` and `amount_eur`, `matches` (up to 10: kind, id, title, role, programme, date, department, amounts, an award's `tender_value_eur`, `self`), `public_url` (its F&T Portal profile when the PIC is known), `body_txt` / `body_html` (the same, as text), `document_date`, `creation_date`, `updated_date`.

**Identity**
The PIC where known; a payment's beneficiary or an award's winner takes the PIC of the CORDIS organisation with the same VAT number (a TED company identifier counts as a VAT number only when shaped like its own country's); else the VAT number; else the name within its country. A name alone never joins two records, so one organisation can appear twice (for instance under its PIC and, for payments with no VAT number, under its name). Private persons are left out: the FTS's own, and of TED's award winners (TED never says which is a person) those that are neither a CORDIS or FTS organisation by their VAT number nor named with a legal form or an organisation word (GmbH, SL, Ltd, Institute, University...), so an individual expert named in a notice is not a partner; the Partner Search's person profiles and persons' announcements are never read, and a self-registered Partner Search profile typed Other, SME or private for-profit whose name carries no legal form, organisation word or digit is left out with its announcements (it may be a person's own registration).

**Data freshness**
Funded projects read every Sunday (CORDIS, the F&T Portal); FTS files for 2024 and 2025 read every Sunday; the VAT to PIC pairing rebuilt after them; TED award notices read every day; Partner Search read every day (new announcements, and a seventh of the older ones in turn)."""


@router.get("/partners", response_model=PaginatedResponse[PartnerItem], tags=["v2-funding"],
            summary="Partners — organisations found by what they were funded, paid or contracted for", description=_DESC)
async def list_partners(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
    q: Optional[str] = Query(None, description="The subject: words in the activities' titles, objectives, keywords or payment subjects."),
    name: Optional[str] = Query(None, description="Part of the organisation's name."),
    role: Optional[str] = Query(None, description="coordinator | participant | beneficiary | contractor | offer | request."),
    programme: Optional[str] = Query(None, description="Part of the programme's name or code."),
    topic: Optional[str] = Query(None, description="A topic code or its start; on payments, the FTS call ID."),
    dg: Optional[str] = Query(None, description="The paying or buying department (payments and awards), e.g. CNECT."),
    country: Optional[str] = Query(None, min_length=2, max_length=2, description="ISO-2; EL/GR and UK/GB are the same country."),
    activity_type: Optional[str] = Query(None, description="HES | REC | PRC | PUB | OTH (projects only)."),
    is_sme: Optional[bool] = Query(None, description="SME as CORDIS states it (projects only)."),
    since: Optional[date] = Query(None, description="Activities starting on or after (YYYY-MM-DD)."),
    min_amount_eur: Optional[float] = Query(None, ge=0, description="EU contribution plus payments over the matches, at least."),
    source: str = Query("all", description="all | projects | payments | awards | announcements."),
    order: str = Query("matches", description="matches | amount | name."),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
):
    if not (q or name):
        raise HTTPException(status_code=400, detail="Give q (the subject) or name: a partner search over every organisation at once is not served.")
    for val, allowed, label in ((role, ROLES, "role"), (activity_type, ACTIVITY_TYPES, "activity_type"),
                                (source, SOURCES, "source"), (order, ORDERS, "order")):
        if val is not None and val not in allowed:
            raise HTTPException(status_code=400, detail=f"{label} must be one of {list(allowed)}")
    sql, params = _sql(q=q, name=name, role=role, programme=programme, topic=topic, dg=dg, country=country,
                       activity_type=activity_type, is_sme=is_sme, since=since, source=source,
                       min_amount_eur=min_amount_eur, key=None, order=order, matches_cap=MATCHES_ON_LIST)
    if sql is None:
        return build_envelope([], 0, page, limit)
    params.update(limit=limit, offset=(page - 1) * limit)
    db.execute(text("SET LOCAL statement_timeout = '60s'"))
    rows = db.execute(text(sql), params).fetchall()
    base = str(request.base_url).rstrip("/")
    return build_envelope([_item(r, base) for r in rows], rows[0].total if rows else 0, page, limit)


@router.get("/partners/{id:path}", response_model=PartnerItem, tags=["v2-funding"],
            summary="One partner — an organisation's funded projects, EU payments, contract awards and Partner Search announcements",
            description="""**What it does**
One organisation from `/api/v2/funding/partners`: every funded project it takes part in, every FTS payment it received and every TED contract award from an EU buyer it won (up to 50, newest first), with its counts and totals over all of them.

**When to use it**
After a partner search, to read one organisation's whole record.

**Input**
`id` — the organisation's key from the list: `pic:<PIC>`, `vat:<VAT number>` or `name:<country>:<name>` (each item's `self` is this route). A `vat:` id whose VAT number is paired with a PIC answers as that PIC.

**Try it**
```
GET /api/v2/funding/partners/pic:999991722
```

**You get back**
One organisation, the same fields as the list, `matches` up to 50, or 404.

**Data freshness**
As the list.""")
async def get_partner(
    request: Request,
    id: str = PathParam(..., description="pic:<PIC>, vat:<VAT number> or name:<country>:<name>."),
    db: Session = Depends(get_db),
    user: User = Depends(api_user_with_rate_limit),
):
    kind, _, val = id.partition(":")
    if kind not in ("pic", "vat", "name") or not val:
        raise HTTPException(status_code=404, detail=f"No partner with id {id}")
    if kind == "vat":
        val = vat_key(val) or ""
        id = f"vat:{val}"
        # A VAT number paired with a PIC stands under that PIC (the list gives it that id).
        paired = db.execute(text("SELECT pic FROM funding_org_identities WHERE vat_key = :v"), {"v": val}).scalar()
        if paired:
            id = f"pic:{paired}"
    sql, params = _sql(q=None, name=None, role=None, programme=None, topic=None, dg=None, country=None,
                       activity_type=None, is_sme=None, since=None, source="all", min_amount_eur=None,
                       key=id, order="matches", matches_cap=MATCHES_ON_ITEM)
    params.update(limit=1, offset=0)
    db.execute(text("SET LOCAL statement_timeout = '60s'"))
    r = db.execute(text(sql), params).fetchone()
    if r is None:
        raise HTTPException(status_code=404, detail=f"No partner with id {id}")
    return _item(r, str(request.base_url).rstrip("/"))
