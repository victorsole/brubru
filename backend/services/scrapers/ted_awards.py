"""
TED contract award notices where an EU institution, body or agency is the buyer (26 Oct 2026,
partner search: who wins contracts like this one).

TED's own buyer label is not enough. Of 1,000 result notices of 2025 labelled eu-ins-bod-ag, about
half came from national buyers (the Croatian central procurement office, Slovenian ministries, a
Polish hospital), and 137 notices since 2024 from EU bodies carry another label (body-pl, int-org,
"8"). A notice is kept when one of its buyers' own web or e-mail addresses is on europa.eu (TED's
eNotices service excepted: a Polish municipality wrote its address there) or on one of the few EU
bodies' own domains below.

The winners are read from each notice's eForms XML, never from the search API's flat lists: there
names, countries and identifiers are separate lists that stop lining up when a lot has several
winners (an ECB notice: 40 names, 24 countries). In the XML a lot result names its tenders, a
settled contract names the tender it was concluded with, and a tendering party names its
organisations; a winner is an organisation of a tender a contract was concluded with.

EU bodies kept filing the pre-eForms forms into 2024 (69 of 79 candidates in February 2024 were
legacy TED XML): the legacy award forms (F03 and its siblings) are read too, one awarded contract
per AWARD_CONTRACT and every CONTRACTOR in it a winner.
"""
from __future__ import annotations

import html
import json
import logging
import time
import xml.etree.ElementTree as ET
from datetime import date
from typing import Dict, Iterator, List, Optional
from urllib.parse import urlparse

import requests

from services.funding.countries import alpha3_code, eu_code, vat_number
from services.tenders.eforms_parser import EFORMS_NS as NS

logger = logging.getLogger(__name__)

SEARCH_API = "https://api.ted.europa.eu/v3/notices/search"
XML_URL = "https://ted.europa.eu/en/notice/{}/xml"
NOTICE_URL = "https://ted.europa.eu/en/notice/-/detail/{}"

# EU bodies whose own domain is not on europa.eu, each seen as a buyer on TED since 2024.
EU_BODY_DOMAINS = ("eib.org", "eif.org", "sesarju.eu", "clean-aviation.eu", "euam-ukraine.eu", "eupolcopps.eu")
# TED's eNotices service: an address there says who filed the notice, not who buys.
NOT_A_BUYER = "ted.europa.eu"

# The candidates: TED's own EU label, or an address on an EU domain whatever the label.
_ADDRESS_TERMS = ("europa.eu",) + EU_BODY_DOMAINS[:2]
SELECTION = "form-type=result AND ({})".format(" OR ".join(
    ["buyer-legal-type=eu-ins-bod-ag"]
    + [f'buyer-{field}~"{term}"' for term in _ADDRESS_TERMS for field in ("internet-address", "email")]))
SEARCH_FIELDS = ["publication-number", "buyer-internet-address", "buyer-email"]
# eForms winner-selection-status: what a lot's result says.
RESULTS = {"selec-w": "winner chosen", "clos-nw": "closed, no winner chosen", "open-nw": "no winner chosen yet"}


def host(value: Optional[str]) -> str:
    """The host of a web address or the domain of an e-mail address, lower case, no www."""
    s = (value or "").strip().lower()
    if not s:
        return ""
    if "@" in s and "://" not in s:
        return s.rsplit("@", 1)[1].strip(" .>")
    if "://" not in s:
        s = "http://" + s
    try:
        h = urlparse(s).hostname or ""
    except ValueError:
        return ""
    return h[4:] if h.startswith("www.") else h


def _under(h: str, domain: str) -> bool:
    return h == domain or h.endswith("." + domain)


def is_eu_body_address(value: Optional[str]) -> bool:
    """True for an address on europa.eu (TED's eNotices service excepted) or an EU body's domain."""
    h = host(value)
    if not h or _under(h, NOT_A_BUYER):
        return False
    return _under(h, "europa.eu") or any(_under(h, d) for d in EU_BODY_DOMAINS)


def _post(session: requests.Session, body: dict) -> dict:
    """One search call; TED answers 429 to bursts, so wait and retry, then give up loudly."""
    for attempt in range(8):
        r = session.post(SEARCH_API, json=body, timeout=120)
        if r.status_code == 429:
            time.sleep(15 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("TED search kept answering 429")


def search_awards(session: requests.Session, start: date, end: date) -> Iterator[str]:
    """Publication numbers of result notices published from start to end (inclusive) whose buyer
    has an EU-body address. The XML decides again (parse_award); this only saves the downloads."""
    query = f"{SELECTION} AND publication-date>={start:%Y%m%d} AND publication-date<={end:%Y%m%d}"
    token = None
    while True:
        body = {"query": query, "fields": SEARCH_FIELDS, "limit": 250, "scope": "ALL",
                "paginationMode": "ITERATION"}
        if token:
            body["iterationNextToken"] = token
        d = _post(session, body)
        notices = d.get("notices") or []
        for x in notices:
            addresses = (x.get("buyer-internet-address") or []) + (x.get("buyer-email") or [])
            if any(is_eu_body_address(a) for a in addresses):
                yield x["publication-number"]
        token = d.get("iterationNextToken")
        if not token or not notices:
            return


def fetch_xml(session: requests.Session, publication_number: str) -> str:
    for attempt in range(6):
        r = session.get(XML_URL.format(publication_number), headers={"Accept": "application/xml"}, timeout=120)
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10 * (attempt + 1))
            continue
        r.raise_for_status()
        return r.text
    raise RuntimeError(f"TED kept refusing the XML of {publication_number}")


# --- eForms reading ---------------------------------------------------------------------------

def _t(el: Optional[ET.Element], path: str) -> Optional[str]:
    if el is None:
        return None
    f = el.find(path, NS)
    return f.text.strip() if f is not None and f.text and f.text.strip() else None


def _all(el: ET.Element, path: str) -> List[str]:
    return [f.text.strip() for f in el.findall(path, NS) if f.text and f.text.strip()]


def _text_in(el: Optional[ET.Element], path: str) -> Optional[str]:
    """A multilingual text: the English version when the notice gives one, else the first."""
    if el is None:
        return None
    found = [f for f in el.findall(path, NS) if f.text and f.text.strip()]
    if not found:
        return None
    eng = next((f for f in found if (f.get("languageID") or "").upper() == "ENG"), found[0])
    return eng.text.strip()


def _line(value: Optional[str]) -> Optional[str]:
    """A name or title on one line: TED keeps the line breaks of the form ("...informacijskih\nsustava")."""
    return " ".join(value.split()) if value else None


def _day(value: Optional[str]) -> Optional[str]:
    """eForms dates carry an offset ("2025-03-14+01:00"): the day is the first ten characters."""
    return value[:10] if value and len(value) >= 10 else None


def _amount(el: Optional[ET.Element], path: str):
    if el is None:
        return None, None
    f = el.find(path, NS)
    if f is None or not (f.text or "").strip():
        return None, None
    try:
        return float(f.text.strip()), f.get("currencyID")
    except ValueError:
        return None, None


def _organisations(root: ET.Element) -> Dict[str, dict]:
    orgs: Dict[str, dict] = {}
    for org in root.iter(f"{{{NS['efac']}}}Organization"):
        company = org.find("efac:Company", NS)
        ref = _t(company, "cac:PartyIdentification/cbc:ID")
        if company is None or not ref:
            continue
        orgs[ref] = {
            "name": _line(_text_in(company, "cac:PartyName/cbc:Name")),
            "city": _line(_t(company, "cac:PostalAddress/cbc:CityName")),
            "country": alpha3_code(_t(company, "cac:PostalAddress/cac:Country/cbc:IdentificationCode")),
            "company_id": _t(company, "cac:PartyLegalEntity/cbc:CompanyID"),
            "size": _t(company, "efbc:CompanySizeCode"),
            "website": _t(company, "cbc:WebsiteURI"),
            "email": _t(company, "cac:Contact/cbc:ElectronicMail"),
        }
    return orgs


def parse_award(xml_text: str, publication_number: str) -> Optional[dict]:
    """One award notice: the notice, its EU buyers, its lots and its winners. None when the XML is
    not an eForms award notice or none of its buyers has an EU-body address."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    if root.tag.endswith("TED_EXPORT"):
        return _parse_legacy(root, publication_number)
    if not root.tag.endswith("ContractAwardNotice"):
        return None
    orgs = _organisations(root)

    buyers = []
    for party in root.findall("cac:ContractingParty", NS):
        ref = _t(party, "cac:Party/cac:PartyIdentification/cbc:ID")
        org = orgs.get(ref or "", {})
        legal = next((c.text.strip() for c in party.findall("cac:ContractingPartyType/cbc:PartyTypeCode", NS)
                      if c.get("listName") == "buyer-legal-type" and c.text), None)
        buyers.append({"name": org.get("name"), "country": org.get("country"), "city": org.get("city"),
                       "legal_type": legal, "website": org.get("website"), "email": org.get("email"),
                       "eu_body": is_eu_body_address(org.get("website")) or is_eu_body_address(org.get("email"))})
    eu_buyers = [b for b in buyers if b["eu_body"]]
    if not eu_buyers:
        return None

    project = root.find("cac:ProcurementProject", NS)
    lots = {}
    for lot in root.findall("cac:ProcurementProjectLot", NS):
        lot_id = _t(lot, "cbc:ID")
        if lot_id:
            lots[lot_id] = {"lot_id": lot_id, "title": _line(_text_in(lot, "cac:ProcurementProject/cbc:Name")),
                            "description": _text_in(lot, "cac:ProcurementProject/cbc:Description"),
                            "result": None, "tenders_received": None}

    result = root.find(".//efac:NoticeResult", NS)
    total, total_cur = _amount(result, "cbc:TotalAmount")
    winners: List[dict] = []
    if result is not None:
        tenders = {_t(t, "cbc:ID"): t for t in result.findall("efac:LotTender", NS) if _t(t, "cbc:ID")}
        parties = {_t(p, "cbc:ID"): p for p in result.findall("efac:TenderingParty", NS) if _t(p, "cbc:ID")}
        contracts_of: Dict[str, List[ET.Element]] = {}
        for c in result.findall("efac:SettledContract", NS):
            for ref in _all(c, "efac:LotTender/cbc:ID"):
                contracts_of.setdefault(ref, []).append(c)
        for lr in result.findall("efac:LotResult", NS):
            lot_id = _t(lr, "efac:TenderLot/cbc:ID")
            code = _t(lr, "cbc:TenderResultCode")
            received = next((int(float(s.findtext("efbc:StatisticsNumeric", "", NS) or 0))
                             for s in lr.findall("efac:ReceivedSubmissionsStatistics", NS)
                             if s.findtext("efbc:StatisticsCode", "", NS) == "tenders"), None)
            if lot_id:
                lot = lots.setdefault(lot_id, {"lot_id": lot_id, "title": None, "description": None})
                lot["result"], lot["tenders_received"] = code, received
            if code != "selec-w":
                continue
            refs = _all(lr, "efac:LotTender/cbc:ID")
            # The tenders a contract was concluded with; a notice that names no contract for
            # this lot leaves its result's own tenders as the winners.
            won = [r for r in refs if r in contracts_of] or refs
            for ref in won:
                tender = tenders.get(ref)
                if tender is None:
                    continue
                value, cur = _amount(tender, "cac:LegalMonetaryTotal/cbc:PayableAmount")
                rank = _t(tender, "cbc:RankCode")
                contract = (contracts_of.get(ref) or [None])[0]
                party = parties.get(_t(tender, "efac:TenderingParty/cbc:ID") or "")
                members = party.findall("efac:Tenderer", NS) if party is not None else []
                for m in members:
                    org = orgs.get(_t(m, "cbc:ID") or "", {})
                    if not org.get("name"):
                        continue
                    winners.append({
                        "lot_id": lot_id or _t(tender, "efac:TenderLot/cbc:ID"), "tender_id": ref,
                        "org_ref": _t(m, "cbc:ID"),
                        "rank": int(rank) if rank and rank.isdigit() else None,
                        "name": org["name"], "country": org.get("country"), "city": org.get("city"),
                        "company_id": org.get("company_id"),
                        "vat_key": vat_number(org.get("company_id"), org.get("country")), "size": org.get("size"),
                        "is_group_lead": (_t(m, "efbc:GroupLeadIndicator") or "").lower() == "true",
                        "group_size": len(members), "tender_value": value, "tender_value_currency": cur,
                        "contract_id": _t(contract, "cbc:ID"),
                        "contract_reference": _t(contract, "efac:ContractReference/cbc:ID"),
                        "contract_title": _line(_text_in(contract, "cbc:Title")),
                        "contract_date": _day(_t(contract, "cbc:IssueDate")),
                        "award_date": _day(_t(contract, "cbc:AwardDate")),
                    })

    for w in winners:
        w["lot_title"] = (lots.get(w["lot_id"] or "") or {}).get("title")
    notice_id = next((e.text.strip() for e in root.findall("cbc:ID", NS)
                      if e.get("schemeName") == "notice-id" and e.text), None) or _t(root, "cbc:ID")
    pub = root.find(".//efac:Publication", NS)
    first = eu_buyers[0]
    return {
        "publication_number": publication_number,
        "notice_uuid": notice_id,
        "notice_version": _t(root, "cbc:VersionID"),
        "procedure_uuid": _t(root, "cbc:ContractFolderID"),
        "changed_notice": _t(root, ".//efac:Changes/efbc:ChangedNoticeIdentifier"),
        "notice_subtype": _t(root, "cbc:NoticeTypeCode"),
        "publication_date": _day(_t(pub, "efbc:PublicationDate")),
        "dispatch_date": _day(_t(root, "cbc:IssueDate")),
        "title": _line(_text_in(project, "cbc:Name")),
        "description": _text_in(project, "cbc:Description"),
        "contract_nature": _t(project, "cbc:ProcurementTypeCode"),
        "procedure_type": _t(root, "cac:TenderingProcess/cbc:ProcedureCode"),
        "cpv_main": _t(project, "cac:MainCommodityClassification/cbc:ItemClassificationCode"),
        "cpv_codes": sorted(set(_all(root, ".//cac:MainCommodityClassification/cbc:ItemClassificationCode")
                                + _all(root, ".//cac:AdditionalCommodityClassification/cbc:ItemClassificationCode"))),
        "contracting_authority": first["name"], "buyer_country": first["country"], "buyer_legal_type": first["legal_type"],
        "buyers": eu_buyers,
        "awarded_value": total, "awarded_value_currency": total_cur,
        "lots": sorted(lots.values(), key=lambda l: l["lot_id"]),
        "winners": winners,
        "public_url": NOTICE_URL.format(publication_number),
    }


# --- legacy TED XML (R2.0.9 forms) ----------------------------------------------------------------

# The legacy procedure elements, as the eForms procedure codes.
_LEGACY_PROCEDURES = {
    "PT_OPEN": "open", "PT_RESTRICTED": "restricted", "PT_COMPETITIVE_NEGOTIATION": "neg-w-call",
    "PT_NEGOTIATED_WITH_PRIOR_CALL": "neg-w-call", "PT_COMPETITIVE_DIALOGUE": "comp-dial",
    "PT_INNOVATION_PARTNERSHIP": "innovation", "PT_AWARD_CONTRACT_WITHOUT_CALL": "neg-wo-call",
    "PT_AWARD_CONTRACT_WITHOUT_PUBLICATION": "neg-wo-call",
}


def _plain(root: ET.Element) -> ET.Element:
    """The legacy forms declare a default namespace: tags without it, so paths read plainly."""
    for el in root.iter():
        if isinstance(el.tag, str) and "}" in el.tag:
            el.tag = el.tag.split("}", 1)[1]
    return root


def _p(el: Optional[ET.Element], path: str) -> Optional[str]:
    """The text of a legacy element made of <P> paragraphs, one line per paragraph."""
    f = el.find(path) if el is not None else None
    if f is None:
        return None
    paras = [" ".join("".join(p.itertext()).split()) for p in f.findall("P")] or [" ".join("".join(f.itertext()).split())]
    return "\n".join(x for x in paras if x) or None


def _lt(el: Optional[ET.Element], path: str) -> Optional[str]:
    f = el.find(path) if el is not None else None
    return " ".join(f.text.split()) if f is not None and f.text and f.text.strip() else None


def _lv(el: Optional[ET.Element], path: str):
    f = el.find(path) if el is not None else None
    if f is None or not (f.text or "").strip():
        return None, None
    try:
        return float(f.text.strip()), f.get("CURRENCY")
    except ValueError:
        return None, None


def _legacy_address(a: Optional[ET.Element]) -> dict:
    country = a.find("COUNTRY") if a is not None else None
    return {"name": _lt(a, "OFFICIALNAME"), "city": _lt(a, "TOWN"),
            "country": eu_code(country.get("VALUE")) if country is not None else None,
            "website": _lt(a, "URL_GENERAL") or _lt(a, "URL_BUYER"), "email": _lt(a, "E_MAIL"),
            "company_id": _lt(a, "NATIONALID")}


def _parse_legacy(root: ET.Element, publication_number: str) -> Optional[dict]:
    root = _plain(root)
    forms = [f for section in root.findall("FORM_SECTION") for f in section
             if f.find("AWARD_CONTRACT") is not None]
    if not forms:
        return None
    # The English version when the notice has one (the data is the same in every language).
    form = next((f for f in forms if f.get("LG") == "EN"), next((f for f in forms if f.get("CATEGORY") == "ORIGINAL"), forms[0]))
    cb = form.find("CONTRACTING_BODY")
    ca_type = cb.find("CA_TYPE") if cb is not None else None
    legal = ca_type.get("VALUE") if ca_type is not None else _lt(cb, "CA_TYPE_OTHER")
    buyers = []
    for a in ([cb.find("ADDRESS_CONTRACTING_BODY")] + cb.findall("ADDRESS_CONTRACTING_BODY_ADDITIONAL")) if cb is not None else []:
        if a is None:
            continue
        b = _legacy_address(a)
        buyers.append({"name": b["name"], "country": b["country"], "city": b["city"], "legal_type": legal,
                       "website": b["website"], "email": b["email"],
                       "eu_body": is_eu_body_address(b["website"]) or is_eu_body_address(b["email"])})
    eu_buyers = [b for b in buyers if b["eu_body"]]
    if not eu_buyers:
        return None

    obj = form.find("OBJECT_CONTRACT")
    lot_titles = {}
    for od in (obj.findall("OBJECT_DESCR") if obj is not None else []):
        if _lt(od, "LOT_NO"):
            lot_titles[_lt(od, "LOT_NO")] = _p(od, "TITLE")
    procedure = form.find("PROCEDURE")
    proc = next((el.tag for el in (procedure if procedure is not None else []) if el.tag.startswith("PT_")), None)
    total, total_cur = _lv(obj, "VAL_TOTAL")
    lots, winners = {}, []
    for ac in form.findall("AWARD_CONTRACT"):
        item = ac.get("ITEM") or str(len(lots) + 1)
        lot_id = _lt(ac, "LOT_NO") or item
        awarded = ac.find("AWARDED_CONTRACT")
        lot = lots.setdefault(lot_id, {"lot_id": lot_id, "title": _p(ac, "TITLE") or lot_titles.get(lot_id),
                                       "description": None, "result": None, "tenders_received": None})
        if awarded is None:
            lot["result"] = lot["result"] or "clos-nw"
            continue
        lot["result"] = "selec-w"
        received = _lt(awarded, "TENDERS/NB_TENDERS_RECEIVED")
        lot["tenders_received"] = int(received) if received and received.isdigit() else lot["tenders_received"]
        value, cur = _lv(awarded, "VALUES/VAL_TOTAL")
        contractors = awarded.findall("CONTRACTORS/CONTRACTOR") or awarded.findall("CONTRACTOR")
        for i, c in enumerate(contractors, 1):
            a = _legacy_address(c.find("ADDRESS_CONTRACTOR"))
            if not a["name"]:
                continue
            winners.append({
                "lot_id": lot_id, "tender_id": f"AC-{item}", "org_ref": f"AC-{item}-{i}", "rank": None,
                "name": a["name"], "country": a["country"], "city": a["city"], "company_id": a["company_id"],
                "vat_key": vat_number(a["company_id"], a["country"]),
                "size": "sme" if c.find("SME") is not None else "large" if c.find("NO_SME") is not None else None,
                "is_group_lead": False, "group_size": len(contractors), "tender_value": value, "tender_value_currency": cur,
                "contract_id": f"AC-{item}", "contract_reference": _lt(ac, "CONTRACT_NO"), "contract_title": _p(ac, "TITLE"),
                "contract_date": _lt(awarded, "DATE_CONCLUSION_CONTRACT"), "award_date": None,
                "lot_title": lot["title"],
            })
    cpvs = sorted({c.get("CODE") for c in form.iter("CPV_CODE") if c.get("CODE")})
    main_cpv = obj.find("CPV_MAIN/CPV_CODE") if obj is not None else None
    ctype = obj.find("TYPE_CONTRACT") if obj is not None else None
    ref_ojs = root.find("CODED_DATA_SECTION/REF_OJS/DATE_PUB")
    pub_day = ref_ojs.text.strip() if ref_ojs is not None and ref_ojs.text else None
    first = eu_buyers[0]
    return {
        "publication_number": publication_number, "notice_uuid": None, "notice_version": None, "procedure_uuid": None,
        "changed_notice": None, "notice_subtype": form.get("FORM"),
        "publication_date": f"{pub_day[:4]}-{pub_day[4:6]}-{pub_day[6:8]}" if pub_day and len(pub_day) == 8 else None,
        "dispatch_date": _lt(form, "COMPLEMENTARY_INFO/DATE_DISPATCH_NOTICE"),
        "title": _line(_p(obj, "TITLE")), "description": _p(obj, "SHORT_DESCR"),
        "contract_nature": (ctype.get("CTYPE") or "").lower() or None if ctype is not None else None,
        "procedure_type": _LEGACY_PROCEDURES.get(proc, proc[3:].lower() if proc else None),
        "cpv_main": main_cpv.get("CODE") if main_cpv is not None else None, "cpv_codes": cpvs,
        "contracting_authority": first["name"], "buyer_country": first["country"], "buyer_legal_type": first["legal_type"],
        "buyers": eu_buyers, "awarded_value": total, "awarded_value_currency": total_cur,
        "lots": sorted(lots.values(), key=lambda l: l["lot_id"]), "winners": winners,
        "public_url": NOTICE_URL.format(publication_number),
    }


def compose_body(n: dict):
    """The notice as text and as HTML: title, buyer, procedure, description, then each lot with its
    result and winners. Built from the notice's own fields; nothing is added."""
    def money(v, cur):
        return f"{v:,.2f} {cur or ''}".strip() if v is not None else "not given"
    lines = [n.get("title") or n["publication_number"],
             f"Buyer: {', '.join(b['name'] for b in n['buyers'] if b.get('name'))}",
             f"Contract type: {n.get('contract_nature') or 'not given'}; procedure: {n.get('procedure_type') or 'not given'}",
             f"Total value of the notice: {money(n.get('awarded_value'), n.get('awarded_value_currency'))}"]
    if n.get("description"):
        lines += ["", n["description"]]
    by_lot: Dict[str, List[dict]] = {}
    for w in n["winners"]:
        by_lot.setdefault(w.get("lot_id") or "", []).append(w)
    parts = ["<h1>{}</h1>".format(html.escape(lines[0]))] + [f"<p>{html.escape(l)}</p>" for l in lines[1:4]]
    if n.get("description"):
        parts.append(f"<p>{html.escape(n['description'])}</p>")
    for lot in n["lots"]:
        head = f"{lot['lot_id']}: {lot.get('title') or ''}".rstrip(": ")
        lines += ["", head, f"Result: {RESULTS.get(lot.get('result'), lot.get('result') or 'not given')}; tenders received: "
                  f"{lot['tenders_received'] if lot.get('tenders_received') is not None else 'not given'}"]
        parts += [f"<h2>{html.escape(head)}</h2>", f"<p>{html.escape(lines[-1])}</p>"]
        ws = by_lot.get(lot["lot_id"], [])
        if ws:
            parts.append("<ul>")
        for w in ws:
            line = (f"Winner: {w['name']} ({w.get('country') or '?'}), tender value "
                    f"{money(w.get('tender_value'), w.get('tender_value_currency'))}"
                    + (f", contract {w['contract_reference']}" if w.get("contract_reference") else "")
                    + (f", signed {w['contract_date']}" if w.get("contract_date") else ""))
            lines.append(line)
            parts.append(f"<li>{html.escape(line)}</li>")
        if ws:
            parts.append("</ul>")
    return "\n".join(lines), "\n".join(parts)


def to_json(value) -> str:
    return json.dumps(value, ensure_ascii=False)
